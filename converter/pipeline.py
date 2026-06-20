from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_loader import get_preset
from .dxf_writer import assign_layers, write_dxf
from .postprocess import refine_segments
from .preprocess import preprocess
from .vectorize import extract_lines, render_preview


@dataclass
class SketchConvertOptions:
    input_path: str
    output_dir: str | None = None
    output_name: str | None = None
    preset: str = "floor_plan"
    scale_mm_per_pixel: float | None = None
    project_name: str = "新塘村民宿改造"
    deskew: bool = True
    export_dwg: bool = False
    run_cad_check: bool = False
    cad_check_script: str | None = None


@dataclass
class SketchConvertResult:
    success: bool
    input_path: str
    dxf_path: str | None = None
    dwg_path: str | None = None
    preview_path: str | None = None
    line_count: int = 0
    layers_used: dict[str, int] = field(default_factory=dict)
    preset: str = "floor_plan"
    scale_mm_per_pixel: float = 5.0
    cad_check: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "input_path": self.input_path,
            "dxf_path": self.dxf_path,
            "dwg_path": self.dwg_path,
            "preview_path": self.preview_path,
            "line_count": self.line_count,
            "layers_used": self.layers_used,
            "preset": self.preset,
            "scale_mm_per_pixel": self.scale_mm_per_pixel,
            "cad_check": self.cad_check,
            "warnings": self.warnings,
            "error": self.error,
        }


def _default_output_dir() -> Path:
    env_dir = os.environ.get("SKETCH_CAD_OUTPUT_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd() / "02-CAD原始平面图"


def _resolve_output_paths(options: SketchConvertOptions) -> tuple[Path, str]:
    out_dir = Path(options.output_dir) if options.output_dir else _default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = options.output_name
    if not stem:
        stem = Path(options.input_path).stem + "_sketch"
    return out_dir, stem


def analyze_sketch(input_path: str, preset: str = "floor_plan") -> dict[str, Any]:
    """分析图像质量，不生成 DXF。"""
    preset_cfg = get_preset(preset)
    _, gray, binary = preprocess(
        input_path,
        deskew_enabled=True,
        adaptive_threshold=bool(preset_cfg.get("adaptive_threshold", False)),
    )
    h, w = gray.shape[:2]
    ink_ratio = float(binary.sum() / 255) / max(h * w, 1)
    recommendations: list[str] = []
    if ink_ratio < 0.005:
        recommendations.append("线条过少，建议使用 preset=sketch_rough 或检查图片对比度")
    if ink_ratio > 0.35:
        recommendations.append("背景噪声较多，建议拍照时提高对比度或使用扫描件")
    if max(h, w) < 800:
        recommendations.append("分辨率偏低，建议宽度至少 1200px 以获得更好矢量化效果")
    return {
        "input_path": input_path,
        "width": w,
        "height": h,
        "ink_ratio": round(ink_ratio, 4),
        "preset": preset,
        "recommendations": recommendations,
    }


def convert_sketch_to_dxf(options: SketchConvertOptions) -> SketchConvertResult:
    input_path = Path(options.input_path)
    if not input_path.is_file():
        return SketchConvertResult(
            success=False,
            input_path=str(input_path),
            error=f"输入文件不存在: {input_path}",
        )

    try:
        preset_cfg = get_preset(options.preset)
    except ValueError as e:
        return SketchConvertResult(success=False, input_path=str(input_path), error=str(e))

    scale = options.scale_mm_per_pixel or float(preset_cfg.get("scale_mm_per_pixel", 5.0))
    out_dir, stem = _resolve_output_paths(options)
    dxf_path = out_dir / f"{stem}.dxf"
    preview_path = out_dir / f"{stem}_preview.png"

    try:
        _, _, binary = preprocess(
            str(input_path),
            deskew_enabled=options.deskew,
            adaptive_threshold=bool(preset_cfg.get("adaptive_threshold", False)),
        )
        segments = extract_lines(
            binary,
            canny_low=int(preset_cfg.get("canny_low", 40)),
            canny_high=int(preset_cfg.get("canny_high", 120)),
            min_line_length_px=int(preset_cfg.get("min_line_length_px", 25)),
        )
        segments = refine_segments(segments, preset=options.preset, config=preset_cfg)
        assign_layers(segments, float(preset_cfg.get("thick_line_threshold_px", 4)))

        warnings: list[str] = []
        if not segments:
            warnings.append("未检测到有效线段，请尝试 preset=sketch_rough 或提高图片质量")

        render_preview(binary, segments, str(preview_path))
        meta = write_dxf(
            segments,
            str(dxf_path),
            scale_mm_per_pixel=scale,
            project_name=options.project_name,
        )

        dwg_path: str | None = None
        if options.export_dwg:
            from .dwg_export import convert_dxf_to_dwg

            dwg_candidate = out_dir / f"{stem}.dwg"
            dwg_path = convert_dxf_to_dwg(str(dxf_path), str(dwg_candidate))
            if not dwg_path:
                warnings.append(
                    "DWG 导出跳过：未检测到 ODA File Converter，请设置 ODA_FILE_CONVERTER 环境变量"
                )

        cad_check_result = None
        if options.run_cad_check and dxf_path.is_file():
            cad_check_result = _run_cad_check(str(dxf_path), options.cad_check_script)

        return SketchConvertResult(
            success=True,
            input_path=str(input_path),
            dxf_path=str(dxf_path),
            dwg_path=dwg_path,
            preview_path=str(preview_path),
            line_count=meta["line_count"],
            layers_used=meta["layers_used"],
            preset=options.preset,
            scale_mm_per_pixel=scale,
            cad_check=cad_check_result,
            warnings=warnings,
        )
    except Exception as e:
        return SketchConvertResult(
            success=False,
            input_path=str(input_path),
            error=str(e),
        )


def _run_cad_check(dxf_path: str, script_path: str | None) -> dict[str, Any] | None:
    if script_path:
        checker = Path(script_path)
    else:
        checker = Path.cwd() / ".pilotdeck" / "skills" / "cad-standard-check" / "cad_standard_check.py"
    if not checker.is_file():
        return {"skipped": True, "reason": f"未找到 CAD 规范检查脚本: {checker}"}
    try:
        proc = subprocess.run(
            ["python", str(checker), dxf_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        if proc.stdout.strip():
            import json

            return json.loads(proc.stdout)
        return {"skipped": True, "reason": proc.stderr or "检查脚本无输出"}
    except Exception as e:
        return {"skipped": True, "reason": str(e)}
