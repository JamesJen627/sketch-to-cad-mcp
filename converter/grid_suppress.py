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


def _estimate_period_1d(
    projection: np.ndarray,
    *,
    min_period: int = 10,
    max_period: int = 72,
) -> tuple[int | None, int]:
    """自相关估计一维投影的主周期与相位。"""
    signal = projection.astype(np.float64)
    signal -= signal.mean()
    norm = float(np.linalg.norm(signal))
    if norm < 1e-6:
        return None, 0

    corr = np.correlate(signal, signal, mode="full")
    corr = corr[len(corr) // 2 :]
    corr[0] = 0

    upper = min(max_period + 1, len(corr))
    if upper <= min_period + 1:
        return None, 0

    search = corr[min_period:upper]
    if search.size == 0:
        return None, 0

    peak_idx = int(np.argmax(search)) + min_period
    peak_val = float(corr[peak_idx])
    baseline = float(np.max(corr[1:min_period])) if min_period > 1 else 0.0
    if peak_val < baseline * 0.45:
        return None, 0

    period = peak_idx
    best_phase, best_score = 0, -1.0
    for phase in range(period):
        score = float(projection[phase::period].sum())
        if score > best_score:
            best_score = score
            best_phase = phase
    return period, best_phase


def _estimate_grid_layout(
    ink: np.ndarray,
    *,
    min_period: int = 10,
    max_period: int = 72,
) -> dict[str, Any]:
    row_proj = np.sum(ink > 0, axis=1).astype(np.float64)
    col_proj = np.sum(ink > 0, axis=0).astype(np.float64)
    period_h, phase_h = _estimate_period_1d(row_proj, min_period=min_period, max_period=max_period)
    period_w, phase_w = _estimate_period_1d(col_proj, min_period=min_period, max_period=max_period)

    # 方格纸通常等距，若 H/V 周期差异大则取较可靠的一个
    if period_h and period_w and abs(period_h - period_w) > 3:
        row_peak = float(row_proj[phase_h::period_h].sum()) if period_h else 0.0
        col_peak = float(col_proj[phase_w::period_w].sum()) if period_w else 0.0
        period = period_h if row_peak >= col_peak else period_w
        phase_h = phase_h if row_peak >= col_peak else phase_w
        phase_w = phase_h
        period_h = period_w = period

    return {
        "period_h": period_h,
        "period_w": period_w,
        "phase_h": phase_h,
        "phase_w": phase_w,
    }


def _build_periodic_grid_mask(
    shape: tuple[int, int],
    layout: dict[str, Any],
    *,
    line_width: int = 2,
    dot_radius: int = 2,
) -> np.ndarray:
    """根据估计周期生成方格纸网格掩膜（含点阵交点）。"""
    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    period_h = layout.get("period_h")
    period_w = layout.get("period_w")
    if not period_h or not period_w:
        return mask

    phase_h = int(layout.get("phase_h") or 0)
    phase_w = int(layout.get("phase_w") or 0)
    lw = max(1, line_width)
    dr = max(1, dot_radius)

    y = phase_h
    while y < h:
        cv2.line(mask, (0, y), (w - 1, y), 255, lw)
        y += period_h

    x = phase_w
    while x < w:
        cv2.line(mask, (x, 0), (x, h - 1), 255, lw)
        x += period_w

    y = phase_h
    while y < h:
        x = phase_w
        while x < w:
            cv2.circle(mask, (x, y), dr, 255, -1)
            x += period_w
        y += period_h

    dilate_k = max(1, lw)
    if dilate_k > 1:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_k * 2 + 1, dilate_k * 2 + 1))
        mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def _binarize_ink(
    channel: np.ndarray,
    ink_threshold: int | None,
    *,
    dark_percentile: float | None = None,
) -> np.ndarray:
    blur = cv2.GaussianBlur(channel, (3, 3), 0)
    if dark_percentile is not None and 0 < dark_percentile < 50:
        thresh = float(np.percentile(blur, dark_percentile))
        _, ink = cv2.threshold(blur, int(thresh), 255, cv2.THRESH_BINARY_INV)
    elif ink_threshold is None or ink_threshold <= 0:
        _, ink = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, ink = cv2.threshold(blur, ink_threshold, 255, cv2.THRESH_BINARY_INV)
    return ink


def _remove_small_blobs(ink: np.ndarray, *, min_area: int = 12) -> np.ndarray:
    """去掉小点状连通域（网格点），保留较长笔画。"""
    if min_area <= 1:
        return ink

    num, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    out = np.zeros_like(ink)
    for idx in range(1, num):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        width = int(stats[idx, cv2.CC_STAT_WIDTH])
        height = int(stats[idx, cv2.CC_STAT_HEIGHT])
        if area >= min_area:
            out[labels == idx] = 255
            continue
        if max(width, height) >= 4 and min(width, height) <= 2:
            # 短笔画（如标注）保留
            out[labels == idx] = 255
    return out


