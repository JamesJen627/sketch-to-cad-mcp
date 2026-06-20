from __future__ import annotations

import math
from typing import Any

import numpy as np

from .vectorize import LineSegment, _line_length


def _segment_angle_rad(seg: LineSegment) -> float:
    return math.atan2(seg.y2 - seg.y1, seg.x2 - seg.x1)


def _undirected_angle_rad(seg: LineSegment) -> float:
    angle = _segment_angle_rad(seg) % math.pi
    if angle < 0:
        angle += math.pi
    return angle


def _angle_diff_rad(a: float, b: float) -> float:
    d = abs(a - b) % math.pi
    return min(d, math.pi - d)


def _line_offset(seg: LineSegment, angle: float) -> float:
    """点到原点的有符号法向距离（沿给定方向角）。"""
    nx = -math.sin(angle)
    ny = math.cos(angle)
    return seg.x1 * nx + seg.y1 * ny


def _project_scalar(seg: LineSegment, angle: float) -> tuple[float, float]:
    dx = math.cos(angle)
    dy = math.sin(angle)
    t1 = seg.x1 * dx + seg.y1 * dy
    t2 = seg.x2 * dx + seg.y2 * dy
    return (min(t1, t2), max(t1, t2))


def _rebuild_segment(
    angle: float,
    offset: float,
    t_min: float,
    t_max: float,
    *,
    thickness_px: float,
    layer: str,
) -> LineSegment:
    nx = -math.sin(angle)
    ny = math.cos(angle)
    dx = math.cos(angle)
    dy = math.sin(angle)
    x1 = nx * offset + dx * t_min
    y1 = ny * offset + dy * t_min
    x2 = nx * offset + dx * t_max
    y2 = ny * offset + dy * t_max
    length = _line_length(x1, y1, x2, y2)
    return LineSegment(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        thickness_px=thickness_px,
        length_px=length,
        layer=layer,
    )


def _endpoint_distance(a: LineSegment, b: LineSegment) -> float:
    pairs = (
        (a.x1, a.y1, b.x1, b.y1),
        (a.x1, a.y1, b.x2, b.y2),
        (a.x2, a.y2, b.x1, b.y1),
        (a.x2, a.y2, b.x2, b.y2),
    )
    return min(float(np.hypot(x2 - x1, y2 - y1)) for x1, y1, x2, y2 in pairs)


def _segments_collinear(
    a: LineSegment,
    b: LineSegment,
    *,
    angle_tol_rad: float,
    offset_tol_px: float,
) -> bool:
    angle_a = _undirected_angle_rad(a)
    angle_b = _undirected_angle_rad(b)
    if _angle_diff_rad(angle_a, angle_b) > angle_tol_rad:
        return False
    angle = (angle_a + angle_b) / 2.0
    offset_a = _line_offset(a, angle)
    offset_b = _line_offset(b, angle)
    return abs(offset_a - offset_b) <= offset_tol_px


def merge_collinear(
    segments: list[LineSegment],
    *,
    merge_gap_px: float = 15.0,
    angle_tol_deg: float = 6.0,
    offset_tol_px: float = 8.0,
) -> list[LineSegment]:
    if not segments:
        return []

    angle_tol_rad = math.radians(angle_tol_deg)
    merged = list(segments)
    changed = True
    while changed:
        changed = False
        out: list[LineSegment] = []
        used = [False] * len(merged)
        for i, seg in enumerate(merged):
            if used[i]:
                continue
            angle = _undirected_angle_rad(seg)
            offset = _line_offset(seg, angle)
            t_min, t_max = _project_scalar(seg, angle)
            thickness = seg.thickness_px
            layer = seg.layer
            used[i] = True

            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                other = merged[j]
                if not _segments_collinear(
                    seg,
                    other,
                    angle_tol_rad=angle_tol_rad,
                    offset_tol_px=offset_tol_px,
                ):
                    continue
                o_angle = _undirected_angle_rad(other)
                o_offset = _line_offset(other, o_angle)
                ot_min, ot_max = _project_scalar(other, o_angle)
                angle = (angle + o_angle) / 2.0
                offset = (offset + o_offset) / 2.0
                t_min = min(t_min, ot_min)
                t_max = max(t_max, ot_max)
                thickness = max(thickness, other.thickness_px)
                used[j] = True
                changed = True

            out.append(
                _rebuild_segment(
                    angle,
                    offset,
                    t_min,
                    t_max,
                    thickness_px=thickness,
                    layer=layer,
                )
            )
        merged = out
    return merged


