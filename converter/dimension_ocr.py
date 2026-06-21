from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass
class DimensionLabel:
    value_mm: float
    center_x: float
    center_y: float
    bbox: tuple[float, float, float, float]
    text_raw: str
    confidence: float = 1.0
    source: str = "ocr"

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_mm": self.value_mm,
            "center_x": round(self.center_x, 1),
            "center_y": round(self.center_y, 1),
            "text_raw": self.text_raw,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }


def _parse_dimension_text(text: str) -> float | None:
    digits = re.sub(r"[^\d]", "", text or "")
    if not digits or len(digits) < 3:
        return None
    value = float(digits)
    if value < 100 or value > 100_000:
        return None
    return value


def _isolate_text_mask(binary: np.ndarray) -> np.ndarray:
    """从二值图里去掉长线，保留数字/标注笔画。"""
    h, w = binary.shape[:2]
    kh = max(25, w // 12)
    kv = max(25, h // 12)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv))
    lines = cv2.bitwise_or(
        cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel),
        cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel),
    )
    text = cv2.subtract(binary, lines)
    text = cv2.morphologyEx(text, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    return text


def _ocr_rapidocr(roi_bgr: np.ndarray) -> tuple[str, float]:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return "", 0.0

    if not hasattr(_ocr_rapidocr, "_engine"):
        _ocr_rapidocr._engine = RapidOCR()  # type: ignore[attr-defined]

    result, _ = _ocr_rapidocr._engine(roi_bgr)  # type: ignore[attr-defined]
    if not result:
        return "", 0.0
    texts = [str(item[1]) for item in result if len(item) > 2]
    confs = [float(item[2]) for item in result if len(item) > 2]
    if not texts:
        return "", 0.0
    return "".join(texts), float(sum(confs) / len(confs))


def _digit_templates() -> dict[str, np.ndarray]:
    if hasattr(_digit_templates, "cache"):
        return _digit_templates.cache  # type: ignore[attr-defined]
    templates: dict[str, np.ndarray] = {}
    for digit in "0123456789":
        canvas = np.zeros((48, 32), dtype=np.uint8)
        cv2.putText(canvas, digit, (4, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 255, 2, cv2.LINE_AA)
        templates[digit] = canvas
    _digit_templates.cache = templates  # type: ignore[attr-defined]
    return templates


def _normalize_digit_patch(patch: np.ndarray) -> np.ndarray:
    if patch.size == 0:
        return np.zeros((48, 32), dtype=np.uint8)
    h, w = patch.shape[:2]
    scale = min(40.0 / max(h, w, 1), 32.0 / max(w, 1), 48.0 / max(h, 1))
    nh = max(8, min(48, int(round(h * scale))))
    nw = max(8, min(32, int(round(w * scale))))
    resized = cv2.resize(patch, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((48, 32), dtype=np.uint8)
    y0 = (48 - nh) // 2
    x0 = (32 - nw) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
    return canvas


def _split_digit_patches(roi_bgr: np.ndarray) -> list[np.ndarray]:
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int]] = []
    for cnt in contours:
        x, y, bw_w, bh = cv2.boundingRect(cnt)
        if bw_w * bh < 20 or bh < 6:
            continue
        boxes.append((x, y, bw_w, bh))
    boxes.sort(key=lambda b: b[0])
    patches: list[np.ndarray] = []
    for x, y, bw_w, bh in boxes:
        pad = 2
        patch = bw[max(0, y - pad) : y + bh + pad, max(0, x - pad) : x + bw_w + pad]
        patches.append(patch)
    return patches


def _read_digits_template(roi_bgr: np.ndarray) -> tuple[str, float]:
    h, w = roi_bgr.shape[:2]
    if max(h, w) < 100:
        roi_bgr = cv2.resize(roi_bgr, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    patches = _split_digit_patches(roi_bgr)
    if not patches:
        return "", 0.0
    templates = _digit_templates()
    chars: list[str] = []
    scores: list[float] = []
    for patch in patches:
        norm = _normalize_digit_patch(patch)
        best_digit, best_score = "", -1.0
        for digit, tmpl in templates.items():
            res = cv2.matchTemplate(norm, tmpl, cv2.TM_CCOEFF_NORMED)
            score = float(res.max()) if res.size else 0.0
            if score > best_score:
                best_score = score
                best_digit = digit
        if best_score >= 0.22:
            chars.append(best_digit)
            scores.append(best_score)
    if not chars:
        return "", 0.0
    return "".join(chars), float(sum(scores) / len(scores))


def _ocr_pytesseract(roi_gray: np.ndarray) -> tuple[str, float]:
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError:
        return "", 0.0
    config = r"--psm 7 -c tessedit_char_whitelist=0123456789"
    try:
        text = pytesseract.image_to_string(roi_gray, config=config).strip()
    except Exception:
        return "", 0.0
    return text, 0.6 if text else 0.0


def _read_roi_text(roi_bgr: np.ndarray) -> tuple[str, float, str]:
    if roi_bgr.size == 0:
        return "", 0.0, "none"
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    variants = [
        roi_bgr,
        cv2.cvtColor(255 - gray, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(cv2.bitwise_not(gray), cv2.COLOR_GRAY2BGR),
    ]
    best_text, best_conf, best_src = "", 0.0, "none"
    for variant in variants:
        try:
            text, conf = _ocr_rapidocr(variant)
        except Exception:
            text, conf = "", 0.0
        if conf > best_conf:
            best_text, best_conf, best_src = text, conf, "rapidocr"
    if best_conf < 0.45:
        text, conf = _read_digits_template(roi_bgr)
        if conf > best_conf:
            best_text, best_conf, best_src = text, conf, "digit_template"
    if best_conf < 0.35:
        for variant in variants[:2]:
            gray_v = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY)
            text, conf = _ocr_pytesseract(gray_v)
            if conf > best_conf:
                best_text, best_conf, best_src = text, conf, "tesseract"
    return best_text, best_conf, best_src


def _find_text_rois(text_mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    contours, _ = cv2.findContours(text_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rois: list[tuple[int, int, int, int]] = []
    h, w = text_mask.shape[:2]
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh
        if area < 80 or area > h * w * 0.08:
            continue
        if bw < 8 or bh < 8:
            continue
        aspect = bw / max(bh, 1)
        if aspect > 12 or aspect < 0.15:
            continue
        pad = max(4, int(min(bw, bh) * 0.25))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + bw + pad)
        y1 = min(h, y + bh + pad)
        rois.append((x0, y0, x1, y1))
    return rois


def _merge_digit_groups(
    rois: list[tuple[int, int, int, int]],
    *,
    digit_gap: int = 18,
    y_tol: int = 18,
) -> list[tuple[int, int, int, int]]:
    """把同一行、间距很近的数字框合并（单个 3000），不合并相邻的不同标注。"""
    if not rois:
        return []
    rois = sorted(rois, key=lambda r: ((r[1] + r[3]) / 2, r[0]))
    groups: list[list[tuple[int, int, int, int]]] = []
    for roi in rois:
        cy = (roi[1] + roi[3]) / 2
        placed = False
        for group in groups:
            gcy = (group[0][1] + group[0][3]) / 2
            gx1 = max(r[2] for r in group)
            gap = roi[0] - gx1
            if abs(cy - gcy) <= y_tol and gap <= digit_gap:
                group.append(roi)
                placed = True
                break
        if not placed:
            groups.append([roi])

    merged: list[tuple[int, int, int, int]] = []
    for group in groups:
        x0 = min(r[0] for r in group)
        y0 = min(r[1] for r in group)
        x1 = max(r[2] for r in group)
        y1 = max(r[3] for r in group)
        merged.append((x0, y0, x1, y1))
    return merged


def _merge_nearby_rois(
    rois: list[tuple[int, int, int, int]],
    *,
    gap: int = 12,
) -> list[tuple[int, int, int, int]]:
    return _merge_digit_groups(rois, digit_gap=gap)


def extract_dimensions(
    bgr: np.ndarray,
    binary: np.ndarray,
    *,
    manual_labels: list[dict[str, Any]] | None = None,
    min_confidence: float = 0.3,
) -> tuple[list[DimensionLabel], dict[str, Any]]:
    """
    从手绘图中 OCR 尺寸标注（如 3000、4500）。
    manual_labels: [{"value_mm": 3000, "center_x": 120, "center_y": 80}, ...]
    """
    meta: dict[str, Any] = {"ocr_engine": None, "roi_count": 0, "warnings": []}
    labels: list[DimensionLabel] = []

    if manual_labels:
        for item in manual_labels:
            value = float(item.get("value_mm") or item.get("value") or 0)
            if value < 100:
                continue
            labels.append(
                DimensionLabel(
                    value_mm=value,
                    center_x=float(item.get("center_x", 0)),
                    center_y=float(item.get("center_y", 0)),
                    bbox=(
                        float(item.get("x0", item.get("center_x", 0) - 20)),
                        float(item.get("y0", item.get("center_y", 0) - 10)),
                        float(item.get("x1", item.get("center_x", 0) + 20)),
                        float(item.get("y1", item.get("center_y", 0) + 10)),
                    ),
                    text_raw=str(item.get("text") or int(value)),
                    confidence=1.0,
                    source="manual",
                )
            )
        meta["ocr_engine"] = "manual"
        return labels, meta

    text_mask = _isolate_text_mask(binary)
    rois = _merge_nearby_rois(_find_text_rois(text_mask))
    meta["roi_count"] = len(rois)

    # 全图 OCR 兜底（标注较少时）
    if len(rois) <= 2:
        full_text, full_conf, src = _read_roi_text(bgr)
        meta["ocr_engine"] = src
        value = _parse_dimension_text(full_text)
        if value and full_conf >= min_confidence:
            h, w = bgr.shape[:2]
            labels.append(
                DimensionLabel(
                    value_mm=value,
                    center_x=w / 2,
                    center_y=h / 2,
                    bbox=(0, 0, float(w), float(h)),
                    text_raw=full_text,
                    confidence=full_conf,
                    source=src,
                )
            )

    used_engine: str | None = None
    for x0, y0, x1, y1 in rois:
        roi = bgr[y0:y1, x0:x1]
        text, conf, src = _read_roi_text(roi)
        used_engine = src
        value = _parse_dimension_text(text)
        if value is None or conf < min_confidence:
            continue
        labels.append(
            DimensionLabel(
                value_mm=value,
                center_x=(x0 + x1) / 2.0,
                center_y=(y0 + y1) / 2.0,
                bbox=(float(x0), float(y0), float(x1), float(y1)),
                text_raw=text,
                confidence=conf,
                source=src,
            )
        )

    meta["ocr_engine"] = used_engine
    labels = _dedupe_labels(labels)
    if not labels:
        meta["warnings"].append(
            "未 OCR 到有效尺寸标注，可传 manual_dimensions 或安装 rapidocr-onnxruntime"
        )
    return labels, meta


def _dedupe_labels(labels: list[DimensionLabel], *, dist_px: float = 24.0) -> list[DimensionLabel]:
    kept: list[DimensionLabel] = []
    for label in sorted(labels, key=lambda item: -item.confidence):
        duplicate = False
        for existing in kept:
            if (
                abs(label.center_x - existing.center_x) <= dist_px
                and abs(label.center_y - existing.center_y) <= dist_px
                and label.value_mm == existing.value_mm
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(label)
    return kept
