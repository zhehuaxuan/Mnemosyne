# EDPAgent 思维链话术与固定帧替换 功能特性用例（v1.3）

> 基于需求规格 + 澄清收敛生成。文档涵盖业务场景话术、工具集话术、固定帧话术三大模块，按"角色—前置—主流程—备选流—后置—验收"标准结构组织。
>
> 版本：v1.3（已收敛 Q1–Q12 共 12 项澄清；v1.3 对齐 Java 实现：request_start/planning_start 为话术配置键，以 interrupt_start 事件发出）

***

## 1. 需求背景

| #  | 背景                           | 业务影响                               |
| -- | ---------------------------- | ---------------------------------- |
| B1 | 金融行业合规要求：模型原始输出 token 不能直接面客 | 必须用预定义话术替换模型输出，避免敏感/不当内容外泄         |
| B2 | 动态规划过程中需向用户呈现思维链             | 思维链需可读、可控、可替换，用固定话术表达 Agent 当前阶段意图 |

核心目标：在 EDPAgent 动态规划执行链路上，对 `tool_start/tool_end/todo_start/todo_end/todolist_start/end/interrupt_start` 等事件，以及大模型思考 token 流，提供**分层话术配置 + 固定帧替换**能力。其中 `request_start`/`planning_start` 为**话术配置键**（非独立事件类型），首轮开场时以 `interrupt_start` 事件发出（对齐 Python `InterruptStartEvent` 设计，由 `ScriptsRail.beforeInvoke` 实现）。

***

## 2. 角色定义

| 角色 ID | 名称           | 职责                                   |
| ----- | ------------ | ------------------------------------ |
| R1    | 场景配置管理员      | 维护兜底话术、场景级话术、任务级匹配模板、Skill.yaml 工具话术 |
| R2    | 终端用户（客户）     | 通过对话消费话术展示，触发中断/确认/取消                |
| R3    | EDPAgent 运行时 | 执行话术优先级解析、模板变量渲染、帧切分与推送              |
| R4    | Skill 脚本开发者  | 在 Skill 脚本中主动送出自定义事件与话术              |

***

## 3. 话术优先级模型（贯穿所有用例）

```
工具级模板匹配 (query_intent_tool_text)   [精确匹配，对所有业务工具生效]
        ↓ 未命中
默认兜底话术 (ScriptsConfig.tool_start / tool_end，支持 {title} 变量渲染)
```

固定帧话术独立于上述链路，作用于"大模型思考 token 流"层。

***

## 4. 用例清单总览

| 用例 ID  | 模块    | 标题                                 | 优先级 |
| ------ | ----- | ---------------------------------- | --- |
| UC-A01 | 兜底话术  | 默认兜底话术加载与覆盖全部事件                    | 高   |
| UC-A02 | 场景级话术 | 场景级自定义话术配置与命中                      | 高   |
| UC-A03 | 工具级话术 | 工具级模板匹配（命中/降级链）  | 高   |
| UC-A04 | 工具集话术 | 工具执行结果话术（response_template_keys 成功/失败二选一）  | 高   |
| UC-A05 | 工具集话术 | Skill 脚本主动送出事件话术                   | 中   |
| UC-A06 | 模板变量  | 话术模板变量渲染（{tool\_name}/{title}）     | 高   |
| UC-A07 | 工具集话术 | ask\_user 工具话术（response\_template\_keys dict + status + vars） | 高 |
| UC-B01 | 固定帧开关 | 固定帧启用/关闭切换                         | 高   |
| UC-B02 | 关键字匹配 | query\_patterns 关键字命中帧话术           | 高   |
| UC-B03 | 帧参数   | 字符数/token数/时间间隔配置                  | 高   |
| UC-B04 | 阶段化话术 | planning/executing/resuming 阶段切换   | 高   |
| UC-B05 | 降级兼容  | scripts 字段向后兼容降级                   | 中   |
| UC-C01 | 事件覆盖  | todolist\_start/end 话术             | 中   |
| UC-C02 | 事件覆盖  | interrupt\_start 中断追问话术            | 高   |
| UC-C03 | 事件覆盖  | task\_cancelled/cancel\_confirm 话术 | 中   |
| UC-C04 | 事件覆盖  | out\_of\_scope 超范围话术               | 中   |
| UC-C05 | 事件覆盖  | 首轮开场话术（request\_start/planning\_start 以 interrupt\_start 发出）  | 中   |

***

## 5. 模块 A：业务场景话术

### UC-A01 默认兜底话术加载与覆盖全部事件

| 字段    | 内容                                                                                                                                                                                                                                     |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-A01                                                                                                                                                                                                                                 |
| 主参与者  | R3 EDPAgent 运行时                                                                                                                                                                                                                        |
| 前置条件  | 1. 系统已加载默认兜底话术定义（附件1）；2. 未配置场景级/任务级话术，或场景/任务级话术未命中。                                                                                                                                                                                    |
| 主流程   | 1. Agent 触发话术事件（如 tool\_start/todo\_start/interrupt\_start 等）；2. 运行时按优先级链查询：任务级→场景级→兜底；3. 任务级、场景级均未命中；4. 运行时从默认兜底 scripts 中取对应键值；5. 渲染模板变量（见 UC-A06）；6. 将话术推送至前端。                                                                      |
| 备选流   | A1. 兜底话术某键缺失：记录 warn 日志，推送空字符串或跳过事件，不抛异常阻断主流程。A2. 兜底话术文件加载失败：启动期 fail-fast，阻止 Agent 启动。                                                                                                                                                |
| 后置条件  | 终端用户看到兜底话术内容；日志记录话术来源 = `default`。                                                                                                                                                                                                     |
| 验收标准  | 1. 附件1中 12 个话术配置键（tool\_start/tool\_end/todo\_start/todo\_end/todolist\_start/todolist\_end/interrupt\_start/request\_start/planning\_start/task\_cancelled/cancel\_confirm/out\_of\_scope）均能正确输出；**其中 `request_start`/`planning_start` 为话术配置键（非独立事件类型），首轮开场时以 `interrupt_start` 事件发出（对齐 Python `InterruptStartEvent`，由 `ScriptsRail.beforeInvoke` 实现）**；2. 未配置任何自定义话术时，所有事件回退到兜底；3. 话术来源标识可追溯。 |

***

### UC-A02 场景级自定义话术配置与命中

| 字段    | 内容                                                                                                |
| ----- | ------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-A02                                                                                            |
| 主参与者  | R1 场景配置管理员 / R3 运行时                                                                               |
| 前置条件  | 1. 管理员已为某场景（如"理财购买"）配置场景级话术 YAML，结构与附件1相同；2. Agent 已加载该场景配置。                                      |
| 主流程   | 1. 用户会话进入指定场景；2. Agent 触发话术事件；3. 任务级模板未命中（见 UC-A03）；4. 运行时定位当前场景话术定义；5. 命中场景级话术对应键；6. 渲染变量并推送。    |
| 备选流   | A1. 场景话术部分键缺失：仅缺失键回退到兜底，其余键仍使用场景级。A2. 场景配置文件格式错误：启动期校验失败，记录错误，按兜底运行。A3. 多场景切换：会话上下文切换场景时，话术源同步切换。 |
| 后置条件  | 命中键使用场景级话术；未命中键使用兜底；话术来源标识 = `scene:<场景名>`。                                                       |
| 验收标准  | 1. 场景级话术结构与兜底结构一致（12 个键）；2. 场景级覆盖优先于兜底；3. 部分覆盖时未覆盖键正确回退；4. 场景切换实时生效。                              |

***

### UC-A03 工具级模板匹配（命中/降级链）

| 字段    | 内容                                                                                                                                                                                                 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-A03                                                                                                                                                                                             |
| 主参与者  | R3 运行时                                                                                                                                                                                             |
| 前置条件  | 1. 已加载任务级匹配模板（附录A.2 query\_intent\_tool\_text）；2. 当前工具调用参数 `tool_args` 中包含 `query_intent` 字段（由 LLM 根据 SKILL.md 填写）。                                                                                  |
| 主流程   | 1. Agent 进入工具调用，需输出 tool\_start/tool\_end；2. 运行时以 `tool_args["query_intent"]` 作为 key，对 `query_intent_tool_text` 执行**精确匹配**（key 完全相等才命中）；3. 命中（如"理财购买"）；4. 取命中项的 `tool_start`/`tool_end` 文案（**注：配置层面键名为 `tool_start`/`tool_end`，具体事件类型可在客户话术脚本中修改**）；5. 推送至前端。 |
| 备选流   | A1. 任务级未命中 → 降级到 `ScriptsConfig.tool_start`/`tool_end` 兜底，使用 `{tool_name}` 变量渲染（`tool_name` = `query_intent` 值）；A2. `query_intent` 字段缺失：跳过任务级匹配，直接降级到兜底话术。                                                 |
| 后置条件  | 命中时话术来源 = `task_template:<匹配key>`；降级时来源为 `default`。                                                                                                                                                |
| 验收标准  | 1. 附录A.2 中 5 个示例意图（查询账户余额/快速转账/理财购买/理财选品购买/理财推荐）均能命中对应话术；2. 降级链顺序严格为 任务级→兜底（两层）；3. 任务级话术仅作用于 tool\_start/tool\_end 事件；4. "理财购买" 与 "理财选品购买" 互不误命中（精确匹配）；5. key 大小写/空白敏感（精确匹配语义）。   |

***

### UC-A04 工具执行结果话术（response_template_keys 成功/失败二选一）

