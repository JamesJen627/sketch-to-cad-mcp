from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def detect_colored_grid_paper(bgr: np.ndarray) -> dict[str, Any]:
    """检测橙/蓝方格纸（手机实拍测绘图常见）。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(hsv, np.array([8, 60, 90]), np.array([28, 255, 255]))
    blue = cv2.inRange(hsv, np.array([95, 40, 90]), np.array([130, 255, 255]))
    total = max(bgr.shape[0] * bgr.shape[1], 1)
    orange_ratio = float(np.count_nonzero(orange) / total)
    blue_ratio = float(np.count_nonzero(blue) / total)
    dominant = "orange" if orange_ratio >= blue_ratio else "blue"
    ratio = max(orange_ratio, blue_ratio)
    return {
        "is_grid_paper": ratio >= 0.25,
        "dominant_color": dominant,
        "orange_ratio": round(orange_ratio, 4),
        "blue_ratio": round(blue_ratio, 4),
        "grid_ratio": round(ratio, 4),
    }


def _ink_channel(bgr: np.ndarray, dominant: str) -> np.ndarray:
    b, _g, r = cv2.split(bgr)
    if dominant == "orange":
        return b
    if dominant == "blue":
        return r
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def _binarize_ink(channel: np.ndarray, ink_threshold: int | None) -> np.ndarray:
    blur = cv2.GaussianBlur(channel, (3, 3), 0)
    if ink_threshold is None or ink_threshold <= 0:
        _, ink = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, ink = cv2.threshold(blur, ink_threshold, 255, cv2.THRESH_BINARY_INV)
    return ink


def _extract_thin_grid(
    ink: np.ndarray,
    *,
    morph_h: int,
    morph_v: int,
    max_stroke_radius: float,
) -> np.ndarray:
    """提取细长的水平/垂直线（方格纸网格），保留较粗墙体。"""
    h, w = ink.shape[:2]
    kh = max(32, min(morph_h, w // 4))
    kv = max(32, min(morph_v, h // 4))

    dist = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
    thin = np.where(dist <= max(1.0, max_stroke_radius), 255, 0).astype(np.uint8)

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
    grid_h = cv2.morphologyEx(thin, cv2.MORPH_OPEN, h_kernel)
    grid_v = cv2.morphologyEx(thin, cv2.MORPH_OPEN, v_kernel)
    return cv2.bitwise_or(grid_h, grid_v)


def suppress_grid_binary(
    bgr: np.ndarray,
    *,
    ink_threshold: int | None = None,
    morph_h: int = 64,
    morph_v: int = 64,
    min_wall_thickness: int = 3,
    max_stroke_radius: float = 1.6,
    dominant_color: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    从橙/蓝方格纸实拍中提取黑色墨线，并尽量去掉细网格线。

    策略：OTSU/高阈值二值化 → 距离变换筛细线 → 长核形态学提取 H/V 网格 → 从原图扣除。
    """
    detection = detect_colored_grid_paper(bgr)
    dominant = dominant_color or detection["dominant_color"]
    channel = _ink_channel(bgr, dominant)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 橙格纸优先 B 通道 OTSU；若墨线保留不足则回退灰度 OTSU
    ink = _binarize_ink(channel, ink_threshold)
    ink_gray = _binarize_ink(gray, None)
    if np.count_nonzero(ink) < np.count_nonzero(ink_gray) * 0.55:
        ink = ink_gray
        source = "gray_otsu"
    else:
        source = "channel_otsu" if ink_threshold is None else "channel_fixed"

    grid = _extract_thin_grid(
        ink,
        morph_h=morph_h,
        morph_v=morph_v,
        max_stroke_radius=max_stroke_radius,
    )

    if min_wall_thickness > 1:
        wall_kernel = np.ones((min_wall_thickness, min_wall_thickness), np.uint8)
        walls = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, wall_kernel)
        grid = cv2.subtract(grid, walls)

    clean = cv2.subtract(ink, grid)
    clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8), iterations=1)

    h, w = ink.shape[:2]
    meta = {
        "dominant_color": dominant,
        "source": source,
        "ink_threshold": ink_threshold,
        "morph_h": max(32, min(morph_h, w // 4)),
        "morph_v": max(32, min(morph_v, h // 4)),
        "max_stroke_radius": max_stroke_radius,
        "ink_pixels_before": int(np.count_nonzero(ink)),
        "grid_pixels": int(np.count_nonzero(grid)),
        "ink_pixels_after": int(np.count_nonzero(clean)),
        "reduction_ratio": round(
            1.0 - np.count_nonzero(clean) / max(np.count_nonzero(ink), 1),
            4,
        ),
        "detection": detection,
    }
    return clean, meta


def suppress_grid_from_bgr(
    bgr: np.ndarray,
    config: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    cfg = config or {}
    th = cfg.get("grid_ink_threshold")
    ink_threshold = None if th is None or int(th) <= 0 else int(th)
    return suppress_grid_binary(
        bgr,
        ink_threshold=ink_threshold,
        morph_h=int(cfg.get("grid_morph_h", 64)),
        morph_v=int(cfg.get("grid_morph_v", 64)),
        min_wall_thickness=int(cfg.get("grid_min_wall_thickness", 3)),
        max_stroke_radius=float(cfg.get("grid_max_stroke_radius", 1.6)),
    )