def _extract_thin_grid(
    ink: np.ndarray,
    *,
    morph_h: int,
    morph_v: int,
    max_stroke_radius: float,
) -> np.ndarray:
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
    grid_period_h: int | None = None,
    grid_period_w: int | None = None,
    grid_line_width: int = 2,
    grid_dot_radius: int = 2,
    grid_dark_percentile: float = 18.0,
    grid_min_blob_area: int = 12,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    方格纸二值化：深色墨线提取 + 周期网格掩膜扣除 + 小点过滤。

    相比旧版仅做「细线形态学」，本版会：
    1. 用 B/灰度通道分位数阈值优先提取黑色墙体
    2. 自相关估计网格周期，生成 H/V 网格掩膜并扣除
    3. 去掉残留小连通域（点阵）
    """
    detection = detect_colored_grid_paper(bgr)
    dominant = dominant_color or detection["dominant_color"]
    channel = _ink_channel(bgr, dominant)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    ink_dark = _binarize_ink(channel, ink_threshold, dark_percentile=grid_dark_percentile)
    ink_otsu = _binarize_ink(channel, ink_threshold, dark_percentile=None)
    ink_gray = _binarize_ink(gray, None, dark_percentile=None)

    # 选墨线保留更充分、且噪声更低的候选
    candidates: list[tuple[str, np.ndarray]] = [
        ("dark_percentile", ink_dark),
        ("channel_otsu", ink_otsu),
        ("gray_otsu", ink_gray),
    ]
    best_name, ink = max(candidates, key=lambda item: np.count_nonzero(item[1]))
    if np.count_nonzero(ink_dark) >= np.count_nonzero(ink_gray) * 0.35:
        ink = ink_dark
        source = "dark_percentile"
    else:
        source = best_name

    layout = _estimate_grid_layout(ink)
    if grid_period_h and grid_period_h > 0:
        layout["period_h"] = int(grid_period_h)
    if grid_period_w and grid_period_w > 0:
        layout["period_w"] = int(grid_period_w)

    grid_mask = _build_periodic_grid_mask(
        ink.shape[:2],
        layout,
        line_width=grid_line_width,
        dot_radius=grid_dot_radius,
    )

    morph_grid = _extract_thin_grid(
        ink,
        morph_h=morph_h,
        morph_v=morph_v,
        max_stroke_radius=max_stroke_radius,
    )
    grid = cv2.bitwise_or(grid_mask, morph_grid)

    if min_wall_thickness > 1:
        wall_kernel = np.ones((min_wall_thickness, min_wall_thickness), np.uint8)
        walls = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, wall_kernel)
        grid = cv2.subtract(grid, walls)

    clean = cv2.subtract(ink, grid)
    clean = _remove_small_blobs(clean, min_area=grid_min_blob_area)
    clean = cv2.morphologyEx(clean, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8), iterations=1)

    h, w = ink.shape[:2]
    meta = {
        "dominant_color": dominant,
        "source": source,
        "ink_threshold": ink_threshold,
        "grid_dark_percentile": grid_dark_percentile,
        "grid_layout": layout,
        "morph_h": max(32, min(morph_h, w // 4)),
        "morph_v": max(32, min(morph_v, h // 4)),
        "max_stroke_radius": max_stroke_radius,
        "ink_pixels_before": int(np.count_nonzero(ink)),
        "grid_mask_pixels": int(np.count_nonzero(grid_mask)),
        "grid_pixels": int(np.count_nonzero(grid)),
        "ink_pixels_after": int(np.count_nonzero(clean)),
        "reduction_ratio": round(
            1.0 - np.count_nonzero(clean) / max(np.count_nonzero(ink), 1),
            4,
        ),
        "detection": detection,
    }
    return clean, meta


def build_grid_mask_debug(
    shape: tuple[int, int],
    layout: dict[str, Any],
    *,
    line_width: int = 2,
    dot_radius: int = 2,
) -> np.ndarray:
    """调试输出：周期性网格掩膜。"""
    return _build_periodic_grid_mask(
        shape,
        layout,
        line_width=line_width,
        dot_radius=dot_radius,
    )


def suppress_grid_from_bgr(
    bgr: np.ndarray,
    config: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    cfg = config or {}
    th = cfg.get("grid_ink_threshold")
    ink_threshold = None if th is None or int(th) <= 0 else int(th)
    period_h = cfg.get("grid_period_h")
    period_w = cfg.get("grid_period_w")
    return suppress_grid_binary(
        bgr,
        ink_threshold=ink_threshold,
        morph_h=int(cfg.get("grid_morph_h", 64)),
        morph_v=int(cfg.get("grid_morph_v", 64)),
        min_wall_thickness=int(cfg.get("grid_min_wall_thickness", 4)),
        max_stroke_radius=float(cfg.get("grid_max_stroke_radius", 1.6)),
        grid_period_h=int(period_h) if period_h else None,
        grid_period_w=int(period_w) if period_w else None,
        grid_line_width=int(cfg.get("grid_line_width", 2)),
        grid_dot_radius=int(cfg.get("grid_dot_radius", 2)),
        grid_dark_percentile=float(cfg.get("grid_dark_percentile", 18.0)),
        grid_min_blob_area=int(cfg.get("grid_min_blob_area", 12)),
    )
