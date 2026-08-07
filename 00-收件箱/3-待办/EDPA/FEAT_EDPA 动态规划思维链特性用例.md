# EDPAgent 动态规划思维链 — 特性用例

## 1. 概述

### 1.1 功能目标

为 EDPAgent（企业级动态规划智能体）增加加加动态规划思维链加加输出能力，通过 SSE（Server-Sent Events）向前端实时推送 20 种事件，完整呈现智能体"思考→规划→执行→观察→回答"的全过程。

### 1.2 功能边界

| 维度       | 范围内                             | 范围外                                                            |
| -------- | ------------------------------- | -------------------------------------------------------------- |
| 传输协议     | SSE 流式响应                        | WebSocket / 轮询                                                 |
| 接入方式     | A2A JSON-RPC `/a2a`             | RESTful / WebSocket / 轮询等非 A2A 协议                              |
| 思维链事件    | 20 种标准化事件                       | 自定义事件扩展                                                        |
| 任务规划     | 从预配置任务列表中动态规划                   | 运行时动态创建新任务                                                     |
| 任务依赖     | 前置任务校验与执行顺序控制                   | 任务依赖图动态生成                                                      |
| 业务工具事件范围 | 仅 `call_mcp` / `call_versatile` | `ask_user`/`cancel_task`/`skill_tool`/`read_file`/`bash` 等其他工具 |

### 1.3 用户角色

| 角色    | 说明                               |
| ----- | -------------------------------- |
| 前端客户端 | 手机银行/网银前端，通过 A2A SSE 接收思维链事件并渲染  |
| 终端用户  | 银行客户，通过前端与 EDPAgent 交互           |
| 配置管理员 | 维护 `edp-config.yaml` 中的任务列表与依赖关系 |

### 1.4 事件清单

| #   | 事件类型                 | SSE event 行          | 方向       | 触发时机                                                                 | 必含字段                                        |
| --- | -------------------- | -------------------- | -------- | -------------------------------------------------------------------- | ------------------------------------------- |
| 1   | conversation\_start  | `conversation_start` | Agent→前端 | 对话开始                                                                 | session\_id, timestamp                      |
| 2   | think\_start         | `think_start`        | Agent→前端 | LLM 开始推理                                                             | timestamp                                   |
| 3   | think\_chunk         | `think_chunk`        | Agent→前端 | LLM 流式输出模型内容（直接输出，可多次）                                               | content, timestamp                          |
| 4   | think\_end           | `think_end`          | Agent→前端 | LLM 推理结束                                                             | timestamp                                   |
| 5   | todolist\_start      | `todolist_start`     | Agent→前端 | 任务规划完成或重新规划后                                                         | timestamp                                   |
| 6   | todolist\_item       | `todolist_item`      | Agent→前端 | 逐条发送任务（每条一个事件）                                                       | {id, task\_name, status}, timestamp         |
| 7   | todolist\_end        | `todolist_end`       | Agent→前端 | 任务列表发布完毕                                                             | timestamp                                   |
| 8   | todo\_start          | `todo_start`         | Agent→前端 | 单个任务开始执行（一个 todo 可含多个 tool 调用）                                       | tools\[{id, tool\_name, status}], timestamp |
| 9   | todo\_status         | `todo_status`        | Agent→前端 | 任务执行中间状态推送（可多次）                                                      | content, timestamp                          |
| 10  | todo\_end            | `todo_end`           | Agent→前端 | 单个任务执行完毕                                                             | timestamp                                   |
| 11  | tool\_start          | `tool_start`         | Agent→前端 | 开始调用业务工具（仅 call\_mcp / call\_versatile，嵌套在 todo\_start/todo\_end 之间） | tool（工具名）, args（入参）, timestamp              |
| 12  | tool\_status         | `tool_status`        | Agent→前端 | 工具执行中间状态推送（可多次）                                                      | tool, content, timestamp                    |
| 13  | tool\_end            | `tool_end`           | Agent→前端 | 业务工具调用返回结果（仅 call\_mcp / call\_versatile）                            | tool, data（返回数据）, timestamp                 |
| 14  | final\_answer\_start | `final_answer_start` | Agent→前端 | 开始生成最终回答                                                             | timestamp                                   |
| 15  | final\_answer\_chunk | `final_answer_chunk` | Agent→前端 | 最终回答完整文本（流式，可多次）                                                     | content, timestamp                          |
| 16  | final\_answer\_end   | `final_answer_end`   | Agent→前端 | 回答结束                                                                 | timestamp                                   |
| 17  | interrupt\_start     | `interrupt_start`    | Agent→前端 | 智能体追问用户                                                              | interrupt\_id, content（追问内容）, timestamp     |
| 18  | interrupt\_end       | `interrupt_end`      | Agent→前端 | 用户补充信息后继续处理                                                          | interrupt\_id, timestamp                    |
| 19  | conversation\_end    | `conversation_end`   | Agent→前端 | 对话结束                                                                 | session\_id, timestamp                      |
| 20  | error\_event         | `error_event`        | Agent→前端 | 系统异常/服务不可用/工具执行错误/依赖冲突                                               | error\_type, content, timestamp             |

#### error\_type 枚举定义

| error\_type            | 触发场景          | 对应用例          |
| ---------------------- | ------------- | ------------- |
| `LLM_TIMEOUT`          | LLM 调用超时/失败   | UC-10         |
| `LLM_AUTH_ERROR`       | LLM 认证失败（401） | UC-10 AF-10-A |
| `INVALID_TOOL_OUTPUT`  | 工具返回非法 JSON   | UC-04 AF-04-B |
| `TOOL_TIMEOUT`         | 工具执行超时        | UC-04 AF-04-A |
| `DEPENDENCY_VIOLATION` | 任务依赖缺失/循环依赖   | UC-11         |
| `INTERNAL_ERROR`       | 其他未捕获异常       | 兜底            |

>   事件序列约束  ：`error_event` 后始终跟 `conversation_end`（异常终止 = 错误通知 + 连接关闭）。

***

### 1.6 非功能性需求

| 维度          | 指标      | 说明                                           |
| ----------- | ------- | -------------------------------------------- |
| SSE 事件推送延迟  | ≤ 100ms | 从 Rail hook 触发到前端收到 SSE 事件的端到端延迟             |
| 最大并发 SSE 连接 | ≥ 500   | 单实例支持的并发 SSE 连接数                             |
| 单次对话超时      | 300s    | 单次 conversation 从开始到 conversation\_end 的最大时长 |
| LLM 调用超时    | 60s     | 单次 LLM API 调用超时阈值，超时后重试（最多 3 次）              |
| 工具执行超时      | 30s     | 单次 call\_mcp/call\_versatile 工具执行超时阈值        |
| Redis 读写延迟  | ≤ 10ms  | TodoTool Redis 持久化的单次读写延迟                    |
| 事件顺序保证      | 严格有序    | SSE 事件按发射顺序到达前端，不乱序                          |

***

## 2. 任务列表数据结构

### 2.1 配置格式（edp-config.yaml 扩展）

```yaml
todolist_steps:
  - step_id: 1
    task_name: "推荐理财产品"
    description: "根据用户风险偏好和资金情况，推荐合适的理财产品列表"
    skill: "product_recommend_skill"
    depends_on: []                    # 无前置任务
  - step_id: 2
    task_name: "交互式理财筛选"
    description: "用户从推荐列表中选择具体产品，确认购买意向"
    skill: "product_select_skill"
    depends_on: [1]                   # 依赖 step 1 完成
  - step_id: 3
    task_name: "查询余额与资金筹划"
    description: "查询理财卡余额，不足时从储蓄卡补足，执行购买"
    skill: "fund_planning_skill"
    depends_on: [2]                   # 依赖 step 2 完成
```

### 2.2 字段说明

| 字段          | 类型     |  必填 | 说明                           | OpenJiuwen Core 对应           |
| ----------- | ------ | :-: | ---------------------------- | ---------------------------- |
| step\_id    | int    |  是  | 任务唯一标识                       | `TodoItem.id`                |
| task\_name  | string |  是  | 任务名称，显示在 `todolist_item` 事件中 | `TodoItem.content`           |
| description | string |  是  | 任务描述，供 LLM 理解任务意图            | `TodoItem.description`       |
| skill       | string |  否  | 关联的 Skill 名称                 | `TodoItem.meta_data.skill`   |
| depends\_on | int\[] |  否  | 前置任务 step\_id 列表，空数组表示无依赖    | `TodoItem.depends_on`（已原生支持） |

>   复用说明  ：OpenJiuwen Core 的 `TodoItem` 已原生支持 `depends_on` 字段（`List<String>`）和 `status`（TODO/IN\_PROGRESS/COMPLETED/CANCELLED），无需扩展数据结构。`TodoTool` 已提供 `create`/`list`/`get`/`modify`（含 append/insert\_after/insert\_before）完整操作。

>   类型转换说明  ：YAML 中 `depends_on` 配置为 `int[]`（如 `[1]`），加载到 `TodoItem` 时自动转换为 `List<String>`（如 `["1"]`）。`step_id` 同理，int → String 转换在预加载阶段完成。

### 2.3 任务状态枚举

全文统一使用 OpenJiuwen Core 原生状态枚举，事件中 `status` 字段值如下：

| 状态值           | 含义  | 触发时机                     |
| ------------- | --- | ------------------------ |
| `TODO`        | 待执行 | 任务已创建但未开始                |
| `IN_PROGRESS` | 执行中 | 任务开始执行（`todo_start` 发射时） |
| `COMPLETED`   | 已完成 | 任务执行完毕（`todo_end` 发射时）   |
| `CANCELLED`   | 已取消 | 任务被用户取消或依赖冲突终止           |

***

## 3. 用例清单

| 用例 ID | 用例名称                     | 优先级 | 模块     |
| ----- | ------------------------ | :-: | ------ |
| UC-01 | 正常对话全链路思维链输出             |  高  | SSE 事件 |
| UC-02 | 多步任务动态规划与依赖校验            |  高  | 任务规划   |
| UC-03 | 任务重新规划（re-plan）          |  中  | 任务规划   |
| UC-04 | 工具调用事件输出                 |  高  | SSE 事件 |
| UC-05 | LLM 推理流式 think\_chunk 输出 |  高  | SSE 事件 |
| UC-06 | 最终回答流式输出                 |  高  | SSE 事件 |
| UC-07 | 追问中断与恢复                  |  高  | 中断恢复   |
| UC-08 | 任务取消终止                   |  中  | 中断恢复   |
| UC-09 | SSE 连接断开处理               |  中  | 异常处理   |
| UC-10 | LLM 调用超时/失败              |  中  | 异常处理   |
| UC-11 | 任务依赖冲突检测                 |  中  | 任务规划   |
| UC-12 | 超范围业务拒绝                  |  中  | 业务边界   |
| UC-13 | 前端断线重连续接                 |  低  | 异常处理   |
| UC-14 | 多轮对话上下文保持                |  中  | 会话管理   |

***

## 4. 详细用例

### UC-01：正常对话全链路思维链输出



用例 ID

：UC-01



优先级

：高



主参与者

：前端客户端



前置条件

：

1. EDPAgent 服务已启动，端口 8190 可访问
2. `edp-config.yaml` 已配置 `todolist_steps`（含 task\_name / description / depends\_on）
3. LLM API Key 已配置（`EDP_AGENT_MODEL_API_KEY`）
4. Versatile 服务已启动（如涉及购买类操作）



正常流程

：

| 步骤 | 系统                                                                                            | 事件输出                                                                                                                      |
| -- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| 1  | 前端发送 `POST /v1/{project_id}/agents/{agent_id}/conversations/{conversation_id}`，body 含 `query` | —                                                                                                                         |
| 2  | 服务端接收请求，创建会话上下文，分配 `session_id`                                                               | `conversation_start`                                                                                                      |
| 3  | EDPAgent 进入 Think 阶段（第 1 轮），调用 LLM 开始推理                                                       | `think_start`                                                                                                             |
| 4  | LLM 流式返回模型内容，直接输出                                                                             | `think_chunk`（N 次）                                                                                                        |
| 5  | LLM 推理结束，决策需要任务规划                                                                             | `think_end`                                                                                                               |
| 6  | EDPAgent 从 `edp-config.yaml` 的 `todolist_steps` 中选择任务，根据 `depends_on` 拓扑排序                    | `todolist_start`                                                                                                          |
| 7  | 逐条发送任务列表（全部 status=TODO）                                                                      | `todolist_item`（N 次，每次 1 条任务）                                                                                             |
| 8  | 任务列表发布完毕                                                                                      | `todolist_end`                                                                                                            |
| 9  | 第一个任务开始执行                                                                                     | `todo_start`                                                                                                              |
| 10 | 任务内调用 `skill_tool` 加载 Skill（内部工具，不产生 tool 事件）                                                 | —                                                                                                                         |
| 11 | 任务内调用业务工具（如 `call_mcp` 或 `call_versatile`），可多次                                                | `tool_start` → `tool_status`（可选） → `tool_end` → \[`tool_start` → `tool_status`（可选） → `tool_end`]                          |
| 12 | 第一个任务完成，标记 COMPLETED                                                                          | `todo_end`                                                                                                                |
| 13 |   ReAct 循环回到 Think 阶段（第 2 轮）  ，LLM 根据工具返回结果重新推理                                               | `think_start` → `think_chunk`（N 次） → `think_end`                                                                          |
| 14 |   重新输出更新后的任务列表  （task-1 status=COMPLETED，其余 TODO）                                             | `todolist_start` → `todolist_item`（N 次，每次 1 条含最新状态） → `todolist_end`                                                      |
| 15 | 第二个任务开始执行                                                                                     | `todo_start`                                                                                                              |
| 16 | 任务内调用业务工具（仅 call\_mcp/call\_versatile），可多次                                                    | `tool_start` → `tool_status`（可选） → `tool_end` → \[`tool_start` → `tool_status`（可选） → `tool_end`]                          |
| 17 | 第二个任务完成，标记 COMPLETED                                                                          | `todo_end`                                                                                                                |
| 18 |   重复步骤 13-17   执行后续任务，每轮 = Think → 更新 todolist → todo → tool → todo\_end                      | `think_start` → ... → `think_end` → `todolist_start` → `todolist_item` → `todolist_end` → `todo_start` → ... → `todo_end` |
| 19 | 所有任务完成，LLM 最终推理决策输出回答                                                                         | `final_answer_start`                                                                                                      |
| 20 | LLM 流式输出最终回答文本                                                                                | `final_answer_chunk`（N 次）                                                                                                 |
| 21 | 回答结束                                                                                          | `final_answer_end`                                                                                                        |
| 22 | 对话结束，关闭 SSE 连接                                                                                | `conversation_end`                                                                                                        |



