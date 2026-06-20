---
name: 算法管线 - 线段后处理
about: Agent A 负责：合并碎线、去噪、正交吸附、预处理增强
title: "[Agent A] feat: 线段后处理与预处理增强 (postprocess)"
labels: agent-a, algorithm, priority-p0
assignees: ''
---

## 背景

当前 Hough 矢量化输出大量碎线段，总平/复杂手绘图效果差。需要在 `converter/` 内增加确定性后处理，**不依赖 PilotDeck**。

## 负责范围（仅改这些文件）

- [ ] `converter/postprocess.py`（**新建**）
- [ ] `converter/preprocess.py`
- [ ] `converter/vectorize.py`
- [ ] `converter/wall_chain.py`（可选，阶段 2）
- [ ] `config/homestay_layers.json`（仅新增 preset 参数字段，PR 说明即可）

## 禁止修改

- `mcp_server.py`
- `converter/pipeline.py`（除非只加一行 `refine_segments()` 调用，需与 Agent B 协调）
- `converter/quality.py`（Agent B 负责）

## 任务清单

### P0
- [ ] 实现 `merge_collinear()` — 合并共线、端点间距 < `merge_gap_px` 的线段
- [ ] 实现 `remove_duplicates()` — 去重重复 Hough 命中
- [ ] 实现 `filter_short_noise()` — 过滤孤立短线
- [ ] 实现 `snap_orthogonal()` — floor_plan 模式下 5~8° 内吸附到 0°/90°
- [ ] 导出统一入口 `refine_segments(segments, *, preset: str) -> list[LineSegment]`

### P1
- [ ] 预处理：长边归一化到 2000~3000px
- [ ] 预处理：形态学闭运算 `MORPH_CLOSE` 减少虚线感
- [ ] 保存中间调试图 `*_binary.png`、`*_edges.png`（可选开关）

### P2（时间允许）
- [ ] `site_plan` preset 增加 `contour_mode` 轮廓提取路径

## 接口契约（Agent B 会调用）

```python
# converter/postprocess.py
def refine_segments(
    segments: list[LineSegment],
    *,
    preset: str,
    config: dict | None = None,
) -> list[LineSegment]:
    ...
```

## 验收标准

- [ ] `python scripts/test_convert.py` 通过
- [ ] `sample_floor_plan` 线段数从 ~12 降到 **≤6** 且预览为连续线
- [ ] 若有 `test_samples/real/` 样本：`short_line_ratio` 较基线下降 **≥50%**
- [ ] 不引入新必填依赖（仅 opencv/numpy）

## 分支

```bash
git checkout -b feat/postprocess
```

## 合并前自检

```cmd
D:\python3.12\python.exe scripts\test_convert.py
```

## 参考

- 现有代码：`converter/vectorize.py`（HoughLinesP）
- 计划文档：见仓库 README「优化路线」章节（如有）
