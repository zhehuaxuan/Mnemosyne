## 三层架构总览

上下文记忆系统由三层构成，分别对应不同粒度和持久度：

| 层级  | 名称                   | 存储位置                         | 持久性         | 访问方式          | 数据粒度            |
| --- | -------------------- | ---------------------------- | ----------- | ------------- | --------------- |
| 第一层 | ContextMessageBuffer | 内存                           | 会话级         | 直接追加/弹出       | 完整消息            |
| 第二层 | SessionMemory Notes  | 文件系统 `session_context.md`    | 会话级（可跨压缩存活） | 后台 agent 读写文件 | 结构化 Markdown 摘要 |
| 第三层 | LongTermMemory       | KV Store + Vector Store + DB | 跨会话永久       | LLM 提取 + 语义搜索 | 向量化的碎片记忆        |

**核心思想**: 三层记忆分别对应不同粒度和持久度——`ContextMessageBuffer` 是当前窗口的短期记忆，`SessionMemoryNotes` 是同会话内节省 token 的"笔记摘要"，`LongTermMemory` 是跨会话的长期知识库。

---

## 完整调用链全景图

```
用户发起一次对话请求
         │
         ▼
┌────── Phase 0: 上下文初始化（跨 session 恢复）─────────────────────────┐
│                                                                       │
│  ContextEngine.create_context()          ← 交互点 A: Session Notes 恢复│
│    ├─ 读取 session_context.md（上一轮保存的笔记）                       │
│    ├─ 解析为 history_messages 作为新 context 的种子                     │
│    ├─ SessionModelContext.__init__(history_messages)                   │
│    │    └─ ContextMessageBuffer.rebulid(history_messages)              │
│    └─ 注册 ContextProcessors 处理器链                                   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ReActAgent.invoke()                         ← react_agent.py
         │
   ┌─────┴─────┐
   │  Rail 生命周期  │
   └─────┬─────┘
         │
┌──────▼─────────────────────────────────────────────────────────────┐
│  Phase 1: BEFORE_INVOKE rails                                      │
│  ─────────────────────                                              │
│  MemoryRail.before_invoke()          ← 交互点 B（长期记忆读路径）     │
│    ├─ LongTermMemory.get_variables()   加载用户变量                  │
│    ├─ LongTermMemory.search_user_mem()  语义搜索用户画像记忆         │
│    └─ LongTermMemory.search_user_history_summary() 搜索历史摘要      │
│  结果注入到 system prompt 的 {sys_memory_variables} 和               │
│  {sys_long_term_memory} 占位符中                                     │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────── Phase 2: ReAct 循环（多次迭代）─────────────────────────────────┐
│                                                                       │
│  ┌─ 2a. BEFORE_MODEL_CALL rails ────────────────────────────────┐     │
│  │  ContextProcessorRail.before_model_call()                     │     │
│  │    ├─ 刷新 task_state runtime   读取最新的任务运行状态           │     │
│  │    └─ 注入 offload section 到 system prompt 读懂压缩后的会话信息  │     │
│  └───────────────────────────────────────────────────────────────┘     │
│         │                                                             │
│  ┌─ 2b. _railed_model_call() ───── 交互点 C（第一层核心流程）──┐     │
│  │                                                               │     │
│  │  ① 构建最终 system message                                   │     │
│  │                                                               │     │
│  │  ② ctx.context.get_context_window()                          │     │
│  │    ├── SessionModelContext._get_window_messages()              │     │
│  │    │    └─ ContextMessageBuffer.get_back() 从缓冲区取消息      │     │
│  │    │    └─ 按 dialogue_round 或 window_size 截取              │     │
│  │    │                                                           │     │
│  │    ├── 遍历 ContextProcessor.on_get_context_window() 链       │     │
│  │    │    ├─ ToolResultBudgetProcessor: 预算裁减工具结果        │     │
│  │    │    ├─ MicroCompactProcessor: 微型压缩                   │     │
│  │    │    ├─ ReasoningToolLoopCompactProcessor: 推理循环压缩   │     │
│  │    │    └─ FullCompactProcessor: 完整压缩（LLM 生成摘要）    │     │
│  │    │                                                           │     │
│  │    ├── 执行 window_mutators（如 prompt_attachment）           │     │
│  │    │                                                           │     │
│  │    └── KVCacheManager.release()   ← 释放推理引擎 KV Cache    │     │
│  │                                                               │     │
│  │  ③ LLM invoke / stream  ← 最终发送给 LLM 的窗口内容          │     │
│  │                                                               │     │
│  └───────────────────────────────────────────────────────────────┘     │
│         │                                                             │
│  ┌─ 2c. AFTER_MODEL_CALL rails ── 交互点 D（第二层触发检查）──┐     │
│  │  ContextProcessorRail.after_model_call()                      │     │
│  │    ├─ SessionMemoryManager.update_inherited_system_prompt()   │     │
│  │    └─ SessionMemoryManager.maybe_schedule_update()            │     │
│  │         │                                                      │     │
│  │         ├─ should_update(): 检查 token/工具调用阈值            │     │
│  │         │   ├─ 初始：token >= trigger_tokens (10000)          │     │
│  │         │   └─ 增量：新增token >= trigger_add_tokens(5000)    │     │
│  │         │         且工具调用次数 >= tool_min_ (3)              │     │
│  │         │                                                      │     │
│  │         └─ 满足条件 → 启动后台异步更新                         │     │
│  │              └─ _update_background() 写 session_context.md    │     │
│  │                 ├─ 读取/初始化 session_context.md              │     │
│  │                 ├─ 写 .pending 临时文件（写时复制）            │     │
│  │                 ├─ SessionMemoryUpdateAgent 更新 notes        │     │
│  │                 │   ├─ agent_edit: ReActAgent + edit_file     │     │
│  │                 │   └─ direct_replace: LLM 直接替换全量       │     │
│  │                 └─ 原子替换 pending → 生效文件                 │     │
│  └───────────────────────────────────────────────────────────────┘     │
│         │                                                             │
│  ┌─ 2d. 工具执行 + add_messages ─── 交互点 E（第一层被动压缩）──┐     │
│  │                                                               │     │
│  │  ① 解析 AssistantMessage 中的 tool_calls                     │     │
│  │  ② 执行每个工具调用，收集 ToolMessage 结果                    │     │
│  │  ③ ctx.context.add_messages(ToolMessage)                     │     │
│  │    ├─ 获取处理器锁（避免并发压缩冲突）                         │     │
│  │    ├─ _run_add_processors() 被动压缩检查                      │     │
│  │    │   └─ 处理器判断 token 是否超限，执行 on_add_messages()   │     │
│  │    └─ ContextMessageBuffer.add_back() 追加到环形缓冲          │     │
│  │       └─ _if_need_resize() 超限时丢弃最早的一半消息            │     │
│  │                                                               │     │
│  └───────────────────────────────────────────────────────────────┘     │
│         │                                                             │
│         └──→ 回到 2a，开始下一轮迭代（直到 max_iterations 或 stop）    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
         │  ReAct loop 结束
         ▼
┌──────▼─────────────────────────────────────────────────────────────┐
│  Phase 3: AFTER_INVOKE rails                                       │
│  ────────────────────                                               │
│  MemoryRail.after_invoke()          （长期记忆写路径）     │
│    └─ LongTermMemory.add_messages()  （异步后台任务）               │
│         │                                                            │
│         ├─ MessageManager.add() → DB（持久化原始消息）               │
│         │                                                            │
│         ├─ Generator.gen_all_memory()  ← LLM 记忆提取              │
│         │    ├─ 提取 variables（用户变量）                           │
│         │    ├─ 提取 user_profile（用户画像）                       │
│         │    ├─ 提取 semantic_memory（语义记忆）                    │
│         │    ├─ 提取 episodic_memory（情景记忆）                    │
│         │    └─ 提取 summary（摘要）                                 │
│         │                                                            │
│         └─ WriteManager.add_memories()  按类型写入存储              │
│              ├─ FragmentMemoryManager → MemoryIndex (向量+KV)      │
│              ├─ VariableManager → KV Store                         │
│              └─ SummaryManager → MemoryIndex (向量+KV)             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 关键时刻协同细节

以下按时间顺序描述每个关键交互点的精确行为：

### 交互点 A: SessionMemory Notes 读取与上下文恢复

#### 作用

`ContextEngine.create_context()` 是 Phase 0（上下文初始化）的核心入口，在每次新的 ReAct 循环启动时被调用。SessionMemory Notes（第二层）的读取恢复发生在此阶段：

```
用户发起一次新的对话
  │
  └─ ContextEngine.create_context()            ← 交互点 A 在此
       │
       ├─ 读取 session_context.md（上一轮保存的笔记）
       ├─ 解析为 history_messages 列表
       ├─ SessionModelContext.__init__(history_messages)
       └─ 注册 ContextProcessors 处理器链
