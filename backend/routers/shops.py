from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.collectors.remote_edge import remote_edge_manager
from backend.routers.common import (
    ShopsBindPayload,
    _load_shops_default,
    _task_runtime_for_bound_page,
    broadcast_snapshot,
    safe_upsert_task,
)
from backend.services import shop_config, store

router = APIRouter()


@router.get("/api/shops")
async def shops() -> list[dict[str, Any]]:
    return _load_shops_default()


@router.post("/api/shops/init")
async def init_shops() -> dict[str, Any]:
    try:
        configs = shop_config.load_shop_configs()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"shops.csv 校验失败，未同步任何任务：{exc}") from exc
    if not configs:
        raise HTTPException(status_code=404, detail="data/shops.csv 不存在或为空")
    result = store.sync_tasks_with_shop_configs()
    await broadcast_snapshot()
    return result


@router.get("/api/shops/match")
async def shops_match(session_id: str = Query(default="")) -> dict[str, Any]:
    if not session_id:
        sessions = [item for item in store.list_edge_sessions() if item.session_id != "default_real_edge"]
        session_id = sessions[0].session_id if sessions else "default_real_edge"
    session = store.get_edge_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="edge_session_not_found")

    client = remote_edge_manager.get_client(
        session.session_id,
        name=session.name,
        debug_port=session.debug_port,
        user_data_dir=session.user_data_dir,
        session_mode=session.session_mode,
    )
    if not client.health().debug_available:
        raise HTTPException(status_code=409, detail=f"Edge 调试端口 {session.debug_port} 未连接，请先启动对应店铺的 Edge")

    try:
        pages = await asyncio.to_thread(client.list_pages)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    shops_config = _load_shops_default()
    tasks_in_session = [
        store.task_to_dict(t)
        for t in store.list_tasks(include_disabled=True)
        if t.edge_session_id == session_id
    ]

    def _url_score(url: str, patterns: list[str], must_contain: list[str]) -> float:
        if not url:
            return 0.0
        url_lower = url.lower()
        if must_contain and not all(kw.lower() in url_lower for kw in must_contain):
            return 0.0
        score = 0.0
        for pattern in patterns:
            if pattern.lower() in url_lower:
                score += 1.0
        return score

    page_list = [{"page_id": p.page_id, "url": p.url, "title": p.title} for p in pages]

    suggestions: list[dict[str, Any]] = []
    for task in tasks_in_session:
        shop_cfg = next((s for s in shops_config if s.get("shop_name") == task["shop_name"]), None)
        patterns = shop_cfg.get("url_patterns", []) if shop_cfg else []
        must_contain = shop_cfg.get("url_must_contain", []) if shop_cfg else []
        candidates = []
        for page in page_list:
            score = _url_score(page["url"], patterns, must_contain)
            if score > 0:
                candidates.append({**page, "score": score})
        candidates.sort(key=lambda p: p["score"], reverse=True)
        suggestions.append(
            {
                "task_id": task["id"],
                "task_name": task["shop_name"],
                "platform": task["platform"],
                "current_page_id": task["page_id"],
                "current_page_url": task["page_url"],
                "candidates": candidates[:5],
                "confidence": "high" if candidates and candidates[0]["score"] >= 1 else "low",
            }
        )

    return {
        "session_id": session_id,
        "session_name": session.name,
        "pages": page_list,
        "suggestions": suggestions,
    }


@router.post("/api/shops/bind")
async def shops_bind(payload: ShopsBindPayload) -> dict[str, Any]:
    results = []
    for binding in payload.bindings:
        task_id = binding.get("task_id")
        page_id = (binding.get("page_id") or "").strip()
        if not task_id or not page_id:
            continue
        task = store.get_task(int(task_id))
        if task is None:
            results.append({"task_id": task_id, "status": "not_found"})
            continue
        data = store.task_to_dict(task)
        data.update(
            {
                "capture_mode": binding.get("capture_mode", task.capture_mode),
                "page_id": page_id,
                "page_url": binding.get("page_url", ""),
                "page_title": binding.get("page_title", ""),
                "edge_session_id": binding.get("edge_session_id", task.edge_session_id),
            }
        )
        saved = safe_upsert_task(data)
        if saved.capture_mode == "remote_edge" and saved.id is not None:
            runtime = _task_runtime_for_bound_page(
                saved,
                {"page_id": page_id, "url": binding.get("page_url", ""), "title": binding.get("page_title", "")},
                automatic=False,
            )
            store.update_task_runtime(saved.id, runtime)
        results.append({"task_id": task_id, "status": "ok", "page_id": page_id})
    await broadcast_snapshot()
    return {"bound": len([r for r in results if r["status"] == "ok"]), "results": results}
