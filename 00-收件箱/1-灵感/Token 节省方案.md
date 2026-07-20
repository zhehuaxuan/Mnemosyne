---
title: Token 节省方案
description: 在不影响使用效果的前提下，系统性降低 AI 编程 Token 消耗的策略与方案
date: 2026-07-11
tags:
  - AI
  - Token
  - 成本优化
  - 效率
type: 方案策划
related:
  - "[[Token Plan对比]]"
---

## 目录

### 第一章：背景与目标

- 1.1 为什么要省 Token：套餐定价倒逼效率
- 1.2 目标定义：省 Token 但不动效果

### 第二章：Token 消耗全景分析

- 2.1 Token 花在哪：输入/输出/缓存/思考
- 2.2 各环节占比：典型工作流拆解
- 2.3 最大浪费点诊断
- 2.4 总体解决方案：CodeGraph 代码图谱加速

  CodeGraph 是 Claude Code 的标准 MCP 工具，在本地通过构建代码图谱（SQLite 知识库）来加速代码检索与定位，从而**间接显著降低** AI 编程场景下的 Token 消耗。用户无需手动调用工具命令，正常提问即可，Claude Code 会自动判断并触发查询。

  #### 2.4.1 它为什么能省 Token

  | 痛点 | 没有 CodeGraph | 有 CodeGraph |
  |------|--------------|--------------|
  | 找某个函数在哪定义 | `Grep` + `Read` 多个文件 | 一次精准查询，返回行号源码 |
  | 了解某模块工作原理 | 连读 5–10 个文件 | 一次调用拿到结构图 + 调用链 |
  | 改代码前评估影响 | 手动 `grep` 谁调用了 | 自动返回"blast radius" |
  | 上下文里塞整文件 | 几 KB 起送 | 只回必要片段 |

  核心收益：把"读全文 → 自己消化"变成"拿到结构化摘要 + 必要片段"，**上下文窗口占用减少 60% 以上**。

  #### 2.4.2 工作区当前状态（实测）

  以本仓库 `E:\knowledge\Mnemosyne` 为例：

  ```bash
  $ ls .codegraph/
  .codegraph/.gitignore     # 阻止索引数据入库
  .codegraph/codegraph.db   # 11.8 MB，SQLite 主库
  .codegraph/codegraph.db-shm
  .codegraph/codegraph.db-wal
  .codegraph/daemon.log
  .codegraph/daemon.pid
  ```

  `daemon.log` 关键信息：

  ```
  [CodeGraph daemon] Listening on \\.\pipe\codegraph-... (pid 34280, v1.4.1). Idle timeout 300000ms.
  [CodeGraph MCP] File watcher active — graph will auto-sync on changes
  [CodeGraph MCP] Query pool: up to 15 worker thread(s) for concurrent reads.
  ```

  含义：

  - **v1.4.1**：当前 daemon 版本
  - **File watcher active**：自动监听文件改动，增量同步（无需手动重建）
  - **15 worker threads**：可并发处理查询请求
  - **Idle timeout 300000ms**：5 分钟空闲后自动退出 daemon

  `.codegraph/.gitignore` 内容（已正确屏蔽）：

  ```
  # CodeGraph data files — local to each machine, not for committing.
  *
  !.gitignore
  ```

  #### 2.4.3 初始化流程（新项目）

  进入项目根目录：

  ```cmd
  codegraph init -i
  ```

  执行后会在项目下生成 `.codegraph/` 目录（内含结构化代码图谱的本地 SQLite 数据库），自动遵循 `.gitignore` 规则，不会索引 `node_modules`、构建产物等无关文件。后续 CodeGraph 会自动监听代码改动，增量更新索引，无需手动重建。

  #### 2.4.4 正确性判断流程

  | 状态 | 检查方法 | 含义 |
  |------|---------|------|
  | `codegraph` 在 MCP 列表里 | `claude mcp list` | daemon 进程起来了 ✅ |
  | `.codegraph/codegraph.db` 存在 | `ls .codegraph/` | **真正的索引建好了** ✅ |
  | 二者都成立 | — | 才算"能用" |

  注意：**"MCP Connected" ≠ "索引可用"**。务必以 `codegraph.db` 文件存在为准。

  #### 2.4.5 省 Token 实战要点

  1. **提问精准化**：直接点名文件/符号/功能，query 越具体返回越精简。
  2. **优先 MCP 通道**：Claude Code 自动用 `mcp__codegraph__codegraph_explore`，无需手动输入命令。
  3. **需要全文时才 `Read`**：explore 返回的行号源码已经标记为"已 Read"，别重复读取。
  4. **缩小范围**：用 `maxFiles` 参数控制返回文件数（默认 12，查询单一目标可降到 4）。
  5. **避免盲搜**：用 explore 替代 `Grep` + `Read` 循环，单次调用即可获得源码 + 调用链 + 影响范围。

  #### 2.4.6 适用场景与收益边界

  - **大型代码库探索**：首次接触陌生项目时，几次 explore 即可建立全局认知。
  - **Bug 定位**：从报错信息或症状出发，逆推到具体符号与文件。
  - **重构规划**：通过 blast radius 评估改动影响面。
  - **Code Review**：聚焦被改动的符号及其调用方，避免通读 diff。

  **收益边界**：对于 < 10 个文件的小项目，CodeGraph 优势不明显；超过 50 个文件时节省效果显著。 

### 第三章：模型选择策略

- 3.1 按任务分级：什么活用什么模型
- 3.2 旗舰模型降级时机：什么时候能用便宜的
- 3.3 消耗系数陷阱：智谱 ×3 / 方舟 ×5 的应对

### 第四章：Prompt 优化

- 4.1 精简原则：提问越短，回复越短
- 4.2 系统提示词瘦身
- 4.3 分段 / 分批 vs 全部塞入

### 第五章：上下文管理

- 5.1 对话精简：及时清理历史
- 5.2 上下文窗口选型：1M 不是每次都要开满
- 5.3 关键信息截取 vs 全文喂入

### 第六章：缓存策略

- 6.1 各家缓存机制对比（MiniMax / 腾讯云 / 小米 MiMo）
- 6.2 提示词复用：固定模板缓存化
- 6.3 高频调用的缓存命中率优化

### 第七章：工具链调优

- 7.1 减少无效调用：差量编辑 vs 全量重写
- 7.2 IDE 插件配置优化
- 7.3 CI/CD 场景降本

### 第八章：多模型组合方案

- 8.1 主力省钱 + 补位强模型架构
- 8.2 路由策略：自动降级
- 8.3 组合套餐实测对比

### 第九章：效果验证

- 9.1 如何定义「不影响使用效果」
- 9.2 降本前后对比框架
- 9.3 回退机制：发现降质如何恢复

### 第十章：执行路线图

- 10.1 第一阶段：快速见效（1-3 天）
- 10.2 第二阶段：系统优化（1-2 周）
- 10.3 第三阶段：持续监控与调优