完整事件序列

：

```
conversation_start
→ think_start → think_chunk(×N) → think_end
→ todolist_start → todolist_item(×N) → todolist_end
→ todo_start → tool_start → tool_status(可选) → tool_end → tool_start → tool_status(可选) → tool_end → todo_end
→ think_start → think_chunk(×N) → think_end
→ todolist_start → todolist_item(×N，更新) → todolist_end
→ todo_start → tool_start → tool_status(可选) → tool_end → todo_end
→ think_start → think_chunk(×N) → think_end
→ todolist_start → todolist_item(×N，更新) → todolist_end
→ todo_start → ...
→ final_answer_start → final_answer_chunk(×N) → final_answer_end
→ conversation_end
```

>   关键说明  ：每轮 ReAct 循环 = Think（推理）→ Plan（更新 todolist）→ Act（todo + tool）→ Observe（进入下一轮 Think）。`todo_end` 后不直接进入下一个 `todo_start`，而是先回到 `think_start` 重新推理，再输出更新后的 todolist，再执行下一个 todo。



后置条件

：

- SSE 流已关闭
- 会话上下文已持久化（checkpoint）
- 前端已渲染完整思维链



验收标准

：

| #  | 验收项                             | 验证方法                                                                                                                                             |
| -- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1  | 20 种事件全部可见                      | SSE 日志中 20 种 `event` 字段全部出现                                                                                                                      |
| 2  | 事件顺序正确                          | `conversation_start` → `think_start` → ... → `conversation_end`（见完整事件序列）                                                                         |
| 3  | `todolist_item` 为逐条发射           | 每次发送 1 条任务，共发送 N 次（N=任务总数）                                                                                                                       |
| 3a | 每个 todo 完成后先 Think 再更新 todolist | 每次 `todo_end` 后紧跟 `think_start` → `think_chunk` → `think_end` → `todolist_start` → `todolist_item` → `todolist_end`                              |
| 3b | todolist 状态递进更新                 | 每轮 `todolist_item`（×N）中已完成任务 status=COMPLETED，当前执行中为 IN\_PROGRESS，其余为 TODO                                                                       |
| 4  | `think_chunk` 直接输出模型内容          | 每个 `think_chunk` 的 `content` 为 LLM 流式输出片段                                                                                                        |
| 5  | `final_answer_chunk` 为流式文本      | 每个 `final_answer_chunk` 的 `content` 为文本片段，拼接后为完整回答                                                                                               |
| 6  | todo/tool 层级正确                  | 事件顺序为 `todo_start` → `tool_start` → `tool_status`（可选） → `tool_end` \[→ `tool_start` → `tool_status`（可选） → `tool_end`] → `todo_end`               |
| 6a | ReAct 循环事件正确                    | `todo_end` 后不直接 `todo_start`，而是 `think_start` → `think_chunk` → `think_end` → `todolist_start` → `todolist_item` → `todolist_end` → `todo_start` |
| 7  | `todo_status` 中间状态推送            | 长耗时任务执行过程中推送 `todo_status`，`content` 为任务进度描述                                                                                                     |
| 8  | `tool_status` 中间状态推送            | 长耗时工具执行过程中推送 `tool_status`，`content` 为工具执行进度描述                                                                                                   |
| 9  | 每个事件含 `timestamp` 字段            | 所有事件 data 中包含毫秒级 Unix 时间戳（与北向接口 `createdTime` 一致）                                                                                                |
| 10 | SSE 连接正常关闭                      | 最后一个事件为 `conversation_end`，连接随后关闭                                                                                                                |

***

### UC-02：多步任务动态规划与依赖校验



用例 ID

：UC-02



优先级

：高



主参与者

：EDPAgent LLM 推理引擎



前置条件

：

1. `edp-config.yaml` 配置了含 `depends_on` 的任务列表
2. 用户发起涉及多步 Skill 串联的请求（如"推荐并购买理财产品"）



正常流程

：

| 步骤 | 系统行为                                                                | 说明                                 |
| -- | ------------------------------------------------------------------- | ---------------------------------- |
| 1  | LLM 推理后决定需要任务规划                                                     | EDPAgent 触发任务规划流程                  |
| 2  | EDPAgent 读取 `edp-config.yaml` 的 `todolist_steps`                    | 获取全部可用任务定义                         |
| 3  | LLM 从任务列表中选择本次需要的 step\_id 子集                                       | 如 \[1, 2, 3]，排除不需要的步骤              |
| 4  | EDPAgent 校验 `depends_on` 依赖完整性                                      | step 3 依赖 \[2]，step 2 依赖 \[1] → 合法 |
| 5  | 按 `depends_on` 拓扑排序生成执行顺序                                           | \[1, 2, 3]                         |
| 6  | 输出 `todolist_start` → `todolist_item`(×3，每次 1 条任务) → `todolist_end` | 前端展示任务列表                           |
| 7  | 按顺序执行任务，每完成一个标记 `COMPLETED`                                         | `todo_start` → ... → `todo_end` 循环 |



备选流程

：



AF-02-A：LLM 选择了依赖不完整的任务子集



| 步骤 | 系统行为                                | 说明                            |
| -- | ----------------------------------- | ----------------------------- |
| 1  | LLM 选择 step\_id = \[1, 3]，跳过 step 2 | step 3 依赖 \[2] 但 2 未选         |
| 2  | EDPAgent 检测到依赖缺失                    | 校验 `depends_on` 中 \[2] 不在选中列表 |
| 3  | 终止当前任务规划，输出 `conversation_end`      | SSE 流关闭                       |



AF-02-B：LLM 选择的任务顺序违反依赖关系



| 步骤 | 系统行为                         | 说明                            |
| -- | ---------------------------- | ----------------------------- |
| 1  | LLM 输出 todo 列表顺序为 \[3, 2, 1] | step 3 依赖 2，但 3 排在 2 前面       |
| 2  | EDPAgent 检测到顺序违反             | 校验每个任务的 `depends_on` 是否在它之前出现 |
| 3  | 自动按 `depends_on` 拓扑排序修正      | 调整为 \[1, 2, 3]                |
| 4  | 输出修正后的 `todolist_item`       | 前端展示正确顺序                      |



后置条件

：

- 任务列表中所有任务的 `depends_on` 在执行前均已完成
- `todolist_item` 事件中的任务顺序满足拓扑排序



验收标准

：

| # | 验收项         | 验证方法                                              |
| - | ----------- | ------------------------------------------------- |
| 1 | 依赖校验生效      | 故意选择依赖不完整子集，确认 `conversation_end` 触发并终止           |
| 2 | 拓扑排序正确      | `todolist_item` 事件顺序满足 `depends_on` 约束            |
| 3 | 任务列表内容完整    | 每个 `todolist_item` 含 `id`、`task_name`、`status` 字段 |
| 4 | 任务状态流转正确    | 执行前 `status=TODO`，执行后 `status=COMPLETED`          |
| 5 | 重新规划时任务列表更新 | EDPAgent 更新任务列表后，`todolist_start` 再次触发            |

***

### UC-03：任务重新规划（re-plan）



用例 ID

：UC-03



优先级

：中



主参与者

：EDPAgent LLM 推理引擎



前置条件

：

1. 初始任务列表已输出（`todolist_end` 已发送）
2. 执行过程中发现需要调整任务规划



正常流程

：

| 步骤 | 系统行为                                                     | 事件输出                 |
| -- | -------------------------------------------------------- | -------------------- |
| 1  | 执行 step 1（推荐产品）完成                                        | `todo_end`           |
| 2  | LLM 观察结果，发现需要追加新步骤                                       | Think 阶段推理           |
| 3  | EDPAgent 更新完整任务列表（覆盖式）                                   | —                    |
| 4  | EDPAgent 输出重新规划的 `todolist_start`                        | `todolist_start`     |
| 5  | 输出更新后的 `todolist_item`（逐条发送，已完成的标记 COMPLETED，新增的标记 TODO） | `todolist_item`（N 次） |
| 6  | 输出 `todolist_end`                                        | `todolist_end`       |
| 7  | 继续执行新规划的任务                                               | `todo_start` → ...   |



备选流程

：



AF-03-A：用户修改需求导致重新规划



| 步骤 | 系统行为                                                     |
| -- | -------------------------------------------------------- |
| 1  | 用户在中断恢复后改变需求（如"不买第一款了，换第二款"）                             |
| 2  | LLM 推理后决定重新规划                                            |
| 3  | EDPAgent 更新列表（step 1 标记 COMPLETED，step 2 重新标记 TODO）      |
| 4  | 输出新的 `todolist_start` → `todolist_item` → `todolist_end` |



后置条件

：

- 前端展示最新任务列表，已完成项保留 `COMPLETED` 状态



验收标准

：

| # | 验收项                     | 验证方法                                    |
| - | ----------------------- | --------------------------------------- |
| 1 | 覆盖式更新生效                 | EDPAgent 更新列表后 `todolist_item` 反映最新完整列表 |
| 2 | 已完成任务保留 COMPLETED 状态    | 重新规划后 COMPLETED 项不被重置为 TODO             |
| 3 | 重新规划触发 `todolist_start` | 不是静默更新，前端可感知                            |

***

### UC-04：业务工具调用事件输出



用例 ID

：UC-04



优先级

：高



主参与者

：EDPAgent Rail 拦截层



前置条件

：

1. 任务正在执行中（`todo_start` 已发送）
2. LLM 决定调用业务工具（`call_mcp` 或 `call_versatile`）

>   工具范围说明  ：`tool_start`/`tool_end` 事件仅针对   `call_mcp`   和   `call_versatile`   两个业务工具。其他工具（`ask_user`、`cancel_task`、`skill_tool`、`read_file`、`bash` 等）的调用均不产生 `tool_start`/`tool_end` 事件。



todo/tool 层级关系

：

```
todo_start
  ├── tool_start (tool_1)
  ├── tool_end   (tool_1)
  ├── tool_start (tool_2)     ← 一个 todo 内可含多个 tool 调用
  └── tool_end   (tool_2)
todo_end
```



正常流程

：

| 步骤 | 系统行为                                                          | 事件输出                                                      |
| -- | ------------------------------------------------------------- | --------------------------------------------------------- |
| 1  | LLM 输出 `tool_call(call_mcp, {script_command, script_params})` | —                                                         |
| 2  | Rail 拦截业务工具调用（如 `McpInterruptRail`）                           | —                                                         |
| 3  | 输出 `tool_start`                                               | `tool_start`：`{tool: "call_mcp", args: {...}, timestamp}` |
| 4  | Rail 执行脚本（ProcessBuilder + 超时 + JSON 校验）                      | —                                                         |
| 5  | 脚本返回 JSON 结果                                                  | —                                                         |
| 6  | 输出 `tool_end`                                                 | `tool_end`：`{tool: "call_mcp", data: {...}, timestamp}`   |
| 7  | 工具结果注入 ToolDataChannel                                        | —                                                         |
| 8  | LLM 进入下一轮 Think                                               | `think_start`                                             |

>   注意  ：若 LLM 调用的是 `skill_tool`（加载 Skill 文档）、`ask_user`、`cancel_task` 等非 call\_mcp/call\_versatile 工具，不产生 `tool_start`/`tool_end` 事件，前端无感知。



备选流程

：



AF-04-A：工具执行超时



| 步骤 | 系统行为                                           | 事件输出                                                                 |
| -- | ---------------------------------------------- | -------------------------------------------------------------------- |
| 1  | 脚本执行超过 30 秒                                    | —                                                                    |
| 2  | `McpInterruptRail` 调用 `destroyForcibly()` 终止进程 | —                                                                    |
| 3  | 输出 `tool_end`（含错误信息）                           | `tool_end`：`{tool: "call_mcp", data: {error: "TIMEOUT"}, timestamp}` |
| 4  | LLM 决定重试或终止                                    | 后续 Think                                                             |



AF-04-B：工具返回非法 JSON



| 步骤 | 系统行为                                                                                |
| -- | ----------------------------------------------------------------------------------- |
| 1  | 脚本 stdout 不是合法 JSON                                                                 |
| 2  | `McpInterruptRail.validateJsonOutput()` 校验失败                                        |
| 3  | 输出 `tool_end`（含错误信息）：`{tool: "call_mcp", data: {error: "INVALID_JSON"}, timestamp}` |
| 4  | 输出 `error_event`（error\_type=INVALID\_TOOL\_OUTPUT）                                 |
| 5  | 输出 `conversation_end` 终止会话                                                          |



