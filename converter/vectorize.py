from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class LineSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    thickness_px: float
    length_px: float
    layer: str = "手绘转图-线稿"


def _line_length(x1: float, y1: float, x2: float, y2: float) -> float:
    return float(np.hypot(x2 - x1, y2 - y1))


def extract_lines(
    binary: np.ndarray,
    *,
    canny_low: int = 40,
    canny_high: int = 120,
    min_line_length_px: int = 25,
    max_line_gap_px: int = 12,
) -> list[LineSegment]:
    edges = cv2.Canny(binary, canny_low, canny_high, apertureSize=3)
    raw = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=min_line_length_px,
        maxLineGap=max_line_gap_px,
    )
    if raw is None:
        return []

    height = binary.shape[0]
    segments: list[LineSegment] = []
    seen: set[tuple[int, int, int, int]] = set()

    for item in raw:
        x1, y1, x2, y2 = map(int, item[0])
        key = tuple(sorted([(x1, y1), (x2, y2)]))  # type: ignore[arg-type]
        if key in seen:
            continue
        seen.add(key)  # type: ignore[arg-type]

        thickness = _estimate_thickness(binary, x1, y1, x2, y2)
        length = _line_length(x1, y1, x2, y2)
        # CAD 坐标系 Y 轴向上，图像 Y 轴向下
        segments.append(
            LineSegment(
                x1=float(x1),
                y1=float(height - y1),
                x2=float(x2),
                y2=float(height - y2),
                thickness_px=thickness,
                length_px=length,
            )
        )
    return segments


def _estimate_thickness(binary: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
    mask = np.zeros_like(binary)
    cv2.line(mask, (x1, y1), (x2, y2), 255, 1)
    dilated = cv2.dilate(binary, np.ones((3, 3), np.uint8), iterations=1)
    overlap = cv2.bitwise_and(mask, dilated)
    count = int(np.count_nonzero(overlap))
    length = max(_line_length(x1, y1, x2, y2), 1.0)
    return max(1.0, count / length)


def classify_layer(segment: LineSegment, thick_line_threshold_px: float) -> str:
    if segment.thickness_px >= thick_line_threshold_px and segment.length_px >= 80:
        return "墙体-240"
    if segment.thickness_px >= thick_line_threshold_px * 0.7 and segment.length_px >= 50:
        return "墙体-120"
    if segment.length_px >= 200 and segment.thickness_px <= 2:
        return "轴线"
    return "手绘转图-线稿"


def render_preview(binary: np.ndarray, segments: list[LineSegment], output_path: str) -> None:
    preview = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height = binary.shape[0]
    for seg in segments:
        cv2.line(
            preview,
            (int(seg.x1), int(height - seg.y1)),
            (int(seg.x2), int(height - seg.y2)),
            (0, 180, 0),
            1,
        )
    cv2.imencode(".png", preview)[1].tofile(output_path)
