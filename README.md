# 手绘转 CAD MCP

基于 **OpenCV + ezdxf** 的开源矢量化方案，为 PilotDeck 民宿改造项目定制。

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
pip install -r requirements.txt
```

## 本地测试

```bash
python scripts/test_convert.py
```

## PilotDeck 配置

在 `pilotdeck.yaml` 的 `mcpServers` 中添加：

```yaml
sketch-to-cad:
  command: python
  args:
    - "sketch-to-cad-mcp/mcp_server.py"
  env:
    SKETCH_CAD_OUTPUT_DIR: "02-CAD原始平面图"
    CAD_CHECK_SCRIPT: ".pilotdeck/skills/cad-standard-check/cad_standard_check.py"
    # ODA_FILE_CONVERTER: "C:/Program Files/ODA/ODAFileConverter.exe"  # 可选 DWG
```

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

## 限制

- 开源矢量化适合**线稿类**输入，复杂渲染图/透视图效果有限
- 尺寸比例为估算值（`scale_mm_per_pixel`），施工前需人工复核
- DWG 导出依赖 [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)（免费）

## 技术栈

- OpenCV：预处理、边缘检测、Hough 线段提取
- ezdxf：DXF 写入
- 参考：2D-Floor-Plan-to-DXF、jpg-dwg、pdf-to-dxf-converter 思路