def remove_duplicates(
    segments: list[LineSegment],
    *,
    duplicate_dist_px: float = 10.0,
    angle_tol_deg: float = 5.0,
    overlap_ratio: float = 0.85,
) -> list[LineSegment]:
    if not segments:
        return []

    angle_tol_rad = math.radians(angle_tol_deg)
    kept: list[LineSegment] = []
    for seg in segments:
        duplicate = False
        for existing in kept:
            if _angle_diff_rad(_undirected_angle_rad(seg), _undirected_angle_rad(existing)) > angle_tol_rad:
                continue
            if _endpoint_distance(seg, existing) > duplicate_dist_px * 3:
                angle = _undirected_angle_rad(existing)
                if not _segments_collinear(
                    seg,
                    existing,
                    angle_tol_rad=angle_tol_rad,
                    offset_tol_px=duplicate_dist_px,
                ):
                    continue
            t_seg = _project_scalar(seg, _undirected_angle_rad(seg))
            t_exist = _project_scalar(existing, _undirected_angle_rad(existing))
            overlap = max(0.0, min(t_seg[1], t_exist[1]) - max(t_seg[0], t_exist[0]))
            span = max(t_seg[1] - t_seg[0], t_exist[1] - t_exist[0], 1e-6)
            if overlap / span >= overlap_ratio or _endpoint_distance(seg, existing) <= duplicate_dist_px:
                if seg.length_px <= existing.length_px:
                    duplicate = True
                    break
                kept.remove(existing)
                break
        if not duplicate:
            kept.append(seg)
    return kept


def filter_short_noise(
    segments: list[LineSegment],
    *,
    min_length_px: float = 30.0,
    endpoint_connect_px: float = 18.0,
) -> list[LineSegment]:
    if not segments:
        return []

    long_enough = [s for s in segments if s.length_px >= min_length_px]
    if len(long_enough) == len(segments):
        return segments

    if not long_enough:
        long_enough = sorted(segments, key=lambda s: s.length_px, reverse=True)[: max(1, len(segments) // 2)]

    endpoints: list[tuple[float, float]] = []
    for seg in long_enough:
        endpoints.extend([(seg.x1, seg.y1), (seg.x2, seg.y2)])

    result: list[LineSegment] = []
    for seg in segments:
        if seg.length_px >= min_length_px:
            result.append(seg)
            continue
        connected = False
        for x, y in ((seg.x1, seg.y1), (seg.x2, seg.y2)):
            for ex, ey in endpoints:
                if np.hypot(x - ex, y - ey) <= endpoint_connect_px:
                    connected = True
                    break
            if connected:
                break
        if connected:
            result.append(seg)
    return result


def snap_orthogonal(
    segments: list[LineSegment],
    *,
    snap_angle_deg: float = 8.0,
) -> list[LineSegment]:
    snap_rad = math.radians(snap_angle_deg)
    snapped: list[LineSegment] = []

    for seg in segments:
        angle = _segment_angle_rad(seg)
        undirected = _undirected_angle_rad(seg)
        horizontal_dist = min(_angle_diff_rad(undirected, 0.0), _angle_diff_rad(undirected, math.pi))
        vertical_dist = abs(undirected - math.pi / 2)

        if horizontal_dist <= snap_rad:
            y = (seg.y1 + seg.y2) / 2.0
            x_min, x_max = sorted([seg.x1, seg.x2])
            snapped.append(
                LineSegment(
                    x1=x_min,
                    y1=y,
                    x2=x_max,
                    y2=y,
                    thickness_px=seg.thickness_px,
                    length_px=_line_length(x_min, y, x_max, y),
                    layer=seg.layer,
                )
            )
        elif vertical_dist <= snap_rad:
            x = (seg.x1 + seg.x2) / 2.0
            y_min, y_max = sorted([seg.y1, seg.y2])
            snapped.append(
                LineSegment(
                    x1=x,
                    y1=y_min,
                    x2=x,
                    y2=y_max,
                    thickness_px=seg.thickness_px,
                    length_px=_line_length(x, y_min, x, y_max),
                    layer=seg.layer,
                )
            )
        else:
            snapped.append(seg)
    return snapped


def _resolve_config(preset: str, config: dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        from .config_loader import get_preset

        config = get_preset(preset)
    return config


def refine_segments(
    segments: list[LineSegment],
    *,
    preset: str,
    config: dict[str, Any] | None = None,
) -> list[LineSegment]:
    cfg = _resolve_config(preset, config)
    merge_gap_px = float(cfg.get("merge_gap_px", 15))
    duplicate_dist_px = float(cfg.get("duplicate_dist_px", 10))
    min_segment_length_px = float(cfg.get("min_segment_length_px", 30))
    snap_angle_deg = float(cfg.get("snap_angle_deg", 8))
    angle_tol_deg = float(cfg.get("merge_angle_tol_deg", 6))

    result = merge_collinear(
        segments,
        merge_gap_px=merge_gap_px,
        angle_tol_deg=angle_tol_deg,
    )
    result = remove_duplicates(result, duplicate_dist_px=duplicate_dist_px, angle_tol_deg=angle_tol_deg)
    result = filter_short_noise(result, min_length_px=min_segment_length_px)
    if preset == "floor_plan":
        result = snap_orthogonal(result, snap_angle_deg=snap_angle_deg)
    return result
