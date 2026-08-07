# 上下文压缩 Processor 切换指南

本文档介绍在客户现场如何在三种上下文压缩 processor 之间切换，以及各自适用场景。

**基线说明**：本文以**上游原版** `openjiuwenagentscaffolds-main` 为对照基线。原版 starter 只内置 `HermesStyleCompactProcessor` 一个 processor；要支持三种 processor 切换，需要在原版基础上做下述【新增】改造。改造完成后，yml 改 `context-processor-names` 即可纯配置切换。

## 三种 Processor 对比（bench 实测）

| Processor | 事实保留 | 平均省率 | 平均延迟 | LLM 调用次数/会话 | 适用场景 |
|---|---|---|---|---|---|
| **HermesStyleCompactProcessor** | 26/27（最高） | 86.6% | ~60s | 2 | 事实保留优先、延迟可接受 |
| **OpenCodeStyleCompactProcessor** | 24/27 | 78.8% | ~20s（最低） | 1 | 延迟/成本优先、交互式场景 |
| **OpenJiuwenChainProcessor**（MessageOffloader + MessageSummaryOffloader + FullCompactProcessor） | 25/27 | 96.1%（最狠） | ~74s | 4-7 | 省 token 优先、离线批处理 |
| 不压缩（基线） | 26/27 | 0% | 0 | 0 | 上下文不超窗口的小场景 |

**选型建议**：
- 实时交互 agent（对延迟敏感）→ **OpenCodeStyle**
- 事实保留最关键（金融、合规、审计场景）→ **HermesStyle**
- 离线长会话、要极致省 token → **OpenJiuwenChain**

## 三种 Processor 压缩逻辑与延迟

### HermesStyleCompactProcessor

- **延迟**：~60s / 会话（2 次 LLM 调用）
- **触发**：总 token > 窗口 × `trigger-context-ratio`(0.65)，或单条消息 > 窗口 × `single-message-trigger-ratio`(0.15)
- **整轮压缩逻辑**：
  1. `protectedHeadSize` 保护首条 `SystemMessage` + 前 3 条消息不动
  2. 中间消息（headEnd → compactEnd）送 LLM 做结构化摘要（目标长度原文 20%，强制结构：历史任务快照/目标/约束/已完成动作/当前状态/阻塞/关键决策/相关文件 等）
  3. 尾部按 `tail-context-ratio`(0.10) 比例保留原文
  4. 摘要前后塞 `[HERMES_STYLE_COMPACT_BOUNDARY]` 标记，第二轮压缩识别此 marker 后只保留首条 SystemMessage（不再保护旧伪 head）
- **单条超长逻辑**：拆 3 段送 LLM 摘要 → 失败降级到开头+结尾采样（`summarizeOversizedReportSample`）→ 还失败硬截断（`hardTruncateMessage`）→ 还不更小就保留原文（三级 fallback）
- **优化项**：CJK 感知 token 估算（中文 1 token/字符、ASCII 0.25、其他 0.5）+ `ThreadLocal<IdentityHashMap>` 缓存避免重复估算 + reasoning 模型 `finish_reason=length` 时空回复用 `SUMMARY_RETRY_TOKEN_CAP=2000` 重试一次 + `effectiveSummaryMaxTokens = min(summaryMaxTokens, (window-tail)/2)` 防摘要撑爆窗口 + source 太小（< 摘要预算）直接返回不动 LLM

### OpenCodeStyleCompactProcessor

- **延迟**：~20s / 会话（1 次 LLM 调用，三者最低）
- **触发**：总 token > 窗口 - `max(summaryOutput, buffer)`（buffer = 窗口 × 0.35，绝对 token 阈值，非比例）
- **压缩逻辑**：
  1. 按 `keepTokens`(窗口/8) 预算从末尾向前保留尾部消息，边界消息按字符切片拆分
  2. 中间历史送 LLM 生成结构化锚定摘要（Markdown 模板：Objective / Important Details / Work State Completed / Active 等）
  3. **若上一轮摘要已存在**，把旧摘要 + 最近尾部传给 LLM 做「更新」而非「重建」——避免每次压缩从头摘要，保留累积上下文
  4. 所有 tool 输出在序列化前按 `toolOutputMaxChars` 预剪枝，防单条 tool 返回撑爆摘要输入
- **延迟低的原因**：只调 1 次 LLM；触发线用绝对 token 数（窗口 - buffer），更晚触发，压缩次数少

### OpenJiuwenChainProcessor