```

**交互点 A 的核心作用**：在上下文初始化阶段，将持久化的 SessionMemory Notes（L2）反序列化为消息列表，作为新 ContextMessageBuffer（L1）的种子消息。这样上一轮对话在压缩中保护下来的关键信息就能在当前轮次继续可用。

**交互点 A 是被动读取的**——SessionMemory Notes 不会主动注入到运行中的 ContextMessageBuffer，它只影响新 context 的初始状态。如果 `create_context()` 没有传入 `history_messages`，则 SessionMemory Notes 不会被加载，所有上下文从零开始。

#### 实现

```
ContextEngine.create_context()
  │
  ├─ 0. 确定是否需要从 SessionMemory 恢复
  │    - 检查配置是否启用了 session_memory
  │    - 检查 session_id 对应的 session_context.md 是否存在
  │    - 都不满足 → 创建空 context
  │
  ├─ 1. 读取 session_context.md（如果存在）
  │     path: {workspace}/context/{session_id}_context/session_memory/session_context.md
  │     ├─ 文件内容包含结构化 Markdown 段落:
  │     │   # Session Title / # Current State
  │     │   # Task specification / # Files and Functions
  │     │   # Workflow / # Errors & Corrections
  │     │   # Learnings / # Key results / # Worklog
  │     └─ 读取成功 → 将内容封装为 history_messages 列表
  │                    通常作为 UserMessage 注入
  │
  ├─ 2. 创建 SessionModelContext
  │     SessionModelContext.__init__(
  │         history_messages=history_messages,  ← 从 session notes 恢复的消息
  │         processors=processors,              ← 已注册的处理器链
  │         ...
  │     )
  │     └─ ContextMessageBuffer.rebulid(history_messages)
  │          用 history_messages 重建环形缓冲区
  │
  ├─ 3. 注册 ContextProcessors 处理器链
  │     根据 preset 和用户配置构建处理器列表
  │     有 SessionMemory → ToolResultBudget → MicroCompact → ReasoningToolLoop → FullCompact
  │     无 SessionMemory → MessageSummaryOffloader → ReasoningToolLoop → Dialogue → CurrentRound → RoundLevel
  │
  └─ 4. 返回 SessionModelContext 实例
        新 context 就绪，进入 Phase 1 BEFORE_INVOKE rails
