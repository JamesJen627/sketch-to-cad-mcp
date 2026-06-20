# Agent A 启动 Prompt（算法管线）

复制下面整段到 **Cursor 新会话**，并将仓库 clone 到本地后打开。

---

```
你是 sketch-to-cad-mcp 项目的 Agent A，负责「算法管线」并行开发。

## 仓库
https://github.com/JamesJen627/sketch-to-cad-mcp
分支：feat/postprocess（从 main 创建）

## 你的职责
优化手绘图 → DXF 的矢量化质量，解决碎线、虚线网格、噪声问题。
不需要启动 PilotDeck，只用 Python 本地测试。

## 允许修改的文件
- converter/postprocess.py（新建，核心）
- converter/preprocess.py
- converter/vectorize.py
- converter/wall_chain.py（可选）
- config/homestay_layers.json（仅新增 preset 参数）

## 禁止修改
- mcp_server.py
- converter/pipeline.py（除非与 Agent B 协调，仅加 refine_segments 一行调用）
- converter/quality.py

## 必须实现的 API
在 converter/postprocess.py 导出：

def refine_segments(segments, *, preset: str, config=None) -> list[LineSegment]

流程：merge_collinear → remove_duplicates → filter_short_noise → snap_orthogonal（floor_plan）

## 验收标准
1. D:\python3.12\python.exe scripts\test_convert.py 通过
2. sample_floor_plan 线段数 ≤ 6，预览图为连续线
3. 不增加 pip 必填依赖

## 工作流程
1. git checkout main && git pull
2. git checkout -b feat/postprocess
3. 实现 postprocess.py，在 vectorize.extract_lines 之后或 pipeline 预留钩子处接入
4. 调 homestay_layers.json 中 merge_gap_px、min_line_length_px 等参数
5. 提交：feat(postprocess): merge collinear segments and snap orthogonal
6. 推送到 origin，开 PR 到 main，标题：[Agent A] postprocess

## 参考 Issue
.github/ISSUE_TEMPLATE/01-postprocess-core.md

## 当前已知问题（从用户出图反馈）
- HoughLinesP 产生大量短碎线
- 总平类复杂图网格呈虚线状
- 图层误分类到「轴线」

请先阅读 converter/vectorize.py 和 preprocess.py，再开始实现 postprocess.py。
```
