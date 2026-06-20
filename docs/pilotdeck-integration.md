# PilotDeck 集成指南

本文说明如何在 PilotDeck 项目中启用 `sketch-to-cad-mcp` MCP 服务，并与民宿改造工作流衔接。

## 前置条件

- Python 3.10+（推荐 **3.12**，Windows 绝对路径示例：`D:\python3.12\python.exe`）
- 已安装依赖：`python -m pip install -r requirements.txt`
- 项目根目录包含 `sketch-to-cad-mcp/` 子目录

## pilotdeck.yaml 配置

在项目根目录的 `pilotdeck.yaml` 中添加 MCP 服务器：

```yaml
mcpServers:
  sketch-to-cad:
    command: D:\python3.12\python.exe
    args:
      - "sketch-to-cad-mcp/mcp_server.py"
    env:
      SKETCH_CAD_OUTPUT_DIR: "02-CAD原始平面图"
      CAD_CHECK_SCRIPT: ".pilotdeck/skills/cad-standard-check/cad_standard_check.py"
      # ODA_FILE_CONVERTER: "C:/Program Files/ODA/ODAFileConverter.exe"  # 可选 DWG
```

> **注意**：`command` 必须使用 Python 解释器的**绝对路径**，避免 PilotDeck 启动时找不到 `python`。

### 环境变量说明

| 变量 | 说明 |
|------|------|
| `SKETCH_CAD_OUTPUT_DIR` | DXF/预览 PNG 默认输出目录 |
| `CAD_CHECK_SCRIPT` | CAD 规范检查脚本路径（`cad_standard_check.py`） |
| `ODA_FILE_CONVERTER` | ODA File Converter 可执行文件路径（可选，用于 DWG 导出） |

## MCP 工具一览

| 工具 | 用途 |
|------|------|
| `sketch_analyze` | 预检图片质量，推荐 preset |
| `sketch_to_dxf` | 图片 → DXF + 预览 PNG + **quality 报告** |
| `sketch_to_cad` | 完整流程 + 可选 DWG + CAD 规范检查 + **quality 报告** |

### quality 返回字段

转换完成后，JSON 响应包含 `quality` 对象：

```json
{
  "success": true,
  "dxf_path": "02-CAD原始平面图/一层平面_sketch.dxf",
  "quality": {
    "score": 85.2,
    "grade": "A",
    "metrics": {
      "fragmentation_score": 0.12,
      "short_line_ratio": 0.08,
      "orthogonal_ratio": 0.92,
      "line_count": 47
    },
    "issues": [],
    "suggest_rerun_with": null
  }
}
```

- `score`：0–100 综合质量分
- `grade`：A / B / C 等级
- `issues`：质量问题描述列表
- `suggest_rerun_with`：建议重试的 preset（如 `sketch_rough`）

## 与 PilotDeck Skill 衔接

项目内已有 `.pilotdeck/skills/sketch-to-cad/SKILL.md`，Agent 可通过自然语言调用 MCP 工具。

典型对话：

> 帮我把这张手绘平面图转成 CAD，输出到 02-CAD 文件夹

Agent 应调用 `sketch_to_cad`：

```json
{
  "input_path": "uploads/一层平面手绘.jpg",
  "preset": "floor_plan",
  "export_dwg": false,
  "run_cad_check": true
}
```

转换后若 `quality.grade` 为 C 或 `suggest_rerun_with` 非空，Agent 应告知用户并建议换 preset 重试。

## 本地验证

```cmd
D:\python3.12\python.exe sketch-to-cad-mcp\scripts\test_convert.py
D:\python3.12\python.exe sketch-to-cad-mcp\scripts\benchmark.py
```

`benchmark.py` 会在 `test_samples/benchmark_report.json` 生成批量测试报告，并在 `test_samples/output/` 生成三栏对比预览图。

## 输出文件

| 文件 | 说明 |
|------|------|
| `{name}_sketch.dxf` | CAD 矢量线稿 |
| `{name}_sketch_preview.png` | 矢量叠加预览 |
| `{name}_comparison.png` | 三栏对比（benchmark 专用） |

DXF 标题栏使用 SimHei 字体样式，在 AutoCAD 中应正常显示中文。若目标环境无 SimHei，可在 `write_dxf` 中设置 `include_title=False` 使用英文标题。

## 故障排查

1. **MCP 启动失败**：确认 `command` 为绝对路径，且 `args` 中的 `mcp_server.py` 路径相对于项目根目录正确。
2. **CAD 检查跳过**：确认 `CAD_CHECK_SCRIPT` 指向有效的 `cad_standard_check.py`。
3. **质量分偏低**：查看 `quality.issues`，按 `suggest_rerun_with` 换 preset 重试。
4. **DXF 中文乱码**：确保 AutoCAD 安装了 SimHei（黑体）字体；或关闭中文标题。