```

### 交互点 B: 长期记忆的完整读写路径

**读路径**（`before_invoke` → 注入到 system prompt）：

```
MemoryRail.before_invoke()
  │
  ├─ 获取 user_id 和 query
  │
  ├─ LongTermMemory.get_variables()
  │    → VariableManager.get_user_variable()
  │      → KV Store 直接查询
  │    结果 → {sys_memory_variables} → system prompt
  │
  ├─ LongTermMemory.search_user_mem()
  │    → SearchManager.search()
  │      → MemoryIndex.search() 向量相似度搜索
  │        → 按 threshold=0.3, top_k=10 过滤
  │    结果 → {sys_long_term_memory} → system prompt
  │
  └─ LongTermMemory.search_user_history_summary()
       → SearchManager.search(memory_type=SUMMARY)
       → threshold=0.3, top_k=5
      结果 → {sys_long_term_memory} → system prompt
```

**写路径**（`after_invoke` → 异步后台写入）：

```
MemoryRail.after_invoke()
  │  仅当 result_type == "answer" 时触发
  │
  └─ LongTermMemory.add_messages(query, output)
       │
       ├─ 1. 持久化原始消息
       │    MessageManager.add() → SqlMessageStore → DB
       │
       ├─ 2. LLM 提取记忆
       │    Generator.gen_all_memory()
       │    ├─ 对每种 memory type 调用 LLM
       │    │  (使用 scope 级别的 LLM 或系统默认 LLM)
       │    ├─ 使用历史消息作为 context
       │    └─ 结果包含: variables, user_profile,
       │       semantic_memory, episodic_memory, summary
       │
       └─ 3. 按类型分发写入
            WriteManager.add_memories()
            ├─ FragmentMemoryManager → MemoryIndex
            │  (向量化写入 vector store + KV store)
            ├─ VariableManager → KV Store
            │  (键值对直接覆盖写入)
            └─ SummaryManager → MemoryIndex
               (向量化写入 vector store + KV store)

            注意: 全程使用 DistributedLock(f"user/{user_id}")
            保证同一用户级别的并发安全
```
### 交互点 C: `get_context_window()` 调用途中

#### 作用

`_railed_model_call()` 是 ReActAgent 中"组装 LLM 输入并执行调用"的核心方法。它被 `@rail` 装饰器包裹，在调用前后会触发 `BEFORE_MODEL_CALL` / `AFTER_MODEL_CALL` 钩子。其完整职责是：

```
_railed_model_call(ctx)
  ├─ BEFORE_MODEL_CALL rails 已执行完毕
  │   （此时 system prompt 各部分已组装完成、offload section 已注入）
  │
  ├─ ① 构建最终 system message
  │
  ├─ ② ctx.context.get_context_window()     ← 交互点 C 在此
  │    ├─ 从 ContextMessageBuffer 取消息
  │    ├─ 过 ContextProcessor 链（压缩/摘要/卸载）
  │    ├─ 执行 window_mutators
  │    └─ KVCacheManager.release()
  │
  ├─ ③ 更新 ctx.inputs.messages/tools（供 after_model_call 钩子查看）
  │
  └─ ④ LLM invoke / stream                   ← 实际发送给 LLM
```

**交互点 C 的核心作用**：在 LLM 调用之前，从消息缓冲区中取出原始消息，经过一道可插拔的处理器流水线（ContextProcessor 链），生成最终发送给 LLM 的上下文窗口。这是**第一层记忆（ContextMessageBuffer）对 LLM 输入进行加工的唯一出口**，所有的压缩、摘要、卸载、KV Cache 释放都在这一步完成。

没有交互点 C，LLM 看到的就是未加工的原始缓冲区内容，token 会迅速耗尽、推理结果会因为 Cache 未释放而出错。

#### 实现

```
SessionModelContext.get_context_window()
  │
  ├─ 1. 获取原始消息: _get_window_messages()
  │     从 ContextMessageBuffer 中取出消息
  │     约束1: max_buffer_size（硬限制，超过则丢弃旧消息）
  │     约束2: dialogue_round / window_size（当前窗口大小）
  │
  ├─ 2. 遍历处理器链（按注册顺序）:
  │
  │  Step A: ToolResultBudgetProcessor
  │   触发条件: 工具结果消息 token 超过预算
  │   动作: 将超长的工具结果替换为摘要占位符
  │
  │  Step B: MicroCompactProcessor
  │   触发条件: 上下文 token 接近限制
  │   动作: 压缩单轮对话中的冗余消息
  │
  │  Step C: ReasoningToolLoopCompactProcessor
  │   触发条件: 检测到 long-thinking 的推理循环
  │   动作: 折叠推理过程中的中间思考链
  │
  │  Step D: FullCompactProcessor
  │   触发条件: 总 token 超过阈值
  │   动作:
  │     - 选取压缩候选（靠前的、较旧的消息）
  │     - 调用 LLM 生成摘要
  │     - 将原始消息替换为摘要消息
  │     - 记录 compression_usage（token 消耗）
  │
  │  注意: 每个处理器执行时都通过 ProcessorStateRecorder
  │  记录 before/after 指标，并发射 ContextCompressionState 事件
  │  到 session 流，前端可以实时看到压缩状态
  │
  ├─ 3. window_mutators
  │     prompt_attachment_manager.make_window_mutator(session_id)
  │     → 在窗口返回前注入 prompt 附件
  │
  └─ 4. KVCacheManager.release()
       比较 last_context_window 与当前窗口:
       - 逐条比较消息: 如果某条消息变更（被压缩替换了），
         从变更位置开始释放 KV Cache
       - 比较工具列表: 工具变更也触发释放
       - 调用 model.release(session_id, messages, messages_released_index)
