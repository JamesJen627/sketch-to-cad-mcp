#!/usr/bin/env python3
"""批量测试 test_samples/ 并生成 benchmark_report.json。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from converter.pipeline import SketchConvertOptions, convert_sketch_to_dxf
from converter.preprocess import load_image, preprocess
from converter.vectorize import extract_lines


def _make_sample_floor_plan(path: Path) -> None:
    img = np.ones((800, 1000, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (120, 120), (880, 680), (0, 0, 0), 6)
    cv2.line(img, (500, 120), (500, 680), (0, 0, 0), 3)
    cv2.line(img, (120, 400), (880, 400), (0, 0, 0), 3)
    cv2.line(img, (480, 680), (520, 680), (255, 255, 255), 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", img)[1].tofile(str(path))


def _make_sample_site_plan(path: Path) -> None:
    img = np.ones((600, 900, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (80, 80), (820, 520), (0, 0, 0), 4)
    cv2.circle(img, (450, 300), 60, (0, 0, 0), 2)
    cv2.line(img, (80, 300), (820, 300), (0, 0, 0), 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", img)[1].tofile(str(path))


def _ensure_samples(samples_dir: Path) -> list[Path]:
    samples_dir.mkdir(parents=True, exist_ok=True)
    floor = samples_dir / "sample_floor_plan.png"
    site = samples_dir / "sample_site_plan.png"
    if not floor.is_file():
        _make_sample_floor_plan(floor)
    if not site.is_file():
        _make_sample_site_plan(site)
    return sorted(samples_dir.glob("*.png"))


def _build_comparison_preview(
    input_path: Path,
    binary: np.ndarray,
    segments: list,
    output_path: Path,
) -> None:
    """三栏对比：原图 | 二值化 | 矢量叠加。"""
    original = load_image(str(input_path))
    h, w = original.shape[:2]
    binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    if binary_bgr.shape[:2] != (h, w):
        binary_bgr = cv2.resize(binary_bgr, (w, h))

    overlay = original.copy()
    for seg in segments:
        x1, y1 = int(seg.x1), int(h - seg.y1)
        x2, y2 = int(seg.x2), int(h - seg.y2)
        cv2.line(overlay, (x1, y1), (x2, y2), (0, 0, 255), 2)

    canvas = np.hstack([original, binary_bgr, overlay])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", canvas)[1].tofile(str(output_path))


def run_benchmark() -> dict:
    samples_dir = ROOT / "test_samples"
    output_dir = samples_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = _ensure_samples(samples_dir)
    results: list[dict] = []

    for sample in samples:
        stem = sample.stem
        preset = "site_plan" if "site" in stem else "floor_plan"
        result = convert_sketch_to_dxf(
            SketchConvertOptions(
                input_path=str(sample),
                output_dir=str(output_dir),
                output_name=f"{stem}_converted",
                preset=preset,
                project_name="新塘村民宿改造-基准测试",
                run_cad_check=False,
            )
        )

        comparison_path = output_dir / f"{stem}_comparison.png"
        try:
            _, _, binary = preprocess(str(sample), deskew_enabled=True)
            segments = extract_lines(binary)
            _build_comparison_preview(sample, binary, segments, comparison_path)
        except Exception as exc:
            comparison_path = None  # type: ignore[assignment]
            result.warnings.append(f"对比预览生成失败: {exc}")

        entry = {
            "input": str(sample),
            "preset": preset,
            "success": result.success,
            "line_count": result.line_count,
            "quality": result.quality,
            "comparison_preview": str(comparison_path) if comparison_path else None,
            "dxf_path": result.dxf_path,
            "preview_path": result.preview_path,
            "warnings": result.warnings,
            "error": result.error,
        }
        results.append(entry)

    scores = [r["quality"]["score"] for r in results if r.get("quality")]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(results),
        "success_count": sum(1 for r in results if r["success"]),
        "average_quality_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "results": results,
    }
    return report


def main() -> None:
    report = run_benchmark()
    report_path = ROOT / "test_samples" / "benchmark_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已写入: {report_path}")


if __name__ == "__main__":
    main()