- **延迟**：~74s / 会话（4-7 次 LLM 调用，三者最高）
- **触发**：链里任一 sub-processor `triggerAddMessages` 返回 true 即触发
- **三层链逻辑**（顺序执行，前一个输出流入后一个）：
  1. `MessageOffloader`：单条 tool 输出字符数 > `largeMessageThreshold`(2000 字符) 时字符截断保留前 `trimSize`(1000 字符) + OMIT 标记，**无 LLM 调用**
  2. `MessageSummaryOffloader`：单条消息仍超阈值时 LLM 摘要替换，**1 次/条 LLM 调用**
  3. `FullCompactProcessor`：整轮累积 token > `triggerRatio`(0.65) 窗口时整轮摘要，**1 次 LLM 调用**
- **设计意图**：三层渐进式压缩，每层兜底——字符截断（最便宜）先削超长 tool 输出，LLM 摘要（中等）处理仍超长的单条，整轮摘要（最贵）处理多轮累积。事实保留优先于省率。
- **配置项关键约束**：`largeMessageThreshold` / `trimSize` 是**字符数**非 token，务必保持 ≥ 2000/1000，否则长 tool 输出被截成残骸（bench 验证 80/40 配置会把所有 1000+ 字符的 tool 输出截断到 40 字符，事实保留掉到 4/9）。
- **若只想用其中一层**：客户可在 yml 单独配 `FullCompactProcessor` 或 `MessageSummaryOffloader`，不走聚合 processor。

## 原版 starter 状态（对照基线）

原版 resolver 关键代码（**这是基线，下面所有改造都在它之上叠加**）：

```java
public DeepAgentContextProcessorResolver() {
    registerContextProcessors();          // 原版只注册 Hermes 一个
}

private static void registerContextProcessors() {
    ContextEngine.registerProcessor(      // 原版只有这一条
            HermesStyleCompactProcessor.PROCESSOR_TYPE,
            HermesStyleCompactProcessor.class,
            config -> new HermesStyleCompactProcessor((HermesStyleCompactProcessorConfig) config)
    );
}

private List<ContextEngine.ProcessorSpec> resolveContextProcessors(...) {
    for (String processorName : processorNames) {
        String normalizedName = processorName.trim();
        if (HermesStyleCompactProcessor.PROCESSOR_TYPE.equals(normalizedName)) {
            processors.add(new ContextEngine.ProcessorSpec(
                    HermesStyleCompactProcessor.PROCESSOR_TYPE,
                    compressionConfig.toBuilder()                       // 原版 inline 构造 spec
                            .model(compressionModelRequest(...))
                            .modelClient(compressionModelClient(...))
                            .build()
            ));
        } else {
            log.warn("[DeepAgent Starter] [{}] unknown context processor: {}", ...);
        }
    }
    return processors;
}
```

## 改造：支持三种 processor 切换（原版基础上的【新增】）

### 步骤 1：加两个 processor 类 + 两个 config 类【新增】

| 类 | 放置路径（starter 内） | 来源 |
|---|---|---|
| `OpenCodeStyleCompactProcessor.java` | `src/main/java/com/icbc/mlp/deepagent/springboot/autoconfigure/context/` | 从 agent-core-java 移植或自行实现 |
| `OpenCodeStyleCompactProcessorConfig.java` | `src/main/java/com/icbc/mlp/deepagent/springboot/autoconfigure/properties/` | 同上 |
| `OpenJiuwenChainProcessor.java` | `src/main/java/com/icbc/mlp/deepagent/springboot/autoconfigure/context/` | 聚合 `MessageOffloader` + `MessageSummaryOffloader` + `FullCompactProcessor`（来自 agent-core-java 0.1.13） |
| `OpenJiuwenChainProcessorConfig.java` | `src/main/java/com/icbc/mlp/deepagent/springboot/autoconfigure/properties/` | 同上 |

> 若只想支持其中一种切换，只加对应的一组类即可。Hermes 类原版已有，不动。

### 步骤 2：改造 resolver（原版 if-else → Registry+Strategy 模式）【新增】

**改的文件**（只改这一个）：

```
deepagent-spring-boot-starter/src/main/java/com/icbc/mlp/deepagent/springboot/autoconfigure/resolver/DeepAgentContextProcessorResolver.java
```

把原版的 if-else 替换成 `processorBuilders` Map + spec builder 方法。**原版的 `configureForInstance` / `compressionModelRequest` / `compressionModelClient` / `resolveModelName` 等辅助方法不动**，只动构造函数、`registerContextProcessors`、`resolveContextProcessors` 三个方法 + 新增 `buildXxxSpec` 私有方法。