```

### 交互点 D: SessionMemory 更新时机

#### 作用

`maybe_schedule_update()` 在 `AFTER_MODEL_CALL` rail 中被调用，作用是**决策是否需要将当前对话内容总结写入 SessionMemory 笔记文件**。它是从**第一层（ContextMessageBuffer）流向第二层（SessionMemory Notes）的桥梁**：

```
_railed_model_call(ctx) 完成一轮 LLM 调用
  │
  ├─ AFTER_MODEL_CALL rails 执行
  │    │
  │    ├─ ContextProcessorRail.after_model_call()
  │    │    ├─ _refresh_task_state_runtime()
  │    │    ├─ update_inherited_system_prompt()    同步 system prompt
  │    │    │
  │    │    └─ maybe_schedule_update()          ← 交互点 D 在此
  │    │         （检查 token/工具调用阈值，判断是否需要写入笔记）
  │    │
  │    └─ 其他 rails...
  │
  └─ 进入第 2d 阶段（工具执行 + add_messages）
```

**交互点 D 的核心作用**：在每轮 LLM 调用之后，判断当前对话是否产生了足够多的新信息，如果是，则在后台启动一个异步任务，将对话内容结构化地写入 `session_context.md` 文件。这确保了当第一层被压缩或清除后，关键信息不会丢失——压缩后的上下文可以通过 SessionMemory Notes 恢复。

没有交互点 D，SessionMemory Notes 就是空文件，交互点 A 恢复上下文时也拿不到任何信息。

#### 实现

```
SessionMemoryManager.maybe_schedule_update(ctx)
  │
  ├─ 0. 快速失败检查
  │    - 是否已有正在运行的同 session 更新任务？
  │      有 → 跳过（防止重复调度）
  │    - session_id 是否有效？无效 → 跳过
  │
  ├─ 1. collect_context_window()
  │     获取当前完整上下文消息列表
  │     包含 system messages + context messages
  │
  ├─ 2. _truncate_context_window_to_completed_api_round()
  │     只保留"已完成 API 轮次"的消息
  │     （与压缩语义保障相同的原则：不将正在进行的工具调用纳入总结）
  │
  ├─ 3. should_update() 决策:
  │    ├─ 首次初始化条件:
  │    │   token >= trigger_tokens (10000)
  │    │   → 将 initialized 设为 True, 不立即更新
  │    │   → 等待下次满足增量条件
  │    │
  │    ├─ 增量更新条件:
  │    │   新增 token >= trigger_add_tokens (5000)
  │    │   AND 新增工具调用 >= tool_min_ (3)
  │    │   → 启动更新
  │    │
  │    └─ 上下文缩小（用户清除上下文等情况）:
  │        → 自动重置 baseline token/tool_call 计数
  │        → 防止"基线漂移"导致永远无法触发更新
  │
  ├─ 4. 调度后台更新任务（不阻塞主流程）:
  │    ├─ 读取当前 session_context.md 内容
  │    ├─ 复制到 .pending 文件（写时复制模式）
  │    │
  │    ├─ mode == "agent_edit"（默认模式）:
  │    │   创建一个独立的 ReActAgent
  │    │   将完整对话消息注入为其初始上下文
  │    │   Agent 调用 edit_file 工具增量更新 .pending 文件
  │    │   最多 2 次迭代（防止 Agent 死循环）
  │    │
  │    ├─ mode == "direct_replace":
  │    │   直接用 LLM 生成完整的新 notes 内容
  │    │   不使用 Agent，不做增量编辑，全量覆盖
  │    │   失败自动重试（最多 2 次）
  │    │
  │    └─ 更新成功:
  │         .pending.replace(active_path)  →  原子替换生效
  │
  │  后台更新完成后记录状态到 session runtime:
  │  - tokens_at_last_update: 更新时的 token 计数（新的基线）
  │  - tool_calls_at_last_update: 更新时的工具调用计数（新的基线）
  │  - notes_upto_message_id: 已处理到哪条消息（增量追踪点）
  │  - is_extracting: 标记为 False（提取完成）
