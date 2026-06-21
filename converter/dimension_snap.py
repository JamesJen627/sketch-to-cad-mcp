from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .dimension_ocr import DimensionLabel
from .vectorize import LineSegment, _line_length


@dataclass
class DimensionMatch:
    label: DimensionLabel
    segment_index: int
    distance_px: float
    old_length_px: float
    new_length_px: float
    implied_scale: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_mm": self.label.value_mm,
            "text_raw": self.label.text_raw,
            "segment_index": self.segment_index,
            "distance_px": round(self.distance_px, 1),
            "old_length_px": round(self.old_length_px, 1),
            "new_length_px": round(self.new_length_px, 1),
            "implied_scale_mm_per_px": round(self.implied_scale, 4),
        }


@dataclass
class DimensionSnapResult:
    segments: list[LineSegment]
    scale_mm_per_pixel: float
    matches: list[DimensionMatch] = field(default_factory=list)
    unmatched_labels: list[DimensionLabel] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale_mm_per_pixel": round(self.scale_mm_per_pixel, 4),
            "match_count": len(self.matches),
            "matches": [m.to_dict() for m in self.matches],
            "unmatched_labels": [label.to_dict() for label in self.unmatched_labels],
            "warnings": self.warnings,
        }


def _segment_image_coords(seg: LineSegment, image_height: float) -> tuple[float, float, float, float]:
    return seg.x1, image_height - seg.y1, seg.x2, image_height - seg.y2


def _segment_angle_rad(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.atan2(y2 - y1, x2 - x1)


def _point_segment_distance_and_t(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-6:
        return float(np.hypot(px - x1, py - y1)), 0.0
    t = ((px - x1) * dx + (py - y1) * dy) / len_sq
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return float(np.hypot(px - proj_x, py - proj_y)), t


def _label_is_horizontal(label: DimensionLabel) -> bool:
    x0, y0, x1, y1 = label.bbox
    return (x1 - x0) >= (y1 - y0)


def _segment_is_horizontal(x1: float, y1: float, x2: float, y2: float) -> bool:
    return abs(x2 - x1) >= abs(y2 - y1)


def _match_labels_to_segments(
    segments: list[LineSegment],
    labels: list[DimensionLabel],
    *,
    image_height: float,
    max_dist_px: float = 90.0,
) -> list[tuple[int, int, float]]:
    """返回 (label_idx, segment_idx, distance)。"""
    pairs: list[tuple[float, int, int, float]] = []
    for li, label in enumerate(labels):
        horizontal = _label_is_horizontal(label)
        for si, seg in enumerate(segments):
            ix1, iy1, ix2, iy2 = _segment_image_coords(seg, image_height)
            seg_h = _segment_is_horizontal(ix1, iy1, ix2, iy2)
            if horizontal != seg_h:
                continue
            dist, t = _point_segment_distance_and_t(label.center_x, label.center_y, ix1, iy1, ix2, iy2)
            if t < -0.15 or t > 1.15:
                dist += 40.0
            if dist <= max_dist_px:
                pairs.append((dist, li, si, dist))

    pairs.sort(key=lambda item: item[0])
    used_labels: set[int] = set()
    used_segments: set[int] = set()
    assignments: list[tuple[int, int, float]] = []
    for _dist, li, si, dist in pairs:
        if li in used_labels or si in used_segments:
            continue
        used_labels.add(li)
        used_segments.add(si)
        assignments.append((li, si, dist))
    return assignments


def _resize_segment(seg: LineSegment, new_length_px: float) -> LineSegment:
    if new_length_px <= 0 or seg.length_px <= 1e-6:
        return seg
    cx = (seg.x1 + seg.x2) / 2.0
    cy = (seg.y1 + seg.y2) / 2.0
    dx = seg.x2 - seg.x1
    dy = seg.y2 - seg.y1
    ux = dx / seg.length_px
    uy = dy / seg.length_px
    half = new_length_px / 2.0
    return LineSegment(
        x1=cx - ux * half,
        y1=cy - uy * half,
        x2=cx + ux * half,
        y2=cy + uy * half,
        thickness_px=seg.thickness_px,
        length_px=new_length_px,
        layer=seg.layer,
    )


def snap_segments_to_dimensions(
    segments: list[LineSegment],
    labels: list[DimensionLabel],
    *,
    image_height: float,
    base_scale_mm_per_pixel: float,
    max_dist_px: float = 90.0,
) -> DimensionSnapResult:
    """
    将 OCR 尺寸标注吸附到最近墙线，并按标注 mm 调整线段长度。
    同时用匹配对的中位比例尺更新全局 scale。
    """
    warnings: list[str] = []
    if not segments:
        warnings.append("无线段可吸附")
        return DimensionSnapResult(
            segments=segments,
            scale_mm_per_pixel=base_scale_mm_per_pixel,
            warnings=warnings,
        )
    if not labels:
        warnings.append("无尺寸标注")
        return DimensionSnapResult(
            segments=segments,
            scale_mm_per_pixel=base_scale_mm_per_pixel,
            warnings=warnings,
        )

    assignments = _match_labels_to_segments(
        segments,
        labels,
        image_height=image_height,
        max_dist_px=max_dist_px,
    )
    matched_label_idx = {li for li, _si, _d in assignments}
    unmatched_labels = [labels[i] for i in range(len(labels)) if i not in matched_label_idx]

    scales: list[float] = []
    matches: list[DimensionMatch] = []
    for li, si, dist in assignments:
        seg = segments[si]
        label = labels[li]
        if seg.length_px < 1e-3:
            continue
        implied = label.value_mm / seg.length_px
        scales.append(implied)
        matches.append(
            DimensionMatch(
                label=label,
                segment_index=si,
                distance_px=dist,
                old_length_px=seg.length_px,
                new_length_px=0.0,
                implied_scale=implied,
            )
        )

    if not scales:
        warnings.append("尺寸标注与线段未能匹配，请检查标注是否靠近墙线")
        return DimensionSnapResult(
            segments=segments,
            scale_mm_per_pixel=base_scale_mm_per_pixel,
            unmatched_labels=unmatched_labels,
            warnings=warnings,
        )

    scale = float(np.median(scales))
    if base_scale_mm_per_pixel > 0 and abs(scale - base_scale_mm_per_pixel) / base_scale_mm_per_pixel > 0.01:
        warnings.append(
            f"比例尺由 preset {base_scale_mm_per_pixel:.2f} 校准为 OCR 中位值 {scale:.2f} mm/px"
        )

    new_segments = list(segments)
    for match in matches:
        target_px = match.label.value_mm / scale
        match.new_length_px = target_px
        new_segments[match.segment_index] = _resize_segment(new_segments[match.segment_index], target_px)

    if unmatched_labels:
        warnings.append(f"{len(unmatched_labels)} 个标注未匹配到墙线")

    return DimensionSnapResult(
        segments=new_segments,
        scale_mm_per_pixel=scale,
        matches=matches,
        unmatched_labels=unmatched_labels,
        warnings=warnings,
    )