**① 构造函数加 `processorBuilders` Map【新增】**（原版构造函数只有一行 `registerContextProcessors()`）：

```java
private final Map<String, BiFunction<HermesStyleCompactProcessorConfig,
        DeepAgentInstanceProperties, ContextEngine.ProcessorSpec>> processorBuilders;

public DeepAgentContextProcessorResolver() {
    registerContextProcessors();
    this.processorBuilders = Map.of(                                    // 【新增】整个 Map
            HermesStyleCompactProcessor.PROCESSOR_TYPE, this::buildHermesSpec,
            OpenCodeStyleCompactProcessor.PROCESSOR_TYPE, this::buildOpenCodeSpec,           // 【新增】
            OpenJiuwenChainProcessor.PROCESSOR_TYPE, this::buildOpenJiuwenChainSpec          // 【新增】
    );
}
```

**② `registerContextProcessors` 加两条 register 调用【新增】**（原版只有 Hermes 一条）：

```java
private static void registerContextProcessors() {
    ContextEngine.registerProcessor(                                    // 已有，不动
            HermesStyleCompactProcessor.PROCESSOR_TYPE,
            HermesStyleCompactProcessor.class,
            config -> new HermesStyleCompactProcessor((HermesStyleCompactProcessorConfig) config)
    );
    ContextEngine.registerProcessor(                                    // 【新增】
            OpenCodeStyleCompactProcessor.PROCESSOR_TYPE,
            OpenCodeStyleCompactProcessor.class,
            config -> new OpenCodeStyleCompactProcessor((OpenCodeStyleCompactProcessorConfig) config)
    );
    ContextEngine.registerProcessor(                                    // 【新增】
            OpenJiuwenChainProcessor.PROCESSOR_TYPE,
            OpenJiuwenChainProcessor.class,
            config -> new OpenJiuwenChainProcessor((OpenJiuwenChainProcessorConfig) config)
    );
}
```

**③ `resolveContextProcessors` 把 if-else 换成 Map lookup【改造】**（原版是 `if (HermesStyleCompactProcessor.PROCESSOR_TYPE.equals(...))` 分支）：

```java
private List<ContextEngine.ProcessorSpec> resolveContextProcessors(...) {
    // ... 前置空判断同原版，不动 ...
    for (String name : processorNames) {
        if (name == null || name.isBlank()) continue;
        var builder = processorBuilders.get(name.trim());               // 【改造】原版是 if-else
        if (builder == null) {
            log.warn("[DeepAgent Starter] [{}] unknown context processor: {}", agentName, name);
            continue;
        }
        processors.add(builder.apply(compressionConfig, properties));
    }
    return processors;
}
```

**④ 写三个 `buildXxxSpec` 私有方法【新增】**（原版没有这些方法，spec 构造是 inline 写在 if 分支里的）：

```java
private ContextEngine.ProcessorSpec buildHermesSpec(
        HermesStyleCompactProcessorConfig c, DeepAgentInstanceProperties p
) {
    return new ContextEngine.ProcessorSpec(
            HermesStyleCompactProcessor.PROCESSOR_TYPE,
            c.toBuilder()
                    .model(compressionModelRequest(p, c))
                    .modelClient(compressionModelClient(p))
                    .build()
    );
}

private ContextEngine.ProcessorSpec buildOpenCodeSpec(
        HermesStyleCompactProcessorConfig c, DeepAgentInstanceProperties p
) {
    return new ContextEngine.ProcessorSpec(
            OpenCodeStyleCompactProcessor.PROCESSOR_TYPE,
            OpenCodeStyleCompactProcessorConfig.builder()
                    .contextWindowTokens(c.getContextWindowTokens())
                    .summaryMaxTokens(c.getSummaryMaxTokens())
                    .model(compressionModelRequest(p, c))
                    .modelClient(compressionModelClient(p))
                    .build()
    );
}

private ContextEngine.ProcessorSpec buildOpenJiuwenChainSpec(
        HermesStyleCompactProcessorConfig c, DeepAgentInstanceProperties p
) {
    return new ContextEngine.ProcessorSpec(
            OpenJiuwenChainProcessor.PROCESSOR_TYPE,
            OpenJiuwenChainProcessorConfig.builder()
                    .contextWindowTokens(c.getContextWindowTokens())
                    .largeMessageThreshold(OpenJiuwenChainProcessorConfig.DEFAULT_LARGE_MESSAGE_THRESHOLD)
                    .trimSize(OpenJiuwenChainProcessorConfig.DEFAULT_TRIM_SIZE)
                    .summaryMaxTokens(c.getSummaryMaxTokens())
                    .messagesToKeep(OpenJiuwenChainProcessorConfig.DEFAULT_MESSAGES_TO_KEEP)
                    .triggerRatio(OpenJiuwenChainProcessorConfig.DEFAULT_TRIGGER_RATIO)
                    .model(compressionModelRequest(p, c))
                    .modelClient(compressionModelClient(p))
                    .build()
    );
}
```

