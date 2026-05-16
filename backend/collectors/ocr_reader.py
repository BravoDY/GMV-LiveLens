from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
from collections.abc import Iterable
from dataclasses import asdict
from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from PIL import Image

from backend.models import CandidateAmount

# --- OCR 形近字纠错特征库 ---
OCR_CHAR_REPLACEMENTS = {
    # 0的形近字
    "o": "0", "O": "0", "D": "0", "U": "0", "u": "0",
    # 1的形近字
    "l": "1", "I": "1", "i": "1", "j": "1", "J": "1",
    # 4的形近字
    "P": "4", "h": "4", "H": "4", "旧": "4", "忙": "4",
    # 5的形近字
    "s": "5", "S": "5",
    # 7的形近字
    "门": "7", ">": "7",
}

# 容易被误识别为货币符的汉字/符号特征库
OCR_CURRENCY_ALIASES = ["半", "举", "夫", "羊", "旧"]

_currency_pattern = "|".join(["RMB", "CNY", r"\u00a5", r"\uffe5", r"\u7f8a", "Y"] + OCR_CURRENCY_ALIASES)
AMOUNT_PATTERN = re.compile(
    rf"(?:(?:{_currency_pattern})\s*)?([0-9][0-9,\uff0c.\s]{{2,}})(?:\s*([\u4e07\u4ebf]))?",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"\d{4}[-/.\u5e74]\d{1,2}[-/.\u6708]\d{1,2}")
TIME_PATTERN = re.compile(r"\d{1,2}:\d{1,2}(:\d{1,2})?")


def _apply_numeric_context_replacements(text: str) -> tuple[str, int]:
    if not text:
        return "", 0
    chars = list(text)
    replacements = 0
    for index, char in enumerate(chars):
        replacement = OCR_CHAR_REPLACEMENTS.get(char)
        if replacement is None:
            continue
        left = chars[index - 1] if index > 0 else ""
        right = chars[index + 1] if index + 1 < len(chars) else ""
        left_is_numeric = left.isdigit() or left in {",", ".", "，", "。"}
        right_is_numeric = right.isdigit() or right in {",", ".", "，", "。"}
        if not (left_is_numeric or right_is_numeric):
            continue
        chars[index] = replacement
        replacements += 1
    return "".join(chars), replacements


def available_engines() -> dict[str, bool]:
    return {
        "rapidocr": importlib.util.find_spec("rapidocr") is not None,
        "legacy_rapidocr": importlib.util.find_spec("rapidocr_onnxruntime") is not None,
        "paddleocr": importlib.util.find_spec("paddleocr") is not None,
        "ddddocr": importlib.util.find_spec("ddddocr") is not None,
        "tesseract": importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is not None,
    }


@lru_cache(maxsize=1)
def _rapid_engine():
    from rapidocr import RapidOCR

    return RapidOCR()


@lru_cache(maxsize=1)
def _legacy_rapid_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


@lru_cache(maxsize=1)
def _paddle_engine():
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)


@lru_cache(maxsize=1)
def _dddd_engine():
    import ddddocr

    engine = ddddocr.DdddOcr(ocr=True, det=False, show_ad=False)
    return engine


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _scale_to_min_height(bgr: np.ndarray, min_height: int = 160) -> np.ndarray:
    height, width = bgr.shape[:2]
    if height >= min_height:
        return bgr
    scale = min_height / max(1, height)
    return cv2.resize(bgr, (int(width * scale), min_height), interpolation=cv2.INTER_CUBIC)


def _load_ocr_experiment_profile(platform: str = "", shop_name: str = "") -> dict[str, Any]:
    try:
        from backend.services.store import get_setting

        raw = get_setting("ocr_experiment_profiles", "{}")
        data = json.loads(raw or "{}")
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    candidates = [
        f"{platform.strip()}::{shop_name.strip()}",
        f"{platform.strip()}/{shop_name.strip()}",
        shop_name.strip(),
        platform.strip(),
        "default",
    ]
    for key in candidates:
        if not key:
            continue
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _preprocess_variants(image: Image.Image, profile: dict[str, Any] | None = None) -> list[tuple[str, np.ndarray]]:
    base = _scale_to_min_height(_pil_to_bgr(image))
    variants: list[tuple[str, np.ndarray]] = [("color", base)]

    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    contrast = cv2.convertScaleAbs(gray, alpha=1.55, beta=8)
    variants.append(("contrast_gray", cv2.cvtColor(contrast, cv2.COLOR_GRAY2BGR)))

    # GMV screens often use bright yellow digits on magenta/purple backgrounds.
    hsv = cv2.cvtColor(base, cv2.COLOR_BGR2HSV)
    yellow_mask = cv2.inRange(hsv, np.array([15, 45, 120]), np.array([45, 255, 255]))
    yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    yellow_binary = cv2.bitwise_not(yellow_mask)
    variants.append(("yellow_digits", cv2.cvtColor(yellow_binary, cv2.COLOR_GRAY2BGR)))

    _, otsu = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("otsu", cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR)))
    profile = profile or {}
    extra_variants = profile.get("extra_variants") or []
    if "adaptive_binary" in extra_variants:
        adaptive = cv2.adaptiveThreshold(
            contrast,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )
        variants.append(("adaptive_binary", cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR)))
    if "sharpen" in extra_variants:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        variants.append(("sharpen", cv2.filter2D(base, -1, kernel)))
    if "invert_gray" in extra_variants:
        inverted = cv2.bitwise_not(contrast)
        variants.append(("invert_gray", cv2.cvtColor(inverted, cv2.COLOR_GRAY2BGR)))
    return variants


