# DeepAgent Starter 上下文压缩触发流程

> 文档对应代码版本：`deepagent-spring-boot-starter` 0.1.12-SNAPSHOT

## 触发链路总览

用户的一条消息从发送到最终触发压缩，经历两个独立的压缩机制，分别在**不同时机**和**不同层级**工作。

```mermaid
flowchart TB
    subgraph USER["用户交互入口"]
        A["用户发送消息<br/>DeepAgentClient.invoke() / stream()"]
    end

    subgraph DEEPAGENT["DeepAgent 运行时"]
        B["AgentSessionApi.preRun()<br/>准备会话上下文"]
        C["agent.invoke()<br/>ReAct 循环执行"]
    end

    subgraph ADD_MSG["消息写入上下文"]
        D["ModelContext.addMessages()<br/>将新消息加入消息列表"]
        E["遍历所有已注册 ContextProcessor<br/>调用 onAddMessages()"]
    end

    subgraph COMPRESSOR["HermesStyleCompactProcessor<br/>（被动压缩，消息入口触发）"]
        F["triggerAddMessages()<br/>判断是否要压缩"]
        G["compact()<br/>执行两阶段压缩"]
    end

    subgraph PHASE1["阶段一：单条压缩"]
        H["compactOversizedMessages()<br/>遍历所有消息"]
        I{"单条 ToolMessage/AssistantMessage<br/>≥ singleMessageTriggerTokens？"}
        J["isOversizedCompressibleMessage()<br/>- 非 ToolCall 消息<br/>- 非已摘要消息<br/>- Token 超过单条阈值"]
        K1["splitIntoReportSegments()<br/>三段切分 ≤ 三段？"]
        K1_YES["每段分别调 LLM 摘要<br/>→ 拼接为分段摘要"]
        K1_NO["summarizeOversizedReportSample()<br/>取开头 15% + 结尾 15% 抽样<br/>→ 调 LLM 生成局部摘要<br/>标记 [HERMES_STYLE_PARTIAL_SUMMARY]"]
        K2["替换原始消息为摘要<br/>标注 hermes_style_message_summary"]
    end

    subgraph PHASE2["阶段二：全局压缩"]
        L{"总历史 Token > triggerTotalTokens<br/>AND 有可压缩窗口？"}
        L_YES["分割消息为三段："]
        L1["head = 前 N 条保护<br/>（System + 前 3 条 /<br/>检测到 BOUNDARY_MARKER = 0 条）"]
        L2["middle = 中间待压缩段<br/>（调 LLM 生成结构化摘要<br/>SUMMARY_PROMPT）"]
        L3["tail = 尾部保留段<br/>（selectTail() 保留最近 6 条<br/>含最新 user + assistant + tool 配对）"]
        L4["buildReplacement()<br/>head + [BOUNDARY_MARKER] + 摘要 + tail"]
        L5{"压缩收益率 > 5%？"}
        L5_YES["替换上下文消息列表"]
        L5_NO["跳过本次压缩<br/>保留原文<br/>打 warn 日志"]
        L_NO["跳过全局压缩"]
    end

    subgraph GUARD["ContextCompressionGuard<br/>（主动压缩，尚未接线 ⚠️）"]
        M["compressIfNeeded()<br/>— 当前无任何调用方 —"]
        N{"上下文 Token ><br/>contextWindowTokens × 85%？"}
        N_YES["context.compressContext()<br/>委托给 HermesStyleCompactProcessor"]
        N_NO["不触发"]
    end

    subgraph FRAMEWORK["框架层异常处理"]
        O["SessionModelContext.addMessages()<br/>try/catch 包裹所有 processor"]
        O_ERR["异常被吞掉 → 打 warn<br/>→ 本次压缩跳过<br/>→ 上下文继续膨胀<br/>→ 最终超窗 API 失败"]
    end

    A --> B --> C --> D --> E --> F

    F --> |"containsOversized<br/>CompressibleMessage"| I
    F --> |"estimatedTokens > triggerTotal<br/>&& hasCompressibleWindow"| L

    I --> |"是"| J
    I --> |"否"| L
    J --> K1
    K1 --> |"≤ 3 段"| K1_YES
    K1 --> |"> 3 段"| K1_NO
    K1_YES --> K2
    K1_NO --> K2
    K2 --> L

    L --> |"是"| L_YES
    L --> |"否"| L_NO
    L1 --> L2 --> L3 --> L4 --> L5
    L5 --> |"是"| L5_YES
    L5 --> |"否"| L5_NO

    M --> N
    N --> |"是"| N_YES
    N --> |"否"| N_NO

    H -.-> |"抛 IllegalStateException 被框架吞掉"| O_ERR
    L4 -.-> |"抛 IllegalStateException 被框架吞掉"| O_ERR
```