| 字段    | 内容                                                                                                                                                                                                 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-A04                                                                                                                                                                                             |
| 主参与者  | R4 Skill 脚本开发者 / R3 运行时                                                                                                                                                                            |
| 前置条件  | 1. 工具调用参数 `tool_args` 中包含 `response_template_keys`（JSON 数组字符串 `[成功key, 失败key]`）；2. 工具调用参数 `tool_args` 中包含 `query_response_analysis_scripts`（归一化脚本命令，工作目录为 `skills/`）；3. 话术 key 对应的话术文本已在 Skill.yaml `scripts` 字段或兜底话术中定义。 |
| 主流程   | 1. LLM 调用 `call_versatile` 工具，传入 `response_template_keys` 和 `query_response_analysis_scripts` 参数；2. Rail 拦截并委托工作流执行业务逻辑；3. 工作流执行完成后，运行时在沙箱中执行归一化脚本（`query_response_analysis_scripts`），脚本通过环境变量 `SKILL_INPUT` 接收业务数据，返回 `[status, normalized_data]`；4. 运行时按 `status` 取 `response_template_keys` 下标：`status="success"` → 取 `[0]`（成功 key），`status!="success"` → 取 `[1]`（失败 key）；5. 从话术配置中查找该 key 对应的话术文本（两级查找：先查 Skill.yaml `scripts` 字段，再查兜底 `ScriptsConfig`）；6. 将话术文本写入 `session.response_template`；7. Agent 流末读取 `response_template`，以 `interrupt_start` 事件将话术推送至前端。 |
| 备选流   | A1. `status="success"` → 取 `response_template_keys[0]`（成功话术）；A2. `status!="success"`（如 `"failed"`） → 取 `response_template_keys[1]`（失败话术）；A3. 归一化脚本返回 `ui_notice` → **跳过 `response_template_keys` 机制**，由 `ui_notice` 接管话术输出（见 UC-A05），避免两条话术同时输出；A4. `response_template_keys` 为空或未传 → 不输出结果话术，仅输出默认 `tool_end`；A5. key 在话术配置中未找到 → 记录 warn 日志，不输出结果话术；A6. 归一化脚本执行超时或异常 → 降级透传原始业务数据，status 视为非 success，取失败 key。 |
| 后置条件  | 前端收到工具执行结果话术（成功或失败）；话术来源 = `response_template:<匹配key>`；话术**不被固定帧切分**（即使 `think_chunk_mode=fixed_script`）。 |
| 验收标准  | 1. `status="success"` 时输出 `response_template_keys[0]` 对应的成功话术；2. `status!="success"` 时输出 `response_template_keys[1]` 对应的失败话术；3. `ui_notice` 优先于 `response_template_keys`（两者同时存在时仅 `ui_notice` 生效）；4. `response_template_keys` 为空时不输出结果话术；5. key 在话术配置中未找到时记录 warn 日志，不阻断主流程；6. 话术通过 `interrupt_start` 事件推送至前端，**不经固定帧切分**；7. 话术文本完全由话术配置决定，脚本仅返回 status 和 key 下标，不直接返回话术内容。 |

**参数说明**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|:---:|------|
| `response_template_keys` | string（JSON 数组字符串） | 否 | 操作结果话术 key 的 JSON 数组字符串，格式为 `'[成功key, 失败key]'`。key 对应 Skill.yaml `scripts` 字段或兜底话术中定义的话术文本。留空则不输出结果话术。 |
| `query_response_analysis_scripts` | string | 否 | 归一化脚本运行命令，工作目录为 `skills/`。脚本通过环境变量 `SKILL_INPUT`（JSON）接收业务数据，返回 `[status_string, normalized_dict]`。留空则透传原始工作流返回数据，status 视为 None。 |
| `notice_context` | string | 否 | 透传给归一化脚本的上下文信息（JSON 字符串），由脚本解析后决定输出哪条场景化话术（配合 `ui_notice` 使用，见 UC-A05）。 |
| `input_key` | string | 否 | 后台通道数据 key，用于从后台通道读取前序工作流结果并注入脚本的 `SKILL_INPUT.input_data`。 |

**归一化脚本返回格式**：

脚本通过 stdout 输出 JSON，支持两种格式：

```
格式1: [status_string, normalized_dict]   → status 用于 response_template_keys 下标选择
格式2: {"key": value, ...}               → status 为 None，response_template_keys 不生效
```

`status` 取值：
- `"success"` → 取 `response_template_keys[0]`
- 其他值（如 `"failed"`）→ 取 `response_template_keys[1]`

**话术查找机制（两级查找）**：

```
1. 先查 Skill.yaml scripts 字段（业务话术，如 fund_planning_success）
2. 再查兜底 ScriptsConfig（通用话术，如 tool_end）
```

***

### UC-A05 Skill 脚本主动送出事件话术

| 字段    | 内容                                                                                                                                                                    |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-A05                                                                                                                                                                |
| 主参与者  | R4 Skill 脚本开发者                                                                                                                                                        |
| 前置条件  | Skill 脚本具备送出事件能力（API/SDK 支持）。                                                                                                                                         |
| 主流程   | 1. Skill 脚本在执行过程中达到某业务节点；2. 脚本主动调用送出接口，附带事件名与话术内容；3. 运行时**原样透传**该事件与话术至前端，**不经过固定帧切分**。                                                                               |
| 备选流   | A1. 脚本送出的事件名非法/为空：拒绝送出，记录错误日志；A2. 脚本送出话术为空：使用事件名对应的兜底话术；A3. 脚本未授权送出：拒绝并告警。                                                                                            |
| 后置条件  | 前端收到脚本自定义事件及话术；话术来源 = `skill_script:<脚本名>`。                                                                                                                           |
| 验收标准  | 1. 脚本可送出任意自定义事件名及对应话术；2. 话术内容完全由脚本控制，不被覆盖；3. 非法事件名被拒绝；4. 送出行为可审计；5. 脚本送出的话术长度不限，一次性推送，不被 chars\_per\_frame/tokens\_between\_frames 切分；6. 即使固定帧 enabled=true，脚本话术也不切分。 |

***

### UC-A06 话术模板变量渲染

| 字段    | 内容                                                                                                                                                                             |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 用例 ID | UC-A06                                                                                                                                                                         |
| 主参与者  | R3 运行时                                                                                                                                                                         |
| 前置条件  | 话术模板包含变量占位符（如 `{tool_name}`、`{title}`）。                                                                                                                                        |
| 主流程   | 1. 运行时准备事件上下文（tool\_name/title 等）；2. 扫描话术模板中的 `{var}` 占位符；3. 用上下文值替换占位符；4. 推送渲染后话术。                                                                                            |
| 备选流   | A1. 变量值缺失：**保留占位符原样**（如 `{tool_name}` 不替换），不替换为空字符串。A2. 变量值含特殊字符：按文本透传，不二次解析。                                                                                                  |
| 后置条件  | 用户看到变量已替换的话术。                                                                                                                                                                  |
| 验收标准  | 1. `{tool_name}` 在 tool\_start/tool\_end 中正确替换为工具名；2. `{title}` 在 todo\_start/todo\_end 中正确替换为任务标题；3. 缺失变量时，输出中保留 `{var}` 占位符文本；4. 示例：tool\_name 缺失时，"正在调用：{tool\_name}" 原样输出。 |

***

### UC-A07 ask\_user 工具话术（response\_template\_keys dict + status + vars）

| 字段    | 内容                                                                                                                                                                                                 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-A07                                                                                                                                                                                             |
| 主参与者  | R3 运行时 / R4 Skill 脚本开发者                                                                                                                                                                            |
| 前置条件  | 1. LLM 调用 `ask_user` 工具，参数 `tool_args` 中包含 `response_template_keys`（**dict** 格式 `{"status_value": "话术key"}`）；2. 参数中包含 `response_template_status`（字符串，指定当前状态）；3. 可选参数 `response_template_vars`（dict，模板变量）；4. 话术 key 对应的话术文本已在话术配置中定义。 |
| 主流程   | 1. LLM 调用 `ask_user` 工具，传入 `response_template_keys`（dict）、`response_template_status`、`response_template_vars`；2. Rail 拦截 `ask_user` 调用；3. 解析 `response_template_keys` 为 dict（`keys_map`）；4. 用 `response_template_status` 值在 `keys_map` 中查找对应的话术 key（`template_key = keys_map.get(status)`）；5. 从话术配置中查找该 key 对应的话术文本（两级查找：先查 Skill.yaml `scripts` 字段，再查兜底 `ScriptsConfig`）；6. 解析 `response_template_vars` 为 dict，用 `safe_format`（`format_map`）渲染话术模板中的变量占位符；7. 将渲染后的话术文本写入 `session.response_template`；8. 触发 `InterruptRequest` 中断，等待用户回复；9. Agent 流末读取 `response_template`，以 `interrupt_start` 事件将话术推送至前端。 |
| 备选流   | A1. `status="missing_amount"` → 查找 `keys_map["missing_amount"]` 对应的话术 key（如 `"ask_buy_amount"`）→ 输出"请告诉我您想购买的金额"；A2. `status="confirm"` → 查找 `keys_map["confirm"]` 对应的话术 key（如 `"confirm_product"`）→ 输出"确认购买以下产品吗？"，**同时将 `response_template_vars` 写入 `session.selected_product`**（记录用户选品信息）；A3. `status="cancel_confirm"` → 查找 `keys_map["cancel_confirm"]` 对应的话术 key（如 `"cancel_confirm"`）→ 输出"确认要取消当前操作吗？"（见 UC-C03 两步取消流程）；A4. `response_template_keys` 为空或未传 → 放行原 `ask_user` 行为（不输出话术）；A5. `response_template_status` 为空 → 放行原 `ask_user` 行为；A6. key 在话术配置中未找到 → 放行原 `ask_user` 行为；A7. `response_template_vars` 中变量缺失 → `safe_format` 将缺失变量替换为空字符串（不保留占位符）。 |
| 后置条件  | 前端收到 `interrupt_start` 事件的话术；话术来源 = `ask_user:<status>`；话术**不被固定帧切分**；当 `status="confirm"` 时，`session.selected_product` 被写入。 |
| 验收标准  | 1. `status="missing_amount"` 时输出对应询问话术；2. `status="confirm"` 时输出确认话术且 `selected_product` 被写入；3. `status="cancel_confirm"` 时输出取消确认话术；4. `response_template_vars` 中的变量在话术模板中正确替换；5. 变量缺失时替换为空字符串（非保留占位符）；6. `response_template_keys` 为空时放行原 `ask_user` 行为；7. key 未找到时放行原 `ask_user` 行为；8. 话术通过 `interrupt_start` 事件推送，**不经固定帧切分**；9. 用户回复后，Rail 将用户回复作为 `tool_result` 回给 LLM（Resume 路径）。 |

