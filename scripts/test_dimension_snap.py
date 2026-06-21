#!/usr/bin/env python3
"""测试尺寸 OCR 吸附：生成带标注草图并验证 DXF 墙长。"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import ezdxf
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from converter.pipeline import SketchConvertOptions, convert_sketch_to_dxf


def make_dimensioned_sketch(path: Path) -> None:
    """两联矩形平面，标注 3000 / 4500 / 2500 / 1000。"""
    img = np.ones((900, 1200, 3), dtype=np.uint8) * 255
    # 左大框 + 右小框（类似用户草图）
    cv2.rectangle(img, (150, 180), (650, 720), (0, 0, 0), 5)
    cv2.rectangle(img, (650, 180), (950, 720), (0, 0, 0), 5)
    cv2.line(img, (650, 180), (650, 720), (0, 0, 0), 5)
    # 门洞
    cv2.line(img, (330, 720), (430, 720), (255, 255, 255), 10)
    cv2.line(img, (760, 720), (860, 720), (255, 255, 255), 10)

    font = cv2.FONT_HERSHEY_SIMPLEX
    labels = [
        ("3000", (220, 160), 1.4, 3),
        ("4500", (360, 160), 1.4, 3),
        ("2500", (760, 160), 1.4, 3),
        ("1000", (350, 770), 1.1, 2),
        ("1000", (780, 770), 1.1, 2),
    ]
    for text, (x, y), scale, thick in labels:
        cv2.putText(img, text, (x, y), font, scale, (0, 0, 0), thick, cv2.LINE_AA)

    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", img)[1].tofile(str(path))


def _line_length_mm(doc: ezdxf.document.Drawing) -> list[float]:
    lengths: list[float] = []
    msp = doc.modelspace()
    for entity in msp:
        if entity.dxftype() != "LINE":
            continue
        x1, y1, _ = entity.dxf.start
        x2, y2, _ = entity.dxf.end
        lengths.append(float(math.hypot(x2 - x1, y2 - y1)))
    return sorted(lengths, reverse=True)


def main() -> None:
    sample = ROOT / "test_samples" / "sample_dimension_plan.png"
    make_dimensioned_sketch(sample)
    out_dir = ROOT / "test_samples" / "output"
    result = convert_sketch_to_dxf(
        SketchConvertOptions(
            input_path=str(sample),
            output_dir=str(out_dir),
            output_name="sample_dimension_snapped",
            preset="floor_plan",
            snap_dimensions=True,
            deskew=False,
        )
    )
    print("convert:", {k: result.to_dict()[k] for k in ("success", "scale_mm_per_pixel", "dimension_report", "warnings")})

    dxf_path = Path(result.dxf_path or "")
    if not dxf_path.is_file():
        raise SystemExit("DXF 未生成")

    doc = ezdxf.readfile(str(dxf_path))
    lengths = _line_length_mm(doc)
    print("DXF line lengths (mm, top 8):", [round(v, 1) for v in lengths[:8]])

    report = result.dimension_report or {}
    matches = report.get("matches") or []
    for m in matches:
        expected = m["value_mm"]
        actual = m["new_length_px"] * result.scale_mm_per_pixel
        print(f"  match {m['text_raw']}: expected={expected} actual={actual:.1f}")


if __name__ == "__main__":
    main()