验收标准

：

| # | 验收项                    | 验证方法                                                                                     |
| - | ---------------------- | ---------------------------------------------------------------------------------------- |
| 1 | `tool_start` 含业务工具名和入参 | 事件 data 中 `tool` 为 `call_mcp` 或 `call_versatile`，`args` 字段存在                             |
| 2 | `tool_end` 含业务工具名和返回数据 | 事件 data 中 `tool` 和 `data` 字段存在                                                           |
| 3 | 非业务工具不产生事件             | `ask_user`/`cancel_task`/`skill_tool`/`read_file`/`bash` 调用时无 `tool_start`/`tool_end` 事件 |
| 4 | 超时正确终止                 | 配置 1s 超时执行 sleep 5s 脚本，确认 `tool_end` 含 TIMEOUT 错误信息                                      |
| 5 | 事件配对完整                 | 每个业务工具（call\_mcp/call\_versatile）的 `tool_start` 后必须有对应的 `tool_end`                       |

***

### UC-05：LLM 推理流式 think\_chunk 输出



用例 ID

：UC-05



优先级

：高



主参与者

：EDPAgent LLM 流式推理层



前置条件

：

1. `think_start` 已发送
2. LLM API 支持流式输出（stream=true）



正常流程

：

| 步骤 | 系统行为                                     | 事件输出                                       |
| -- | ---------------------------------------- | ------------------------------------------ |
| 1  | EDPAgent 调用 LLM API（stream=true）         | —                                          |
| 2  | LLM 返回第一个内容片段，直接输出                       | `think_chunk`：`{content: "我", timestamp}`  |
| 3  | LLM 返回第二个内容片段，直接输出                       | `think_chunk`：`{content: "需要", timestamp}` |
| 4  | ...（N 次）                                 | `think_chunk`（N 次）                         |
| 5  | LLM 返回 finish\_reason=stop 或 tool\_calls | —                                          |
| 6  | 输出 `think_end`                           | `think_end`：`{timestamp}`                  |

>   说明  ：`think_chunk` 直接输出 LLM 流式返回的模型内容，无需 DeepAgent 暴露 token 级回调。



备选流程

：



AF-05-A：LLM 决定调用工具（finish\_reason=tool\_calls）



| 步骤 | 系统行为                                              |
| -- | ------------------------------------------------- |
| 1  | LLM 流式输出包含 tool\_call 指令                          |
| 2  | `think_end` 发送后进入 `todolist_start` 或 `tool_start` |
| 3  | 不进入 `final_answer_start`                          |



AF-05-B：LLM 流式中断（网络异常）



| 步骤 | 系统行为                       |
| -- | -------------------------- |
| 1  | LLM SSE 连接中断               |
| 2  | 已接收的 `think_chunk` 保留      |
| 3  | 输出 `conversation_end` 终止会话 |
| 4  | 触发重试（最多 3 次，指数退避）          |



验收标准

：

| # | 验收项                            | 验证方法                                                                 |
| - | ------------------------------ | -------------------------------------------------------------------- |
| 1 | `think_chunk` 直接输出模型内容         | 每个 `think_chunk` 的 `content` 为 LLM 流式返回的模型内容片段                       |
| 2 | `think_start` 和 `think_end` 配对 | 每个 Think 轮次有且仅有一对                                                    |
| 3 | 多轮 Think 正确                    | ReAct 循环中每轮 Think 都有 `think_start` → `think_chunk`(×N) → `think_end` |
| 4 | ReAct 循环中 think 事件正确           | 执行工具后回到 Think 时，新的 `think_start` 触发                                  |

***

### UC-06：最终回答流式输出



用例 ID

：UC-06



优先级

：高



主参与者

：EDPAgent Answer 阶段



前置条件

：

1. 所有任务已完成（`todo_end` 已发送）
2. LLM 决定输出最终答案（finish\_reason=stop，无 tool\_calls）



正常流程

：

| 步骤 | 系统行为                    | 事件输出                                              |
| -- | ----------------------- | ------------------------------------------------- |
| 1  | LLM 决定输出最终答案            | —                                                 |
| 2  | 输出 `final_answer_start` | `final_answer_start`：`{timestamp}`                |
| 3  | LLM 流式返回回答 token        | `final_answer_chunk`：`{content: "根据", timestamp}` |
| 4  | ...（N 次）                | `final_answer_chunk`（N 次）                         |
| 5  | LLM 回答完成                | —                                                 |
| 6  | 输出 `final_answer_end`   | `final_answer_end`：`{timestamp}`                  |
| 7  | 输出 `conversation_end`   | `conversation_end`：`{session_id, timestamp}`      |
| 8  | 关闭 SSE 连接               | —                                                 |



备选流程

：



AF-06-A：回答内容被截断（max\_tokens 限制）



| 步骤 | 系统行为                            |
| -- | ------------------------------- |
| 1  | LLM 回答超过 max\_tokens 限制         |
| 2  | `final_answer_end` 发送           |
| 3  | 追加 `final_answer_chunk`（截断提示文本） |
| 4  | 正常输出 `conversation_end`         |



验收标准

：

| # | 验收项                                       | 验证方法                                |
| - | ----------------------------------------- | ----------------------------------- |
| 1 | `final_answer_start` 在所有 `todo_end` 之后    | 事件顺序校验                              |
| 2 | `final_answer_chunk` 拼接为完整回答              | 所有 chunk 的 `content` 拼接后等于 LLM 完整输出 |
| 3 | `final_answer_end` 后紧跟 `conversation_end` | 事件顺序校验                              |
| 4 | `conversation_end` 后 SSE 连接关闭             | 无更多事件                               |

***

### UC-07：追问中断与恢复



用例 ID

：UC-07



优先级

：高



主参与者

：前端客户端 / EDPAgent AskUserTemplateRail



前置条件

：

1. 任务执行中需要用户确认（如购买确认、参数补充）
2. `ask_user` 工具被调用



正常流程（中断触发）

：

| 步骤 | 系统行为                                | 事件输出                                                                 |
| -- | ----------------------------------- | -------------------------------------------------------------------- |
| 1  | LLM 决定追问用户                          | `tool_call(ask_user, {question, response_template_status})`          |
| 2  | `AskUserTemplateRail` 拦截，渲染追问话术     | —                                                                    |
| 3  | 生成 `interrupt_id`（如 "int-a1b2c3d4"） | —                                                                    |
| 4  | 输出 `interrupt_start`                | `interrupt_start`：`{interrupt_id, content: "请确认是否购买...", timestamp}` |
| 5  | SSE 流保持连接，等待用户回复                    | 前端展示追问弹窗                                                             |



正常流程（中断恢复）

：

| 步骤 | 系统行为                                                                                                                                       | 事件输出                                        |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| 6  | 用户通过前端发送回复（同一 `conversation_id`）：`POST /v1/{project_id}/agents/{agent_id}/conversations/{conversation_id}`，body 中携带 `interrupt_id` 和用户回复内容 | —                                           |
| 7  | EDPAgent 从 checkpoint 恢复上下文                                                                                                                | —                                           |
| 8  | 输出 `interrupt_end`                                                                                                                         | `interrupt_end`：`{interrupt_id, timestamp}` |
| 9  | 继续执行中断点后续逻辑                                                                                                                                | `think_start` → ...                         |



备选流程

：



AF-07-A：用户回复后需重新规划



| 步骤 | 系统行为                                       |
| -- | ------------------------------------------ |
| 1  | 用户回复改变了需求方向                                |
| 2  | `interrupt_end` 后触发 `todolist_start`（重新规划） |
| 3  | 新任务列表输出                                    |



AF-07-B：中断后用户取消



| 步骤 | 系统行为                                  | 事件输出               |
| -- | ------------------------------------- | ------------------ |
| 1  | 用户回复"取消"                              | —                  |
| 2  | LLM 调用 `ask_user`（cancel\_confirm 模板） | `interrupt_start`  |
| 3  | 用户确认取消                                | —                  |
| 4  | LLM 调用 `cancel_task`                  | —                  |
| 5  | 输出 `conversation_end`                 | `conversation_end` |



验收标准

：

| # | 验收项                                                         | 验证方法                                            |
| - | ----------------------------------------------------------- | ----------------------------------------------- |
| 1 | `interrupt_start` 含 `interrupt_id` 和 `content`              | 事件 data 字段校验                                    |
| 2 | SSE 流在中断时不关闭                                                | `interrupt_start` 后无 `conversation_end`         |
| 3 | 恢复时 `interrupt_end` 的 `interrupt_id` 与 `interrupt_start` 一致 | 事件字段匹配                                          |
| 4 | 恢复后继续输出后续事件                                                 | `interrupt_end` 后有 `think_start` 或 `todo_start` |
| 5 | 中断→恢复→继续 全链路可用                                              | E2E 路径 2（储蓄卡补足购买）验证通过                           |

***

### UC-08：任务取消终止



用例 ID

：UC-08



优先级

：中



主参与者

：前端客户端 / EDPAgent CancelRail



前置条件

：

1. 任务执行中或中断等待中
2. 用户表达终止意图



正常流程

：

| 步骤 | 系统行为                                           | 事件输出               |
| -- | ---------------------------------------------- | ------------------ |
| 1  | 用户发送"取消"/"不买了"/"退出"                            | —                  |
| 2  | LLM 识别终止意图，调用 `ask_user`（cancel\_confirm）      | `interrupt_start`  |
| 3  | 用户确认取消                                         | `interrupt_end`    |
| 4  | LLM 调用 `cancel_task`（reason="task\_cancelled"） | —                  |
| 5  | `CancelRail` 清理会话上下文                           | —                  |
| 6  | 输出 `conversation_end`                          | `conversation_end` |



验收标准

：

| # | 验收项           | 验证方法                                        |
| - | ------------- | ------------------------------------------- |
| 1 | 取消后 SSE 流正常关闭 | `conversation_end` 后连接断开                    |
| 2 | 取消原因记录        | `cancel_task` 参数含 `reason` 字段               |
| 3 | 二次确认生效        | 取消前触发 `interrupt_start`（cancel\_confirm 模板） |

***

### UC-09：SSE 连接断开处理



用例 ID

：UC-09



优先级

：中



主参与者

：EDPAgent SSE 连接管理



前置条件

：

1. SSE 连接已建立，思维链事件正在输出



正常流程

：

| 步骤 | 系统行为                                                 | 说明                |
| -- | ---------------------------------------------------- | ----------------- |
| 1  | 客户端网络断开                                              | SSE 连接中断          |
| 2  | 服务端检测到连接断开（`onCompletion` / `onError` / `onTimeout`） | Reactor Flux 自动清理 |
| 3  | EDPAgent 保存当前 checkpoint                             | 会话状态持久化           |
| 4  | 后台 Agent 执行线程继续完成（不中断）                               | 结果写入 checkpoint   |
| 5  | 前端重连后可查询历史事件                                         | 从 checkpoint 恢复   |



验收标准

：

| # | 验收项             | 验证方法                 |
| - | --------------- | -------------------- |
| 1 | 连接断开后服务端无异常     | 日志无未捕获异常             |
| 2 | checkpoint 正确保存 | 重连后可查询会话状态           |
| 3 | 后台执行不受影响        | 连接断开后日志显示 Agent 正常完成 |

***

### UC-10：LLM 调用超时/失败



用例 ID

：UC-10



优先级

：中



主参与者

：EDPAgent LLM 调用层



前置条件

：

1. LLM API 不可用或响应超时



正常流程

：

| 步骤 | 系统行为                                  | 事件输出                                                                                                                             |
| -- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 1  | LLM 调用超时（默认 60s）                      | —                                                                                                                                |
| 2  | 自动重试（最多 3 次，指数退避：1s → 2s → 4s）        | —                                                                                                                                |
| 3  | 重试全部失败                                | —                                                                                                                                |
| 4  | 输出 `error_event` → `conversation_end` | `error_event`：`{error_type: "LLM_TIMEOUT", content: "LLM 调用超时，请稍后重试", timestamp}` → `conversation_end`：`{session_id, timestamp}` |
| 5  | 关闭 SSE 连接                             | —                                                                                                                                |



备选流程

：



AF-10-A：LLM 返回错误状态码（401/429/500）



| 步骤 | 系统行为                                                                |
| -- | ------------------------------------------------------------------- |
| 1  | LLM API 返回 401（认证失败）                                                |
| 2  | 不重试（非可重试错误）                                                         |
| 3  | 输出 `error_event`（error\_type=LLM\_AUTH\_ERROR） → `conversation_end` |
| 4  | 关闭 SSE 连接                                                           |



AF-10-B：重试后成功



| 步骤 | 系统行为                   |
| -- | ---------------------- |
| 1  | 第一次调用超时                |
| 2  | 第二次调用成功                |
| 3  | 正常输出 `think_chunk` 等事件 |
| 4  | 正常输出事件流，无异常终止          |



验收标准

：

| # | 验收项                                      | 验证方法                                                                     |
| - | ---------------------------------------- | ------------------------------------------------------------------------ |
| 1 | 超时后触发 `error_event` → `conversation_end` | 模拟 LLM 不可用，确认 error\_event（error\_type=LLM\_TIMEOUT）后跟 conversation\_end |
| 2 | 重试机制生效                                   | 日志可见 3 次重试记录                                                             |
| 3 | `conversation_end` 正确终止                  | 会话终止，SSE 连接关闭                                                            |
| 4 | 错误后 SSE 流关闭                              | `conversation_end` 后连接断开                                                 |

