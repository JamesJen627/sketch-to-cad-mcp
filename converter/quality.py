from __future__ import annotations

import math
from typing import Any

from .vectorize import LineSegment

SHORT_LINE_THRESHOLD_PX = 30.0
ORTHO_ANGLE_TOLERANCE_DEG = 12.0


def short_line_ratio(segments: list[LineSegment], *, threshold_px: float = SHORT_LINE_THRESHOLD_PX) -> float:
    """短线段占比，越高表示矢量化越碎片化。"""
    if not segments:
        return 0.0
    short_count = sum(1 for seg in segments if seg.length_px < threshold_px)
    return short_count / len(segments)


def orthogonal_ratio(
    segments: list[LineSegment],
    *,
    angle_tolerance_deg: float = ORTHO_ANGLE_TOLERANCE_DEG,
) -> float:
    """近水平/垂直线段占比，平面图通常应较高。"""
    if not segments:
        return 0.0

    ortho_count = 0
    for seg in segments:
        dx = seg.x2 - seg.x1
        dy = seg.y2 - seg.y1
        angle = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        near_horizontal = angle <= angle_tolerance_deg or angle >= 180.0 - angle_tolerance_deg
        near_vertical = abs(angle - 90.0) <= angle_tolerance_deg
        if near_horizontal or near_vertical:
            ortho_count += 1
    return ortho_count / len(segments)


def fragmentation_score(segments: list[LineSegment]) -> float:
    """
    碎片化评分 0–1，越高越碎片化（质量越差）。
    基于平均线长与最长线段的比值估算。
    """
    if not segments:
        return 1.0
    if len(segments) == 1:
        return 0.0

    lengths = [seg.length_px for seg in segments]
    avg_len = sum(lengths) / len(lengths)
    max_len = max(lengths)
    if max_len <= 0:
        return 1.0

    continuity = avg_len / max_len
    return max(0.0, min(1.0, 1.0 - continuity))


def grade_score(
    segments: list[LineSegment],
    *,
    preset: str = "floor_plan",
    ink_ratio: float | None = None,
) -> dict[str, Any]:
    """
    综合质量评分，返回 score (0–100)、grade (A/B/C)、issues、suggest_rerun_with。
    """
    frag = fragmentation_score(segments)
    short_ratio = short_line_ratio(segments)
    ortho = orthogonal_ratio(segments)

    metrics = {
        "fragmentation_score": round(frag, 4),
        "short_line_ratio": round(short_ratio, 4),
        "orthogonal_ratio": round(ortho, 4),
        "line_count": len(segments),
    }

    issues: list[str] = []
    suggest_rerun_with: str | None = None

    if not segments:
        issues.append("未检测到有效线段")
        suggest_rerun_with = "sketch_rough"
        return {
            "score": 0,
            "grade": "C",
            "metrics": metrics,
            "issues": issues,
            "suggest_rerun_with": suggest_rerun_with,
        }

    score = 100.0
    score -= frag * 30.0
    score -= short_ratio * 25.0

    if preset in ("floor_plan", "site_plan") and ortho < 0.55:
        issues.append("正交线段占比偏低，墙体可能未对齐或输入非平面图")
        score -= 15.0

    if short_ratio > 0.5:
        issues.append("短线段过多，矢量化结果可能碎片化")
        score -= 10.0

    if frag > 0.65:
        issues.append("线段碎片化严重，建议提高图片分辨率或换 preset")
        score -= 10.0

    if ink_ratio is not None:
        if ink_ratio < 0.005:
            issues.append("图像线条占比过低，可能对比度不足")
            score -= 15.0
        elif ink_ratio > 0.35:
            issues.append("背景噪声较多，建议扫描件或提高拍照对比度")
            score -= 10.0

    score = max(0.0, min(100.0, score))
    grade = "A" if score >= 80 else "B" if score >= 60 else "C"

    if score < 70 and preset != "sketch_rough":
        suggest_rerun_with = "sketch_rough"
    elif score < 80 and preset == "floor_plan":
        suggest_rerun_with = "site_plan" if ortho < 0.4 else None

    return {
        "score": round(score, 1),
        "grade": grade,
        "metrics": metrics,
        "issues": issues,
        "suggest_rerun_with": suggest_rerun_with,
    }