def _flatten_rapid_v3(result: Any) -> list[tuple[str, float, Any]]:
    rows: list[tuple[str, float, Any]] = []
    txts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    boxes = getattr(result, "boxes", None)
    if txts is not None:
        for index, text in enumerate(txts):
            score = float(scores[index]) if scores is not None and index < len(scores) else 0.0
            box = boxes[index].tolist() if boxes is not None and index < len(boxes) else None
            text = str(text).strip()
            if text:
                rows.append((text, score, box))
        return rows
    return _flatten_legacy_result(result)


def _flatten_legacy_result(result: Any) -> list[tuple[str, float, Any]]:
    rows: list[tuple[str, float, Any]] = []
    if not result:
        return rows
    items = result[0] if isinstance(result, tuple) else result
    if not items:
        return rows
    for item in items:
        try:
            box = item[0]
            raw_text = item[1]
            # 兼容新格式 (text, score) 元组和旧格式纯字符串
            if isinstance(raw_text, (list, tuple)) and len(raw_text) >= 2:
                text, score = str(raw_text[0]).strip(), float(raw_text[1])
            else:
                text, score = str(raw_text).strip(), float(item[2])
        except Exception:
            continue
        if text:
            rows.append((text, score, box))
    return rows


def _run_rapidocr(image: np.ndarray) -> list[tuple[str, float, Any]]:
    return _flatten_rapid_v3(_rapid_engine()(image))


def _run_legacy_rapidocr(image: np.ndarray) -> list[tuple[str, float, Any]]:
    return _flatten_legacy_result(_legacy_rapid_engine()(image))


def _run_paddleocr(image: np.ndarray) -> list[tuple[str, float, Any]]:
    result = _paddle_engine().ocr(image, cls=False)
    rows: list[tuple[str, float, Any]] = []
    for page in result or []:
        for item in page or []:
            try:
                box = item[0]
                text = str(item[1][0]).strip()
                score = float(item[1][1])
            except Exception:
                continue
            if text:
                rows.append((text, score, box))
    return rows


def _run_tesseract(image: np.ndarray) -> list[tuple[str, float, Any]]:
    import pytesseract

    config = "--psm 7 -c tessedit_char_whitelist=0123456789,.，¥￥RMB"
    text = pytesseract.image_to_string(image, lang="eng", config=config).strip()
    return [(text, 0.5, None)] if text else []


def _run_ddddocr(image: np.ndarray) -> list[tuple[str, float, Any]]:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        return []
    text = str(_dddd_engine().classification(encoded.tobytes())).strip()
    return [(text, 0.5, None)] if text else []


def _engine_order(platform: str = "", shop_name: str = "") -> list[str]:
    from backend.services.store import get_setting

    requested = get_setting("ocr_engine", "auto").lower().strip()
    if not requested or requested == "auto":
        requested = os.environ.get("GMV_OCR_ENGINE", "auto").lower().strip()

    engines = available_engines()
    if requested != "auto":
        return [requested] if engines.get(requested) else []
    order = ["rapidocr", "legacy_rapidocr", "paddleocr", "ddddocr", "tesseract"]
    profile = _load_ocr_experiment_profile(platform, shop_name)
    if profile.get("prefer_ddddocr") and engines.get("ddddocr"):
        order = ["ddddocr"] + [engine for engine in order if engine != "ddddocr"]
    return [engine for engine in order if engines.get(engine)]


def _allowed_variants_for_engine(engine: str, profile: dict[str, Any] | None = None) -> set[str] | None:
    profile = profile or {}
    if engine == "ddddocr":
        configured = profile.get("ddddocr_variants")
        if isinstance(configured, list) and configured:
            return {str(item) for item in configured if item}
        # ddddocr 对强二值化变体更容易产出结构性误识别，默认限制在较稳的变体上。
        return {"color", "contrast_gray", "sharpen"}
    return None