```

### 交互点 E: `add_messages()` 调用途中

#### 作用

`add_messages()` 是 ReAct 循环中"将新消息写入上下文"的入口方法。ReAct 循环中的工具执行步骤（第 2d 阶段）会在每次工具返回后调用 `ctx.context.add_messages(ToolMessage)` 将结果写入缓冲区。它在循环中的位置是：

```
ReAct 循环第 2d 阶段（after_model_call 之后）
  │
  ├─ 解析 AssistantMessage 中的 tool_calls
  ├─ 执行每个工具调用，收集 ToolMessage 结果
  │
  └─ ctx.context.add_messages(ToolMessage)    ← 交互点 E 在此
       ├─ 被动压缩检查（_run_add_processors）
       └─ 追加到环形缓冲（ContextMessageBuffer.add_back）
```

**交互点 E 的核心作用**：在消息被写入缓冲区之前，触发一次被动压缩检查——如果有处理器判定当前上下文即将超限，就在写入前主动执行压缩，让新消息能顺利写入而不会立即撑爆窗口。这是**第一层记忆（ContextMessageBuffer）的写入侧压缩出口**，与交互点 C 的读取侧压缩形成互补。

没有交互点 E，所有压缩压力都会堆积到下次 LLM 调用时的 `get_context_window()`，可能导致 LLM 调用前才仓促压缩，增加延迟。

#### 实现

```
SessionModelContext.add_messages(messages)
  │
  ├─ 0. 检查是否正在主动压缩中
  │     如果 _active_compression_in_progress 且锁被持有
  │     → 跳过被动处理器，直接追加消息到缓冲区后返回
  │     （避免主动压缩和被动压缩互相阻塞死锁）
  │
  ├─ 1. 获取处理器锁 asyncio.Lock()
  │     （避免并发压缩冲突）
  │
  ├─ 2. _run_add_processors() 被动处理器检查
  │     遍历注册的处理器列表（同交互点 C 的处理器链）:
  │     │
  │     ├─ 每个处理器调用 trigger_add_messages() 判断是否需要介入
  │     │   ├─ FullCompactProcessor: 当前消息总 token >= 180000?
  │     │   ├─ MicroCompactProcessor: 单轮内冗余过多?
  │     │   └─ ReasoningToolLoopCompactProcessor: 推理循环过长?
  │     │
  │     └─ 如果触发 → on_add_messages() 执行压缩
  │          ├─ FullCompactProcessor: 调用 LLM 生成摘要
  │          │   替换旧消息为摘要，返回空 messages_to_add
  │          │   （新消息通过 set_messages 直接写入缓冲区）
  │          └─ 返回 ContextEvent + 压缩后的消息列表
  │
  │     注意: 每个处理器执行时通过 ProcessorStateRecorder
  │     记录 before/after 指标，失败时记录 error 状态
  │
  ├─ 3. ContextMessageBuffer.add_back(messages_to_add)
  │     追加到环形缓冲
  │     - 如超出 max_buffer_size × 2，_if_need_resize()
  │       丢弃最早的一半消息（硬限制兜底）
  │
  └─ 4. 释放处理器锁
