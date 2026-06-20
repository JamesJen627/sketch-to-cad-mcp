#!/usr/bin/env python3
"""生成测试用手绘平面图并运行转换 pipeline。"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from converter.pipeline import SketchConvertOptions, convert_sketch_to_dxf


def make_sample_sketch(path: Path) -> None:
    img = np.ones((800, 1000, 3), dtype=np.uint8) * 255
    # 外墙
    cv2.rectangle(img, (120, 120), (880, 680), (0, 0, 0), 6)
    # 内隔墙
    cv2.line(img, (500, 120), (500, 680), (0, 0, 0), 3)
    cv2.line(img, (120, 400), (880, 400), (0, 0, 0), 3)
    # 门洞
    cv2.line(img, (480, 680), (520, 680), (255, 255, 255), 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", img)[1].tofile(str(path))


def main() -> None:
    sample = ROOT / "test_samples" / "sample_floor_plan.png"
    make_sample_sketch(sample)
    out_dir = ROOT / "test_samples" / "output"
    result = convert_sketch_to_dxf(
        SketchConvertOptions(
            input_path=str(sample),
            output_dir=str(out_dir),
            output_name="sample_converted",
            preset="floor_plan",
            project_name="新塘村民宿改造-测试",
        )
    )
    print(result.to_dict())


if __name__ == "__main__":
    main()
