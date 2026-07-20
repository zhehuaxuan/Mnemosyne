---
tags: [claude, dev, workflow, superpowers]
---

# 基于 Claude 进行软件工程开发

## Claude Code 技能系统（Superpowers）

Claude Code 拥有一个**技能（Skill）系统**，每个技能封装了特定场景的最佳实践。使用 `/skill-name` 调用。

### 核心原则

- **任何操作前**，先思考是否有技能适用
- **`using-superpowers`** 是入口技能，每次会话自动加载，要求你在做任何事之前先检查相关技能
- 技能之间可以组合：例如先 `/brainstorming` 再 `/writing-plans`

---

## 已安装技能一览

### Superpowers（来自 obra/superpowers）

| 技能 | 用途 | 何时使用 |
|------|------|---------|
| `brainstorming` | 创意工作前的需求探索 | 创建新功能、组件、修改行为前 |
| `systematic-debugging` | 结构化排错 | 遇到任何 bug、测试失败、异常行为时 |
| `writing-plans` | 编写实现计划 | 有需求但尚未确定多步实现方案时 |
| `executing-plans` | 执行已有计划 | 已有书面实现计划需要分步执行 |
| `subagent-driven-development` | 并行执行独立任务 | 计划中的子任务相互独立时 |
| `dispatching-parallel-agents` | 并行派发 2+ 独立任务 | 多个无需共享状态的任务 |
| `test-driven-development` | TDD 流程 | 实现功能或修复前先写测试 |
| `requesting-code-review` | 请求代码审查 | 完成任务、合并前验证工作质量 |
| `receiving-code-review` | 接收审查反馈 | 收到审查意见后，尤其是反馈不清晰时 |
| `verification-before-completion` | 完成前验证 | 声明完成、提交或创建 PR 前 |
| `writing-skills` | 编写/编辑技能 | 创建新技能或修改现有技能 |
| `using-git-worktrees` | 隔离工作区 | 开始需要隔离的功能开发时 |
| `finishing-a-development-branch` | 开发完成后的分支处理 | 实现完成，决定如何合并/提交 |

### Firecrawl（网页抓取与搜索）

| 技能 | 用途 |
|------|------|
| `firecrawl-search` | 网页搜索 + 全文内容提取 |
| `firecrawl-scrape` | 从 URL 提取干净 Markdown |
| `firecrawl-crawl` | 批量抓取整个网站 |
| `firecrawl-map` | 发现并列出网站所有 URL |
| `firecrawl-interact` | 与网页交互（点击、填表） |
| `firecrawl-download` | 下载整个网站为本地文件 |
| `firecrawl-monitor` | 监控网页内容变化 |
| `firecrawl-parse` | 解析本地文件（PDF、DOCX 等）为 Markdown |
| `firecrawl-agent` | AI 自主提取结构化数据 |

### UI/UX 设计

| 技能 | 用途 |
|------|------|
| `ui-ux-pro-max` | UI/UX 设计知识库（50+ 风格、配色方案、排版） |
| `ui-styling` | 用 shadcn/ui + Tailwind 构建界面 |
| `design` | 品牌标识、Logo、CIP、幻灯片 |
| `banner-design` | 22 种社交/广告/网页/印刷横幅风格 |
| `design-system` | 设计 Token 架构、组件规范 |
| `slides` | 用 Chart.js + 设计 Token 创建 HTML 演示文稿 |
| `brand` | 品牌调性、视觉识别、消息框架 |

### 其他实用技能

| 技能 | 用途 |
|------|------|
| `deep-research` | 多源深度研究，对抗验证，生成引用报告 |
| `dataviz` | 创建图表、数据可视化 |
| `verify` | 端到端验证代码修改是否生效 |
| `code-review` | 审查当前 diff 的正确性和简化机会 |
| `simplify` | 审查并自动应用简化/复用优化 |
| `claude-api` | Claude/Anthropic API 参考 |
| `run` | 启动并驱动项目应用 |
| `init` | 初始化 CLAUDE.md 项目文档 |

---

## 推荐工作流程

### 日常开发

```
接到任务 → /brainstorming → /writing-plans（可选）→ 实现 → /verification-before-completion → /requesting-code-review → 提交/PR
```

### Bug 修复

```
遇到 Bug → /systematic-debugging → 定位根因 → 修复 → /verification-before-completion
```

### TDD 模式

```
需求 → /test-driven-development → 先写测试 → 实现 → 验证 → 重构
```

### 大型任务的并行执行

```
规划 → /writing-plans → /executing-plans → /subagent-driven-development
```

---

## 关键原则

1. **技能优先**：即使只有 1% 的可能性某个技能适用，也必须检查
2. **持续验证**：不要声称完成，要运行验证命令确认
3. **独立思考**：使用 CodeGraph 理解代码，不要做重复的 grep/read 循环
4. **工具>Bash**：能用 Read/Edit/Write/Glob/Grep 就不用 Bash