```


---

## 压缩器家族（Processor Types）

| 处理器 | 触发时机 | 作用阶段 | 具体行为 |
|--------|----------|----------|----------|
| `ToolResultBudgetProcessor` | add / get | 被动+主动 | 超长工具调用结果 → 摘要占位符 |
| `MicroCompactProcessor` | add / get | 被动+主动 | 单轮内的冗余消息折叠 |
| `DialogueCompressor` | get | 被动 | 整个对话压缩（`tokens_threshold=100000` 触发） |
| `CurrentRoundCompressor` | get | 被动 | 仅压缩最新轮次（保留最近 3 条） |
| `RoundLevelCompressor` | get | 被动 | 按轮次压缩（`trigger_context_ratio=0.9`，目标 160k tokens） |
| `ReasoningToolLoopCompactProcessor` | add / get | 被动+主动 | 折叠推理循环中的中间思考 |
| `FullCompactProcessor` | add / get | 被动+主动 | 完整压缩，LLM 生成摘要 |
| `MessageSummaryOffloader` | add | 被动 | 大消息卸载到文件系统（`large_message_threshold=15000`） |
| `MessageOffloader` | add | 被动 | 消息卸载到文件系统 |
| `ToolResultWindowProcessor` | add / get | 被动+主动 | 工具结果窗口管理 |

### 两种 Preset 模式

**有 SessionMemory 时**:
```
ToolResultBudgetProcessor → MicroCompactProcessor → ReasoningToolLoopCompactProcessor → FullCompactProcessor
```

**无 SessionMemory 时**:
```
MessageSummaryOffloader → ReasoningToolLoopCompactProcessor → DialogueCompressor → CurrentRoundCompressor → RoundLevelCompressor
```

---

## 各层核心实现

### 第一层: SessionModelContext (context.py)

继承自 `ModelContext`，是 LLM 调用看到的上下文窗口。

- **ContextMessageBuffer** (`message_buffer.py`): 带容量限制的环形消息缓冲区
  - `max_buffer_size`: 最大消息数硬限制（超过时从头部丢弃）
  - `history_messages_size`: 追踪"历史消息"与"当前消息"的分界线
  - 当长度超过 `max_buffer_size * 2` 时自动裁减前半段

- **Context Processors（上下文处理器）**: 压缩/摘要引擎
  - **被动触发**: 每次 `add_messages()` 调用时，检查是否达到压缩阈值，触发压缩处理器
  - **主动压缩**: 手动调用 `compress_context()`，使用处理器对消息进行摘要/压缩
  - **GET 时压缩**: `get_context_window()` 获取上下文时，处理器对窗口内的消息进行被动压缩
  - 每次压缩都通过 `ContextProcessorStateRecorder` 记录状态并发射事件

- **KV Cache Manager** (`kv_cache_manager.py`): 管理推理引擎的 KV Cache 释放
  - 跟踪上一次的 `ContextWindow`
  - 检测消息或工具是否有变更，通知模型释放对应的 KV Cache 前缀

- **OffloadMessageBuffer**: 消息卸载机制
  - 支持 `in_memory`（内存中暂存）和 `filesystem`（写到磁盘文件系统）两种卸载方式
  - 卸载路径: `{workspace}/context/{session_id}_context/offload/{handle}.json`

- **ProcessorStateRecorder**: 记录每次上下文的压缩操作历史（最多 100 条），并通过事件系统广播状态

### 第二层: SessionMemoryNotes (session_memory_manager.py)

跨上下文压缩的持久化记忆机制，解决"上下文窗口满了之后，重要信息不丢失"的问题。

- **存储位置**: `{workspace}/context/{session_id}_context/session_memory/session_context.md`
- **模板段落**:
  - Session Title / Current State / Task specification / Files and Functions
  - Workflow / Errors & Corrections / Codebase and System Documentation
  - Learnings / Key results / Worklog

- **触发条件**:
  - 初始触发: token >= `trigger_tokens`（默认 10000）
  - 增量触发: 新增 token >= `trigger_add_tokens`（默认 5000）且工具调用数 >= `tool_min_`（默认 3）
  - 上下文裁减后自动重置基线

- **更新方式**:
  - `agent_edit`（默认）: 启动独立 ReActAgent，用 `edit_file` 工具更新文件
  - `direct_replace`: LLM 直接返回完整新内容覆盖写入（失败自动重试最多 2 次）

- **并发安全**:
  - 写时复制: 先写到 `.pending` 文件，完成后 `replace` 原子替换
  - 异步更新: 后台 task 中进行，不影响主对话
  - 同一 session 同一时刻只有一个更新任务

### 第三层: LongTermMemory (long_term_memory.py)

跨会话长期记忆引擎（单例模式）。

- **存储后端**:
  - KV Store（必需）: 快速键值存储，用于变量和配置
  - Vector Store（可选）: 向量存储，用于语义搜索
  - DB Store（可选）: 关系型数据库，用于持久化消息

- **记忆类型**:
  - `USER_PROFILE` / `EPISODIC_MEMORY` / `SEMANTIC_MEMORY`: 片段式记忆（向量存储）
  - `VARIABLE`: 键值对变量（KV Store）
  - `SUMMARY`: 聚合摘要（向量存储）

- **Scope 隔离**: 每个 `scope_id` 代表一个隔离记忆域，可配置独立 LLM 和 Embedding 模型

- **AES 存储加密**: `AesStorageCodec` 对敏感数据加密存储

---

## 核心设计要点

1. **分层衰减**: 消息从第一层开始，经历多次压缩后部分信息透过第二层笔记保留，再通过第三层跨会话沉淀
2. **增量提取**: SessionMemory 和 LongTermMemory 都追踪"已处理到哪条消息"，避免重复提取
3. **异步解耦**: SessionMemory 更新和 LongTermMemory 写入都是后台 task，不阻塞主对话流程
4. **写时复制**: SessionMemory 先写 `.pending` 再原子替换，避免更新过程中被中断导致文件损坏
5. **Scope 隔离**: LongTermMemory 的 scope_id 支持多租户隔离，每个 scope 可配置独立 LLM 和 Embedding 模型
6. **KV Cache 协同**: KVCacheManager 监测 ContextProcessor 对消息的修改（压缩替换），触发推理引擎释放对应位置的 KV Cache，避免推理结果错误
7. **事件驱动**: 每次压缩操作都通过 ProcessorStateRecorder 发射 `ContextCompressionState` 事件到 session 流，前端可实时看到压缩状态
8. **API 轮次完整性**: 只对"已完成 API 轮次"的消息进行总结和压缩，确保不会将正在进行的工具调用纳入处理

---

## 压缩语义正确性保障机制

`get_context_window()` 在压缩上下文时，通过一整套分层保障体系来确保语义不丢失、不扭曲。以下按**压缩前 → 压缩中 → 压缩后**的时间顺序逐一阐述。

### 1. 压缩前：对象隔离与保护

#### 1a. API 轮次完整性过滤

`group_completed_api_rounds()` 只将**已完成**的对话轮次标记为压缩候选。一个完成的轮次定义为：

```
AssistantMessage(含 tool_calls) → ToolMessage × N → AssistantMessage(无 tool_calls, 纯文本回复)
```

如果 LLM 刚发起 `read_file` 调用、`ToolMessage` 尚未返回，这段未闭合的对话**不会进入压缩器**。这一过滤同时被 `FullCompactProcessor._group_messages_by_api_round()` 和 `RoundLevelCompressor._build_raw_targets()` 使用。

相关代码：
- `session_memory_manager.py`: `group_completed_api_rounds()`、`find_last_completed_api_round_end()`
- `full_compact_processor.py:565-566`: `_group_messages_by_api_round()`
- `round_level_compressor.py:460-493`: `_build_raw_targets()`

#### 1b. 最新消息免压缩保护

`FullCompactProcessor._select_messages_to_keep()` 保留最近 N 条消息不变（默认 10 条）：

```
messages_to_keep = self._messages_to_keep  # 默认 10
start_index = max(len(messages) - keep_recent, 0)
return list(messages[start_index:])
```

更进一步，`_adjust_start_index_for_tool_pairs()` 会反向扫描，确保最近的 `ToolMessage` 和其对应的 `AssistantMessage` 配对不被拆散——即 **tool_call_boundary protection**。

#### 1c. Token 阈值触发（避免无意义的压缩）

每个处理器都有触发阈值，只有上下文达到一定规模才激活：

| 处理器 | 触发条件 |
|--------|----------|
| `FullCompactProcessor` | `trigger_total_tokens >= 180000` |
| `RoundLevelCompressor` | `trigger_context_ratio >= 0.9`（即占满 90% context budget） |
| `DialogueCompressor` | `tokens_threshold >= 100000` |

这避免了在上下文还很短、信息密度很高时进行不必要的压缩。

---

### 2. 压缩中：LLM 摘要 + 多级退火

#### 2a. LLM 生成摘要（而非截断）

最核心的语义保障：FullCompactProcessor 和 RoundLevelCompressor **都不做随机丢弃或简单截断**，而是调用 LLM 来结构化地理解和重述对话。

**FullCompactProcessor** 使用 `BASE_COMPACT_PROMPT` + `DETAILED_ANALYSIS_INSTRUCTION` 作为 system 指令（full_compact_processor.py:67-162），要求 LLM 按以下结构生成摘要：

1. Primary Request and Intent
2. Key Technical Concepts
3. Files and Code Sections（含完整代码片段和原因说明）
4. Errors and Fixes
5. Problem Solving
6. All User Messages（保留所有用户原始提问）
7. Pending Tasks
8. Current Work
9. Optional Next Step

要求必须输出 `<analysis>` + `<summary>` 双块结构，确保 LLM 先**理解再总结**，而不是直接丢出一个模糊概括。

**RoundLevelCompressor** 的 system prompt（round_level_compressor.py:38-81）明确要求语义保留规则：

```
Priority order:
1. Ongoing ReAct state and exact handoff point
2. Unfinished work, blockers, pending actions, and last concrete action
3. Critical facts, constraints, decisions, corrections, and outputs needed for correct continuation
4. Durable conclusions from completed work
5. Secondary historical detail only if budget allows