**参数说明**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|:---:|------|
| `response_template_keys` | string（JSON dict 字符串） | 否 | 状态到话术 key 的映射 dict，格式为 `'{"status_value": "话术key"}'`。如 `'{"missing_amount": "ask_buy_amount", "confirm": "confirm_product"}'`。 |
| `response_template_status` | string | 否 | 当前状态值，用于在 `response_template_keys` dict 中查找对应的话术 key。如 `"missing_amount"`、`"confirm"`、`"cancel_confirm"`。 |
| `response_template_vars` | string（JSON dict 字符串） | 否 | 模板变量 dict，格式为 `'{"product_name": "稳盈宝", "buy_amount": 50000}'`。用于 `safe_format` 渲染话术模板中的 `{var}` 占位符。 |

**与 UC-A04 的差异**：

| 对比项 | UC-A04（call\_versatile） | UC-A07（ask\_user） |
|--------|--------------------------|---------------------|
| `response_template_keys` 类型 | JSON 数组 `[成功key, 失败key]` | JSON dict `{"status": "key"}` |
| key 选择方式 | 按 status 取下标（0=成功/1=失败） | 按 status 在 dict 中查找 |
| 模板变量 | 无（话术文本固定） | 有（`response_template_vars` + `safe_format`） |
| 触发中断 | 是（`InterruptRequest`） | 是（`InterruptRequest`） |
| 特殊行为 | 无 | `status="confirm"` 时写入 `selected_product` |
| 话术输出事件 | `interrupt_start` | `interrupt_start` |

***

## 6. 模块 B：固定帧话术

### UC-B01 固定帧启用/关闭切换

| 字段    | 内容                                                                                                                                                                          |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-B01                                                                                                                                                                      |
| 主参与者  | R1 配置管理员 / R3 运行时                                                                                                                                                           |
| 前置条件  | 配置项 `think_chunk_mode` 与 `think_chunk_fixed_scripts.enabled` 存在。                                                                                                            |
| 主流程   | 1. 配置 `think_chunk_mode = fixed_script`、`enabled = true`；2. Agent 进入思考阶段，开始接收 LLM token 流；3. 运行时不输出原始 token，改按固定帧话术推送；4. 思考结束，恢复正常输出。                                       |
| 备选流   | A1. `think_chunk_mode = real_stream`：忽略 fixed\_scripts 配置，直接输出原始 token；A2. `enabled = false`：即使 mode=fixed\_script 也不启用，输出原始 token；A3. 运行中切换开关：**不支持热切换**，配置变更需重启 Agent 生效。 |
| 后置条件  | 启用时：用户看到固定帧话术而非真实思考 token；关闭时：用户看到真实 token 流。                                                                                                                               |
| 验收标准  | 1. `mode=fixed_script & enabled=true` → 输出固定帧话术；2. `mode=real_stream` 或 `enabled=false` → 输出原始 token；3. 切换不导致会话中断；4. 运行期内修改 enabled/think\_chunk\_mode 不影响当前会话；5. 重启后新配置生效。 |

***

### UC-B02 query\_patterns 关键字匹配帧话术

| 字段    | 内容                                                                                                                                                                                                                                                                                 |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-B02                                                                                                                                                                                                                                                                             |
| 主参与者  | R3 运行时                                                                                                                                                                                                                                                                             |
| 前置条件  | 1. 固定帧已启用；2. 当前为 planning 阶段（第1轮思考）；3. 已加载 default\_scripts / query\_patterns / scripts。                                                                                                                                                                                           |
| 主流程   | 1. 用户输入 query（如"我想购买理财"）；2. 运行时按 query\_patterns 顺序匹配 keywords；3. 命中"购买/买/下单/确认"组；4. 取该组 scripts\["正在确认相关信息..."]；5. 按帧参数切分并推送。                                                                                                                                                     |
| 备选流   | A1. 多个 pattern 命中：按配置顺序取第一个命中项；A2. 全部 pattern 未命中：降级使用 `default_scripts`；A3. default\_scripts 也为空：降级使用 `scripts` 字段（向后兼容，见 UC-B05）；A4. keywords 为空数组：该 pattern 永不命中；A5. 场景级 query\_patterns 与框架级 query\_patterns：**同 key 时场景级覆盖框架级，不合并**；不同 key 各自生效；覆盖判定以 keywords 组为单位（非逐关键字合并）。 |
| 后置条件  | 用户看到与关键词匹配的固定帧话术。                                                                                                                                                                                                                                                                  |
| 验收标准  | 1. 附件3 中 3 组通用关键词（推荐类/购买类/查询类）均能命中对应话术；2. 未命中时正确降级到 default\_scripts；3. 多命中取首个；4. 匹配在 planning 阶段生效；5. 场景级定义了与框架级相同的 keywords 组时，仅场景级生效；6. 场景级未定义的 keywords 组，框架级继续生效。                                                                                                             |

***

### UC-B03 帧渲染参数配置（字符数/token数/间隔）

| 字段    | 内容                                                                                                                                                                                                                                                |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-B03                                                                                                                                                                                                                                            |
| 主参与者  | R3 运行时                                                                                                                                                                                                                                            |
| 前置条件  | 固定帧已启用；已配置 chars\_per\_frame / tokens\_between\_frames / min\_interval\_ms。                                                                                                                                                                       |
| 主流程   | 1. 选定目标话术脚本（如"正在分析您的需求..."）；2. 按 `chars_per_frame=4` 切分为子帧："正在分析"、"您的需求"、"..."；3. 每累积 `tokens_between_frames=2` 个 LLM token 推送一个子帧；4. 相邻子帧间隔不少于 `min_interval_ms=50ms`。                                                                           |
| 备选流   | A1. `chars_per_frame=0`：不切分，整句一次性推送；A2. `tokens_between_frames=0`：不按 token 节流，按 min\_interval\_ms 节流；A3. `min_interval_ms=0`：不限速，按 token 节流推送；A4. 话术字符数不足以填满一帧：按实际剩余字符推送；A5. LLM token 流提前结束：剩余未推送子帧立即冲刷输出；A6. 话术长度 < chars\_per\_frame：单帧推送完整话术。 |
| 后置条件  | 前端收到逐字渲染的固定帧序列，节奏符合配置。                                                                                                                                                                                                                            |
| 验收标准  | 1. chars\_per\_frame=4 时，4字一帧；2. tokens\_between\_frames=2 时，每2个 token 推一帧；3. min\_interval\_ms=50 时，帧间隔 ≥ 50ms；4. 三参数为 0 时的边界行为符合定义；5. token 流结束时分帧全部冲刷完毕。                                                                                       |

***

### UC-B04 阶段化帧话术切换（planning/executing/resuming）

| 字段    | 内容                                                                                                                                                                                                                                                                          |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-B04                                                                                                                                                                                                                                                                      |
| 主参与者  | R3 运行时                                                                                                                                                                                                                                                                      |
| 前置条件  | 固定帧已启用；配置了 default\_scripts/query\_patterns/execution\_scripts/resume\_scripts。                                                                                                                                                                                             |
| 主流程   | 1. 第1轮思考（planning）：使用 default\_scripts 或 query\_patterns 命中项；2. 工具执行后进入第2轮思考（executing）：切换到 execution\_scripts；3. 用户中断后回复"continue"触发续轮（resuming）：若 `enable_resume_scripts=true` 使用 resume\_scripts，否则不输出固定话术。                                                              |
| 备选流   | A1. executing 阶段 execution\_scripts 为空：降级到 scripts 字段；A2. `enable_resume_scripts=false`：resuming 阶段**不输出固定话术，也不回退 real\_stream**（即不输出任何思考内容）；A3. 阶段切换时上一阶段未推完的子帧：**继续输出完毕，不丢弃**，然后才开始新阶段话术推送；A4. resuming 触发条件非"continue"：按实际 Cascade 协议判定。                                 |
| 后置条件  | 不同思考阶段输出对应阶段话术。                                                                                                                                                                                                                                                             |
| 验收标准  | 1. planning 阶段使用 default\_scripts/query\_patterns；2. executing 阶段使用 execution\_scripts；3. enable\_resume\_scripts=true 时 resuming 使用 resume\_scripts；4. enable\_resume\_scripts=false 时 resuming 不输出固定话术，也不输出真实 token；5. 阶段切换时，上一阶段剩余子帧全部推送完成后，再切换到新阶段话术；6. 不出现子帧丢弃导致的文案截断。 |

***

### UC-B05 scripts 字段向后兼容降级

| 字段    | 内容                                                                                                                                    |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-B05                                                                                                                                |
| 主参与者  | R3 运行时                                                                                                                                |
| 前置条件  | default\_scripts / query\_patterns / execution\_scripts / resume\_scripts 均为空或缺省。                                                     |
| 主流程   | 1. 固定帧启用，但所有阶段化字段为空；2. 运行时降级使用顶层 `scripts` 字段（如 "正在分析您的需求..."）；3. 按 UC-B03 切分推送。                                                      |
| 备选流   | A1. `scripts` 也为空：`select_fixed_scripts` 返回 `[]`，feeder 以空列表初始化，`all_sent=True`，抑制真实输出，保持静默；A2. 仅部分阶段字段为空：仅该阶段降级到 scripts，其他阶段保持各自配置。 |
| 后置条件  | 旧版配置（仅 scripts）仍可工作。                                                                                                                  |
| 验收标准  | 1. 阶段化字段全空时，scripts 字段被使用；2. 部分空时仅对应阶段降级；3. 向后兼容不破坏新配置行为。                                                                             |

***

## 7. 模块 C：思维链事件话术覆盖

### UC-C01 todolist\_start/end 话术

| 字段    | 内容                                                                                                                                                                                |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-C01                                                                                                                                                                            |
| 主参与者  | R3 运行时                                                                                                                                                                            |
| 前置条件  | Agent 进入任务清单规划阶段。                                                                                                                                                                 |
| 主流程   | 1. Agent 开始规划 todolist；2. 触发 todolist\_start → 输出"已生成任务规划"；3. 规划完成；4. 触发 todolist\_end → 输出"任务规划完成"。                                                                              |
| 备选流   | A1. 场景级覆盖了 todolist\_start/end：使用场景级文案；A2. 规划失败：**不输出 todolist\_end**，仅 todolist\_start 已输出；失败按错误流处理。                                                                             |
| 后置条件  | 用户看到规划开始/完成的提示。                                                                                                                                                                   |
| 验收标准  | 1. todolist\_start/end 文案正确；2. 场景级覆盖生效；3. 事件时机与规划生命周期一致；4. 规划成功：todolist\_start → todolist\_end 均输出；5. 规划失败：仅 todolist\_start，无 todolist\_end；6. 失败后不进入 todo\_start/todo\_end 流程。 |

