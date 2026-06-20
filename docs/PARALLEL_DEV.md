# 双 Agent 并行开发指南

仓库：https://github.com/JamesJen627/sketch-to-cad-mcp

## 是否需要 PilotDeck？

| 环节 | 需要 PilotDeck？ |
|------|------------------|
| 算法 / MCP 代码开发 | **否** |
| `test_convert.py` / `benchmark.py` | **否** |
| 飞书发图 → Agent 调 MCP 验收 | **是** |

## 快速开始

### 1. 首次推送 MVP（只做一次）

```cmd
cd sketch-to-cad-mcp
git init
git remote add origin https://github.com/JamesJen627/sketch-to-cad-mcp.git
git add .
git commit -m "feat: initial MVP - sketch to DXF MCP server"
git branch -M main
git push -u origin main
```

### 2. 在 GitHub 创建 Issues

- 使用模板：**算法管线 - 线段后处理** → Agent A
- 使用模板：**产品质量 - 质量评分与 MCP 集成** → Agent B

或手动 New Issue，标题带 `[Agent A]` / `[Agent B]`。

### 3. 开两个 Cursor 会话

| 会话 | 复制文件 | 分支 |
|------|----------|------|
| Cursor #1 | `docs/AGENT_A_PROMPT.md` 内代码块 | `feat/postprocess` |
| Cursor #2 | `docs/AGENT_B_PROMPT.md` 内代码块 | `feat/quality-report` |

### 4. 合并顺序

```
main ← feat/postprocess (Agent A 先合)
main ← feat/quality-report (Agent B rebase 后合)
```

### 5. PilotDeck 集成验收（合并后）

见 `docs/pilotdeck-integration.md`（Agent B 编写）。

## 冲突预防

```
Agent A 领地          Agent B 领地
─────────────────     ─────────────────
postprocess.py        quality.py
preprocess.py         pipeline.py
vectorize.py          mcp_server.py
wall_chain.py         benchmark.py
                      dxf_writer.py
                      docs/
```

共享文件 `config/homestay_layers.json`：Agent B 维护结构，Agent A 通过 PR 描述新增字段。

## 本地测试命令

```cmd
D:\python3.12\python.exe -m pip install -r requirements.txt
D:\python3.12\python.exe scripts\test_convert.py
D:\python3.12\python.exe scripts\benchmark.py
```