## 三层压缩架构

项目的上下文压缩分为**三个独立层级**，分别在用户消息的不同处理阶段工作：

```mermaid
flowchart LR
    subgraph L1["Layer 1: 意图识别层（intent-engine-core）"]
        CS["CompressingConversationStore<br/>主动压缩 ✅ 已启用"]
        CS_DESC["每轮对话写入后 checkThreshold()<br/>轮数 ≥ maxRounds(5) 或 token ≥ maxHistory(2000)<br/>→ 立即 LLM 链式摘要<br/>保留最近 2 轮，旧消息压成摘要"]
    end

    subgraph L2["Layer 2: Agent 运行时层（deepagent-spring-boot-starter）"]
        HP["HermesStyleCompactProcessor<br/>被动压缩 ✅ 已启用"]
        HP_DESC["消息写入 ModelContext 时 onAddMessages()<br/>两阶段：单条压缩 → 全局压缩<br/>三段切分 + LLM 摘要 + 收益校验<br/>失败抛错 → 框架吞掉 → 压缩跳过"]
    end

    subgraph L3["Layer 3: Agent 运行时上下文窗口守卫（deepagent-spring-boot-starter）"]
        CG["ContextCompressionGuard<br/>主动压缩 ⚠️ 已实现但未接线"]
        CG_DESC["compressIfNeeded()<br/>每次 LLM 调用前 85% 水位检查<br/>到达阈值提前压缩<br/>**当前无任何调用方**"]
    end

    USER["用户消息"] --> INTENT["IntentEngine.analyzeWithMemory()<br/>意图识别"]
    INTENT --> CS
    CS --> AGENT["agent.invoke()<br/>ReAct 循环"]
    AGENT --> HP
    AGENT -.-> |"应该在这里调用"| CG
```

## Layer 1 vs Layer 2 vs Layer 3 对比

| 维度 | CompressingConversationStore | HermesStyleCompactProcessor | ContextCompressionGuard |
|---|---|---|---|
| **所属模块** | `intent-engine-core` | `deepagent-spring-boot-starter` | `deepagent-spring-boot-starter` |
| **触发时机** | 意图识别阶段，每轮对话写入后 | Agent 运行时，消息写入 ModelContext 时 | Agent 运行时，LLM 调用前 |
| **触发方式** | **主动** — checkThreshold() 每轮检查 | **被动** — onAddMessages() 由框架回调 | **主动** — compressIfNeeded() 外部调用 |
| **压缩对象** | 意图识别的对话历史（user/assistant 文本） | Agent 的完整上下文消息列表 | Agent 的 ModelContext |
| **触发条件** | 轮数 ≥ maxRounds(5) 或 token ≥ maxHistoryTokens(2000) | 单条 ≥ 2400 token 或 总计 ≥ 10400 token | 上下文占用 ≥ 窗口 85% |
| **压缩策略** | LLM 链式摘要，保留最近 2 轮 | 三段切分，头保护 + 中间 LLM 摘要 + 尾保留 | 委托给 HermesStyleCompactProcessor |
| **当前状态** | **已启用** ✅ | **已启用** ✅ | **已实现但未接线** ⚠️ |
| **失败行为** | LLM 失败 → 降级滑动窗口删旧消息 | 抛 IllegalStateException → 框架吞掉 → 压缩跳过 → 上下文持续膨胀 | 暂不生效 |