***

### UC-C02 interrupt\_start 中断追问话术

| 字段    | 内容                                                                                                                                                                                                                                                   |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-C02                                                                                                                                                                                                                                               |
| 主参与者  | R2 终端用户 / R3 运行时                                                                                                                                                                                                                                     |
| 前置条件  | Agent 检测到需用户补充信息，触发中断。                                                                                                                                                                                                                               |
| 主流程   | 1. Agent 检测信息缺失；2. 触发 interrupt\_start → 输出"需要您确认以下信息"；3. 附带追问内容，追问内容来源由场景配置开关 `interrupt_source` 控制（配置位置：场景 frontmatter，可选值 `"script"` / `"llm"`，默认 `"script"`）：若 `interrupt_source = "script"`，则追问内容**必须来源脚本**（不可由 LLM 生成）；4. 等待用户回复；5. 用户回复后继续执行。 |
| 备选流   | A1. 用户取消：走 UC-C03；A2. 用户超时未回复：**超时后链接断开，不输出任何话术**；A3. 场景级覆盖 interrupt\_start：使用场景级文案。                                                                                                                                                                |
| 后置条件  | 用户被引导补充信息；会话进入等待态。                                                                                                                                                                                                                                   |
| 验收标准  | 1. interrupt\_start 文案正确；2. 中断后 Agent 暂停执行等待用户；3. 用户回复后正确续行；4. `interrupt_source = "script"` 时，追问内容必须来自脚本，LLM 生成内容被拒绝；5. `interrupt_source = "llm"` 时，追问内容可由 LLM 生成；6. 超时后连接断开，不送 task\_cancelled/兜底话术；7. 超时断链事件可审计。                                 |

***

### UC-C03 task\_cancelled / cancel\_confirm 话术（两步取消流程）

| 字段    | 内容                                                                                                                                                                                                 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-C03                                                                                                                                                                                             |
| 主参与者  | R2 终端用户 / R3 运行时 / LLM                                                                                                                                                                            |
| 前置条件  | 用户发起取消或 Agent 触发取消确认。                                                                                                                                                                              |
| 主流程   | **两步取消流程**：**第一步（确认取消）**：1. 用户表达取消意图；2. LLM 识别取消意图后调用 `ask_user` 工具，传入 `response_template_status='cancel_confirm'`、`response_template_keys='{"cancel_confirm": "cancel_confirm"}'`；3. `AskUserRail` 拦截 `ask_user`，用 `cancel_confirm` key 从话术配置查找话术文本"确认要取消当前操作吗？"；4. 写入 `session.response_template` → 触发 `InterruptRequest` 中断 → 前端收到 `interrupt_start` 事件；5. 用户回复确认取消。**第二步（执行取消）**：6. `AskUserRail` Resume 路径将用户回复作为 `tool_result` 回给 LLM；7. LLM 调用 `cancel_task` 工具（`reason` 默认 `"task_cancelled"`）；8. `CancelRail.after_tool_call` 拦截 `cancel_task`，用 `reason` 作为 key 从话术配置查找话术文本"好的，已为您取消当前操作。如需其他帮助，请随时告诉我。"；9. 写入 `session.response_template` → 标记 `checkpoint_to_release`（下一轮请求时清理 Redis + 内存 session + context\_engine）；10. 调用 `ctx.request_force_finish()` 强制终止 Agent 循环；11. Agent 流末读取 `response_template` → 以 `interrupt_start` 事件推送取消话术至前端。 |
| 备选流   | A1. 用户在 cancel\_confirm 阶段选择"不取消"：`AskUserRail` Resume 路径将用户回复回给 LLM，LLM 继续正常执行，不调用 `cancel_task`；A2. 系统异常导致强制取消：直接输出 task\_cancelled，跳过 cancel\_confirm；A3. 场景级覆盖：使用场景级文案替代默认文案；A4. `cancel_task` 的 `reason` 参数可自定义（如 `"session_timeout"`），对应话术 key 为 `reason` 值；A5. 话术配置中未找到 `reason` 对应的 key：记录 warn 日志，不输出话术，但仍强制终止。 |
| 后置条件  | 任务被取消：Agent 循环终止；`session.response_template` 包含取消话术；`checkpoint_to_release` 已标记（下一轮请求时执行三层清理）；前端收到 `interrupt_start` 事件。 |
| 验收标准  | 1. cancel\_confirm 话术正确输出"确认要取消当前操作吗？"；2. task\_cancelled 话术正确输出"好的，已为您取消当前操作..."；3. 二次确认逻辑生效（用户不确认时不执行取消）；4. `cancel_task` 执行后 Agent 循环强制终止；5. `checkpoint_to_release` 被标记，下一轮请求时 Redis/内存/session 被清理；6. `reason` 参数可自定义话术 key（如 `"session_timeout"`）；7. 话术 key 未找到时记录 warn 日志但不阻断取消流程；8. 取消话术通过 `interrupt_start` 事件推送，**不经固定帧切分**。 |

***

### UC-C04 out\_of\_scope 超范围话术

| 字段    | 内容                                                                         |
| ----- | -------------------------------------------------------------------------- |
| 用例 ID | UC-C04                                                                     |
| 主参与者  | R3 运行时                                                                     |
| 前置条件  | Agent 识别用户请求超出业务支持范围。                                                      |
| 主流程   | 1. Agent 识别意图超出范围；2. 触发 out\_of\_scope → 输出"正在学习中，暂不支持该业务。"；3. 不执行后续工具/规划。 |
| 备选流   | A1. 场景级覆盖 out\_of\_scope：使用场景级文案；A2. 误判为超范围：用户可重新表述，Agent 重新识别。            |
| 后置条件  | 用户收到不支持提示；会话不进入规划。                                                         |
| 验收标准  | 1. out\_of\_scope 文案正确；2. 超范围时不触发 todolist/tool 事件；3. 场景级覆盖生效。             |

***

### UC-C05 首轮开场话术（request_start / planning_start 以 interrupt_start 发出）

> **对齐说明（v1.3）**：Java 实现对齐 Python `InterruptStartEvent` 设计——`request_start`/`planning_start` 是**话术配置键**（script keys），不是独立事件类型。首轮开场时，两者成对以 `interrupt_start` 事件发出（`ScriptsRail.beforeInvoke`），续轮不重复（对齐 Python `is_resume` 守卫）。`EdpaEventType.REQUEST_START`/`PLANNING_START` 枚举值仅保留用于话术键查找（`wireName()`），不再作为事件类型发射。`planning_start` 不因 `todo_create` 或 `PLAN_FIRST` 拦截而单独触发（已移除 `maybeEmitPlanningStart`，仅首轮成对发出）。

| 字段    | 内容                                                                                                                                                                                                   |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 用例 ID | UC-C05                                                                                                                                                                                               |
| 主参与者  | R3 运行时（`ScriptsRail.beforeInvoke`）                                                                                                                                                                  |
| 前置条件  | 1. 用户请求已接收，Agent 即将进入首轮规划；2. 当前为会话首轮（`isFirstTurn(ctx) == true`，即无 resume 标记）。                                                                                                                       |
| 主流程   | 1. 用户发送请求；2. `ScriptsRail.beforeInvoke` 判定为首轮（`isFirstTurn`）；3. 以 `interrupt_start` 事件发出 `request_start` 话术 → 输出"您的请求已收到。"；4. 以 `interrupt_start` 事件发出 `planning_start` 话术 → 输出"我们正在为您进行规划。"；5. 后续接 todolist\_start（UC-C01）。 |
| 备选流   | A1. 场景级覆盖：使用场景级文案；A2. 用户请求非法/为空：**仍送出 request\_start 话术**（首轮无条件发出），之后按非法请求处理流程（如 out\_of\_scope 或错误提示）；A3. 续轮（非首轮，`isFirstTurn == false`）：**不重复发出 request\_start/planning\_start 话术**（对齐 Python `is_resume` 守卫）。 |
| 后置条件  | 用户感知到请求接收与规划开始；前端收到两个 `interrupt_start` 事件（分别承载 request\_start 和 planning\_start 话术）。                                                                                                               |
| 验收标准  | 1. request\_start/planning\_start 话术文案正确；2. 两者均以 `interrupt_start` 事件类型发出（**非独立事件类型**）；3. 事件顺序为 `interrupt_start`(request\_start话术) → `interrupt_start`(planning\_start话术) → todolist\_start；4. 仅首轮发出，续轮不重复（`isFirstTurn` 守卫）；5. 场景级覆盖生效；6. 空请求/非法请求仍触发首轮开场话术输出；7. `planning_start` 话术不因 `todo_create` 或 `PLAN_FIRST` 拦截而单独触发（仅首轮成对发出）。 |

***

## 8. 待澄清问题（剩余）

> 无剩余待澄清问题。

***

## 9. 澄清收敛记录（v1.1）

| 原 Q# | 问题                               | 答复               | 影响用例   | 收敛结论                                                                      |
| ---- | -------------------------------- | ---------------- | ------ | ------------------------------------------------------------------------- |
| Q1   | 变量值缺失处理                          | 保留占位符            | UC-A06 | 缺失变量保留 `{var}` 原样                                                         |
| Q2   | enabled 是否热切换                    | 不支持，需重启          | UC-B01 | 运行中不切换，重启生效                                                               |
| Q3   | 场景级 vs 框架级 query\_patterns       | 相同定义时覆盖          | UC-B02 | 同 key 场景级覆盖框架级，不合并                                                        |
| Q4   | enable\_resume\_scripts=false 行为 | 不回退 real\_stream | UC-B04 | resuming 阶段不输出固定话术，也不出真实 token                                            |
| Q5   | 阶段切换未推完子帧                        | 继续输出，不丢弃         | UC-B04 | 切换前子帧队列冲刷完成后再切阶段                                                          |
| Q6   | 阶段化字段与顶层 scripts 均为空时行为          | 返回空列表            | UC-B05 | `select_fixed_scripts` 返回 `[]`，feeder 以空列表初始化→`all_sent=True`→抑制真实输出，保持静默 |
| Q7   | 规划失败是否送 todolist\_end            | 不送               | UC-C01 | 仅规划成功才送 todolist\_end                                                     |
| Q8   | interrupt 追问内容来源                 | 按开关配置，配脚本则必须脚本   | UC-C02 | 配置开关控制来源，脚本优先级强制                                                          |
| Q9   | interrupt 超时策略                   | 链接断开，无话术         | UC-C02 | 超时即断链，不输出任何话术                                                             |
| Q10  | 非法/空请求是否送 request\_start         | 送出（以 interrupt\_start 事件） | UC-C05 | 首轮无条件送出 request\_start 话术（以 `interrupt_start` 事件发出，对齐 Python `InterruptStartEvent`） |
| Q11  | 任务级匹配方式                          | 精确匹配             | UC-A03 | key 必须完全相等才命中                                                             |
| Q12  | Skill 脚本事件话术是否经固定帧切分             | 不需要              | UC-A05 | 脚本话术原样透传，不切分                                                              |

