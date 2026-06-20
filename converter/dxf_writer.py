from __future__ import annotations

from typing import Any

import ezdxf
from ezdxf.enums import TextEntityAlignment

from .config_loader import load_homestay_config
from .vectorize import LineSegment, classify_layer

CHINESE_STYLE = "SimHei"
FALLBACK_TITLE = "Sketch-to-CAD"


def _ensure_chinese_style(doc: ezdxf.document.Drawing) -> None:
    """注册支持中文的 DXF 文字样式，避免 AutoCAD 显示 ????。"""
    if CHINESE_STYLE in doc.styles:
        return
    doc.styles.add(CHINESE_STYLE, font="simhei.ttf")
    try:
        doc.header["$DWGCODEPAGE"] = "ANSI_936"
    except (AttributeError, KeyError):
        pass


def write_dxf(
    segments: list[LineSegment],
    output_path: str,
    *,
    scale_mm_per_pixel: float = 5.0,
    project_name: str = "民宿改造",
    include_title: bool = True,
) -> dict[str, Any]:
    cfg = load_homestay_config()
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    _ensure_chinese_style(doc)

    for layer_name, meta in cfg.get("layers", {}).items():
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=int(meta.get("color", 7)))

    layer_counts: dict[str, int] = {}

    for seg in segments:
        layer = seg.layer
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        msp.add_line(
            (seg.x1 * scale_mm_per_pixel, seg.y1 * scale_mm_per_pixel),
            (seg.x2 * scale_mm_per_pixel, seg.y2 * scale_mm_per_pixel),
            dxfattribs={"layer": layer},
        )

    if include_title:
        title_text = f"{project_name} · 手绘转CAD"
        msp.add_text(
            title_text,
            dxfattribs={
                "layer": "标注-文字",
                "height": 250.0,
                "style": CHINESE_STYLE,
            },
        ).set_placement((0, -500), align=TextEntityAlignment.LEFT)
    else:
        msp.add_text(
            FALLBACK_TITLE,
            dxfattribs={
                "layer": "标注-文字",
                "height": 250.0,
            },
        ).set_placement((0, -500), align=TextEntityAlignment.LEFT)

    doc.saveas(output_path)
    return {
        "line_count": len(segments),
        "layers_used": layer_counts,
        "scale_mm_per_pixel": scale_mm_per_pixel,
    }


def assign_layers(segments: list[LineSegment], thick_line_threshold_px: float) -> None:
    for seg in segments:
        seg.layer = classify_layer(seg, thick_line_threshold_px)