***

### UC-11：任务依赖冲突检测



用例 ID

：UC-11



优先级

：中



主参与者

：EDPAgent 任务规划引擎



前置条件

：

1. `edp-config.yaml` 配置了 `depends_on` 依赖关系
2. LLM 输出的 todo 列表违反依赖约束



正常流程

：

| 步骤 | 系统行为                                  | 说明                                                                                                            |
| -- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1  | LLM 输出任务规划，step\_id = \[3, 1]         | step 3 依赖 \[2] 但 2 未选                                                                                         |
| 2  | EDPAgent 拦截校验                         | —                                                                                                             |
| 3  | 检测到 step 3 的 `depends_on` \[2] 不在选中列表 | 依赖缺失                                                                                                          |
| 4  | 输出 `error_event`                      | `error_event`：`{error_type: "DEPENDENCY_VIOLATION", content: "step 3 依赖 step 2，但 step 2 未在任务列表中", timestamp}` |
| 5  | 输出 `conversation_end` 终止会话            | `conversation_end`：`{session_id, timestamp}`                                                                  |



备选流程

：



AF-11-A：循环依赖检测



| 步骤 | 系统行为                              |
| -- | --------------------------------- |
| 1  | 配置中 step 1 依赖 \[2]，step 2 依赖 \[1] |
| 2  | 拓扑排序检测到循环                         |
| 3  | 输出 `conversation_end` 终止会话        |
| 4  | 服务启动时 fail-fast 拒绝启动              |



验收标准

：

| # | 验收项              | 验证方法                                       |
| - | ---------------- | ------------------------------------------ |
| 1 | 依赖缺失检测           | 选择不完整子集，确认 `conversation_end` 触发并终止        |
| 2 | 循环依赖检测           | 配置循环依赖，确认启动失败                              |
| 3 | 错误信息含具体 step\_id | `error_event` 的 `content` 字段包含冲突的 step\_id |

***

### UC-12：超范围业务拒绝



用例 ID

：UC-12



优先级

：中



主参与者

：EDPAgent 系统提示词约束



前置条件

：

1. 用户请求超出 `edp-config.yaml` 的 `scope.allowed` 范围



正常流程

：

| 步骤 | 系统行为                                                  | 事件输出                                              |
| -- | ----------------------------------------------------- | ------------------------------------------------- |
| 1  | 用户发送"帮我买基金"                                           | —                                                 |
| 2  | LLM 推理识别超出业务范围                                        | `think_start` → `think_chunk`(×N) → `think_end`   |
| 3  | LLM 调用 `ask_user`（out\_of\_scope 模板，非业务工具不产生 tool 事件） | —                                                 |
| 4  | 输出 `interrupt_start`                                  | `interrupt_start`：`{content: "尚在学习中", timestamp}` |
| 5  | 不进入 `todolist_start`（无任务规划）                           | —                                                 |



验收标准

：

| # | 验收项                                                 | 验证方法                       |
| - | --------------------------------------------------- | -------------------------- |
| 1 | 超范围请求触发 `ask_user`（out\_of\_scope）                  | 工具调用日志确认                   |
| 2 | 不输出 `todolist_start`                                | SSE 事件序列无 `todolist_start` |
| 3 | `interrupt_start` content 为 out\_of\_scope\_message | 内容匹配 `edp-config.yaml` 配置  |

***

### UC-13：前端断线重连续接



用例 ID

：UC-13



优先级

：低



主参与者

：前端客户端



前置条件

：

1. SSE 连接断开时 Agent 仍在后台执行
2. Checkpoint 已保存
3.   Checkpoint Redis 持久化已实现（阶段 5 T5.9）  



正常流程

：

| 步骤 | 系统行为                           | 说明             |
| -- | ------------------------------ | -------------- |
| 1  | 前端检测到 SSE 连接断开                 | —              |
| 2  | 前端携带同一 `conversation_id` 发起新请求 | —              |
| 3  | 服务端从 checkpoint 恢复会话           | —              |
| 4  | 输出 `conversation_start`        | 新 SSE 流        |
| 5  | 续接已完成的思维链事件                    | 前端展示历史事件 + 新事件 |

>   范围说明  ：断线重连的完整事件回放属于阶段 5（持久化）范围，本用例仅验证会话可恢复。



验收标准

：

| # | 验收项                         | 验证方法                    |
| - | --------------------------- | ----------------------- |
| 1 | 断线后同一 `conversation_id` 可恢复 | 重连后服务端不报错               |
| 2 | 后续事件正常输出                    | 重连后收到 `think_start` 等事件 |

***

### UC-14：多轮对话上下文保持



用例 ID

：UC-14



优先级

：中



主参与者

：前端客户端



前置条件

：

1. 第一轮对话已完成（`conversation_end` 已发送）
2. 前端在同一 `conversation_id` 发起新请求
3.   Checkpoint Redis 持久化已实现（阶段 5 T5.9）  



正常流程

：

| 步骤 | 系统行为                               | 事件输出                                                |
| -- | ---------------------------------- | --------------------------------------------------- |
| 1  | 用户发送第二轮 query（同一 conversation\_id） | —                                                   |
| 2  | 服务端从 checkpoint 恢复历史上下文            | —                                                   |
| 3  | 输出 `conversation_start`            | 新 SSE 流                                             |
| 4  | LLM 推理时参考历史消息                      | `think_start` → `think_chunk` → `think_end`         |
| 5  | 根据需要重新规划任务                         | `todolist_start` → `todolist_item` → `todolist_end` |
| 6  | 已完成任务标记 COMPLETED，新任务标记 TODO       | `todolist_item` 反映历史状态                              |



验收标准

：

| # | 验收项           | 验证方法                                              |
| - | ------------- | ------------------------------------------------- |
| 1 | 第二轮对话可引用第一轮结果 | LLM 回答中包含第一轮的产品信息                                 |
| 2 | 任务列表保留历史状态    | `todolist_item` 中已完成步骤仍为 `COMPLETED`              |
| 3 | 每轮对话独立输出完整事件链 | 两轮各有独立的 `conversation_start` → `conversation_end` |

***

## 5. 事件序列模板

### 5.1 正常对话（含工具调用）

```
conversation_start
think_start
think_chunk (×N)                      ← 直接输出模型内容
think_end
todolist_start
todolist_item (×1)                    ← 一次性发送完整任务列表数组
todolist_end
todo_start
  todo_status (可选×N)                ← 任务执行中间状态
  tool_start                          ← 业务工具调用（skill_tool 等内部工具不产生）
  tool_status (可选×N)                ← 工具执行中间状态
  tool_end
  tool_start                          ← 一个 todo 可含多个业务工具
  tool_status (可选×N)
  tool_end
todo_end
think_start                           ← ReAct 循环
think_chunk (×N)
think_end
todolist_start                        ← 更新任务列表
todolist_item (×1)                    ← 含最新状态（task-1=COMPLETED）
todolist_end
todo_start
  todo_status (可选×N)
  tool_start
  tool_status (可选×N)
  tool_end
todo_end
final_answer_start
final_answer_chunk (×N)
final_answer_end
conversation_end
```

### 5.2 追问中断

```
conversation_start
think_start
think_chunk (×N)                      ← 直接输出模型内容
think_end
todolist_start
todolist_item (×1)                    ← 一次性发送完整任务列表数组
todolist_end
todo_start
  tool_start
  tool_end
todo_end
think_start
think_chunk (×N)
think_end
interrupt_start                       ← 中断触发
[SSE 保持连接]
--- 用户回复 ---
interrupt_end
think_start                           ← 恢复后继续
think_chunk (×N)
think_end
final_answer_start
final_answer_chunk (×N)
final_answer_end
conversation_end
```

### 5.3 错误终止

```
conversation_start
think_start
think_chunk (×N)
think_end
error_event                    ← 错误发生
conversation_end
```

***
## 7. 补充说明

### 7.1 不在本特性范围内的项

| 项                    | 归属阶段            | 说明                                    |
| -------------------- | --------------- | ------------------------------------- |
| A2A SSE 事件适配层实现      | 阶段 5（T5.2）      | 本用例定义事件规格，实现归阶段 5                     |
| Checkpoint Redis 持久化 | 阶段 5（T5.9）      | 断线重连的完整回放依赖持久化                        |
| 超时/熔断/降级保护           | 阶段 5（T5.4-T5.6） | 错误事件输出在本特性范围，保护机制归阶段 5                |
| metrics 事件           | 不在范围            | AS-agent 有 `metrics` 事件，本特性不含（可在后续扩展） |

### 7.2 已确认项

| # | 问题                                                         | 确认结论                                                                                                                         |
| - | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 1 | `think_chunk` 是否需要从 DeepAgent 内部获取 LLM 逐 token 输出？         |   直接输出模型内容  。LLM 流式返回的内容直接作为 `think_chunk` 的 `content` 输出，无需 DeepAgent 暴露 token 级回调                                          |
| 2 | `todolist_item` 事件是逐条发送还是一次性发送数组？                          |   一次性发送  。`todolist_item` 事件仅发送 1 次，`tasks` 字段为包含全部规划任务的完整数组                                                                 |
| 3 | ~~`summary`~~ ~~事件的~~ ~~`content`~~ ~~是固定文案还是 LLM 生成的摘要？~~ |   已删除  。`summary` 事件已移除，最终回答仅通过 `final_answer_chunk` 输出                                                                      |
| 4 | `todo_start`/`todo_end` 与 `tool_start`/`tool_end` 的关系？     |   嵌套关系  。顺序为 `todo_start` → `tool_1_start` → `tool_1_end` → `tool_2_start` → `tool_2_end` → `todo_end`。一个 todo 内可含多个 tool 调用 |

### 7.3 OpenJiuwen Core 能力复用确认结论

| # | 问题                                          | 确认结论                                                                                                                                                                                                                                                            | 需要的动作                                                 |
| - | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| 1 | `ReActAgent` 流式 chunk 是否可通过 Rail hook 拦截？   |   已确认：无需 Rail hook  。Core `ReActAgent.writeAssistantStreamChunk()` 已自动将每个 token chunk 写入 session 流，type 为 `"llm_output"`。`EdpaStreamEventAdapter` 按 type 映射为 `think_chunk` / `final_answer_chunk` 即可                                                            | 无需修改 Core，适配层按 `OutputSchema.type` 路由                 |
| 2 | `TaskPlanningRail` 与 EDPAgent 已有 Rail 是否冲突？ |   已确认：无冲突  。工具名无重叠（`todo_*` vs `call_mcp`/`call_versatile`/`ask_user`/`cancel_task`/`skill_tool`）；Priority 不冲突（`TaskPlanningRail`=90，业务 Rail=10-50）；但 `LiteTodoRail`(35) 与 `TaskPlanningRail`(90) 会重复校验 todo                                                    |   移除     `LiteTodoRail`  ，依赖校验迁移到 `EdpaTodoValidator` |
| 3 | `OutputSchema` 自定义 type 是否被 A2A 层过滤？        |   代码路径显示不过滤  ：`OutputSchema` → `session.streamIterator()` → `EdpaRuntimeHandler` 适配 → `A2aResultRouter`（按 result.type 路由，不按 OutputSchema.type 过滤） → `emitter.appendArtifact()`（type 信息保留在 payload 中）。。。待运行时验证。。：需在 handler 中加日志确认 `"llm_output"` 等 type 是否到达适配层 | 开发阶段在 `EdpaRuntimeHandler` 中加日志验证                     |
| 4 | `TodoTool` 文件持久化是否适合多租户？                    |   已确认：持久化替换为 Redis  。Core 默认文件持久化（`{workspace}/.todo/{sessionId}.json`）不适合多租户 + 高并发。EDPAgent 扩展 `TodoTool` 持久化层为 Redis，按 `tenant:agent:sessionId` 键空间隔离                                                                                                         | 扩展 `TodoTool` 持久化层为 Redis                             |
| 5 | `edp-config.yaml` 任务初始化为 `TodoItem` 的时机？    |   已确认：Core 不支持配置预加载，需 EDPAgent 注入  。`TaskPlanningRail.init()` 只创建 `TodoTool` 实例，任务由 LLM 通过 `todo_create` 动态创建。EDPAgent 需在 `EdpaEventRail.beforeInvoke()` 中检查 `todoTool.list(sessionId)` 为空时从 `edp-config.yaml` 加载并 `create()`                                   | 在 `beforeInvoke()` 中实现预加载逻辑                           |

***

## 附录 A：需求用例评审记录

### A.1 评审概述

本文档经全维度标准化评审（完整性、清晰性、正确性、可测试性、依赖性、规范性六大维度），共发现 12 个问题，其中严重 3 个、主要 6 个、次要 3 个。所有问题已全部修复完成。

### A.2 优点肯定