***

## 10. 验收标准汇总（可测试项）

### 10.1 业务场景话术

- [ ] 默认兜底话术 12 个事件键全部可输出
- [ ] 场景级话术结构与兜底一致，部分覆盖时正确降级
- [ ] 任务级模板 5 个示例意图全部命中
- [ ] 优先级链：任务级 → 兜底（两层），严格生效
- [ ] 任务级模板精确匹配，无歧义命中（UC-A03）
- [ ] "理财购买" 与 "理财选品购买" 互不误命中
- [ ] Skill.yaml 工具话术在 call\_versatile 成功&识别时输出
- [ ] 非 call\_versatile 工具回退兜底
- [ ] response_template_keys 成功时输出成功话术（UC-A04）
- [ ] response_template_keys 失败时输出失败话术（UC-A04）
- [ ] ui_notice 优先于 response_template_keys（UC-A04 备选流 A3）
- [ ] response_template_keys 为空时不输出结果话术（UC-A04 备选流 A4）
- [ ] 结果话术不经固定帧切分（UC-A04）
- [ ] 归一化脚本超时/异常时降级取失败 key（UC-A04 备选流 A6）
- [ ] Skill 脚本可送出自定义事件话术，非法事件被拒
- [ ] Skill 脚本话术原样透传，不经固定帧切分（UC-A05）
- [ ] {tool\_name}/{title} 变量正确渲染
- [ ] 变量缺失时保留 `{var}` 占位符（UC-A06）
- [ ] ask\_user status="missing\_amount" 时输出询问话术（UC-A07）
- [ ] ask\_user status="confirm" 时输出确认话术且 selected\_product 被写入（UC-A07）
- [ ] ask\_user status="cancel\_confirm" 时输出取消确认话术（UC-A07）
- [ ] ask\_user response\_template\_vars 变量正确替换，缺失时替换为空字符串（UC-A07）
- [ ] ask\_user response\_template\_keys 为空时放行原 ask\_user 行为（UC-A07）
- [ ] ask\_user 话术不经固定帧切分（UC-A07）
- [ ] ask\_user 用户回复后 Resume 路径将回复回给 LLM（UC-A07）

### 10.2 固定帧话术

- [ ] `mode=fixed_script & enabled=true` 输出固定帧
- [ ] `mode=real_stream` 或 `enabled=false` 输出原始 token
- [ ] enabled/mode 不支持热切换，需重启（UC-B01）
- [ ] 3 组通用关键词命中对应话术
- [ ] 未命中降级到 default\_scripts
- [ ] default\_scripts 为空降级到 scripts
- [ ] 场景级 query\_patterns 同 key 覆盖框架级，不合并（UC-B02）
- [ ] chars\_per\_frame=4 切分正确，=0 整句推送
- [ ] tokens\_between\_frames=2 节流正确，=0 不按 token 节流
- [ ] min\_interval\_ms=50 限速正确，=0 不限速
- [ ] planning 阶段使用 default\_scripts/query\_patterns
- [ ] executing 阶段使用 execution\_scripts
- [ ] resuming 阶段按 enable\_resume\_scripts 控制是否输出
- [ ] enable\_resume\_scripts=false 时 resuming 不输出任何思考内容（UC-B04）
- [ ] 阶段切换时上一阶段子帧冲刷完毕，不丢弃（UC-B04）
- [ ] token 流结束时剩余子帧全部冲刷

### 10.3 事件覆盖

- [ ] todolist\_start/end、todo\_start/end、tool\_start/end、interrupt\_start、task\_cancelled、cancel\_confirm、out\_of\_scope 全覆盖（`request_start`/`planning_start` 为话术配置键，以 `interrupt_start` 事件发出，见 UC-C05）
- [ ] 各事件场景级覆盖生效
- [ ] 事件时机与 Agent 生命周期一致
- [ ] 规划失败不送 todolist\_end（UC-C01）
- [ ] interrupt 追问来源按开关配置，脚本来源强制脚本（UC-C02）
- [ ] interrupt 超时断链，无话术（UC-C02）
- [ ] 两步取消流程：ask\_user cancel\_confirm → cancel\_task task\_cancelled（UC-C03）
- [ ] cancel\_confirm 话术通过 AskUserRail 输出（UC-C03 第一步）
- [ ] task\_cancelled 话术通过 CancelRail 输出（UC-C03 第二步）
- [ ] cancel\_task 执行后 Agent 循环强制终止（UC-C03）
- [ ] checkpoint\_release 被标记，下一轮请求时三层清理生效（UC-C03）
- [ ] reason 参数可自定义话术 key（如 session\_timeout）（UC-C03）
- [ ] 非法/空请求仍送首轮开场话术（request\_start/planning\_start 以 interrupt\_start 发出）（UC-C05）

### 10.4 安全与合规

- [ ] 固定帧启用时，原始思考 token 不外泄
- [ ] resuming 阶段 enable\_resume\_scripts=false 时，真实 token 也不外泄
- [ ] 话术内容审计可追溯（来源标识：default/scene/task\_template/skill/skill\_script）
- [ ] 配置文件加载失败 fail-fast，不静默运行
- [ ] 运行中配置变更不热生效，避免不一致状态

***

## 11. 范围说明

- 本用例集仅覆盖**话术配置与输出**功能，不涉及：
  - EDPAgent 动态规划算法本身（任务编排/工具选择逻辑）
  - LLM 模型推理性能与质量
  - 前端渲染细节（仅约束推送内容与节奏）
  - 多租户/权限模型（话术配置的访问控制另议）

***

## 附录 A：话术配置模板汇总

### A.1 默认兜底思维链话术定义

```yaml
scripts:
  tool_start: "正在调用：{tool_name}"
  tool_end: "{tool_name} 执行完成"
  todo_start: "开始执行：{title}"
  todo_end: "{title} 已完成"
  todolist_start: "已生成任务规划"
  todolist_end: "任务规划完成"
  interrupt_start: "需要您确认以下信息"
  request_start: "您的请求已收到。"
  planning_start: "我们正在为您进行规划。"
  task_cancelled: "好的，已为您取消当前操作。如需其他帮助，请随时告诉我。"
  cancel_confirm: "确认要取消当前操作吗？"
  out_of_scope: "正在学习中，暂不支持该业务。"
```

> **话术键与事件类型关系（v1.3）**：`request_start`/`planning_start` 为**话术配置键**（script keys），非独立事件类型。首轮开场时由 `ScriptsRail.beforeInvoke` 以 `interrupt_start` 事件发出（对齐 Python `InterruptStartEvent`）。`task_cancelled`/`cancel_confirm` 等结果话术同样以 `interrupt_start` 事件发出（由 `EdpaEventRail.afterInvoke` 出口发射，或 `onToolException` 中断发射）。`EdpaEventType.REQUEST_START`/`PLANNING_START` 枚举值仅保留用于话术键查找（`wireName()`），不再作为事件类型发射。

### A.2 工具级话术匹配模板

```yaml
query_intent_tool_text:
  "查询账户余额":
    tool_start: "正在查询账户余额..."
    tool_end: "已查询账户余额"
  "快速转账":
    tool_start: "正在执行资金转账..."
    tool_end: "资金转账结束"
  "理财购买":
    tool_start: "正在办理理财产品购买..."
    tool_end: "理财产品购买流程结束"
  "理财选品购买":
    tool_start: "正在办理理财产品购买..."
    tool_end: "理财产品购买流程结束"
  "理财推荐":
    tool_start: "正在获取理财产品列表..."
    tool_end: "已获取理财产品列表"
```

> 匹配方式：**精确匹配**（key 完全相等才命中，大小写/空白敏感）。
> 适用范围：**对所有业务工具生效**。`call_versatile` 由 `VersatileInterruptRail` 发送 `tool_start`/`tool_end` 事件；其他工具（如 `call_mcp`）由 `ExecutionLimitRail` 发送。匹配 key 来自 `tool_args["query_intent"]`。

### A.3 固定帧话术定义模板

```yaml
think_chunk_mode: real_stream
# 固定话术帧配置（仅 think_chunk_mode=fixed_script 时生效）
think_chunk_fixed_scripts:
  enabled: true
  chars_per_frame: 4          # 每帧4字符（逐字渲染模式，0=不切分整句推送）
  tokens_between_frames: 2    # 每累积2个LLM token推送一个子帧
  min_interval_ms: 50         # 子帧间最少间隔50ms（0=不限速）
  # ── planning 阶段话术（第1轮思考）──────────────────────────────
  # 默认话术（query_patterns 全未命中时降级使用）
  default_scripts:
    - "正在分析您的需求..."
  # 通用关键词匹配（框架级兜底，当场景配置未命中时使用）
  # 注意：此为通用匹配，业务专属关键词请配置到场景文件 query_patterns 中
  query_patterns:
    # 通用推荐类关键词（跨场景通用）
    - keywords: ["推荐", "看看", "有什么"]
      scripts:
        - "正在为您搜索相关内容..."
    # 通用购买/确认类关键词（跨场景通用）
    - keywords: ["购买", "买", "下单", "确认"]
      scripts:
        - "正在确认相关信息..."
    # 通用查询类关键词（跨场景通用）
    - keywords: ["查询", "查看", "搜索", "了解"]
      scripts:
        - "正在为您查询相关信息..."
  # ── executing 阶段话术（第2轮及后续思考轮次）────────────────────
  # 当 Agent 在执行工具后进入反思/决策思考时使用
  execution_scripts:
    - "正在分析执行结果..."
  # ── resuming 阶段话术（Cascade 续轮，query="continue"）─────────
  # 当用户在中断后回复触发续轮时使用
  # enable_resume_scripts: 是否启用 resuming 阶段固定话术（默认 false）
  # 设为 false 时，resuming 阶段不输出固定话术
  enable_resume_scripts: false
  resume_scripts:
    - "当前业务步骤已为您处理完毕"
  # 保留 scripts 字段（向后兼容：以上所有字段均为空时降级使用）
  scripts:
    - "正在分析您的需求..."
```

