"""Quick grid suppression tuning (no full pipeline)."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from converter.grid_suppress import suppress_grid_from_bgr
from converter.preprocess import binarize, load_image, to_grayscale
from converter.vectorize import extract_lines

INPUT = Path(
    r"D:\PilotDeck-乡村振兴杯-长兴新塘村民宿改造设计项目-Harness Engineering\01-测绘数据\测试测绘图.jpg"
)


def ink_ratio(binary) -> float:
    return float(binary.sum() / 255) / (binary.shape[0] * binary.shape[1])


def count_lines(binary, **kw) -> int:
    return len(extract_lines(binary, **kw))


def main() -> None:
    bgr = load_image(str(INPUT))
    gray = to_grayscale(bgr)
    b = cv2.split(bgr)[0]

    bin_site = binarize(gray, adaptive=False)
    print(
        "site OTSU gray:",
        round(ink_ratio(bin_site), 4),
        "lines40:",
        count_lines(bin_site, canny_low=30, canny_high=100, min_line_length_px=40),
    )

    blur = cv2.GaussianBlur(b, (3, 3), 0)
    _, otsu_b = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    print(
        "OTSU B:",
        round(ink_ratio(otsu_b), 4),
        "lines40:",
        count_lines(otsu_b, canny_low=30, canny_high=100, min_line_length_px=40),
    )

    print("th,mh,mwt,lines,ink,red")
    best = (999999, None)
    for th in (130, 140, 150, 160):
        for mh in (48, 64, 96, 128):
            for mwt in (3, 4, 5):
                cfg = {
                    "grid_ink_threshold": th,
                    "grid_morph_h": mh,
                    "grid_morph_v": mh,
                    "grid_min_wall_thickness": mwt,
                }
                clean, meta = suppress_grid_from_bgr(bgr, cfg)
                n = count_lines(clean, canny_low=30, canny_high=100, min_line_length_px=40)
                ir = ink_ratio(clean)
                print(th, mh, mwt, n, round(ir, 4), meta["reduction_ratio"])
                if n < best[0]:
                    best = (n, (th, mh, mwt, ir, meta["reduction_ratio"]))
    print("best:", best)


if __name__ == "__main__":
    main()
