from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.collectors.ocr_reader import available_engines, candidates_to_dicts, extract_candidates, read_text
from backend.collectors.remote_edge import EdgeActionTimeoutError
from backend.collectors.window_capture import capture_window, image_to_data_url
from backend.routers.common import (
    PreviewRequest,
    TestOcrRequest,
    broadcast_snapshot,
    edge_client_for,
    edge_control_unavailable_detail,
    edge_timeout_detail,
    image_from_data_url,
)
from backend.services import store

router = APIRouter()


@router.get("/api/ocr/engines")
async def ocr_engines() -> dict[str, Any]:
    return {
        "mode": "auto",
        "available": available_engines(),
        "output": "selected_value and candidate text are pure integers without currency symbols or separators",
    }


@router.post("/api/window-preview")
async def window_preview(payload: PreviewRequest) -> dict[str, Any]:
    try:
        image, info = capture_window(payload.hwnd)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "window": info.__dict__,
        "width": image.width,
        "height": image.height,
        "image": image_to_data_url(image, max_width=1400),
    }


@router.post("/api/test-ocr")
async def test_ocr(payload: TestOcrRequest) -> dict[str, Any]:
    try:
        if payload.preview_image:
            image = image_from_data_url(payload.preview_image)
            info_dict = {
                "preview": {
                    "source": "current_preview_image",
                    "width": image.width,
                    "height": image.height,
                }
            }
        elif payload.capture_mode == "remote_edge":
            image, info = await asyncio.to_thread(edge_client_for(payload.edge_session_id).screenshot_page, payload.page_id)
            info_dict = {"page": info.__dict__}
        else:
            if payload.hwnd is None:
                raise ValueError("hwnd_required")
            image, info = capture_window(payload.hwnd)
            info_dict = {"window": info.__dict__}

        from backend.collectors.window_capture import crop_by_ratio
        from backend.services.scheduler import DATASET_DIR

        crop, crop_rect = crop_by_ratio(
            image,
            payload.x_ratio,
            payload.y_ratio,
            payload.width_ratio,
            payload.height_ratio,
            payload.safety_margin,
        )
        platform = ""
        shop_name = ""
        if payload.task_id:
            bound_task = store.get_task(payload.task_id)
            if bound_task is not None:
                platform = bound_task.platform
                shop_name = bound_task.shop_name
        ocr_text, details = read_text(
            crop,
            payload.keyword_hint,
            payload.last_value,
            platform=platform,
            shop_name=shop_name,
        )
        candidates = extract_candidates(ocr_text, details, payload.keyword_hint, payload.last_value)
        candidate_dicts = candidates_to_dicts(candidates)
        suggested_value = candidates[0].value if candidates else None
        suggested_candidate = candidate_dicts[0] if candidate_dicts else None

        try:
            DATASET_DIR.mkdir(parents=True, exist_ok=True)
            safe_text = (
                str(suggested_value)
                if suggested_value is not None
                else re.sub(r'[\\/*?:"<>|]', "", ocr_text or "未识别")
            )
            filename = f"测试采集_{safe_text}_{int(time.time() * 1000)}.png"
            crop.save(DATASET_DIR / filename)
        except Exception:
            pass

        committed = False
        if payload.commit_result and payload.task_id and suggested_value is not None:
            task = store.get_task(payload.task_id)
            if task is None:
                raise ValueError("task_not_found")
            now = store.now_sql()
            reason = "测试识别设为当前可信值"
            store.update_task_runtime(
                payload.task_id,
                {
                    "last_trusted_value": suggested_value,
                    "pending_value": None,
                    "pending_count": 0,
                    "status": "ok",
                    "last_success_at": now,
                    "last_sample_at": now,
                    "last_ocr_text": ocr_text,
                    "last_reason": reason,
                    "last_reason_code": "",
                    "last_value_source": "ocr",
                    "last_screenshot_path": "",
                },
            )
            store.add_sample(
                payload.task_id,
                ocr_text,
                candidate_dicts,
                suggested_value,
                suggested_value,
                "ok",
                reason,
                "",
                sample_meta={
                    "selected_candidate_engine": str((suggested_candidate or {}).get("engine") or ""),
                    "selected_candidate_variant": str((suggested_candidate or {}).get("variant") or ""),
                    "selected_candidate_source_kind": str((suggested_candidate or {}).get("source_kind") or ""),
                    "selected_candidate_correction_count": int((suggested_candidate or {}).get("correction_count") or 0),
                    "required_confirms": 1,
                    "accepted_after_confirms": 1,
                },
            )
            committed = True
            await broadcast_snapshot()
        return {
            **info_dict,
            "crop_rect": crop_rect,
            "image": image_to_data_url(crop, max_width=900),
            "ocr_text": ocr_text,
            "details": details,
            "candidates": candidate_dicts,
            "suggested_value": suggested_value,
            "suggested_candidate": suggested_candidate,
            "committed": committed,
            "committed_task_id": payload.task_id if committed else None,
            "engines": available_engines(),
        }
    except EdgeActionTimeoutError as exc:
        detail = await edge_timeout_detail(
            payload.edge_session_id,
            exc,
            page_id=payload.page_id,
            recovery_hint="OCR 测试截图超时，系统已重建会话连接。请重新生成预览并再次测试；若仍失败，请先重新显示 Edge。",
        )
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        if payload.capture_mode == "remote_edge" and ("真实 Edge 调试端口未连接" in str(exc) or "连接真实 Edge 失败" in str(exc)):
            raise HTTPException(
                status_code=409,
                detail=await edge_control_unavailable_detail(
                    payload.edge_session_id,
                    page_id=payload.page_id,
                    operation_label="测试 OCR",
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