### A.4 理财推荐场景话术配置示例

```yaml
name: interact_finance_rec_skill
description: 处理首次推荐完成后的后续交互式多轮理财产品推荐。
  触发词：换一批、再推荐、换个XX（稳健型/低风险/短期/长期/收益高的）、不要XX（R5/高风险）、追加条件、修改筛选条件、按收益排序。
  不要用于：首次推荐、产品选择确认、资金筹划、账户查询。
# Phase1 解耦优化：业务话术自包含
scripts:
  mcp_result_empty: "根据您的条件没有找到合适产品，您可以从以下产品中选择一个或者重新筛选。"
  product_recommend_success: "我找到以上您可能感兴趣的产品，可以告诉我购买哪支产品及购买金额，如果不满意请告诉我重新推荐，比如换一批产品，或者持有周期在12个月以上的产品。"
  product_recommend_empty: '我理解你对稳健收益的追求，但"稳赚不赔"的产品在金融领域并不存在。我可以从其他角度出发，为你筛选一些历史表现稳健产品作为参考。'
  product_recommend_no_card: "当前理财账户没有绑定借记卡，请到理财菜单下的交易账户管理进行绑定"
```

***

## 附录 B：评审问题清单（逐条澄清用）

> 来源：2026-06-29 基于 `EDPAgent` 源码全维度评审。每条问题标注等级、类型、位置、描述、建议，供逐条澄清后回填结论。

| 编号   | 等级 | 类型   | 位置引用                            | 问题描述                                                                                                                                                                                                                                                                 | 改进建议                                                                                                                                                                 | 澄清结论                          |
| ---- | -- | ---- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| D-01 | 严重 | 正确性  | §3 优先级模型、UC-A03 标题、附录A.2 适用范围     | 文档多处声称 `query_intent_tool_text`"仅对 `call_versatile` 工具有效"。但代码中 `execution_limit_rail.py:146-153` 对 `call_versatile` 以外的业务工具（如 `call_mcp`）同样查 `query_intent_tool_text`；`versatile_interrupt_rail.py:144-152` 对 `call_versatile` 查同一映射。两个 Rail 分工不同但查同一数据源，对所有业务工具均生效。 | 将 UC-A03 标题改为"工具级模板匹配（命中/降级链）"，删除"仅 call\_versatile"限定；附录A.2 适用范围改为"对所有业务工具生效，`call_versatile` 由 VersatileInterruptRail 发送，其他工具（如 `call_mcp`）由 ExecutionLimitRail 发送"。 | 修改为对所有工具生效                    |
| D-02 | 严重 | 完整性  | 文档开头 v1.1 说明、UC-B05 备选流 A1、附录末尾 | 文档三处标注"Q6 仍待澄清"，UC-B05 备选流 A1 写"行为待澄清"。但同名"完档"文档已将 Q6 收敛为"返回空列表——feeder 以空列表初始化→`all_sent=True`→抑制真实输出，保持静默"。本文档未同步。                                                                                                                                                 | 将 Q6 从待澄清移入收敛记录；UC-B05 备选流 A1 改为"`scripts` 也为空：`select_fixed_scripts` 返回 `[]`，feeder 以空列表初始化，`all_sent=True`，抑制真实输出，保持静默"。                                           | 接受建议                          |
| D-03 | 严重 | 清晰性  | UC-A01 验收标准第 1 条                | 验收标准写"附件1中 11 个事件键"，但实际列出 12 个：tool\_start/tool\_end/todo\_start/todo\_end/todolist\_start/todolist\_end/interrupt\_start/request\_start/planning\_start/task\_cancelled/cancel\_confirm/out\_of\_scope。数量与列举不符。                                                     | 将"11 个"改为"12 个"，与附件1实际定义一致。                                                                                                                                          | 修改为12个                        |
| D-04 | 主要 | 清晰性  | §3 优先级模型、附录A.2 字段名                | §3 写 `query_intent_tool_text`，附录A.2 YAML 也写 `query_intent_tool_text:`。但代码实际字段名为 `query_intent_tool_text`（`agent_rule.py:465`、`AgentRule_wealth_purchase.md:108`）。字段名不一致会导致配置填写后运行时无法命中。                                                                                | 全文统一为 `query_intent_tool_text`，与代码 `ScenarioConfig.query_intent_tool_text` 字段名一致。                                                                                    | 全文统一为`query_intent_tool_text` |
| D-05 | 主要 | 正确性  | UC-A03 备选流 A1/A2                | 降级链描述为"任务级→场景级→兜底"三层。但代码中 `execution_limit_rail.py:151-153` 在 `query_intent_tool_text` 未命中时直接降级到 `ScriptsConfig.todo_start.format(title=query_intent)`（兜底），中间无"场景级话术"查找步骤。实际降级链为两层。                                                                                  | 将降级链修正为"任务级精确匹配未命中→降级到 `ScriptsConfig.todo_start`/`todo_end` 兜底（支持 `{title}` 变量渲染）"，删除不存在的"场景级"中间层。                                                                  | 接受建议                          |
| D-06 | 主要 | 清晰性  | UC-C01 主流程、附录A                  | UC-C01 写 todolist\_start 文案为"规划任务清单"、todolist\_end 为"todolist规划完成"。但需求规格文档 §1.1 定义默认值为"已生成任务规划"和"任务规划完成"。两份文档对同一话术键的默认值不一致。                                                                                                                                          | 统一为需求规格文档的默认值——todolist\_start: "已生成任务规划"、todolist\_end: "任务规划完成"。                                                                                                   | 统一为需求规格文档的默认值                 |
| D-07 | 主要 | 规范性  | 附录A.3 `enable_resume_scripts` 注释  | 附录A.3 注释写"默认 true"，但同文件中该字段实际值为 `false`，需求规格文档 §1.3.6 也标注默认值为 `false`。注释与实际值矛盾。                                                                                                                                                                                        | 将注释改为"是否启用 resuming 阶段固定话术（默认 false）"。                                                                                                                               | 接受修改                          |
| D-08 | 次要 | 可测试性 | UC-C02 主流程第 3 步、验收标准第 4-5 条     | UC-C02 描述"追问内容来源由配置开关控制"，但全文未定义该开关的字段名、配置位置、可选枚举值。测试人员无法构造测试数据。                                                                                                                                                                                                      | 补充开关字段名、配置文件位置、可选值（如 `interrupt_source: "script" \| "llm"`），并在验收标准中明确各取值的预期行为。                                                                                       | 补充可测试性描述                      |
| D-09 | 次要 | 清晰性  | UC-A03 前置条件第 2 条                | 前置条件写"当前 todo 节点具备可识别的 `title`/`intent`"。但代码中查找 key 来自 `tool_args.get("query_intent")`，不是 todo 节点的 title。混用会导致测试用例构造错误的数据源。                                                                                                                                          | 将前置条件改为"当前工具调用参数 `tool_args` 中包含 `query_intent` 字段（由 LLM 根据 SKILL.md 填写）"。                                                                                           | 按照建议修改                        |

***

**文档版本**：v1.3
**生成日期**：2026-06-29（v1.2），2026-07-08（v1.3 刷新）
**待澄清**：无（Q1–Q12 已全部收敛；附录 B 评审问题 D-01 \~ D-09 已全部按澄清意见修订入文档；v1.3 对齐 Java 实现：request\_start/planning\_start 为话术配置键，以 interrupt\_start 事件发出）

***

## 附录 C：第二轮评审问题清单（逐条澄清用）

> 来源：2026-06-29 基于 `EDPAgent` 源码第二轮全维度评审。补充第一轮未覆盖的问题。

