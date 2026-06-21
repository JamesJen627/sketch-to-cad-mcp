# sketch-to-cad-mcp

适配 PilotDeck 的手绘/扫描图 → CAD（DXF/DWG）MCP 服务。基于 **OpenCV + ezdxf** 开源矢量化，为民宿改造项目定制。

## 功能

| 工具 | 说明 |
|------|------|
| `sketch_analyze` | 预检图片质量，推荐 preset |
| `sketch_to_dxf` | 图片 → DXF + 预览 PNG |
| `sketch_to_cad` | 完整流程 + 可选 DWG + CAD 规范检查 |

## 民宿项目定制

- 输出图层对齐 `cad-standard-check`：`墙体-240`、`墙体-120`、`轴线` 等
- 三种 preset：`floor_plan`（平面）、`site_plan`（总平）、`sketch_rough`（手机拍照）
- 默认输出到 `02-CAD原始平面图/`
- 可衔接 `.pilotdeck/skills/cad-standard-check/` 自动规范检查

## 安装

```bash
cd sketch-to-cad-mcp
python -m pip install -r requirements.txt
```

Windows 若 `pip` 不可用：

```cmd
D:\python3.12\python.exe -m pip install -r requirements.txt
```

## 本地测试

```cmd
D:\python3.12\python.exe scripts\test_convert.py
D:\python3.12\python.exe scripts\benchmark.py
```

转换结果 JSON 含 `quality` 字段（`score`、`grade`、`issues`、`suggest_rerun_with`），详见 [docs/pilotdeck-integration.md](docs/pilotdeck-integration.md)。

## PilotDeck 配置

在 `pilotdeck.yaml` 的 `mcpServers` 中添加：

```yaml
sketch-to-cad:
  command: D:\python3.12\python.exe
  args:
    - "sketch-to-cad-mcp/mcp_server.py"
  env:
    SKETCH_CAD_OUTPUT_DIR: "02-CAD原始平面图"
    CAD_CHECK_SCRIPT: ".pilotdeck/skills/cad-standard-check/cad_standard_check.py"
    # ODA_FILE_CONVERTER: "C:/Program Files/ODA/ODAFileConverter.exe"  # 可选 DWG
```

## 并行开发

见 [docs/PARALLEL_DEV.md](docs/PARALLEL_DEV.md) 与 GitHub Issue 模板。

## 使用示例（Agent 对话）

> 帮我把这张手绘平面图转成 CAD，输出到 02-CAD 文件夹

Agent 调用 `sketch_to_cad`，参数示例：

```json
{
  "input_path": "uploads/一层平面手绘.jpg",
  "preset": "floor_plan",
  "export_dwg": false,
  "run_cad_check": true
}
```

返回示例（含质量报告）：

```json
{
  "success": true,
  "dxf_path": "02-CAD原始平面图/一层平面_sketch.dxf",
  "quality": {
    "score": 85.2,
    "grade": "A",
    "issues": [],
    "suggest_rerun_with": null
  }
}
```

## 尺寸标注 OCR 吸附（默认开启）

转换时会尝试 OCR 读取图上数字（如 3000、4500），并吸附到最近墙线，使 **DXF 中该段长度 = 标注 mm 值**。

```json
{
  "input_path": "D:/.../平面草图.jpg",
  "preset": "floor_plan",
  "snap_dimensions": true
}
```

OCR 对手写识别有限，失败时可传 **manual_dimensions**（像素坐标，与纠偏后图片一致）：

```json
{
  "manual_dimensions": [
    {"value_mm": 3000, "center_x": 280, "center_y": 150},
    {"value_mm": 4500, "center_x": 420, "center_y": 150},
    {"value_mm": 2500, "center_x": 820, "center_y": 150}
  ]
}
```

返回结果含 `dimension_report`：`labels_found`、`matches`（吸附详情）、`scale_mm_per_pixel`（OCR 校准后比例尺）。

依赖：`rapidocr-onnxruntime`（可选）；内置 OpenCV 数字模板匹配作为兜底。

## 限制

- 开源矢量化适合**线稿类**输入，复杂渲染图/透视图效果有限
- 尺寸：默认 OCR 吸附；无标注时仍用 `scale_mm_per_pixel` 估算
- DWG 导出依赖 [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)（免费）

## 技术栈

- OpenCV：预处理、边缘检测、Hough 线段提取
- ezdxf：DXF 写入
- 参考：2D-Floor-Plan-to-DXF、jpg-dwg、pdf-to-dxf-converter 思路