Rules:
- Preserve the user's original requirements, constraints, acceptance criteria,
  and preferences as completely as possible.
- For ongoing ReAct blocks, keep a distinct `User Requirements` section.
- For completed ReAct blocks, preserve both `User Requirements` and `Final Result`.
- Do not weaken or over-compress the user's original request unless absolutely necessary.
```

#### 2b. 三级退火策略（progressive aggressiveness）

`RoundLevelCompressor._compress_until_target()` 采用 LLM 驱动的三级退火：

```
第 1 轮（first_pass, target=30000 tokens）
  └─ 标准摘要：最小损压缩，保留详细上下文
  └─ 如果 budget 仍超限 ──→
第 2 轮（aggressive_keep_recent, target=20000 tokens）
  └─ 激进摘要：去除冗余推理、重复工具调用噪音
  └─ 如果 budget 仍超限 ──→
第 3 轮（aggressive_full_context, target=10000 tokens）
  └─ 最激进：但要求 keep ongoing work maximally recoverable
  └─ 如果 budget 仍超限 ──→
物理截断（_truncate_to_target）
  └─ 二分查找最大可保留文本量
  └─ 取 20% 头部 + 80% 尾部，中间用 [TRUNCATED] 标记
```

每一轮都是 LLM 调用（不是简单截断），只有 3 轮 LLM 压缩都仍然超 budget 时，才回退到物理截断。而物理截断也使用**二分查找**确定能保留的最大字符数，尽可能保留信息。

#### 2c. Prompt Budget 保护（防止压缩指令被截断）

在向 LLM 发送压缩请求之前，`_prepare_round_compression_messages()` 会检查压缩调用本身是否超 budget。如果连压缩系统 prompt + 消息序列化文本都超过了模型的 `compression_call_max_tokens`，则调用 `_truncate_prompt_to_budget()` 进行二分截断，但至少保留 `[Output Contract]` 节（确保模型理解输出格式要求）。如果连最小压缩 prompt 都放不下，则跳过该压缩阶段。

#### 2d. LLM 压缩结果校验

`_build_json_replacements()`（round_level_compressor.py:891-931）对 LLM 返回的结果做多层校验：

1. **Schema 校验**：必须返回 `{"blocks": [{"block_id": "...", "summary": "..."}]}` 结构
2. **字段完整性**：`block_id` 和 `summary` 必须是有效的非空字符串
3. **压缩收益检查** `_has_compression_benefit()`：替换后的消息 token 必须 < 原始消息 token，否则不应用替换（防止"越压越大"）
4. **Budget 检查** `_is_replacement_under_budget()`：替换后的消息不能超过 compression call budget

---

### 3. 压缩后：状态再注入 + 窗口修复 + KV Cache 释放

#### 3a. 状态再注入（State Reinjection）

压缩的代价是原始消息中的某些"运行状态"被摘要吞没了。FullCompactProcessor 在压缩完成后，会从**被压缩的消息原文中重新提取**关键运行状态，以结构化形式重新注入到压缩后的窗口（full_compact_processor.py:764-795）：

```
build_reinjected_state_messages()
  ├─ [SKILLS]：最近读取过的 skill 文件内容
  │   （仅保留 reinject_recent_skills=3 轮，去重）
  ├─ [TASK_STATUS]：当前循环迭代次数、pending follow-up 数量、stop reason
  └─ [PLAN_MODE]：当前 plan mode 状态
