from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .grid_suppress import suppress_grid_from_bgr


def load_image(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图像: {path}")
    return image


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _deskew_matrix(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return None, None
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return None, None
    h, w = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return matrix, cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def deskew(gray: np.ndarray) -> np.ndarray:
    """简单纠偏：根据轮廓最小外接矩形旋转。"""
    matrix, rotated = _deskew_matrix(gray)
    return rotated if matrix is not None else gray


def _warp_bgr(bgr: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    return cv2.warpAffine(bgr, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def binarize(gray: np.ndarray, adaptive: bool = False) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    if adaptive:
        return cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10
        )
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def _normalize_long_edge(image: np.ndarray, target: int = 2400) -> np.ndarray:
    h, w = image.shape[:2]
    long_edge = max(h, w)
    if long_edge <= target or long_edge < 800:
        return image
    scale = target / long_edge
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess(
    image_path: str,
    *,
    deskew_enabled: bool = True,
    adaptive_threshold: bool = False,
    normalize_long_edge: int = 2400,
    suppress_grid: bool = False,
    grid_config: dict[str, Any] | None = None,
    debug_dir: str | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (原图BGR, 灰度图, 二值图)。"""
    bgr = load_image(image_path)
    gray = to_grayscale(bgr)

    if deskew_enabled:
        matrix, rotated_gray = _deskew_matrix(gray)
        if matrix is not None and rotated_gray is not None:
            gray = rotated_gray
            bgr = _warp_bgr(bgr, matrix)

    bgr = _normalize_long_edge(bgr, target=normalize_long_edge)
    gray = _normalize_long_edge(gray, target=normalize_long_edge)

    grid_meta: dict[str, Any] | None = None
    if suppress_grid:
        binary, grid_meta = suppress_grid_from_bgr(bgr, grid_config)
        if debug_dir:
            out = Path(debug_dir)
            out.mkdir(parents=True, exist_ok=True)
            stem = Path(image_path).stem
            cv2.imencode(".png", binary)[1].tofile(str(out / f"{stem}_grid_suppressed.png"))
            if grid_meta:
                (out / f"{stem}_grid_meta.txt").write_text(str(grid_meta), encoding="utf-8")
    else:
        binary = binarize(gray, adaptive=adaptive_threshold)
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        close_kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel, iterations=1)

    return bgr, gray, binary