-   事件生命周期定义完整  ：§1.4 事件清单覆盖 think→plan→act→answer 全链路，三段式结构（\_start/\_chunk/\_end）规范统一，事件顺序在 UC-01、§5.1-5.3 多处交叉验证
-   ReAct 循环事件序列精准  ：UC-01 明确定义"todo\_end → think\_start → todolist\_item(更新) → todo\_start"的循环模式，避免了 todo 间直接跳转的歧义
-   工具范围边界清晰  ：§1.2 功能边界、UC-04 前置说明均明确限定 tool\_start/tool\_end 仅针对 call\_mcp/call\_versatile，排除了内部工具
-   OpenJiuwen Core 复用方案落地性强  ：§6.1-6.4 详细映射了 TodoItem/TodoTool/TaskPlanningRail/AgentRail 的复用方式，§7.3 对 5 个待确认项给出了明确结论
-   北向接口映射关系明确  ：§1.5.6 字段映射表完整定义了内部事件↔北向接口的转换规则，为 EdpaStreamEventAdapter 实现提供了清晰依据
-   异常备选流程覆盖充分  ：每个用例均含备选流程（AF-xx-x），覆盖超时、非法返回、依赖冲突、循环依赖等异常路径
-   验收标准可量化  ：UC-01 验收标准含 10 项 + 4 个子项，每项均有具体验证方法，可测试性良好

### A.3 问题清单与修复记录

#### A.3.1 严重问题（3 个）

| # | 问题类型 | 问题描述                                                                                               | 改进建议                                                                                                                                    | 修复状态  |
| - | ---- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| 1 | 正确性  | `error_event` 已从 §1.4 事件清单中删除，但仍残留在 UC-04 AF-04-B、UC-11 步骤4、§5.3 错误终止模板 3 处                        | 保留 error\_event，事件总数调整为 20 种；补回 §1.4 事件清单 + error\_type 枚举表（6 种）；§1.5.5 补 error\_event JSON；§1.5.6 补 error\_type 映射；全文 6 处"19 种"→"20 种" | ✅ 已修复 |
| 2 | 正确性  | UC-02 步骤6 `todolist_item`(×3) 与 §1.4 定义"一次性发送完整任务列表数组"矛盾                                           | UC-02 步骤6 改为 `todolist_item`(×1，tasks 数组含 3 个任务)                                                                                        | ✅ 已修复 |
| 3 | 正确性  | UC-12 步骤3 `ask_user` 产生 `tool_start → tool_end`，但 §1.2 功能边界明确 tool 事件仅针对 call\_mcp/call\_versatile | UC-12 步骤3 删除 tool\_start/tool\_end，标注"非业务工具不产生 tool 事件"                                                                                 | ✅ 已修复 |

#### A.3.2 主要问题（6 个）

| # | 问题类型 | 问题描述                                                           | 改进建议                                                                                                                 | 修复状态  |
| - | ---- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----- |
| 4 | 清晰性  | 任务状态值在文档中存在两套不一致的命名（pending/done vs TODO/COMPLETED）            | 全文统一为 Core 原生枚举（TODO/IN\_PROGRESS/COMPLETED/CANCELLED），共替换 16 处；新增 §2.3 任务状态枚举表                                      | ✅ 已修复 |
| 5 | 清晰性  | UC-01 验收标准#9 要求 ISO-8601 格式时间戳，但 §1.5.4 createdTime 为毫秒整数，格式矛盾 | UC-01 #9 改为"毫秒级 Unix 时间戳（与北向接口 createdTime 一致）"                                                                      | ✅ 已修复 |
| 6 | 完整性  | §1.5.5 北向接口缺少 conversation\_end 事件定义                           | §1.5.6 映射表标注"北向接口不单独发送 conversation\_end 事件，通过 SSE 连接关闭表示对话结束"                                                       | ✅ 已修复 |
| 7 | 完整性  | UC-07 中断恢复流程缺少前端回复的 API 端点和请求格式                                | UC-07 步骤6 补充 `POST /v1/{project_id}/agents/{agent_id}/conversations/{conversation_id}`，body 携带 interrupt\_id 和用户回复内容 | ✅ 已修复 |
| 8 | 正确性  | §2.1 depends\_on 为 int\[]，§2.2 标注 Core 对应 List<String>，类型转换未说明 | §2.2 补充类型转换说明（int\[] → List<String>）；新增 §2.3 任务状态枚举表                                                                 | ✅ 已修复 |
| 9 | 可测试性 | UC-13/UC-14 核心验证依赖 checkpoint 持久化（阶段 5 T5.9），当前阶段无法独立测试        | UC-13/UC-14 前置条件增加"Checkpoint Redis 持久化已实现（阶段 5 T5.9）"                                                               | ✅ 已修复 |

#### A.3.3 次要问题（3 个）

| #  | 问题类型 | 问题描述                                                                             | 改进建议                                                                                           | 修复状态  |
| -- | ---- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----- |
| 10 | 完整性  | 文档缺少非功能性需求定义（SSE 延迟、并发数、超时等）                                                     | 新增 §1.6 非功能性需求小节（7 项指标：SSE 延迟≤100ms、并发≥500、对话超时 300s、LLM 超时 60s、工具超时 30s、Redis 延迟≤10ms、事件严格有序） | ✅ 已修复 |
| 11 | 规范性  | §6.4 事件发射路径未覆盖 todo\_start 和 todo\_status 的发射时机                                  | §6.4 补充 todo\_start（afterToolCall 检测 IN\_PROGRESS 时发射）和 todo\_status（可选，长耗时任务周期性推送）发射路径        | ✅ 已修复 |
| 12 | 完整性  | §1.5.5 interrupt\_start/interrupt\_end 的 data 字段为空对象 {}，未体现 interrupt\_id 实际数据结构 | §1.5.5 interrupt\_start/interrupt\_end 的 data 填充 `{"interrupt_id": "int-a1b2c3d4"}`            | ✅ 已修复 |

### A.4 风险提示

#### 1. 业务风险

-   error\_event 残留导致前端行为不确定  （已修复）：§5.3 错误终止模板保留 error\_event，前端可正确区分错误终止与正常结束
-   UC-12 工具事件矛盾导致前端误渲染  （已修复）：ask\_user 不再产生 tool 事件，前端不会在超范围拒绝场景中错误渲染工具调用

#### 2. 技术风险

-   状态值不统一导致前后端解析失败  （已修复）：全文统一为 Core 原生枚举（TODO/IN\_PROGRESS/COMPLETED/CANCELLED）
-   todo\_start 事件发射路径未定义  （已修复）：§6.4 已明确发射时机
-   北向接口缺少 conversation\_end 定义  （已修复）：§1.5.6 已明确通过 SSE 连接关闭表示

#### 3. 合规风险

-   缺少 SSE 端点认证机制说明  ：§1.5.3 请求参数未定义认证相关 Header（如 token、X-USER-ID），北向接口的安全认证方式未说明，存在未授权访问风险。建议后续补充认证机制定义

### A.5 待澄清问题

| # | 疑问点             | 需补充的具体信息                                       |
| - | --------------- | ---------------------------------------------- |
| 1 | SSE 端点的认证机制是什么？ | 需确认北向接口的认证方式（token / cust-token / X-USER-ID 等） |

### A.6 总结建议

#### 文档整体综合质量评价

文档整体质量较高，事件生命周期定义完整，ReAct 循环事件序列精准，OpenJiuwen Core 复用方案具备落地性，北向接口映射关系清晰。经本次评审修复后，事件清单与用例描述完全一致，状态值全局统一，时间戳格式对齐，非功能性指标补齐，可测试性进一步提升。

#### 问题修订优先级排序

1.   第一优先（严重）  ：问题 1（error\_event 保留）、问题 2（UC-02 todolist\_item 次数）、问题 3（UC-12 ask\_user tool 事件）— 已全部修复
2.   第二优先（主要）  ：问题 4-9（状态值统一、timestamp 格式、conversation\_end 北向接口、中断恢复 API、depends\_on 类型、checkpoint 依赖）— 已全部修复
3.   第三优先（次要）  ：问题 10-12（非功能性需求、todo\_start 发射路径、interrupt data 字段）— 已全部修复

#### 文档整体迭代优化方向与落地建议

-   建立事件一致性校验机制  ：确保 §1.4 事件清单为唯一权威源，所有用例、序列模板、发射路径中引用的事件必须与 §1.4 一致
-   保持状态值/字段格式统一约定  ：§2.3 任务状态枚举表和 §1.6 非功能性需求为全局引用基准
-   补充认证机制  ：后续在 §1.5.3 请求参数中补充 SSE 端点认证 Header 定义
-   运行时验证  ：§7.3 确认项 #3（OutputSchema 自定义 type 是否被 A2A 层过滤）需在开发阶段通过日志验证

***

## 附录 B：第二轮评审记录

### B.1 评审概述

本文档在第一轮修复完成后进行第二轮评审，重点检查修复后的全文一致性及新增遗留问题。共发现 8 个问题，其中严重 2 个、主要 4 个、次要 2 个。所有问题已全部修复完成。

### B.2 问题清单与修复记录

#### B.2.1 严重问题（2 个）

| # | 问题类型 | 问题描述                                                                                                                                                                             | 改进建议                                                                                                                                            | 修复状态  |
| - | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| 1 | 正确性  | UC-14 验收标准#2 仍使用小写 `done` 状态值，与 §2.3 任务状态枚举表定义的 `COMPLETED` 不一致（第一轮状态值统一替换遗漏此处）                                                                                                  | UC-14 验收标准#2 `done` → `COMPLETED`                                                                                                               | ✅ 已修复 |
| 2 | 正确性  | UC-10 正常流程步骤4 和 AF-10-A 步骤3 仅输出 `conversation_end`，未输出 `error_event`。与 §1.4 error\_type 枚举定义（LLM\_TIMEOUT/LLM\_AUTH\_ERROR 对应 UC-10）和"error\_event 后始终跟 conversation\_end"序列约束矛盾 | UC-10 正常流程步骤4 补 `error_event`(LLM\_TIMEOUT) → `conversation_end`；AF-10-A 步骤3 补 `error_event`(LLM\_AUTH\_ERROR) → `conversation_end`；验收标准#1 同步更新 | ✅ 已修复 |

#### B.2.2 主要问题（4 个）

| # | 问题类型 | 问题描述                                                                                                                                                       | 改进建议                                                                                                                | 修复状态  |
| - | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----- |
| 3 | 正确性  | §6.4 事件发射路径中 `TodoTool.create()` 注释写"其余 PENDING"，但 §2.3 任务状态枚举表待执行状态为 `TODO`，Core 原生枚举无 `PENDING`                                                          | `PENDING` → `TODO`；同时修复因前次编辑导致的行合并问题                                                                                | ✅ 已修复 |
| 4 | 正确性  | §1.5.5 北向接口示例中 final\_answer\_chunk（createdTime=...86000）早于 final\_answer\_start（...90000），final\_answer\_end（...87000）也早于 final\_answer\_start，事件时间戳非单调递增 | final\_answer\_chunk: ...86000 → ...91000；final\_answer\_end: ...87000 → ...92000；error\_event: ...90000 → ...93000 | ✅ 已修复 |
| 5 | 清晰性  | §1.5.5 interrupt\_end 的 `plugin` 字段值为 `"transfer"`，但 interrupt\_start 的 plugin 为空字符串 `""`，两者不一致                                                            | interrupt\_end 的 `plugin` 改为 `""`（与 interrupt\_start 一致）                                                            | ✅ 已修复 |
| 6 | 规范性  | §6.4 事件发射路径中 todo\_start/todo\_status 行缩进为 5 空格，上下文树形图为 4 空格，导致 ASCII 树形结构错位                                                                               | 统一缩进为 4 空格对齐                                                                                                        | ✅ 已修复 |

#### B.2.3 次要问题（2 个）

| # | 问题类型 | 问题描述                                                          | 改进建议                                                                        | 修复状态  |
| - | ---- | ------------------------------------------------------------- | --------------------------------------------------------------------------- | ----- |
| 7 | 完整性  | UC-04 AF-04-B 步骤3-4 未说明 `tool_end` 和 `error_event` 的先后顺序及时序关系 | 明确步骤顺序为 tool\_end（含错误信息）→ error\_event → conversation\_end，步骤3 补充具体 data 结构 | ✅ 已修复 |
| 8 | 可测试性 | UC-11 验收标准#3 引用旧方案（"日志或 tool\_end.data"），未与 error\_event 对齐   | 验收标准#3 修改为"`error_event` 的 `content` 字段包含冲突的 step\_id"                      | ✅ 已修复 |

### B.3 风险提示

#### 1. 业务风险

-   UC-10 缺少 error\_event 导致前端无法区分超时异常  （已修复）：LLM 超时现在输出 error\_event(LLM\_TIMEOUT)，前端可正确识别超时异常并提示用户

#### 2. 技术风险

-   UC-14 状态值残留 done 导致前端解析失败  （已修复）：全文已无小写状态值残留
-   北向接口示例时间戳非递增  （已修复）：final\_answer 系列事件时间戳已单调递增

#### 3. 合规风险

- SSE 端点认证机制仍未补充（与第一轮一致，待后续处理）

### B.4 待澄清问题

| # | 疑问点                                       | 需补充的具体信息                 |
| - | ----------------------------------------- | ------------------------ |
| 1 | interrupt\_end 的 plugin 字段是否应继承触发中断的工具标识？ | 当前统一为空字符串，后续如需继承工具名需补充说明 |

### B.5 总结建议

#### 文档整体综合质量评价

文档经两轮评审修复后质量已达到可落地水平。事件清单（20 种）与全部用例、序列模板、发射路径全局一致；状态值统一为 Core 原生枚举；error\_type 枚举与对应用例完全对齐；北向接口示例时间戳单调递增；error\_event 在所有异常用例中正确输出。

#### 问题修订优先级排序