```

每条状态消息都带 `[FULL_COMPACT_STATE]` 标记，LLM 能区分哪些是"来自压缩前的状态恢复"，哪些是"当前正在发生的消息"。

#### 3b. 孤立工具消息修复

所有处理器遍历完成后，`ContextUtils.validate_and_fix_context_window()`（context_utils.py:230-244）修复窗口开头可能出现的孤立 `ToolMessage`：

```python
first_non_tool = 0
while first_non_tool < len(messages) and isinstance(messages[first_non_tool], ToolMessage):
    first_non_tool += 1
if first_non_tool > 0:
    context_window.context_messages = messages[first_non_tool:]
```

这确保了窗口开头不会出现"只有工具执行结果但看不到是谁调用的"的语义断裂场景。

#### 3c. KVCacheManager 语义一致性保障

`KVCacheManager._check_release_needed()` 比较**上一次的 ContextWindow** 和**当前经过压缩后的 ContextWindow**，逐条比对消息内容和工具列表。如果第 i 条消息从原始文本变成了压缩摘要（例如被 FullCompactProcessor 替换为 summary message），它会从 i 位置开始释放 KV Cache，通知推理引擎：

> "第 i 条之后的所有缓存 logits 都失效了，请重新计算。"

**不释放 KV Cache 的后果**：推理引擎还在用"缓存中旧消息的 key-value"去匹配"新压缩摘要的 query"，这直接导致语义错位——LLM 看到的 context 是两个不匹配的半区，产生幻觉。

#### 3d. 错误处理与 Fallback 链条

如果 LLM 摘要生成失败（模型调用异常、返回空内容），系统依次降级：

```
LLM 摘要正常 → 使用 LLM 结构化摘要（最佳）
  │
LLM 调用异常 → _build_fallback_summary()
  │              取最近 20 条消息的 role + content 文本拼接
  │
Fallback 仍超 budget → _build_minimal_compact_input()
  │                     只保留最后一条消息 + 合成 UserMessage
  │
截断也放不下 → _build_compact_truncated_message()
               仅输出 [ROUND_LEVEL_MEMORY_BLOCK] + [TRUNCATED] 标记
```

这条链条确保**任何情况下** `get_context_window()` 返回的窗口都至少包含可用的语义锚点，绝不返回空窗口让 LLM "失忆"。

---

### 保障机制全景图

```
压缩前                             压缩中                              压缩后
──────                            ──────                              ──────
API 轮次完整性过滤  ──→   LLM 结构化摘要（BASE_COMPACT_PROMPT）  ──→  状态再注入（skills/task_status/plan_mode）
最新 N 条消息免压缩  ──→   三级退火（30000→20000→10000 tokens）  ──→  孤立 ToolMessage 修复
Token 阈值触发控制  ──→   Prompt Budget 保护                    ──→   KVCacheManager 释放失效缓存
tool_call 边界保护  ──→   LLM 输出 Schema 校验                  ──→   Fallback 链条永不空窗口
                          压缩收益检查
```

每一层都在上一个机制失效时兜底，确保上下文不会在压缩中丢失或扭曲关键语义。**语义正确性不是靠一个魔法检查点保证的，而是靠这 8 道防线逐层递进、相互补充**。 |

## 关键代码路径

| 组件 | 文件路径 |
|------|----------|
| SessionModelContext | `openjiuwen/core/context_engine/context/context.py` |
| ContextMessageBuffer | `openjiuwen/core/context_engine/context/message_buffer.py` |
| SessionMemoryManager | `openjiuwen/core/context_engine/context/session_memory_manager.py` |
| KVCacheManager | `openjiuwen/core/context_engine/context/kv_cache_manager.py` |
| ProcessorStateRecorder | `openjiuwen/core/context_engine/context/processor_state_recorder.py` |
| ContextEngine | `openjiuwen/core/context_engine/context_engine.py` |
| ContextProcessor 基类 | `openjiuwen/core/context_engine/processor/base.py` |
| ContextProcessorRail | `openjiuwen/harness/rails/context_engineer/context_processor_rail.py` |
| MemoryRail | `openjiuwen/core/application/llm_agent/rails/memory_rail.py` |
| LongTermMemory | `openjiuwen/core/memory/long_term_memory.py` |
| ReActAgent | `openjiuwen/core/single_agent/agents/react_agent.py` |
| LongTermMemoryExtractor | `openjiuwen/core/memory/process/extract/long_term_memory_extractor.py` |