> 改造完之后 `resolveContextProcessors` 主循环是 `processorBuilders.get(name).apply(...)`，**零 if-else**。以后再加新 processor 只需在 Map 加 entry + 写一个 `buildXxxSpec` 方法 + 加一条 `registerProcessor` 调用，主循环不动（开闭原则）。

### 步骤 3：配置 application.yml 切换

```yaml
context-processor-names:
  - HermesStyleCompactProcessor          # 或 OpenCodeStyleCompactProcessor / OpenJiuwenChainProcessor
```

## 配置项

```yaml
deep-agent:
  instances:
    - name: my-agent
      context-compression-enabled: true          # 关闭则不挂任何 processor
      context-processor-names:                  # processor type 列表，按顺序注册
        - HermesStyleCompactProcessor
      context-compression:                      # processor 配置
        context-window-tokens: 16000
        trigger-context-ratio: 0.65             # hermes 专用
        tail-context-ratio: 0.10                 # hermes 专用
        summary-max-tokens: 1200
        single-message-trigger-ratio: 0.15       # hermes 专用
```

等价 properties：

```properties
deep-agent.context-compression-enabled=true
deep-agent.context-processor-names=HermesStyleCompactProcessor
deep-agent.context-compression.context-window-tokens=16000
deep-agent.context-compression.trigger-context-ratio=0.65
deep-agent.context-compression.tail-context-ratio=0.10
deep-agent.context-compression.summary-max-tokens=1200
deep-agent.context-compression.single-message-trigger-ratio=0.15
```

## 切换示例（同一实例）

```yaml
deep-agent:
  instances:
    - name: research-agent        # 事实保留优先 → hermes
      context-compression-enabled: true
      context-processor-names:
        - HermesStyleCompactProcessor
      context-compression:
        context-window-tokens: 32000
        trigger-context-ratio: 0.65
        tail-context-ratio: 0.10
        summary-max-tokens: 1200
        single-message-trigger-ratio: 0.15

    - name: chatbot-agent         # 延迟优先 → opencode
      context-compression-enabled: true
      context-processor-names:
        - OpenCodeStyleCompactProcessor
      context-compression:
        context-window-tokens: 32000
        summary-max-tokens: 2000

    - name: batch-agent           # 省 token 优先 → openjiuwen 链
      context-compression-enabled: true
      context-processor-names:
        - OpenJiuwenChainProcessor   # 内部自动跑 MessageOffloader + MessageSummaryOffloader + FullCompactProcessor 三层链
      context-compression:
        context-window-tokens: 32000
        summary-max-tokens: 1200
```

## 关键参数说明

| 参数 | 含义 | 默认 | 调参方向 |
|---|---|---|---|
| `context-window-tokens` | 模型上下文窗口 | 16000 | 按目标模型设 |
| `trigger-context-ratio` | 总 token 达窗口比例触发压缩（hermes/fullcompact） | 0.65 | 调高=触发更晚、上下文更满但压缩次数少 |
| `tail-context-ratio` | 压后保留尾部原文比例（hermes） | 0.10 | 调大=保留更多原文、省率降低 |
| `single-message-trigger-ratio` | 单条消息达窗口比例触发单条压缩（hermes） | 0.15 | 调大=单条更晚触发、长 tool 输出更易撑爆上下文 |
| `summary-max-tokens` | 摘要 LLM 输出上限 | 1200 | 调大=摘要更详细、省率降低 |
| `buffer`（opencode） | 触发缓冲，触发线=窗口-buffer | 窗口×35% | 调大=触发更晚 |
| `keepTokens`（opencode） | 压后保留尾部 token | 窗口/8 | 调大=保留更多原文 |
| `largeMessageThreshold`（openjiuwen） | 单条消息字符数超此值触发截断/摘要 | 2000 | **单位是字符非 token**，调小=更多消息被截断 |

## 已知限制

