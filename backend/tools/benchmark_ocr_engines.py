from __future__ import annotations

# ruff: noqa: E402
import argparse
import csv
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.collectors.ocr_reader import candidates_to_dicts, extract_candidates, read_text

DEFAULT_SAMPLE_DIR = ROOT_DIR / "data" / "ocr_samples"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass
class BenchmarkResult:
    image: str
    engine: str
    expected: int | None
    selected: int | None
    ok: bool | None
    elapsed_ms: float
    text: str
    candidates: list[dict]
    error: str = ""


def _expected_from_name(path: Path) -> int | None:
    match = re.search(r"(?<!\d)(\d{3,})(?!\d)", path.stem)
    return int(match.group(1)) if match else None


def _load_labels(sample_dir: Path) -> dict[str, int]:
    labels_path = sample_dir / "labels.csv"
    labels: dict[str, int] = {}
    if not labels_path.exists():
        return labels
    with labels_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = (row.get("file") or row.get("filename") or row.get("image") or "").strip()
            expected = re.sub(r"\D", "", row.get("expected") or row.get("value") or "")
            if name and expected:
                labels[name] = int(expected)
    return labels


def _production_ocr(image: Image.Image, keyword_hint: str) -> tuple[str, list[dict]]:
    text, details = read_text(image, keyword_hint=keyword_hint)
    candidates = candidates_to_dicts(extract_candidates(text, details, keyword_hint))
    return text, candidates


def _ddddocr_ocr(image: Image.Image, keyword_hint: str) -> tuple[str, list[dict]]:
    import ddddocr

    if not hasattr(_ddddocr_ocr, "_engine"):
        engine = ddddocr.DdddOcr(ocr=True, det=False, show_ad=False)
        try:
            engine.set_ranges(0)
        except Exception:
            pass
        _ddddocr_ocr._engine = engine
    engine = _ddddocr_ocr._engine
    with tempfile.SpooledTemporaryFile() as file:
        image.convert("RGB").save(file, format="PNG")
        file.seek(0)
        text = str(engine.classification(file.read())).strip()
    candidates = candidates_to_dicts(extract_candidates(text, [{"text": text, "engine": "ddddocr", "variant": "raw"}], keyword_hint))
    return text, candidates


def _imgocr_ocr(image: Image.Image, keyword_hint: str) -> tuple[str, list[dict]]:
    from imgocr import ImgOcr

    if not hasattr(_imgocr_ocr, "_engine"):
        _imgocr_ocr._engine = ImgOcr(use_gpu=False, is_efficiency_mode=True)
    engine = _imgocr_ocr._engine
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
        temp_path = Path(file.name)
    try:
        image.convert("RGB").save(temp_path)
        result = engine.ocr(str(temp_path))
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    texts: list[str] = []
    details: list[dict] = []
    for item in result or []:
        text = str(item.get("text") if isinstance(item, dict) else item).strip()
        if text:
            texts.append(text)
            details.append({"text": text, "engine": "imgocr", "variant": "raw"})
    joined = " ".join(texts)
    candidates = candidates_to_dicts(extract_candidates(joined, details, keyword_hint))
    return joined, candidates


def _available_engines() -> dict[str, Callable[[Image.Image, str], tuple[str, list[dict]]]]:
    engines: dict[str, Callable[[Image.Image, str], tuple[str, list[dict]]]] = {
        "production": _production_ocr,
    }
    if importlib.util.find_spec("ddddocr") is not None:
        engines["ddddocr"] = _ddddocr_ocr
    if importlib.util.find_spec("imgocr") is not None:
        engines["imgocr"] = _imgocr_ocr
    return engines


def run_benchmark(sample_dir: Path, keyword_hint: str, requested_engines: list[str]) -> list[BenchmarkResult]:
    labels = _load_labels(sample_dir)
    engines = _available_engines()
    if requested_engines != ["all"]:
        engines = {name: runner for name, runner in engines.items() if name in set(requested_engines)}
    images = sorted(path for path in sample_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    results: list[BenchmarkResult] = []
    for image_path in images:
        expected = labels.get(image_path.name, _expected_from_name(image_path))
        image = Image.open(image_path)
        for engine_name, runner in engines.items():
            started = time.perf_counter()
            try:
                text, candidates = runner(image, keyword_hint)
                selected = int(candidates[0]["value"]) if candidates else None
                error = ""
            except Exception as exc:
                text = ""
                candidates = []
                selected = None
                error = str(exc)
            elapsed_ms = (time.perf_counter() - started) * 1000
            results.append(
                BenchmarkResult(
                    image=str(image_path.relative_to(ROOT_DIR)),
                    engine=engine_name,
                    expected=expected,
                    selected=selected,
                    ok=(selected == expected) if expected is not None and selected is not None else None,
                    elapsed_ms=round(elapsed_ms, 2),
                    text=text,
                    candidates=candidates[:5],
                    error=error,
                )
            )
    return results


def _print_summary(results: list[BenchmarkResult]) -> None:
    by_engine: dict[str, list[BenchmarkResult]] = {}
    for result in results:
        by_engine.setdefault(result.engine, []).append(result)
    for engine, items in by_engine.items():
        checked = [item for item in items if item.ok is not None]
        ok_count = sum(1 for item in checked if item.ok)
        avg_ms = sum(item.elapsed_ms for item in items) / max(1, len(items))
        accuracy = (ok_count / len(checked) * 100) if checked else 0.0
        print(f"{engine}: {ok_count}/{len(checked)} correct, accuracy={accuracy:.1f}%, avg={avg_ms:.1f}ms")
    print("")
    for item in results:
        status = "OK" if item.ok else ("MISS" if item.ok is False else "NO_LABEL")
        print(f"{status} {item.engine:10s} {item.elapsed_ms:8.2f}ms expected={item.expected or '-'} selected={item.selected or '-'} image={item.image}")
        if item.error:
            print(f"  error: {item.error}")
        elif item.text:
            print(f"  text: {item.text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark OCR engines on cropped GMV amount images.")
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLE_DIR), help="Directory containing cropped amount images.")
    parser.add_argument("--engine", action="append", choices=["all", "production", "ddddocr", "imgocr"], default=None)
    parser.add_argument("--keyword-hint", default="")
    parser.add_argument("--json", action="store_true", help="Print full JSON result instead of a summary.")
    args = parser.parse_args()

    sample_dir = Path(args.samples).resolve()
    if not sample_dir.exists():
        raise SystemExit(f"Sample directory does not exist: {sample_dir}")
    requested = args.engine or ["all"]
    if "all" in requested:
        requested = ["all"]
    results = run_benchmark(sample_dir, args.keyword_hint, requested)
    if args.json:
        print(json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2))
    else:
        _print_summary(results)


if __name__ == "__main__":
    os.chdir(ROOT_DIR)
    main()