| 编号   | 等级 | 类型  | 位置引用                | 问题描述                                                                                                                                                                                                                                                                                                         | 改进建议                                                                                                                                                  | 澄清结论 |
| ---- | -- | --- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| E-01 | 严重 | 清晰性 | §4 用例清单 UC-A03 标题   | 用例清单 L49 仍写"工具级模板匹配（命中/降级链，仅 call\_versatile）"——保留了第一轮 D-01 已修正的"仅 call\_versatile"错误描述，与正文 UC-A03 标题不一致。                                                                                                                                                                                                    | 将 §4 用例清单中 UC-A03 标题改为"工具级模板匹配（命中/降级链）"，与正文一致。                                                                                                        | 按照建议修改  |  |
| E-02 | 严重 | 清晰性 | UC-A03 主流程、验收标准、附录A.2 | `query_intent_tool_text` 的键名是 `tool_start`/`tool_end`（见附录A.2 YAML），但代码中发送的事件类型是 `type="todo_start"`/`type="todo_end"`（`execution_limit_rail.py:156`、`versatile_interrupt_rail.py:156`）。文档 UC-A03 主流程写"取命中项的 tool\_start/tool\_end 文案"，验收标准写"任务级话术仅作用于 todo\_start/todo\_end"——命名混淆，测试人员无法区分映射键与事件类型。           | 明确区分：`query_intent_tool_text` 中的键名为 `tool_start`/`tool_end`（配置层面），但运行时发送的事件类型为 `type="todo_start"`/`type="todo_end"`（协议层面）。两者是不同概念，需在文档中明确说明。         | 在文档中说明明确为tool_start/tool_end，具体事件类型可在客户话术脚本中修改  |  |
| E-03 | 主要 | 正确性 | UC-A04 前置条件         | UC-A04 前置条件写"工具为 `call_versatile`（当前唯一支持类型）"。但代码中 `ExecutionLimitRail` 对非 `call_versatile` 的工具（如 `call_mcp`）也发送 `todo_start`/`todo_end` 事件（仅跳过 `call_versatile`，见 L145 `if tool_name != "call_versatile"`）。"唯一支持类型"描述与代码行为矛盾。                                                                                | 将前置条件改为"工具为 `call_versatile`（由 `VersatileInterruptRail` 发送事件）或其他业务工具（如 `call_mcp`，由 `ExecutionLimitRail` 发送事件）"，并说明两类工具的事件发送分工。                       | 明确为只在call_versatile中使用  |  |
| E-04 | 主要 | 清晰性 | UC-A03 验收标准         | UC-A03 验收标准写"任务级话术仅作用于 todo\_start/todo\_end，不覆盖 tool\_start/end 等"。但代码中 `tool_start`/`tool_end` 事件的内容来自 `query_description`/`script_command`/兜底（`execution_limit_rail.py:131-134`），与 `query_intent_tool_text` 无关。此描述易造成误解：`query_intent_tool_text` 只影响 `todo_start`/`todo_end`，不影响 `tool_start`/`tool_end`。 | 改写为"任务级模板（`query_intent_tool_text`）仅用于生成 `todo_start`/`todo_end` 事件的内容，不影响 `tool_start`/`tool_end` 事件（后者使用 `query_description`/`script_command`/兜底）"。 | 根据E-02更新  |  |
| E-05 | 次要 | 规范性 | 文档开头版本号             | 文档开头 L1 标题写"（v1.1）"，但末尾版本信息写"v1.2"。版本号不一致，会导致文档版本溯源混乱。                                                                                                                                                                                                                                                       | 将文档开头标题中的版本号从"v1.1"改为"v1.2"，与末尾一致。                                                                                                                    | 修改一致  |  |
| E-06 | 次要 | 清晰性 | UC-A03 主流程          | UC-A03 主流程写"取命中项的 tool\_start/tool\_end 文案"。但代码中 `query_intent_tool_text` 的键名虽为 `tool_start`/`tool_end`，实际用途是生成 `todo_start`/`todo_end` 事件的 content（见 `execution_limit_rail.py:151-153`）。键名与用途不一致，易造成配置人员误解。                                                                                                 | 在附录A.2 说明中补充："`query_intent_tool_text` 的键名 `tool_start`/`tool_end` 仅用于配置语义，运行时实际映射到 `todo_start`/`todo_end` 事件"。                                        | 根据E-02更新  |

***

## 附录 D：第三轮评审问题清单（合规审查）

> 来源：2026-06-30 基于文档内容全维度合规审查。审查维度：完整性、清晰性、正确性、可测试性、依赖性、规范性。

| 编号   | 等级 | 类型   | 位置引用                    | 问题描述                                                                                                                                                                                                                                                                                                                                                                                                                             | 改进建议                                                                                                                                                                                                                                                                  |
| ---- | -- | ---- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F-01 | 严重 | 正确性  | UC-A03 验收标准第 3 条、UC-A04 主流程/备选流 A2、§3 优先级模型、UC-A02 主流程       | **适用范围描述前后矛盾**：1. UC-A03 验收标准第 3 条仍写"任务级话术仅作用于 todo\_start/todo\_end，不覆盖 tool\_start/end 等"——未反映 E-02/E-04 评审意见的修改要求；2. UC-A04 主流程写"`call_versatile` 工具执行成功且识别时，输出 Skill.yaml 定义的话术"，备选流 A2 写"非 `call_versatile`：**当前不支持**"——与 D-01 结论"对所有业务工具生效"直接矛盾；3. §3 优先级模型写"工具级模板匹配 (query\_intent\_tool\_text) [精确匹配，**对所有业务工具生效**]"，但 UC-A02 主流程写"任务级→场景级→兜底"，与实际代码两层降级链不符。                                                                                     | 1. UC-A03 验收标准第 3 条改为："任务级模板（`query_intent_tool_text`）仅用于生成 `todo\_start`/`todo\_end` 事件的内容，不影响 `tool\_start`/`tool\_end` 事件（后者使用 `query\_description`/`script\_command`/兜底）"；2. UC-A04 主流程/备选流 A2 改为"其他业务工具（如 `call_mcp`）由 `ExecutionLimitRail` 发送 `todo\_start`/`todo\_end` 事件，回退到兜底"；3. §3 优先级模型删除"场景级"中间层，修正为"工具级模板匹配 (query\_intent\_tool\_text) → 降级到 `ScriptsConfig.todo\_start`/`todo\_end` 兜底（两层）"。                          |
| F-02 | 严重 | 正确性  | UC-A04 前置条件              | 前置条件第 2 条写"工具为 `call_versatile`（**当前唯一支持类型**）"，与 D-01 结论"对所有业务工具生效"矛盾，也与 E-03 评审意见的初衷相悖。E-03 澄清结论"明确为只在 call\_versatile 中使用"本身存在错误——代码中 `ExecutionLimitRail` 对非 `call_versatile` 的工具同样查 `query\_intent\_tool\_text`。                                                                                                                                                                         | 将前置条件第 2 条改为"工具为 `call_versatile`（由 `VersatileInterruptRail` 发送 `tool\_start`/`tool\_end` 事件）**或其他业务工具（如 `call_mcp`，由 `ExecutionLimitRail` 发送 `todo\_start`/`todo\_end` 事件）**"，与 D-01 结论一致。E-03 澄清结论应修正为"根据 D-01，对所有工具生效"。                                                                                                      |
| F-03 | 主要 | 清晰性  | UC-C02 主流程、UC-C02 验收标准第 4-5 条   | `interrupt_source` 配置开关的**字段名、配置位置、可选枚举值在正文中未定义**。D-08 评审意见标注"已补充可测试性描述"，但 UC-C02 主流程仅写"追问内容来源由配置开关控制"，验收标准写"`interrupt_source = "script"` 时...、`interrupt_source = "llm"` 时..."——测试人员无法从正文中找到该字段的定义位置和合法取值范围。                                                                                                                                                               | 在 UC-C02 主流程第 3 步中补充："`interrupt_source` 字段位于场景配置 YAML 的 `think_chunk_fixed_scripts` 节点下，可选值为 `"script"`（强制使用 Skill 脚本话术）或 `"llm"`（允许 LLM 生成追问内容）。默认值为 `"script"`。"                                                                                                           |
| F-04 | 主要 | 清晰性  | §3 优先级模型                | §3 写"工具级模板匹配 → 默认兜底话术"，但优先级模型中提到"场景级"作为独立层级，UC-A02 也是场景级话术用例。然而 UC-A03 备选流 A1/A2 的实际降级链只有"任务级→兜底"两层，代码中无场景级查找步骤。§3 的"场景级"描述与实际代码行为不符。                                                                                                                                                                                                                                         | §3 优先级模型中明确说明："实际降级链为两层（任务级精确匹配未命中 → 降级到 `ScriptsConfig.todo\_start`/`todo\_end` 兜底）。UC-A02 场景级话术指的是在 Skill.yaml 场景配置中定义的话术，与任务级匹配模板是两个独立维度，场景级话术通过 `query\_description` 等字段传入，非通过 `query\_intent\_tool\_text` 路径。"                                                                              |
| F-05 | 次要 | 规范性  | §1 需求背景、§11 范围说明        | 范围说明与需求背景存在潜在冲突：§1 B1 强调"金融行业合规要求：模型原始输出 token 不能直接面客"，§11 说"本用例集不涉及...前端渲染细节（仅约束推送内容与节奏）"。但"模型原始思考 token 不外泄"这一核心合规目标需要前端配合才能真正落地——如果前端能访问原始 token，则合规目标失效。文档未明确前端是否有义务配合阻断原始 token。                                                                                                                                                                     | 在 §11 范围说明中补充："固定帧启用时，前端必须配合不展示 EDPAgent 推送的原始思考 token（由 `think_chunk_mode=real_stream` 产生）。此为话术合规目标的前置条件，由前端实现约束，不在本用例集范围内，但需在集成测试中验证。"                                                                                              |
| F-06 | 次要 | 完整性  | UC-A05 主流程、§11 范围说明        | UC-A05 写"Skill 脚本具备送出事件能力（API/SDK 支持）"，但文档未提供该 API/SDK 的接口签名、调用方式、参数类型。测试人员无法根据文档构造 Skill 脚本的测试用例。                                                                                                                                                                                                                                                                                                     | 在 UC-A05 主流程中补充接口描述的关键要素：1. 接口名称（如 `skill.emit_event(event_name, content)`）；2. 调用方式（同步/异步）；3. 事件名合法性校验规则（是否支持任意字符串、是否有枚举限制）。若接口规范另立文档，则在 §11 范围说明中引用。                                                                                   |
| F-07 | 次要 | 清晰性  | 附录A.1、UC-C01 主流程、UC-C05 主流程 | **话术键命名不一致**：附录A.1 默认兜底话术定义中键名为 `task_cancelled` 和 `cancel_confirm`，但 UC-C03 用例正文中多次将 `task_cancelled` 与"取消操作"关联、`cancel_confirm` 与"确认取消"关联。UC-C05 主流程写 `request_start`/`planning_start`，而 UC-A01 验收标准中列举的事件键未包含 `request_start`/`planning_start`——这 12 个事件键的统计口径与 UC-A01 验收标准第 1 条"12 个事件键"的列举不一致。 | 核查 12 个事件键的完整列表，确保附录A.1、UC-A01 验收标准、UC-C 系列用例中的键名完全一致。当前应至少包含：tool\_start、tool\_end、todo\_start、todo\_end、todolist\_start、todolist\_end、interrupt\_start、request\_start、planning\_start、task\_cancelled、cancel\_confirm、out\_of\_scope。 |

***

## 附录 E：response_template_keys 使用示例（UC-A04）

### E.1 场景描述

理财购买流程中，第六步"购买理财产品"调用 `call_versatile` 工具，根据归一化脚本返回的执行状态（成功/失败），从话术配置中选择对应话术输出给用户。

### E.2 SKILL.md 话术定义

`fund_planning_skill/SKILL.md` frontmatter 中定义业务话术：

