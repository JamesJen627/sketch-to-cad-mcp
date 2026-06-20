---
name: 产品质量 - 质量评分与 MCP 集成
about: Agent B 负责：质量报告、benchmark、MCP 扩展、文档与 PilotDeck 集成说明
title: "[Agent B] feat: 质量评分、benchmark 与 MCP 扩展 (quality)"
labels: agent-b, mcp, tooling, priority-p0
assignees: ''
---

## 背景

MVP 已能出 DXF，但缺少质量反馈、基准对比和 PilotDeck 集成文档。需要在**不改动核心 Hough 算法**的前提下，完善产品层。

## 负责范围（仅改这些文件）

- [ ] `converter/quality.py`（**新建**）
- [ ] `converter/pipeline.py`
- [ ] `mcp_server.py`
- [ ] `converter/dxf_writer.py`（中文乱码修复、POLYLINE 输出协调）
- [ ] `scripts/benchmark.py`（**新建**）
- [ ] `docs/pilotdeck-integration.md`（**新建**）
- [ ] `README.md`
- [ ] `config/homestay_layers.json`（结构维护）

## 禁止修改

- `converter/vectorize.py` 内 Hough 参数逻辑（Agent A 负责）
- `converter/postprocess.py`（Agent A 负责，B 只调用）

## 任务清单

### P0
- [ ] 新建 `converter/quality.py`：
  - `fragmentation_score`、`short_line_ratio`、`orthogonal_ratio`
  - `grade_score()` 返回 A/B/C + `issues[]` + `suggest_rerun_with`
- [ ] `pipeline.py` 集成质量报告到 `SketchConvertResult`
- [ ] `mcp_server.py`：`sketch_to_dxf` / `sketch_to_cad` 返回 `quality` 字段
- [ ] 修复 DXF 中文乱码（simhei 字体或暂改英文标题 + `include_title` 开关）

### P1
- [ ] `scripts/benchmark.py`：批量跑 `test_samples/`，输出 JSON 报告
- [ ] 三栏对比预览：原图 | 二值化 | 矢量叠加
- [ ] `docs/pilotdeck-integration.md`：绝对路径 Python、`pilotdeck.yaml` 示例

### P2（时间允许）
- [ ] MCP 工具 `sketch_quality_report`（仅分析不转换）
- [ ] GitHub Actions：`pip install` + `test_convert.py`

## 接口依赖（等 Agent A 或 stub）

```python
# pipeline.py 中在 assign_layers 之后调用：
from .postprocess import refine_segments  # Agent A 提供
segments = refine_segments(segments, preset=options.preset)
```

若 Agent A 未合并，可先用 **no-op stub**：

```python
def refine_segments(segments, *, preset, config=None):
    return segments
```

## 验收标准

- [ ] `sketch_to_cad` 返回 JSON 含 `quality.score`、`quality.issues`
- [ ] `benchmark.py` 对 `test_samples/` 生成 `benchmark_report.json`
- [ ] DXF 在 AutoCAD 打开无 `????` 乱码（或标题可关闭）
- [ ] README 含 PilotDeck 配置片段（`D:\python3.12\python.exe` 绝对路径）

## 分支

```bash
git checkout -b feat/quality-report
```

## 合并顺序

**建议在 Agent A 的 `feat/postprocess` 合并后再合本分支**，或 rebase onto main。

## 合并前自检

```cmd
D:\python3.12\python.exe scripts\test_convert.py
D:\python3.12\python.exe scripts\benchmark.py
```
