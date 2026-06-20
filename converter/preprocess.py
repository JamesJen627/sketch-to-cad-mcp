from __future__ import annotations

import cv2
import numpy as np


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


def deskew(gray: np.ndarray) -> np.ndarray:
    """简单纠偏：根据轮廓最小外接矩形旋转。"""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return gray
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def binarize(gray: np.ndarray, adaptive: bool = False) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    if adaptive:
        return cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10
        )
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def _normalize_long_edge(gray: np.ndarray, target: int = 2400) -> np.ndarray:
    h, w = gray.shape[:2]
    long_edge = max(h, w)
    if long_edge <= target or long_edge < 800:
        return gray
    scale = target / long_edge
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess(
    image_path: str,
    *,
    deskew_enabled: bool = True,
    adaptive_threshold: bool = False,
    normalize_long_edge: int = 2400,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (原图BGR, 灰度图, 二值图)。"""
    bgr = load_image(image_path)
    gray = to_grayscale(bgr)
    if deskew_enabled:
        gray = deskew(gray)
    gray = _normalize_long_edge(gray, target=normalize_long_edge)
    binary = binarize(gray, adaptive=adaptive_threshold)
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    close_kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    return bgr, gray, binary