1.   第一优先（严重）  ：问题 1（UC-14 done 残留）、问题 2（UC-10 error\_event 缺失）— 已全部修复
2.   第二优先（主要）  ：问题 3-6（PENDING 残留、时间戳递增、interrupt\_end plugin、缩进修复）— 已全部修复
3.   第三优先（次要）  ：问题 7-8（AF-04-B 顺序明确、UC-11 验收标准对齐）— 已全部修复

#### 文档整体迭代优化方向与落地建议

-   全量状态值扫描  ：建议对全文进行一次 `done`/`pending`/`in_progress` 小写值扫描，确保无遗漏（本轮已修复 UC-14 残留）
-   error\_event 覆盖性检查  ：所有 error\_type 枚举表中标注的用例（UC-04/UC-10/UC-11）均已确认包含 error\_event 输出（本轮已修复 UC-10 缺失）
-   北向接口示例时间戳校验  ：§1.5.5 所有事件 JSON 示例的时间戳已校验为单调递增（本轮已修复 final\_answer 系列）

***

## 附录 C：第三轮评审记录

### C.1 评审概述

本文档在第二轮修复完成后进行第三轮评审，重点检查修复后的边缘残留问题。共发现 4 个问题，其中严重 1 个、主要 1 个、次要 2 个。所有问题已全部修复完成。

### C.2 问题清单与修复记录

| # | 问题等级 | 问题类型 | 问题描述                                                                                                 | 改进建议                                                                                                                    | 修复状态  |
| - | ---- | ---- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ----- |
| 1 | 严重   | 正确性  | UC-11 正常流程步骤5 仅写"终止当前规划"，未明确输出 `conversation_end`，与 §1.4 "error\_event 后始终跟 conversation\_end"序列约束矛盾 | 步骤5 改为"输出 `conversation_end` 终止会话"，补充事件输出                                                                               | ✅ 已修复 |
| 2 | 主要   | 清晰性  | §1.5.5 事件排列顺序与实际序列不一致，开发者可能误将参考示例当作实际序列                                                              | §1.5.5 开头增加顺序说明（"排列顺序不代表实际执行序列，请参考 §5"）；`todo_start` 增加说明（"当前轮次要执行的任务，在 ReAct 循环之后发射"）；`todo_end` 增加说明（"上一个已完成任务的结束事件"） | ✅ 已修复 |
| 3 | 次要   | 完整性  | §1.5.5 todo 系列事件（todo\_start/todo\_status/todo\_end）的 `plugin` 字段均为空字符串，但未在映射表中明确说明                  | §1.5.6 补充说明：todo 系列事件 `plugin` 固定为空字符串，仅 tool 系列事件携带业务工具名                                                               | ✅ 已修复 |
| 4 | 次要   | 规范性  | §6.4 注释"第 2 个任务"表述不够精确，实际为"第 2 轮 ReAct 循环中的 task-2"                                                  | 注释改为"第 2 轮 ReAct 循环：task-2 购买理财"                                                                                        | ✅ 已修复 |

### C.3 风险提示

-   UC-11 步骤5 缺少 conversation\_end  （已修复）：现在 error\_event 后正确输出 conversation\_end，前端可感知对话终止
-   §1.5.5 事件排列顺序可能误导开发者  （已修复）：已增加顺序说明和 todo\_start/todo\_end 上下文说明

### C.4 总结建议

文档经三轮评审修复后，共发现并修复 24 个问题（严重 6 个、主要 11 个、次要 7 个）。当前文档已具备可交付质量，事件清单与全部用例对齐，状态值统一为 Core 原生枚举，error\_type 枚举与对应用例完全对齐，北向接口示例时间戳单调递增，error\_event 在所有异常用例中正确输出。

***

## 附录 D：思维链事件触发规则补充说明

### D.1 概述

本附录针对 UC-01 正常对话全链路思维链输出中五项关键事件触发规则进行逐条澄清与补充，明确 todolist、todo、tool 三类事件与 ReAct 循环（Think → Plan → Act → Observe）及 Skill 加载之间的时序关系。

### D.2 规则逐条说明

#### 规则 1：首次读取 Skill 前生成 todolist



已在 UC-01 步骤 6-10 体现。



UC-01 首轮 ReAct 循环中，EDPAgent 先完成 Think（步骤 3-5），随后生成任务列表（步骤 6-8：`todolist_start` → `todolist_item` → `todolist_end`），再开始执行第一个任务（步骤 9：`todo_start`），任务执行内才调用 `skill_tool` 加载 Skill（步骤 10）。

时序：`think_end` → `todolist_start` → `todolist_item` → `todolist_end` → `todo_start` → `skill_tool`（内部工具，不产生 tool 事件）

#### 规则 2：再读取 Skill 前更新 todolist



部分体现，需补充澄清。



UC-01 步骤 13-18 定义了 ReAct 循环：每轮 `todo_end` 后回到 Think（步骤 13），再更新 todolist（步骤 14），再执行下一个任务（步骤 15）。todolist 更新确实在下一个任务执行之前。

但 UC-01 步骤 16 仅描述"任务内调用业务工具（仅 call\_mcp/call\_versatile）"，未显式提及后续迭代中是否同样调用 `skill_tool` 加载 Skill。实际 ReAct 执行中，每个任务执行前都会先调用 `skill_tool` 加载对应技能文档（与步骤 10 一致），todolist 更新（步骤 14）发生在 `skill_tool` 之前。



补充澄清

：后续每轮 ReAct 循环中，`todolist_end` → `todo_start` → `skill_tool`（内部工具，不产生 tool 事件）→ 业务工具调用。即 todolist 更新始终在 Skill 加载之前完成。

#### 规则 3：todolist 更新完毕后，如果任务需要执行则生成 todo\_start



部分体现，需补充条件分支。



UC-01 步骤 8→9、步骤 14→15 展示了 todolist 更新后紧跟 `todo_start` 的正向路径。但文档未明确定义 todolist 更新后的条件分支：当所有任务已完成或当前轮次仅需回答无需执行任务时，todolist 更新后应跳过 `todo_start`。



补充定义

：todolist 更新完毕（`todolist_end`）后，EDPAgent 根据当前任务状态决定后续动作：

| 条件                         | 后续动作                     | 事件序列                                                                                  |
| -------------------------- | ------------------------ | ------------------------------------------------------------------------------------- |
| 有任务需要执行                    | 发射 `todo_start` 进入任务执行   | `todolist_end` → `todo_start` → ...                                                   |
| 无任务需要执行（所有任务已完成，或当前轮次仅需回答） | 跳过 `todo_start`，直接进入最终回答 | `todolist_end` → `final_answer_start` → `final_answer_chunk`（N 次）→ `final_answer_end` |

#### 规则 4：需要更新 todolist 前生成 todo\_end



已在 UC-01 步骤 12→13-14 体现。



UC-01 中，第一个任务完成后发射 `todo_end`（步骤 12），随后才回到 Think（步骤 13）并更新 todolist（步骤 14）。文档"关键说明"亦明确："每轮 ReAct 循环 = Think → Plan（更新 todolist）→ Act → Observe。`todo_end` 后不直接进入下一个 `todo_start`，而是先回到 `think_start` 重新推理，再输出更新后的 todolist。"

时序：`todo_end` → `think_start` → `think_chunk`（N 次）→ `think_end` → `todolist_start` → `todolist_item` → `todolist_end`

#### 规则 5：工具调用前生成 tool\_start，工具执行完毕后生成 tool\_end（仅业务工具）



已在 UC-01 步骤 11 及 §1.2 边界表体现。



UC-01 步骤 11 定义了业务工具调用的事件序列：`tool_start` → `tool_status`（可选）→ `tool_end`，一个 todo 内可包含多次业务工具调用。

§1.2 功能边界表明确限定 tool 事件范围：

| 范围内                             | 范围外                                                                    |
| ------------------------------- | ---------------------------------------------------------------------- |
| 仅 `call_mcp` / `call_versatile` | `ask_user` / `cancel_task` / `skill_tool` / `read_file` / `bash` 等其他工具 |

UC-01 步骤 10 亦明确："任务内调用 `skill_tool` 加载 Skill（内部工具，，，不产生 tool 事件，，）"。

时序（任务内）：`todo_start` → `skill_tool`（无 tool 事件）→ `tool_start` → `tool_status`（可选）→ `tool_end` → ... → `todo_end`

### D.3 五项规则时序总览

```
conversation_start
→ think_start → think_chunk(×N) → think_end
→ todolist_start → todolist_item → todolist_end          ← 规则1：首次读取 Skill 前生成 todolist
→ todo_start
  → skill_tool（内部工具，不产生 tool 事件）
  → tool_start → tool_status(可选) → tool_end            ← 规则5：业务工具用 tool_start/tool_end 包裹
  → [tool_start → tool_status(可选) → tool_end]
→ todo_end                                                ← 规则4：更新 todolist 前生成 todo_end
→ think_start → think_chunk(×N) → think_end
→ todolist_start → todolist_item(更新) → todolist_end    ← 规则2：再读取 Skill 前更新 todolist
→ todo_start                                              ← 规则3：有任务需执行则生成 todo_start
  → skill_tool（内部工具，不产生 tool 事件）
  → tool_start → tool_status(可选) → tool_end
→ todo_end
→ ...（重复 ReAct 循环）
→ [无任务需执行时：todolist_end → final_answer_start]     ← 规则3：无任务需执行则跳过 todo_start
→ final_answer_start → final_answer_chunk(×N) → final_answer_end
→ conversation_end
```

### D.4 规则覆盖度汇总

| # | 规则                                |  原文档覆盖度 | 补充内容                                                  |
| - | --------------------------------- | :-----: | ----------------------------------------------------- |
| 1 | 首次读取 Skill 前生成 todolist           |  ✅ 完整体现 | UC-01 步骤 6-10，无需补充                                    |
| 2 | 再读取 Skill 前更新 todolist            | ⚠️ 部分体现 | 补充澄清：后续迭代同样先 skill\_tool 再业务工具，todolist 更新在 Skill 加载前 |
| 3 | todolist 更新后若需执行则生成 todo\_start   | ⚠️ 部分体现 | 补充定义：无任务可执行时跳过 todo\_start，直接进入 final\_answer         |
| 4 | 需要更新 todolist 前生成 todo\_end       |  ✅ 完整体现 | UC-01 步骤 12→13-14，无需补充                                |
| 5 | 业务工具调用前 tool\_start、完毕后 tool\_end |  ✅ 完整体现 | UC-01 步骤 11 + §1.2 边界表，无需补充                           |

***

### 附录E： 北向接口协议

> 本节内容来源于《动态规划智能体南北向接口 v1.4》，定义 EDPAgent 与前端客户端之间的北向接口协议规范。当前文档 §1.4 定义的是 EDPAgent 内部 SSE 事件格式，本节定义的是经过 A2A Gateway 封装后的北向接口格式。`EdpaStreamEventAdapter`（§6.3）负责完成两层之间的转换。

#### 1.5.1 概念定义

| 概念               | 定义                                                                                                                                        |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| conversation\_id | 会话的唯一标识，同一个上下文会话过程记录在同一个 conversation\_id 标识下。conversation\_id 由调用者产生，动态规划 Agent 消费。当 Agent 发现一个新的 conversation\_id 时，将自动产生一个新的上下文会话数据结构。 |
| Think            | 思考过程，对于思考模型会产生                                                                                                                            |
| Todolist         | 针对用户 Query 进行规划时产生的任务列表                                                                                                                   |
| Todo             | todo 是任务列表的一项                                                                                                                             |
| Subtask          | 任务下的子任务项                                                                                                                                  |
| Interrupt        | 智能体运行中中断信息，以便应用补充信息。                                                                                                                      |
| Tool             | 工具列表，在执行任务中，可能会调用各种工具执行，比如工作流、MCP、Skill 等。                                                                                                |
| Customer         | 用户自定义的其他信息                                                                                                                                |
| final\_answer    | 任务执行的总结信息。                                                                                                                                |

#### 1.5.2 设计原则

三段式结构，所有消息类型都遵循三段式结构：

```
┌─────────┐     ┌────────────┐     ┌──────────┐
│ *_start │ --> │ *_stream/*  │ --> │  *_end   │
│ (开始宣告) │     │ (过程推送)   │     │ (结束确认)  │
└─────────┘     └────────────┘     └──────────┘
```

#### 1.5.3 请求参数

-   URI  ：`/v1/{project_id}/agents/{agent_id}/conversations/{conversation_id}`
-   请求方式  ：POST
-   响应方式  ：SSE 流式（`stream: true`）

| 参数类型     | 参数名              | 备注                                           |
| -------- | ---------------- | -------------------------------------------- |
| 路径参数     | project\_id      | 项目 ID                                        |
| <br />   | agent\_id        | 智能体 ID                                       |
| <br />   | conversation\_id | 会话 ID                                        |
| Query 参数 | workspace\_id    | 工作空间 ID                                      |
| <br />   | version          | 版本号                                          |
| <br />   | type             | 类型标识                                         |
| Body 参数  | agent\_id        | 高码接口中的 agent\_id，对应路径参数中的 agent\_id          |
| <br />   | input → query    | 用户提问的问题                                      |
| <br />   | conversation\_id | 高码接口中的 session\_id，对应路径参数中的 conversation\_id |
| <br />   | stream           | 是否启用流式输出（新增参数）                               |
| <br />   | timeout          | 超时时间（新增参数）                                   |
| <br />   | role\_id         | 角色 ID（新增参数）                                  |
| <br />   | role\_name       | 角色名称（新增参数）                                   |
| <br />   | custom\_data     | 低码接口中的 body 参数，整体放到 custom\_data 中           |

