from __future__ import annotations

from typing import Any

from backend.models import CaptureTask
from backend.services import store


def page_to_dict(page: Any) -> dict[str, Any]:
    if isinstance(page, dict):
        return {
            "page_id": str(page.get("page_id") or ""),
            "url": str(page.get("url") or ""),
            "title": str(page.get("title") or ""),
        }
    return {
        "page_id": str(getattr(page, "page_id", "") or ""),
        "url": str(getattr(page, "url", "") or ""),
        "title": str(getattr(page, "title", "") or ""),
    }


def page_match_score(task: CaptureTask, page: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    url = str(page.get("url") or "").strip()
    title = str(page.get("title") or "").strip()
    target_url = (task.target_page_url or "").strip()
    task_page_url = (task.page_url or "").strip()
    task_page_title = (task.page_title or "").strip().lower()

    def url_exact_or_prefix(candidate: str, expected: str) -> bool:
        current = (candidate or "").rstrip("/")
        target = (expected or "").rstrip("/")
        if not current or not target:
            return False
        return current == target or current.startswith(f"{target}/")

    matches_target_url = url_exact_or_prefix(url, target_url)
    matches_task_page_url = url_exact_or_prefix(url, task_page_url)
    title_matches = bool(task_page_title and title and task_page_title in title.lower())
    current_bound = bool(task.page_id and page.get("page_id") == task.page_id)

    score = 0.0
    if current_bound:
        score += 100.0
    if matches_target_url:
        score += 60.0
    elif target_url and target_url.lower() in url.lower():
        score += 30.0
    if matches_task_page_url:
        score += 40.0
    elif task_page_url and task_page_url.lower() in url.lower():
        score += 20.0
    if title_matches:
        score += 10.0

    url_lower = url.lower()
    title_lower = title.lower()
    login_markers = ("login", "signin", "passport", "auth")
    is_login_page = bool(
        any(marker in url_lower for marker in login_markers)
        or "登录" in title
        or "signin" in title_lower
    )
    page_kind = "login" if is_login_page else ("target" if matches_target_url else "other")

    return score, {
        "is_current_bound": current_bound,
        "matches_target_url": matches_target_url,
        "matches_task_page_url": matches_task_page_url,
        "matches_task_page_title": title_matches,
        "is_login_page": is_login_page,
        "is_target_page": page_kind == "target",
        "page_kind": page_kind,
    }


def task_runtime_for_bound_page(task: CaptureTask, page: dict[str, Any], *, automatic: bool) -> dict[str, str]:
    _score, _flags = page_match_score(task, page)
    return {
        "status": "edge_target_page_ready",
        "last_reason_code": "edge_target_page_ready",
        "last_reason": (
            "系统已自动恢复到当前页签，可直接生成预览或继续采集。"
            if automatic
            else "已绑定当前页签，可直接生成预览或继续采集。"
        ),
    }


def rank_task_pages(task: CaptureTask, pages: list[Any]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in pages:
        page = page_to_dict(item)
        score, flags = page_match_score(task, page)
        ranked.append({**page, **flags, "match_score": score})
    ranked.sort(
        key=lambda item: (
            item["match_score"],
            1 if item.get("matches_target_url") else 0,
            1 if item.get("matches_task_page_url") else 0,
            len(item.get("title") or ""),
            len(item.get("url") or ""),
        ),
        reverse=True,
    )
    return ranked


def auto_rebind_decision(task: CaptureTask, ranked: list[dict[str, Any]]) -> dict[str, Any]:
    if any(item.get("is_current_bound") for item in ranked):
        return {
            "can_auto_rebind": False,
            "reason_code": "already_bound",
            "reason": "当前绑定页签仍有效，无需自动改绑。",
            "manual_required": False,
            "recovery_hint": "",
            "candidate": None,
        }

    target_matches = [item for item in ranked if item.get("matches_target_url")]
    if len(target_matches) == 1:
        return {
            "can_auto_rebind": True,
            "reason_code": "unique_target_candidate",
            "reason": "识别到唯一目标业务页候选，允许自动改绑。",
            "manual_required": False,
            "recovery_hint": "",
            "candidate": target_matches[0],
        }
    if len(target_matches) > 1:
        exact_target = [
            item
            for item in target_matches
            if str(item.get("url") or "").rstrip("/") == str(task.target_page_url or "").rstrip("/")
        ]
        if len(exact_target) == 1:
            return {
                "can_auto_rebind": True,
                "reason_code": "unique_exact_target_candidate",
                "reason": "识别到唯一精确目标 URL 候选，允许自动改绑。",
                "manual_required": False,
                "recovery_hint": "",
                "candidate": exact_target[0],
            }
        return {
            "can_auto_rebind": False,
            "reason_code": "ambiguous_target_candidates",
            "reason": "目标业务页存在多个候选，系统拒绝自动改绑以避免误绑。",
            "manual_required": True,
            "recovery_hint": "请手动确认候选页并重新绑定。",
            "candidate": None,
        }

    task_url_matches = [item for item in ranked if item.get("matches_task_page_url")]
    if len(task_url_matches) == 1:
        return {
            "can_auto_rebind": True,
            "reason_code": "unique_task_url_candidate",
            "reason": "识别到唯一历史 URL 候选，允许自动改绑。",
            "manual_required": False,
            "recovery_hint": "",
            "candidate": task_url_matches[0],
        }
    if len(task_url_matches) > 1:
        return {
            "can_auto_rebind": False,
            "reason_code": "ambiguous_task_url_candidates",
            "reason": "历史 URL 存在多个候选，系统拒绝自动改绑以避免误绑。",
            "manual_required": True,
            "recovery_hint": "请手动确认候选页并重新绑定。",
            "candidate": None,
        }

    if not ranked:
        return {
            "can_auto_rebind": False,
            "reason_code": "no_candidate_pages",
            "reason": "当前会话没有可用于恢复绑定的候选页。",
            "manual_required": True,
            "recovery_hint": "请先打开业务页后重新扫描。",
            "candidate": None,
        }

    return {
        "can_auto_rebind": False,
        "reason_code": "no_unique_high_confidence_candidate",
        "reason": "未找到唯一高置信候选，系统保持手动确认流程。",
        "manual_required": True,
        "recovery_hint": "请手动确认候选页并重新绑定。",
        "candidate": None,
    }


def restore_task_binding_from_pages(
    task: CaptureTask,
    session_id: str,
    pages: list[Any],
) -> tuple[CaptureTask, dict[str, Any]]:
    ranked = rank_task_pages(task, pages)
    decision = auto_rebind_decision(task, ranked)
    candidate = decision.get("candidate")
    if decision.get("can_auto_rebind") and isinstance(candidate, dict) and task.id is not None:
        data = store.task_to_dict(task)
        data.update(
            {
                "capture_mode": "remote_edge",
                "page_id": candidate["page_id"],
                "page_url": candidate["url"],
                "page_title": candidate["title"],
                "edge_session_id": session_id,
            }
        )
        saved = store.upsert_task(data)
        runtime = task_runtime_for_bound_page(saved, candidate, automatic=True)
        store.update_task_runtime(saved.id, runtime)
        restored_item = {
            "task_id": saved.id,
            "shop_name": saved.shop_name,
            "page_id": candidate["page_id"],
            "page_url": candidate["url"],
            "page_kind": candidate.get("page_kind", ""),
            "last_reason": runtime["last_reason"],
        }
        decision = {
            **decision,
            "restored": True,
            "manual_required": False,
            "reason_code": "auto_rebind_restored",
            "reason": runtime["last_reason"],
            "recovery_hint": "",
            "restored_item": restored_item,
        }
        return saved, decision

    decision = {**decision, "restored": False}
    return task, decision