def read_text(
    image: Image.Image,
    keyword_hint: str = "",
    last_value: int | None = None,
    platform: str = "",
    shop_name: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    all_rows: list[dict[str, Any]] = []
    profile = _load_ocr_experiment_profile(platform, shop_name)
    variants = _preprocess_variants(image, profile)

    for engine in _engine_order(platform, shop_name):
        runner = {
            "rapidocr": _run_rapidocr,
            "legacy_rapidocr": _run_legacy_rapidocr,
            "paddleocr": _run_paddleocr,
            "ddddocr": _run_ddddocr,
            "tesseract": _run_tesseract,
        }.get(engine)
        if runner is None:
            continue
        allowed_variants = _allowed_variants_for_engine(engine, profile)
        for variant_name, variant in variants:
            if allowed_variants is not None and variant_name not in allowed_variants:
                continue
            try:
                rows = runner(variant)
            except Exception as exc:
                all_rows.append(
                    {
                        "text": "",
                        "score": 0,
                        "box": None,
                        "engine": engine,
                        "variant": variant_name,
                        "error": str(exc),
                    }
                )
                continue
            for text, score, box in rows:
                all_rows.append(
                    {
                        "text": text,
                        "score": score,
                        "box": box,
                        "engine": engine,
                        "variant": variant_name,
                    }
                )
            joined = " ".join(row[0] for row in rows)
            if extract_candidates(joined, all_rows, keyword_hint, last_value):
                text = " ".join(item["text"] for item in all_rows if item.get("text"))
                return text, all_rows

    text = " ".join(item["text"] for item in all_rows if item.get("text"))
    return text, all_rows


def _unit_multiplier(unit: str = "") -> int:
    if unit == "\u4e07":
        return 10_000
    if unit == "\u4ebf":
        return 100_000_000
    return 1


def _amount_groups(raw: str) -> list[str]:
    text = re.sub(r"(?i)RMB|CNY|\u00a5|\uffe5|[\u4e07\u4ebf]", "", raw)
    return [part for part in re.split(r"[,，.\s]+", text.strip()) if part.isdigit()]


def _looks_like_thousands(groups: list[str]) -> bool:
    if len(groups) < 2:
        return False
    return 1 <= len(groups[0]) <= 3 and all(len(part) == 3 for part in groups[1:])


def _valid_amount(value: int) -> int | None:
    if value < 100:
        return None
    return value


def _normalize_unit_amount(raw: str, unit: str) -> int | None:
    multiplier = _unit_multiplier(unit)
    compact = raw.replace("\uff0c", ",").replace(" ", "")
    if DATE_PATTERN.search(compact) or TIME_PATTERN.search(compact) or "%" in compact:
        return None

    groups = _amount_groups(raw)
    if _looks_like_thousands(groups):
        return _valid_amount(int("".join(groups)) * multiplier)

    cleaned = re.sub(r"[^0-9.]", "", compact)
    if not cleaned:
        return None
    if cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    try:
        return _valid_amount(int(round(float(cleaned) * multiplier)))
    except ValueError:
        return None


def _normalize_amount(raw: str, unit: str = "") -> int | None:
    if not raw:
        return None
    compact = raw.replace("\uff0c", ",").replace(" ", "")
    if DATE_PATTERN.search(compact) or TIME_PATTERN.search(compact) or "%" in compact:
        return None
    if unit:
        return _normalize_unit_amount(raw, unit)

    groups = _amount_groups(raw)
    if _looks_like_thousands(groups):
        return _valid_amount(int("".join(groups)))

    digits = re.sub(r"\D", "", compact)
    if not digits:
        return None
    return _valid_amount(int(digits))


def _normalize_amount_values(raw: str, unit: str = "") -> list[int]:
    values: list[int] = []
    groups = _amount_groups(raw)
    has_split_thousands = (
        not unit
        and len(groups) >= 3
        and not _looks_like_thousands(groups)
        and any(len(part) == 3 for part in groups[1:])
    )
    base = _normalize_amount(raw, unit)
    if base is not None and not has_split_thousands:
        values.append(base)

    if len(groups) >= 3 and not _looks_like_thousands(groups):
        # OCR may split one digit out of a comma group: 4.379.6 653 -> 4,379,653.
        first = groups[0]
        three_digit_groups = [part for part in groups[1:] if len(part) == 3]
        if three_digit_groups:
            rebuilt = first + "".join(three_digit_groups)
            rebuilt_value = _normalize_amount(rebuilt, unit)
            if rebuilt_value is not None:
                values.append(rebuilt_value)
        if len(three_digit_groups) >= 2:
            rebuilt = first + "".join(three_digit_groups[-2:])
            rebuilt_value = _normalize_amount(rebuilt, unit)
            if rebuilt_value is not None:
                values.append(rebuilt_value)

    unique: list[int] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _candidate_reason(raw: str, value: int, fragment: str, keyword_hint: str, last_value: int | None) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if re.search(rf"{_currency_pattern}", raw, re.IGNORECASE):
        score += 35
        reasons.append("currency")
    groups = _amount_groups(raw)
    if "," in raw or "\uff0c" in raw or "." in raw or re.search(r"\d\s+\d", raw):
        score += 18
        reasons.append("thousand_sep" if _looks_like_thousands(groups) else "separator")
    if value >= 1000:
        score += 25
        reasons.append("amount_size")
    digit_count = len(str(abs(value)))
    score += min(24, digit_count * 3)
    reasons.append("digit_count")
    if digit_count >= 4:
        score += min(20, (digit_count - 3) * 5)
        reasons.append("complete_digits")
    if value >= 1_000_000:
        score += 12
        reasons.append("gmv_scale")
    if value >= 100_000_000:
        score += 8
        reasons.append("large_gmv")
    if value > 1_000_000_000_000:
        score -= 60
        reasons.append("too_long")
    if keyword_hint and keyword_hint.lower() in fragment.lower():
        score += 25
        reasons.append("keyword")
    if DATE_PATTERN.search(fragment) and str(value).startswith("20"):
        score -= 60
        reasons.append("date_like")
    if last_value is not None:
        if value >= last_value:
            score += 18
            reasons.append("non_decreasing")
        elif value >= last_value * 0.97:
            score += 5
            reasons.append("small_drop")
        else:
            score -= 40
            reasons.append("large_drop")
        if last_value > 0 and value > last_value * 5:
            score -= 35
            reasons.append("large_jump")
    return score, reasons


def extract_candidates(
    ocr_text: str,
    details: list[dict[str, Any]],
    keyword_hint: str = "",
    last_value: int | None = None,
) -> list[CandidateAmount]:
    # 应用特征库进行形近字预纠错
    ocr_text, joined_correction_count = _apply_numeric_context_replacements(ocr_text)

    for d in details:
        if "text" in d:
            text_val, item_correction_count = _apply_numeric_context_replacements(str(d["text"]))
            d["text"] = text_val
            d["correction_count"] = int(d.get("correction_count") or 0) + item_correction_count

    candidates: list[CandidateAmount] = []
    fragments = [
        {
            "fragment": ocr_text,
            "engine": "aggregate",
            "variant": "joined_text",
            "source_kind": "joined_text",
            "correction_count": joined_correction_count,
        }
    ]
    for item in details:
        fragments.append(
            {
                "fragment": str(item.get("text", "")),
                "engine": str(item.get("engine", "")),
                "variant": str(item.get("variant", "")),
                "source_kind": "detail",
                "correction_count": int(item.get("correction_count") or 0),
            }
        )
    keyword_hint = (keyword_hint or "").strip()

    for fragment_meta in fragments:
        fragment = fragment_meta["fragment"]
        if not fragment:
            continue
        date_spans = [match.span() for match in DATE_PATTERN.finditer(fragment)]
        for match in AMOUNT_PATTERN.finditer(fragment):
            start, end = match.span()
            if any(start < date_end and end > date_start for date_start, date_end in date_spans):
                continue
            if end < len(fragment) and fragment[end : end + 1] == "%":
                continue
            raw = match.group(0)
            for value in _normalize_amount_values(match.group(1), match.group(2) or ""):
                score, reasons = _candidate_reason(raw, value, fragment, keyword_hint, last_value)
                candidates.append(
                    CandidateAmount(
                        value=value,
                        text=str(value),
                        score=score,
                        reason=",".join(reasons),
                        engine=fragment_meta["engine"],
                        variant=fragment_meta["variant"],
                        raw_fragment=fragment,
                        raw_text=raw,
                        source_kind=fragment_meta["source_kind"],
                        correction_count=fragment_meta["correction_count"],
                    )
                )

    best_by_value: dict[int, CandidateAmount] = {}
    for item in candidates:
        current = best_by_value.get(item.value)
        if current is None or item.score > current.score:
            best_by_value[item.value] = item
    return sorted(best_by_value.values(), key=lambda item: item.score, reverse=True)


def candidates_to_dicts(items: Iterable[CandidateAmount]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]