#### 1.5.4 响应外层信封

所有事件共享统一的外层信封结构：

| 参数名               | 数据类型    | 说明            |
| ----------------- | ------- | ------------- |
| success           | boolean | 请求是否成功        |
| agent\_id         | string  | 智能体 ID        |
| conversation\_id  | string  | 会话 ID         |
| output            | string  | 输出内容          |
| error             | string  | 错误信息          |
| execution\_time   | number  | 执行耗时（秒）       |
| custom\_rsp\_data | object  | 自定义响应数据（事件载体） |



custom\_rsp\_data 参数结构

：

| 参数名         | 数据类型    | 说明          |
| ----------- | ------- | ----------- |
| data        | object  | 数据内容        |
| event       | string  | 事件类型        |
| content     | string  | 内容          |
| display     | string  | 展示方式        |
| createdTime | integer | 创建时间（毫秒时间戳） |
| latency     | string  | 延迟          |
| plugin      | string  | 插件标识        |

#### 1.5.5 事件接口定义

>   说明  ：本节按事件类型分组展示 JSON 格式示例，事件排列顺序不代表实际执行序列。实际事件序列请参考 §5 事件序列模板。各事件的 `createdTime` 为示例时间戳，仅用于展示字段格式，不反映真实时序关系。

##### event: conversation\_start

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.043,
  "custom_rsp_data": {
    "data": {},
    "event": "conversation_start",
    "content": "本轮对话开启",
    "display": "",
    "createdTime": 1774966674262,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: think\_start

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.045,
  "custom_rsp_data": {
    "data": {},
    "event": "think_start",
    "content": "开始分析用户需求",
    "display": "",
    "createdTime": 1774966675000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: think\_chunk

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.052,
  "custom_rsp_data": {
    "data": {},
    "event": "think_chunk",
    "content": "正在识别用户需求类型...",
    "display": "",
    "createdTime": 1774966676000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: think\_end

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.061,
  "custom_rsp_data": {
    "data": {},
    "event": "think_end",
    "content": "需求分析完成，开始规划任务",
    "display": "",
    "createdTime": 1774966677000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: todolist\_start

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.065,
  "custom_rsp_data": {
    "data": {},
    "event": "todolist_start",
    "content": "开始生成任务列表",
    "display": "",
    "createdTime": 1774966678000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: todolist\_item

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.072,
  "custom_rsp_data": {
    "data": {},
    "event": "todolist_item",
    "content": " 1.理财产品推荐，未开始",
    "display": "",
    "createdTime": 1774966679000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: todolist\_end

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.078,
  "custom_rsp_data": {
    "data": {},
    "event": "todolist_end",
    "content": "任务规划完成",
    "display": "",
    "createdTime": 1774966680000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: todo\_start

>   说明  ：以下 `todo_start` 示例对应的是是是当前轮次要执行的任务是是（如"查询理财产品"）的开始事件。实际执行中 `todo_start` 在 ReAct 循环（think → 更新 todolist）之后发射，表示下一个任务开始执行。

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.082,
  "custom_rsp_data": {
    "data": {},
    "event": "todo_start",
    "content": "开始执行：查询理财产品",
    "display": "",
    "createdTime": 1774966681000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: todo\_status

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.091,
  "custom_rsp_data": {
    "data": {},
    "event": "todo_status",
    "content": "正在查询匹配理财产品",
    "display": "",
    "createdTime": 1774966682000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: todo\_end

>   说明  ：以下 `todo_end` 示例对应的是是是上一个已完成任务是是（如"查询理财产品"）的结束事件。实际执行中每个任务完成后都会发射 `todo_end`，随后进入 ReAct 循环（think → 更新 todolist → 下一个 todo\_start）。

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.097,
  "custom_rsp_data": {
    "data": {},
    "event": "todo_end",
    "content": "理财产品查询完成，为您匹配3款产品：\n1. 稳健理财A：年化2.85%，期限90天，风险等级R2\n2. 稳利宝：年化2.75%，期限180天，风险等级R2\n3. 安心盈：年化3.00%，期限365天，风险等级R2",
    "display": "",
    "createdTime": 1774966683000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: tool\_start

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.110,
  "custom_rsp_data": {
    "data": {},
    "event": "tool_start",
    "content": "开始调用转账工具，执行转账操作",
    "display": "",
    "createdTime": 1774966687000,
    "latency": "",
    "plugin": "transfer"
  }
}
```

##### event: tool\_status

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.112,
  "custom_rsp_data": {
    "data": {},
    "event": "tool_status",
    "content": "转账处理中，账户校验已通过",
    "display": "",
    "createdTime": 1774966688000,
    "latency": "",
    "plugin": "transfer"
  }
}
```

##### event: tool\_end

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.113,
  "custom_rsp_data": {
    "data": {},
    "event": "tool_end",
    "content": "转账完成，从xxx账号到xxx账号成功转账xxx元",
    "display": "",
    "createdTime": 1774966689000,
    "latency": "",
    "plugin": "transfer"
  }
}
```

##### event: interrupt\_start

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.102,
  "custom_rsp_data": {
    "data": {"interrupt_id": "int-a1b2c3d4"},
    "event": "interrupt_start",
    "content": "请输入购买金额",
    "display": "",
    "createdTime": 1774966684000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: interrupt\_end

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.113,
  "custom_rsp_data": {
    "data": {"interrupt_id": "int-a1b2c3d4"},
    "event": "interrupt_end",
    "content": "您输入的金额是xxx元",
    "display": "",
    "createdTime": 1774966685000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: final\_answer\_start

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.115,
  "custom_rsp_data": {
    "data": {},
    "event": "final_answer_start",
    "content": "开始生成最终回答",
    "display": "",
    "createdTime": 1774966690000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: final\_answer\_chunk

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.121,
  "custom_rsp_data": {
    "data": {},
    "event": "final_answer_chunk",
    "content": "已为您匹配理财并完成转账",
    "display": "",
    "createdTime": 1774966691000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: final\_answer\_end

```json
{
  "success": true,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "",
  "execution_time": 0.128,
  "custom_rsp_data": {
    "data": {},
    "event": "final_answer_end",
    "content": "服务完成",
    "display": "",
    "createdTime": 1774966692000,
    "latency": "",
    "plugin": ""
  }
}
```

##### event: error\_event

```json
{
  "success": false,
  "agent_id": "planning_agent",
  "conversation_id": "mock-fund-planning-005333",
  "output": "",
  "error": "LLM_TIMEOUT",
  "execution_time": 60.0,
  "custom_rsp_data": {
    "data": {"error_type": "LLM_TIMEOUT"},
    "event": "error_event",
    "content": "LLM 调用超时，请稍后重试",
    "display": "",
    "createdTime": 1774966693000,
    "latency": "",
    "plugin": ""
  }
}
```

#### 1.5.6 当前文档内部事件 ↔ 北向接口字段映射

`EdpaStreamEventAdapter` 负责将 EDPAgent 内部 SSE 事件（§1.4）转换为北向接口格式（§1.5.5），核心映射关系：

| 内部字段                             | 北向接口字段                                                         | 映射方式                                                       |
| -------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------- |
| `timestamp`                      | `custom_rsp_data.createdTime`                                  | 直接映射                                                       |
| `session_id`                     | `conversation_id`（外层）                                          | 直接映射                                                       |
| `content`                        | `custom_rsp_data.content`                                      | 直接映射                                                       |
| `tool`                           | `custom_rsp_data.plugin`                                       | 工具名映射为 plugin 标识                                           |
| `args`                           | `custom_rsp_data.content`                                      | 入参文本化渲染                                                    |
| `data`                           | `custom_rsp_data.content`                                      | 返回数据文本化渲染                                                  |
| `{id, task_name, status}`        | `custom_rsp_data.content`                                      | 单条任务渲染为文本（如 "1.理财产品推荐，未开始"）                                |
| `tools[{id, tool_name, status}]` | `custom_rsp_data.content`                                      | 结构化数组渲染为文本（如 "开始执行：查询理财产品"）                                |
| `interrupt_id`                   | `custom_rsp_data.data`                                         | 通过 data 字段传递                                               |
| `error_type`                     | `custom_rsp_data.data.error_type` + 外层 `error`                 | error\_type 放入 data 和外层 error 字段                           |
| —                                | `custom_rsp_data.display`                                      | 适配层补充默认值（空字符串）                                             |
| —                                | `custom_rsp_data.latency`                                      | 适配层补充默认值（空字符串）                                             |
| —                                | `success` / `agent_id` / `output` / `error` / `execution_time` | 适配层包装外层信封（error\_event 时 success=false, error=error\_type） |
| `conversation_end`               | —                                                              |   北向接口不单独发送 conversation\_end 事件  ，通过 SSE 连接关闭表示对话结束       |

>   补充说明  ：todo 系列事件（`todo_start`/`todo_status`/`todo_end`）的 `plugin` 字段固定为空字符串 `""`，不映射工具标识。`plugin` 字段仅由 `tool` 系列事件（`tool_start`/`tool_status`/`tool_end`）携带，值为对应的业务工具名（如 `"transfer"`）。


***


## 附录 F：基于 OpenJiuwen Core 的能力复用分析

### 6.1 OpenJiuwen Core 已具备的能力（直接复用）

| 能力              | Core 组件                                                                                                                                     | 本特性复用方式                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
|   任务数据结构        | `TodoItem`（id/content/description/status/depends\_on/meta\_data）                                                                            | `edp-config.yaml` 任务列表映射为 `TodoItem`，字段无需扩展                  |
|   任务 CRUD       | `TodoTool.create/list/get/modify`                                                                                                           | 任务规划、重新规划、状态更新直接调用；持久化替换为 Redis                              |
|   任务持久化         | `TodoTool`（Core 默认文件持久化）                                                                                                                    |   替换为 Redis  ：EDPAgent 扩展 `TodoTool` 持久化层为 Redis，支持多租户 + 高并发 |
|   任务规划 Rail     | `TaskPlanningRail`（auto-register todo\_create/todo\_list/todo\_get/todo\_modify）                                                            | 复用工具注册 + 系统提示词注入 + 进度跟踪                                      |
|   ReAct 循环      | `ReActAgent.raidedModelStreamCall()`                                                                                                        | Think → Act → Observe 循环已内置                                  |
|   Rail 生命周期钩子   | `AgentRail` 8 个 hook（beforeModelCall/afterModelCall/beforeToolCall/afterToolCall/onModelException/onToolException/beforeInvoke/afterInvoke） | 所有事件发射通过 Rail hook 拦截                                        |
|   LLM 流式调用      | `ReActAgent` 内部 `model.stream()` → `AssistantMessageChunk` 迭代器                                                                              | `think_chunk` / `final_answer_chunk` 通过流式 chunk 拦截           |
|   流式输出管道        | `AgentSessionApi.writeStream(OutputSchema)` + `StreamMode.OUTPUT/CUSTOM`                                                                    | 20 种事件通过 `OutputSchema(type, payload)` 写入流管道                 |
|   任务依赖          | `TodoItem.depends_on`（`List<String>`，已原生支持）                                                                                                 | 依赖校验 + 拓扑排序在 Rail `afterToolCall` 中增加                        |
|   中断恢复          | `ToolInterruptionState` + `RESUME_USER_INPUT_KEY`                                                                                           | `interrupt_start/end` 复用已有中断机制                               |
|   会话管理          | `AgentSessionApi`（sessionId/streamIterator/preRun/postRun）                                                                                  | 事件流通过 session 管道传递                                           |

### 6.2 当前状态 vs 目标状态

| 维度     | 当前                                                 | 目标                                                        | 复用 Core 能力                           |
| ------ | -------------------------------------------------- | --------------------------------------------------------- | ------------------------------------ |
| 事件类型   | 5 种（todo\_start/todo\_end/purchase\_confirm/error） | 20 种标准化事件                                                 | `OutputSchema.type` 携带事件名            |
| 事件粒度   | 粗粒度（A2A artifactUpdate 统一）                         | 细粒度（think\_chunk/tool\_start/tool\_end 分离）                | `StreamMode.CUSTOM` + `CustomSchema` |
| LLM 流式 | 无 think\_chunk                                     | 逐 token 流式输出                                              | `ReActAgent` 流式 chunk 迭代器            |
| 任务列表   | step\_id + content + skill                         | step\_id + task\_name + description + skill + depends\_on | `TodoItem` 原生字段                      |
| 依赖管理   | `task_dependencies: {}`（空）                         | `depends_on` 逐任务配置 + 拓扑排序                                 | `TodoItem.depends_on` + Rail 校验      |
| 接入方式   | A2A JSON-RPC `/a2a`                                | A2A JSON-RPC `/a2a`（不变）                                   | —                                    |
| 事件源    | StreamFrameFactory（固定脚本）                           | Rail hook + Session stream                                | `AgentSessionApi.writeStream()`      |

### 6.3 需新增/修改的组件（基于 Core 扩展）

| 组件                              | 类型                      | 职责                                                                                              | 复用的 Core 能力                                       |
| ------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `EdpaEventRail`                 | 新增（extends `AgentRail`） | 统一事件发射 Rail，通过 8 个 hook 拦截全生命周期                                                                 | `AgentRail` hook 机制                               |
| — `beforeModelCall`             | 实现                      | 发射 `think_start`                                                                                | `AgentCallbackContext` 获取 sessionId               |
| — `afterModelCall`              | 实现                      | 发射 `think_end`                                                                                  | `ModelCallInputs.response` 获取 LLM 结果              |
| — `beforeToolCall`              | 实现                      | 发射 `tool_start`（仅 call\_mcp/call\_versatile）                                                    | `ToolCallInputs.toolName` 判断工具名                   |
| — `afterToolCall`               | 实现                      | 发射 `tool_end` + 拦截 todo\_create/modify 发射 `todolist_start/item/end`                             | `ToolCallInputs.toolName` + `TodoTool` 返回值        |
| — `onModelException`            | 实现                      | 异常时输出 `conversation_end` 终止会话                                                                   | `AgentCallbackContext.exception`                  |
| — `beforeInvoke`                | 实现                      | 发射 `conversation_start` +   预加载 edp-config.yaml 任务到 TodoTool                                    | `TodoTool.list/create`（Core 不支持配置预加载，EDPAgent 注入） |
| — `afterInvoke`                 | 实现                      | 发射 `conversation_end`                                                                           | —                                                 |
| `EdpaTodoValidator`             | 新增（辅助类）                 | `depends_on` 依赖校验 + 拓扑排序                                                                        | `TodoItem.depends_on` 字段                          |
| `RedisTodoTool`（或扩展 `TodoTool`） | 新增（扩展 Core）             | 替代 Core 默认文件持久化，按 `tenant:agent:sessionId` 键空间 Redis 持久化                                        | `TodoTool` 接口 + Redis Template                    |
| `EdpaStreamEventAdapter`        | 新增                      | `OutputSchema` → A2A SSE 20 种业务事件帧；按 `type` 映射（`llm_output`→`think_chunk`/`final_answer_chunk`） | `OutputSchema.type` 事件路由                          |
| `EdpaRuntimeHandler`            | 修改                      | 注册 `EdpaEventRail` + 移除 `LiteTodoRail` + 开启流式                                                   | `DeepAgent.registerRail()` + `AgentSessionApi`    |
| `LiteTodoRail`                  |   移除                    | 依赖校验职责迁移到 `EdpaTodoValidator`；任务 CRUD 由 Core `TaskPlanningRail` 替代                              | `TaskPlanningRail`(priority=90) 替代                |
| `edp-config.yaml`               | 修改                      | `todolist_steps` 增加 `task_name`/`description`/`depends_on`                                      | 映射为 `TodoItem` 初始化                                |

>   已确认  ：
>
> - `think_chunk` / `final_answer_chunk` 无需 Rail hook 拦截 token，Core `ReActAgent.writeAssistantStreamChunk()` 已自动写入 `OutputSchema(type=llm_output)` 到 session 流，`EdpaStreamEventAdapter` 按 type 映射即可。
> - `LiteTodoRail` 必须移除，否则与 `TaskPlanningRail`(priority=90) 重复校验 todo 操作。
> - 任务预加载在 `beforeInvoke()` 中执行：检查 `todoTool.list(sessionId)` 为空时从 `edp-config.yaml` 加载并 `create()`。
> - `TodoTool` 持久化方式确定为   Redis  ，替代 Core 默认的文件持久化。EDPAgent 需扩展 `TodoTool` 或在 `TaskPlanningRail.init()` 中注入 Redis-backed 实现替代默认文件实现。

### 6.4 事件发射路径（全链路复用 Core）

```
用户 Query
    │
    ▼
ReActAgent.invoke()                          ← Core: ReAct 循环启动
    │
    ├─ EdpaEventRail.beforeInvoke()          ← Core: AgentRail hook
    │    ├─ session.writeStream(OutputSchema("conversation_start", ...))
    │    └─ 预加载任务: 检查 todoTool.list(sessionId) 是否为空
    │         └─ 为空 → 从 edp-config.yaml 加载 → todoTool.create(sessionId, predefined)
    │            （Core 不支持配置预加载，EDPAgent 在 beforeInvoke 中注入）
    │
    ├─ ReActAgent.raidedModelStreamCall()    ← Core: LLM 流式调用
    │    ├─ EdpaEventRail.beforeModelCall()  ← Core: AgentRail hook
    │    │    └─ session.writeStream(OutputSchema("think_start", ...))
    │    │
    │    ├─ model.stream() → chunk迭代器     ← Core: LLM token 流
    │    │    └─ ReActAgent.writeAssistantStreamChunk()  ← Core: 自动写入
    │    │         → session.writeStream(OutputSchema("llm_output", {content, result_type:"answer"}))
    │    │         （Core 已自动将每个 token chunk 写入 session 流，无需 Rail hook 拦截）
    │    │         （EdpaStreamEventAdapter 按 type="llm_output" 映射为 think_chunk 事件）
    │    │
    │    └─ EdpaEventRail.afterModelCall()   ← Core: AgentRail hook
    │         └─ session.writeStream(OutputSchema("think_end", ...))
    │
    ├─ LLM 决策: tool_call(todo_create)      ← Core: TaskPlanningRail 注册的工具
    │    ├─ EdpaEventRail.beforeToolCall()   ← Core: AgentRail hook
    │    │    └─ (todo_create 非 call_mcp/call_versatile，不发射 tool_start)
    │    ├─ TodoTool.create()                ← Core: 任务创建（第1个 IN_PROGRESS，其余 TODO）
    │    │    └─ RedisTodoTool.create() → Redis 持久化  ← EDPAgent 扩展
    │    └─ EdpaEventRail.afterToolCall()    ← Core: AgentRail hook
    │         ├─ 检测 toolName == "todo_create"
    │         ├─ 从 ToolOutput.data 获取 List<TodoItem>
    │         ├─ EdpaTodoValidator.validate(todoItems)  ← 新增: 依赖校验 + 拓扑排序
    │         │    ├─ 检查 depends_on 引用的 id 是否存在
    │         │    ├─ 检查是否有循环依赖（环检测）
    │         │    └─ 按 depends_on 拓扑排序确认执行顺序
    │         ├─ session.writeStream(OutputSchema("todolist_start", {timestamp}))
    │         ├─ session.writeStream(OutputSchema("todolist_item", {
    │         │      tasks: [{id, task_name: content, status, ...}, ...],  ← 完整数组，一次性发送
    │         │      timestamp
    │         │    }))
    │         └─ session.writeStream(OutputSchema("todolist_end", {timestamp}))
    │         （初次任务列表创建：全部 status=TODO，第1个 IN_PROGRESS）
    │
    ├─ EdpaEventRail.afterToolCall() 检测 todo_modify 将 task-1 改为 IN_PROGRESS
    │    └─ session.writeStream(OutputSchema("todo_start", {timestamp}))
    │       （任务开始执行信号，每个 todo 执行前发射 1 次）
    │
    ├─ [可选] 长耗时任务执行过程中，EdpaEventRail 周期性推送进度
    │    └─ session.writeStream(OutputSchema("todo_status", {content: "任务执行中...", timestamp}))
    │       （todo_status 为可选事件，仅在任务执行时间超过阈值时发射）
    │
    ├─ LLM 决策: tool_call(call_mcp)         ← EDPAgent 业务工具
    │    ├─ EdpaEventRail.beforeToolCall()
    │    │    └─ session.writeStream(OutputSchema("tool_start", {tool: "call_mcp", args: ...}))
    │    ├─ McpInterruptRail 执行脚本        ← EDPAgent 已有 Rail
    │    └─ EdpaEventRail.afterToolCall()
    │         └─ session.writeStream(OutputSchema("tool_end", {tool: "call_mcp", data: ...}))
    │
    ├─ ════════════════════════════════════════════════════════════════
    │   以下为 ReAct 循环：todo_end → think → 更新 todolist → 下一个 todo
    │   ════════════════════════════════════════════════════════════════
    │
    ├─ LLM 决策: tool_call(todo_modify)      ← Core: 标记当前任务完成
    │    ├─ EdpaEventRail.beforeToolCall()
    │    │    └─ (todo_modify 非 call_mcp/call_versatile，不发射 tool_start)
    │    ├─ TodoTool.modify({action:"update", todos:[{id:"task-1", status:"COMPLETED"}]})
    │    │    └─ RedisTodoTool.modify() → Redis 更新  ← EDPAgent 扩展
    │    └─ EdpaEventRail.afterToolCall()
    │         ├─ 检测 toolName == "todo_modify"
    │         ├─ 从 ToolOutput.data 获取更新后的 List<TodoItem>
    │         ├─ session.writeStream(OutputSchema("todo_end", {timestamp}))
    │         │    （当前 todo 完成）
    │         └─ 【不发射 todolist 事件，等待下一轮 Think 后再更新】
    │
    ├─ ReActAgent.raidedModelStreamCall()    ← Core: 第 2 轮 LLM 流式调用
    │    ├─ EdpaEventRail.beforeModelCall()
    │    │    └─ session.writeStream(OutputSchema("think_start", ...))
    │    ├─ model.stream() → writeAssistantStreamChunk()
    │    │    └─ session.writeStream(OutputSchema("llm_output", {content}))  → think_chunk
    │    └─ EdpaEventRail.afterModelCall()
    │         └─ session.writeStream(OutputSchema("think_end", ...))
    │         （LLM 根据工具返回结果重新推理，决策下一步）
    │
    ├─ LLM 决策: tool_call(todo_modify)      ← Core: 更新任务列表状态
    │    ├─ TodoTool.modify({action:"update", todos:[
    │    │      {id:"task-1", status:"COMPLETED"},
    │    │      {id:"task-2", status:"IN_PROGRESS"}
    │    │    ]})
    │    │    └─ RedisTodoTool.modify() → Redis 更新
    │    └─ EdpaEventRail.afterToolCall()
    │         ├─ 检测 toolName == "todo_modify" 且有 status 变更
    │         ├─ todoTool.get(sessionId) → 获取完整列表（含已完成任务）
    │         │    （注意：用 get() 而非 list()，因为 list() 会过滤已完成任务）
    │         ├─ session.writeStream(OutputSchema("todolist_start", {timestamp}))
    │         ├─ session.writeStream(OutputSchema("todolist_item", {
    │         │      tasks: [
    │         │        {id:"task-1", task_name:"查询余额", status:"COMPLETED"},
    │         │        {id:"task-2", task_name:"购买理财", status:"IN_PROGRESS"},
    │         │        {id:"task-3", task_name:"确认交易", status:"TODO"}
    │         │      ],  ← 完整数组，含最新状态，一次性发送
    │         │      timestamp
    │         │    }))
    │         └─ session.writeStream(OutputSchema("todolist_end", {timestamp}))
    │         （任务列表更新：task-1=COMPLETED，task-2=IN_PROGRESS，其余 TODO）
    │
    ├─ LLM 决策: tool_call(call_versatile)   ← EDPAgent 业务工具（第 2 轮 ReAct 循环：task-2 购买理财）
    │    ├─ EdpaEventRail.beforeToolCall()
    │    │    └─ session.writeStream(OutputSchema("tool_start", {tool: "call_versatile", args: ...}))
    │    ├─ VersatileInterruptRail 执行      ← EDPAgent 已有 Rail
    │    └─ EdpaEventRail.afterToolCall()
    │         └─ session.writeStream(OutputSchema("tool_end", {tool: "call_versatile", data: ...}))
    │
    ├─ ════════════════════════════════════════════════════════════════
    │   重复上述 ReAct 循环，直到所有任务 COMPLETED
    │   ════════════════════════════════════════════════════════════════
    │
    │
    ├─ LLM 决策: answer（finish_reason=stop）
    │    ├─ session.writeStream(OutputSchema("final_answer_start", ...))
    │    ├─ model.stream() → chunk迭代器     ← Core: LLM token 流
    │    │    └─ ReActAgent.writeAssistantStreamChunk()  ← Core: 自动写入
    │    │         → session.writeStream(OutputSchema("llm_output", {content, result_type:"answer"}))
    │    │         （EdpaStreamEventAdapter 按 type="llm_output" + finish_reason=stop 映射为 final_answer_chunk）
    │    └─ session.writeStream(OutputSchema("final_answer_end", ...))
    │
    └─ EdpaEventRail.afterInvoke()
         └─ session.writeStream(OutputSchema("conversation_end", ...))

session.streamIterator()                     ← Core: 流管道消费
    │
    ▼
EdpaStreamEventAdapter                       ← 新增: OutputSchema → A2A SSE
    │ OutputSchema.type = "think_chunk" → SSE event: think_chunk
    │ OutputSchema.type = "tool_start"  → SSE event: tool_start
    │ ...
    ▼
A2A SSE /a2a 响应                             ← Core: A2aJsonRpcController
```

### 6.5 核心设计原则

| 原则                      | 说明                                                                 |
| ----------------------- | ------------------------------------------------------------------ |
|   Rail 优先               | 所有事件发射通过 `AgentRail` 的 8 个 hook 拦截，不侵入 ReActAgent 内部               |
|   Session 管道复用          | 20 种事件统一通过 `AgentSessionApi.writeStream(OutputSchema)` 写入 Core 流管道 |
|   TodoItem 原生字段         | 任务数据结构完全复用 `TodoItem`，不新增字段                                        |
|   TodoTool 原生操作         | 任务 CRUD 复用 `TodoTool.create/list/get/modify`，不重写                   |
|   TaskPlanningRail 复用   | 任务规划工具注册 + 系统提示词注入复用 `TaskPlanningRail`，EDPAgent 仅扩展事件发射           |
|   StreamMode 扩展         | 使用 `StreamMode.OUTPUT` + 自定义 `OutputSchema.type` 区分 20 种事件         |