## 关键触发阈值

| 阈值 | 默认值 | 说明 |
|---|---|---|
| `singleMessageTriggerTokens` | `contextWindowTokens × singleMessageTriggerRatio`（~2400 token） | 单条 ToolMessage/AssistantMessage 超过此值触发单条压缩 |
| `triggerTotalTokens` | 可配置（默认 ~10400 token） | 整个历史累计超过此值触发全局压缩 |
| `HYGIENE_RATIO` | 0.85（85%） | `ContextCompressionGuard` 水位阈值（未接线） |
| `PROTECT_FIRST_MESSAGES` | 3 条 | 全局压缩时头部保护的消息数 |
| `MAX_MESSAGES_TO_KEEP` | 6 条 | 全局压缩时尾部保留的消息数 |
| `MIN_TAIL_MESSAGES` | 3 条 | 尾部最少保留消息数 |
| `MIN_MESSAGES_TO_SUMMARIZE` | 2 条 | 中间段最少待摘要消息数 |
| 收益率底线 | 5% | 压缩后收益低于此值则跳过本次压缩 |
| 摘要质量底线 | 120 字符 | 原文 ≥ 480 字符时摘要必须 ≥ 120 字符，否则抛错 |

## 阶段一：单条压缩（`compactOversizedMessages`）

遍历所有消息，对每一条判断是否需要进行单条压缩：

1. **判断条件**：`ToolMessage` 或 `AssistantMessage`（不含 tool_calls）且 token > `singleMessageTriggerTokens`
2. **三段切分**：将超长内容优先按换行切分成 ≤ 3 段，每段分别调 LLM 摘要
3. **抽样降级**：三段仍装不下时，取开头 15% + 结尾 15% 抽样，调 LLM 生成局部摘要，标记 `[HERMES_STYLE_PARTIAL_SUMMARY]`
4. **替换**：原始消息替换为摘要消息，标注 `hermes_style_message_summary` 元数据

## 阶段二：全局压缩（`compact`）

单条压缩后若总 token 仍超阈值，进入全局压缩：

1. **分割消息**：
   - **头部**：SystemMessage + 前 3 条（检测到 `[HERMES_STYLE_COMPACT_BOUNDARY]` 则头部保护降至 0 条）
   - **中间段**：头部之后、尾部之前的所有消息
   - **尾部**：保留最近 6 条，确保最新 user/assistant/tool_call↔tool_result 配对完整
2. **LLM 摘要**：中间段调 LLM 用 `SUMMARY_PROMPT` 生成结构化摘要，包含：历史任务快照、目标、约束、已完成动作、当前状态、阻塞、关键决策、已解决问题、相关文件等
3. **替换**：`head + [BOUNDARY_MARKER] + 摘要 + tail`
4. **收益校验**：压缩后 token 节省比例 < 5% 则跳过，保留原文

## 异常链路

文中三省（`ensureSummaryQuality`、`generateRequiredSummary`、`splitIntoReportSegments`）和汇总两处（`generateSummary`、`compactOversizedMessages` 中的 `summarizeOversizedMessage`）在失败时抛 `IllegalStateException`。

框架层 `SessionModelContext.addMessages()` 用 try/catch 包裹所有 processor，异常被吞掉后只打 warn，**本次压缩被跳过**，上下文原文保留继续膨胀。多次跳过后上下文必然撑爆窗口，最终导致 API 调用失败。

## 引用文档

- 详细分析见：[上下文工程全量梳理.md](上下文工程全量梳理【晓东梳理】.md)
- 代码位置：`deepagent-spring-boot-starter/src/main/java/.../context/`
  - `HermesStyleCompactProcessor.java`
  - `ContextCompressionGuard.java`
  - `DeepAgentContextProcessorResolver.java`
