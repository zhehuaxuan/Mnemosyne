
```
# jiuwen swarm 启动命令
jiuwenswarm-venv\Scripts\activate
#JiuwenSwarm (首次启动)
jiuwenswarm-init

jiuwenswarm-start

jiuwenswarm-tui
```

前端访问：

```
# openjiuwen 启动命令，使用git bash
start.sh up

start.sh down
```



```
git push -u origin xuanzhehua  #基于本地分支，推送到远程分支
```


三个核心进程(AgentServer、Gateway、前端)都在运行,前端页面 http://127.0.0.1:5173 返回 200
服务启动中，端口信息如下：                                                                                            
  ✓ Web UI                 http://localhost:5173                                                                        
  … AgentServer WebSocket  ws://localhost:18092                                                                         
  … Gateway HTTP           http://localhost:19001                                                                       
  … WebChannel WebSocket   ws://localhost:19000/ws





jiuwenswarm-start --stop default
jiuwenswarm-start
jiuwenswarm-start --list


重启命令：
uv run jiuwenswarm-start dev

前端热更新：




Openjiuwen的模块定义：
![](../../_assets/Pasted%20image%2020260728105935.png)



客户的问题：
1. DeepAgent动态规划前界面展示不友好，jiuwenswarm前端展示相对友好，需要借鉴，jiuwen swarm的经验提升DeepAgent后端规划能力稳定性，并在前端友好展示
2. Openjiuwen上下文能力不强，DeepAgent平移了hermes上下文能力以解决该问题，但进行多轮对话后上下文信息混乱，需要借鉴Swarm AI经验解决该问题
3. DeepAgent生产环境使用多台虚拟机分布式部署智能体节点，命名和文件传输到沙箱中执行，沙箱中执行的路径仍为虚拟机路径非沙箱路径，导致沙箱中命名找不到文件，需要解决路径不一致的问题
4. 文件加载分为2种：小文件，大文件，小文件直接作为上下文进行加载，大文件如Excel，csv超过上下文限制，如何作为信源文件进行加载



## 三种模式的区别

它们定义在 `modes.agent` 下，分别是 **性能模式（fast）**、**规划模式（plan）** 和 **集群模式（cluster）**：

### ⚡ 性能模式（fast）
- **记忆策略**：`is_proactive: false` — 记忆**不主动注入**，仅在需要时才检索
- **特点**：轻量、响应快，适合日常快速对话和简单任务
- **适用场景**：闲聊、简单查询、一次性操作，不需要长期上下文跟踪

### 📋 规划模式（plan）← **当前模式**
- **记忆策略**：`is_proactive: true` — 记忆**主动注入**，每轮对话开始时会自动将最新记忆摘要注入到 system prompt
- **特点**：更重的上下文管理，擅长跨轮次跟踪任务进度、维护项目背景
- **适用场景**：复杂任务分解、多步骤执行、需要长期记忆支撑的规划性工作
- 这也是你目前正在使用的模式

### 🏗️ 集群模式（cluster）
- **配置状态**：在注释中提及但**未定义具体配置块**
- **定位**：对应 `team.runtime.mode` 的多机协作场景（当前 `team.runtime.mode: local` 为本地单机模式）
- **特点**：涉及 Leader-Teammate 分布式架构，多个 Agent 实例协同工作
- **适用场景**：大规模任务分发、多角色协作（如 `agent_leader` + `agent_teammate` 分工）

---

### 一句话总结

| 模式 | 核心差异 | 适合场景 |
|------|---------|---------|
| **性能模式** 🏃 | 不做主动记忆，轻量快速 | 日常问答、一次性任务 |
| **规划模式** 🧠 | 主动注入记忆，深度上下文跟踪 | 复杂任务、项目管理 |
| **集群模式** 🌐 | 多 Agent 分布式协作 | 大规模分工协作场景 |

当前你处于**规划模式**，所以我能更好地记住对话上下文和任务进度。如果你想切换模式（比如切换到性能模式获得更快的响应），也可以告诉我。