1. **原版 starter 只内置 Hermes 一个 processor**：要支持 OpenCode / OpenJiuwenChain 切换，必须先做"改造"步骤——加 2 个 processor 类 + 2 个 config 类 + 改 resolver。改造完后 yml 改 `context-processor-names` 即可纯配置切换。
2. **openjiuwen 链的 `largeMessageThreshold` 是字符数**，不是 token。设成 80 会把所有 1000+ 字符的 tool 输出截断到 40 字符残骸——务必保持 ≥ 2000。
3. **hermes 在 re-compaction 时曾丢首条 SystemMessage**（已修）。如果客户反馈"压完模型忘了系统设定"，检查是否用了未优化版本的 `HermesStyleCompactProcessor`。

## 老版本 Hermes → 新版本 Hermes 修复清单

**改的文件**（只改这一个，文件名不变）：

```
deepagent-spring-boot-starter/src/main/java/com/icbc/mlp/deepagent/springboot/autoconfigure/context/HermesStyleCompactProcessor.java
```

原版 1107 行，优化版 1375 行。修复与优化项：

| # | 类别 | 老版本现象 | 新版本修复 |
|---|---|---|---|
| 1 | 摘要失败硬抛 | `generateRequiredSummary` / `summarizeOversizedReport` / `compactOversizedMessages` 等多处抛 `IllegalStateException`（原版 line 492/523/572/591/593/610/627/889），框架 catch 后跳过压缩，上下文不收敛 | 全部改成 warn + return null，上层走三级 fallback，本轮总能产出压缩结果 |
| 2 | 质量检查硬抛 | `ensureSummaryQuality` 检测到 suspiciouslyShort（< 120 字符且原文 ≥ 480 字符）直接抛 `IllegalStateException`（原版 line 907-908） | 降级为 warn + return null，本轮跳过、下轮再试 |
| 3 | re-compaction 丢 SystemMessage | `protectedHeadSize` 检测到 `BOUNDARY_MARKER` 后返回 0（原版 line 825-833），第二轮压缩起 SystemMessage 被摘进新摘要，助手丢角色设定 | 即使 boundary marker 已存在，也返回 `messages.get(0) instanceof SystemMessage ? 1 : 0`，强制保留首条 SystemMessage |
| 4 | CJK token 严重低估 | `estimatedTokens` 直接调框架 `ContextUtils.estimateMessageTokens`（原版 line 948-952），对中文按 ~0.25 token/字符估算，中文 4000 字符只算 1000 token，触发线 / 摘要预算全部失真 | CJK 感知加权估算：CJK 1 token/字符、ASCII 0.25、其他 0.5（line 1026+），中文估算准确 |
| 5 | token 重复估算 | 同一条消息在一次压缩流程里被 `estimatedTokens` 重复估算 4-5 次（before/after/source/tail/quality 全调一遍） | `ThreadLocal<Map<BaseMessage, Integer>>` + `IdentityHashMap` 缓存（line 1022-1023），同一对象只算一次 |
| 6 | reasoning 模型空回复 | reasoning 模型（如 o1 / glm 思考链）用 max_tokens 全吐思考链，content 返空 + `finish_reason=length`，原版直接当失败抛异常 | `SUMMARY_RETRY_TOKEN_CAP=2000`（line 50），finish_reason=length + 空内容时用 `min(maxTokens*2, 2000)` 更大预算递归重试一次；拒答（finish_reason=stop 且空）不重试直接 fallback（line 757-766） |
| 7 | 摘要预算可能撑爆窗口 | 直接用 `config.getSummaryMaxTokens()`，配置 8000 时摘要本身可能占满半个窗口 | `effectiveSummaryMaxTokens()` = `min(summaryMaxTokens, (window - tail)/2)`（line 618），保证摘要不超出窗口预算 |
| 8 | source 太小也走 LLM | 待压缩片段 token 数 < 摘要预算时仍调 LLM 摘要，LLM 返回可能比原文还长，落入 drop-middle fallback 丢事实 | `sourceTokens < effectiveSummaryMaxTokens()` 时直接返回 unchanged（line 319-329），不调 LLM、不丢中间消息 |
| 9 | 单条超长无降级链 | 单条超长消息 LLM 摘要失败就抛异常，无后续兜底 | 三级 fallback：LLM 摘要 → null 时 `summarizeOversizedReportSample`（开头+结尾采样）→ 还 null 时 `hardTruncateMessage`（硬截断）→ 还不更小就保留原文（line 412/425/438） |

**验证**：`/tests` 页面（`http://127.0.0.1:8080/tests`）跑 `very-large` / `small-messages` / `deep-buried-fact` / `low-density` 场景 × 16000 / 4000 / 8000 窗口，对照原版与优化版的事实在留率即可看到差异。
