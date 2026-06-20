# Agent B 启动 Prompt（质量 / MCP / 集成）

复制下面整段到 **Cursor 新会话**（与 Agent A 不同的窗口）。

---

```
你是 sketch-to-cad-mcp 项目的 Agent B，负责「产品质量与 MCP 集成」并行开发。

## 仓库
https://github.com/JamesJen627/sketch-to-cad-mcp
分支：feat/quality-report（从 main 创建）

## 你的职责
质量评分、benchmark 脚本、MCP 返回字段扩展、DXF 中文修复、PilotDeck 集成文档。
不需要启动 PilotDeck 做算法开发；文档中写清 pilotdeck.yaml 配置即可。

## 允许修改的文件
- converter/quality.py（新建）
- converter/pipeline.py
- mcp_server.py
- converter/dxf_writer.py
- scripts/benchmark.py（新建）
- docs/pilotdeck-integration.md（新建）
- README.md
- config/homestay_layers.json

## 禁止修改
- converter/vectorize.py 的 Hough 核心逻辑
- converter/postprocess.py（Agent A 负责；若未合并，在 pipeline 里写 stub）

## 必须实现
1. quality.py：fragmentation_score, short_line_ratio, orthogonal_ratio, grade_score()
2. SketchConvertResult 增加 quality 字段
3. mcp_server 工具返回 quality + suggest_rerun_with
4. dxf_writer：修复中文乱码（simhei 或 include_title=false）
5. benchmark.py：批量测试 test_samples/，输出 benchmark_report.json
6. docs/pilotdeck-integration.md

## Agent A 接口（依赖）
from .postprocess import refine_segments
若 main 上尚无 postprocess，先用 stub：
def refine_segments(segments, *, preset, config=None): return segments

## 验收标准
1. scripts/test_convert.py 通过
2. scripts/benchmark.py 生成 JSON 报告
3. sketch_to_cad 返回含 quality.score
4. README 含 PilotDeck 配置（D:\python3.12\python.exe 绝对路径）

## 工作流程
1. git checkout main && git pull
2. git checkout -b feat/quality-report
3. 实现 quality.py + pipeline 集成 + mcp 字段
4. 修复 dxf_writer 中文
5. 提交：feat(quality): add quality report and benchmark script
6. 推送到 origin，开 PR 到 main（建议在 Agent A PR 合并后 rebase）

## 参考 Issue
.github/ISSUE_TEMPLATE/02-quality-mcp.md

请先阅读 mcp_server.py、converter/pipeline.py、dxf_writer.py，再开始。
```