```yaml
scripts:
  fund_planning_success: "已为您完成理财产品购买"
  fund_planning_buy_failed: "购买失败，请重新尝试"
  fund_planning_transfer_limit: "您已超过转账次数限制，购买失败"
  fund_planning_wealth_insufficient: "理财账户资金不足，查询活期账户余额"
  fund_planning_both_insufficient: "您的活期账户余额不足，结束理财产品购买"
  fund_planning_card_mismatch: "您只有一张卡，不满足当前理财购买流程，已退出购买"
  fund_planning_purchase_aborted: "购买异常，已退出购买流程"
```

其中 `fund_planning_success` 和 `fund_planning_buy_failed` 通过 `response_template_keys` 路径输出（成功/失败二选一），其余通过 `ui_notice` 路径输出（见 UC-A05）。

### E.3 LLM 调用示例

```python
call_versatile(
   query_description="购买理财产品：产品名称：{product_name}，产品代码：{product_id}，金额：{buy_amount}元",
   query_intent="理财选品购买",
   query_response_analysis_scripts="python fund_planning_skill/scripts/run_fund_planning.py",
   response_template_keys='["fund_planning_success", "fund_planning_buy_failed"]'
 )
```

参数说明：
- `query_intent="理财选品购买"`：用于 UC-A03 工具级模板匹配（tool_start/tool_end 话术）
- `query_response_analysis_scripts="python fund_planning_skill/scripts/run_fund_planning.py"`：归一化脚本命令
- `response_template_keys='["fund_planning_success", "fund_planning_buy_failed"]'`：成功取 [0]，失败取 [1]

### E.4 归一化脚本返回示例

归一化脚本 `run_fund_planning.py` 通过 stdout 输出 JSON：

**成功时**：
```json
["success", {"product_name": "稳盈宝", "buy_amount": 50000, "order_id": "ORD20260707001"}]
```

→ `status="success"` → 取 `response_template_keys[0]` = `"fund_planning_success"` → 输出"已为您完成理财产品购买"

**失败时**：
```json
["failed", {"error_code": "INSUFFICIENT_BALANCE", "error_msg": "活期账户余额不足"}]
```

→ `status="failed"` → 取 `response_template_keys[1]` = `"fund_planning_buy_failed"` → 输出"购买失败，请重新尝试"

### E.5 完整数据流

```
LLM 调用:
  call_versatile(
    query_intent="理财选品购买",
    query_response_analysis_scripts="python fund_planning_skill/scripts/run_fund_planning.py",
    response_template_keys='["fund_planning_success", "fund_planning_buy_failed"]'
  )
     │
     ▼ Rail 拦截 → 委托工作流执行 → 业务数据返回
     │
     ▼ 沙箱执行归一化脚本:
     │   cd "skills/" && python fund_planning_skill/scripts/run_fund_planning.py
     │   环境变量: SKILL_INPUT={"query_intent":"理财选品购买","query_description":"...","business_data":{...}}
     │   stdout: ["success", {"product_name":"稳盈宝",...}]
     │
     ▼ response_template_keys 处理:
     │   key_index = 0 (status=="success")
     │   template_key = "fund_planning_success"
     │   template_text = scripts.get_response_template("fund_planning_success")
     │                   = "已为您完成理财产品购买"
     │   session["response_template"] = "已为您完成理财产品购买"
     │
     ▼ Agent 流末:
         yield InterruptStartEvent(content="已为您完成理财产品购买")
         ← 前端收到购买成功话术
```

### E.6 与 UC-A03 / UC-A05 的协作关系

| 机制 | 参数 | 作用阶段 | 输出事件 |
|------|------|---------|---------|
| UC-A03 query_intent_tool_text | `query_intent` | 工具调用前后 | `tool_start` / `tool_end` |
| UC-A04 response_template_keys | `response_template_keys` + `query_response_analysis_scripts` | 工具执行完成后 | `interrupt_start`（话术推送） |
| UC-A05 ui_notice | 脚本返回 `ui_notice` | 工具执行完成后 | `tool_end` / `todo_end` / `interrupt_start` |

三者独立生效，优先级：`ui_notice` > `response_template_keys` > 默认 `tool_end`。

即：当归一化脚本返回 `ui_notice` 时，跳过 `response_template_keys` 机制，由 `ui_notice` 接管话术输出。

***

## 附录 F：ask\_user 与 cancel 话术使用示例（UC-A07 / UC-C03）

### F.1 场景描述

理财购买流程中，LLM 需要与用户进行多轮交互：
1. 用户未提供购买金额 → LLM 调用 `ask_user` 询问金额（status="missing\_amount"）
2. 用户提供金额后 → LLM 调用 `ask_user` 确认选品（status="confirm"）
3. 用户要求取消 → LLM 调用 `ask_user` 确认取消（status="cancel\_confirm"）→ 用户确认 → LLM 调用 `cancel_task` 执行取消

### F.2 话术配置

`ScriptsConfig.md` 或 Skill.yaml `scripts` 字段中定义：

```yaml
# 兜底话术
task_cancelled: "好的，已为您取消当前操作。如需其他帮助，请随时告诉我。"
cancel_confirm: "确认要取消当前操作吗？"

# Skill 业务话术（fund_planning_skill/SKILL.md scripts 字段）
ask_buy_amount: "请告诉我您想购买的金额"
confirm_product: "确认购买以下产品吗？产品名称：{product_name}，金额：{buy_amount}元"
fund_planning_session_timeout: "对话超时，已退出购买流程"
```

### F.3 示例 1：ask\_user 询问金额（status="missing\_amount"）

**LLM 调用**：
```python
ask_user(
   response_template_keys='{"missing_amount": "ask_buy_amount"}',
   response_template_status="missing_amount",
   response_template_vars='{}'
)
```

**处理流程**：
1. `AskUserRail` 拦截 → 解析 `keys_map = {"missing_amount": "ask_buy_amount"}`
2. `status = "missing_amount"` → `template_key = "ask_buy_amount"`
3. `template_text = scripts.get_response_template("ask_buy_amount")` → "请告诉我您想购买的金额"
4. `vars = {}` → 无变量替换
5. 写入 `session.response_template` → 触发 `InterruptRequest`
6. 前端收到 `interrupt_start` 事件："请告诉我您想购买的金额"
7. 用户回复 "50000 元" → `AskUserRail` Resume 路径将 "50000 元" 作为 `tool_result` 回给 LLM

### F.4 示例 2：ask\_user 确认选品（status="confirm"）

**LLM 调用**：
```python
ask_user(
   response_template_keys='{"confirm": "confirm_product"}',
   response_template_status="confirm",
   response_template_vars='{"product_name": "稳盈宝", "product_id": "P001", "buy_amount": 50000}'
)
```

**处理流程**：
1. `AskUserRail` 拦截 → 解析 `keys_map = {"confirm": "confirm_product"}`
2. `status = "confirm"` → `template_key = "confirm_product"`
3. `template_text = scripts.get_response_template("confirm_product")` → "确认购买以下产品吗？产品名称：{product_name}，金额：{buy_amount}元"
4. `vars = {"product_name": "稳盈宝", "product_id": "P001", "buy_amount": 50000}`
5. `safe_format` 渲染 → "确认购买以下产品吗？产品名称：稳盈宝，金额：50000元"
6. **`status == "confirm"` → 将 `vars` 写入 `session.selected_product`**（记录用户选品）
7. 写入 `session.response_template` → 触发 `InterruptRequest`
8. 前端收到 `interrupt_start` 事件："确认购买以下产品吗？产品名称：稳盈宝，金额：50000元"

### F.5 示例 3：两步取消流程（UC-C03）

**第一步：确认取消**

用户说"取消购买" → LLM 识别取消意图：

```python
ask_user(
   response_template_keys='{"cancel_confirm": "cancel_confirm"}',
   response_template_status="cancel_confirm",
   response_template_vars='{}'
)
```

处理流程：
1. `AskUserRail` 拦截 → `status = "cancel_confirm"` → `template_key = "cancel_confirm"`
2. `template_text = scripts.get_response_template("cancel_confirm")` → "确认要取消当前操作吗？"
3. 写入 `session.response_template` → 触发 `InterruptRequest`
4. 前端收到："确认要取消当前操作吗？"
5. 用户回复"确认取消" → `AskUserRail` Resume 路径将回复回给 LLM

**第二步：执行取消**

LLM 调用 `cancel_task`：

```python
cancel_task(reason="task_cancelled")
```

处理流程：
1. `CancelRail.after_tool_call` 拦截 → `reason = "task_cancelled"`
2. `template_text = scripts.get_response_template("task_cancelled")` → "好的，已为您取消当前操作。如需其他帮助，请随时告诉我。"
3. 写入 `session.response_template`
4. 标记 `checkpoint_to_release`（下一轮请求时清理 Redis + 内存 session + context\_engine）
5. 调用 `ctx.request_force_finish()` 强制终止 Agent 循环
6. Agent 流末 → 前端收到 `interrupt_start` 事件："好的，已为您取消当前操作..."

### F.6 示例 4：自定义取消原因（reason="session\_timeout"）

```python
cancel_task(reason="session_timeout")
```

处理流程：
1. `CancelRail` → `reason = "session_timeout"`
2. `template_text = scripts.get_response_template("session_timeout")` → 查找 Skill.yaml `scripts` 中的 `fund_planning_session_timeout` → "对话超时，已退出购买流程"
3. 写入 `session.response_template` → 强制终止

### F.7 ask\_user 与 call\_versatile 话术机制对比

| 对比项 | UC-A04（call\_versatile） | UC-A07（ask\_user） |
|--------|--------------------------|---------------------|
| 拦截 Rail | `VersatileInterruptRail` | `AskUserRail` |
| `response_template_keys` 类型 | JSON 数组 `[成功key, 失败key]` | JSON dict `{"status": "key"}` |
| key 选择方式 | 按归一化脚本返回的 status 取下标 | 按 `response_template_status` 在 dict 中查找 |
| 模板变量 | 无（话术文本固定） | 有（`response_template_vars` + `safe_format`） |
| 中断行为 | 工具执行完成后自动推送话术 | 主动中断等待用户回复 |
| Resume 路径 | 无（工具已完成） | 有（用户回复作为 `tool_result` 回给 LLM） |
| 特殊行为 | 无 | `status="confirm"` 时写入 `selected_product` |
| 话术输出事件 | `interrupt_start` | `interrupt_start` |

