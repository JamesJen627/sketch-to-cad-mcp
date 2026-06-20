from __future__ import annotations

from typing import Any

import ezdxf
from ezdxf.enums import TextEntityAlignment

from .config_loader import load_homestay_config
from .vectorize import LineSegment, classify_layer


def write_dxf(
    segments: list[LineSegment],
    output_path: str,
    *,
    scale_mm_per_pixel: float = 5.0,
    project_name: str = "民宿改造",
) -> dict[str, Any]:
    cfg = load_homestay_config()
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

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

    # 标题栏文字（民宿项目标识）
    msp.add_text(
        f"{project_name} · 手绘转CAD",
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
