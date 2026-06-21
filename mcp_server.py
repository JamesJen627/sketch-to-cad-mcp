#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sketch-to-cad-mcp — 手绘图转 CAD 的 MCP Server（stdio / JSON-RPC）

工具:
  sketch_analyze       — 分析手绘图质量，给出转换建议
  sketch_to_dxf        — 手绘/扫描图 → DXF + 预览 PNG
  sketch_to_cad        — 完整流程：DXF + 可选 DWG + 可选 CAD 规范检查

环境变量:
  SKETCH_CAD_OUTPUT_DIR  — 默认输出目录（默认 ./02-CAD原始平面图）
  ODA_FILE_CONVERTER       — ODA File Converter 可执行文件路径（DWG 导出）
  CAD_CHECK_SCRIPT         — cad_standard_check.py 路径（可选）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from converter.pipeline import SketchConvertOptions, analyze_sketch, convert_sketch_to_dxf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _text_result(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "isError": is_error,
    }


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _tool_sketch_analyze(args: dict[str, Any]) -> dict[str, Any]:
    input_path = args.get("input_path")
    if not input_path:
        return _text_result({"error": "缺少 input_path"}, is_error=True)
    preset = args.get("preset", "floor_plan")
    result = analyze_sketch(input_path, preset=preset)
    return _text_result(result)


def _tool_sketch_to_dxf(args: dict[str, Any]) -> dict[str, Any]:
    input_path = args.get("input_path")
    if not input_path:
        return _text_result({"error": "缺少 input_path"}, is_error=True)
    options = SketchConvertOptions(
        input_path=input_path,
        output_dir=args.get("output_dir"),
        output_name=args.get("output_name"),
        preset=args.get("preset", "floor_plan"),
        scale_mm_per_pixel=args.get("scale_mm_per_pixel"),
        project_name=args.get("project_name", "新塘村民宿改造"),
        deskew=bool(args.get("deskew", True)),
        export_dwg=False,
        run_cad_check=False,
    )
    result = convert_sketch_to_dxf(options)
    return _text_result(result.to_dict(), is_error=not result.success)


def _tool_sketch_to_cad(args: dict[str, Any]) -> dict[str, Any]:
    input_path = args.get("input_path")
    if not input_path:
        return _text_result({"error": "缺少 input_path"}, is_error=True)
    import os

    options = SketchConvertOptions(
        input_path=input_path,
        output_dir=args.get("output_dir"),
        output_name=args.get("output_name"),
        preset=args.get("preset", "floor_plan"),
        scale_mm_per_pixel=args.get("scale_mm_per_pixel"),
        project_name=args.get("project_name", "新塘村民宿改造"),
        deskew=bool(args.get("deskew", True)),
        export_dwg=bool(args.get("export_dwg", False)),
        run_cad_check=bool(args.get("run_cad_check", True)),
        cad_check_script=args.get("cad_check_script") or os.environ.get("CAD_CHECK_SCRIPT"),
    )
    result = convert_sketch_to_dxf(options)
    return _text_result(result.to_dict(), is_error=not result.success)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "sketch_analyze",
        "description": (
            "分析手绘/扫描图是否适合转换为 CAD。返回分辨率、线条占比和建议 preset。"
            "适用于民宿平面草图、总平手绘图的质量预检。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入图片路径（PNG/JPG）"},
                "preset": {
                    "type": "string",
                  "enum": ["floor_plan", "site_plan", "sketch_rough", "survey_grid_paper"],
                  "default": "floor_plan",
                  "description": "floor_plan=室内平面, site_plan=总平, sketch_rough=潦草/手机拍照, survey_grid_paper=橙蓝方格纸实拍",
                },
            },
            "required": ["input_path"],
        },
        "handler": _tool_sketch_analyze,
    },
    {
        "name": "sketch_to_dxf",
        "description": (
            "将手绘图或扫描图转换为 DXF 矢量线稿，并生成预览 PNG。"
            "自动按民宿项目图层（墙体-240/120、轴线等）分类线段。"
            "返回 quality 质量报告（score/grade/issues/suggest_rerun_with）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入图片路径"},
                "output_dir": {
                    "type": "string",
                    "description": "输出目录，默认 02-CAD原始平面图 或 SKETCH_CAD_OUTPUT_DIR",
                },
                "output_name": {"type": "string", "description": "输出文件名（不含扩展名）"},
                "preset": {
                    "type": "string",
                    "enum": ["floor_plan", "site_plan", "sketch_rough", "survey_grid_paper"],
                    "default": "floor_plan",
                },
                "scale_mm_per_pixel": {
                    "type": "number",
                    "description": "像素到毫米的换算比例，覆盖 preset 默认值",
                },
                "project_name": {
                    "type": "string",
                    "default": "新塘村民宿改造",
                    "description": "写入 DXF 标题栏的项目名称",
                },
                "deskew": {"type": "boolean", "default": True, "description": "是否自动纠偏"},
            },
            "required": ["input_path"],
        },
        "handler": _tool_sketch_to_dxf,
    },
    {
        "name": "sketch_to_cad",
        "description": (
            "完整手绘转 CAD 流程：DXF + 预览 PNG，可选导出 DWG，"
            "并自动调用 CAD 规范检查（cad-standard-check skill）。"
            "返回 quality 质量报告（score/grade/issues/suggest_rerun_with）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "输入图片路径"},
                "output_dir": {"type": "string"},
                "output_name": {"type": "string"},
                "preset": {
                    "type": "string",
                    "enum": ["floor_plan", "site_plan", "sketch_rough", "survey_grid_paper"],
                    "default": "floor_plan",
                },
                "scale_mm_per_pixel": {"type": "number"},
                "project_name": {"type": "string", "default": "新塘村民宿改造"},
                "deskew": {"type": "boolean", "default": True},
                "export_dwg": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否导出 DWG（需安装 ODA File Converter）",
                },
                "run_cad_check": {
                    "type": "boolean",
                    "default": True,
                    "description": "转换后是否运行 CAD 规范检查",
                },
                "cad_check_script": {"type": "string", "description": "cad_standard_check.py 路径"},
            },
            "required": ["input_path"],
        },
        "handler": _tool_sketch_to_cad,
    },
]

TOOL_MAP = {t["name"]: t["handler"] for t in TOOLS}


def send_log(msg: str) -> None:
    print(f"[sketch-to-cad-mcp] {msg}", file=sys.stderr, flush=True)


def send_msg(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def handle_request(msg: dict[str, Any]) -> None:
    req_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        send_msg(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sketch-to-cad-mcp", "version": "0.1.0"},
                },
            }
        )
        return

    if method == "notifications/initialized":
        send_log("客户端已初始化")
        return

    if method == "tools/list":
        send_msg(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
                        for t in TOOLS
                    ]
                },
            }
        )
        return

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = TOOL_MAP.get(name)
        if not handler:
            send_msg(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"未知工具: {name}"},
                }
            )
            return
        try:
            send_log(f"调用工具: {name}")
            result = handler(args)
            send_msg({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as e:
            send_msg(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": str(e)},
                }
            )
        return

    if method == "resources/list":
        send_msg({"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}})
        return

    if req_id is not None:
        send_msg(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"未知方法: {method}"},
            }
        )


def main() -> None:
    send_log("启动中...")
    send_log("已就绪，等待 MCP 客户端连接...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle_request(json.loads(line))
        except json.JSONDecodeError as e:
            send_log(f"解析错误: {e}")


if __name__ == "__main__":
    main()
