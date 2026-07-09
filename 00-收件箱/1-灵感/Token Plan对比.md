# Token Plan 对比

## 第一章：AI Coding SOAT 排名查看渠道

"SOAT" 这个词在 AI 编程领域没有标准对应，但在模型编程能力评测中，有几个**权威基准测试和排行榜**值得关注：

### 1. **SWE-bench** ⭐ 最权威
- **地址**: [https://www.swebench.com/leaderboard](https://www.swebench.com/leaderboard)
- 测试 AI 模型解决真实 GitHub Issue 的能力（从 Python 热门项目中提取）
- 目前 **Claude (Anthropic)** 和 **GPT** 系列经常占据榜首
- 这个是编程能力评测里最公认、最难、也最接近真实场景的基准

### 2. **Aider Polyglot Benchmark**
- **地址**: [https://aider.chat/docs/leaderboards/](https://aider.chat/docs/leaderboards/)
- 测试多语言（Python, JS, Go, Rust 等）的代码编辑能力
- 按语言分组排名，更细粒度

### 3. **BigCodeBench**
- **地址**: [https://bigcode-project.org](https://bigcode-project.org)
- 由 HuggingFace 维护，专注代码生成质量

### 4. **LMArena / LiveBench**
- **地址**: [https://lmarena.ai](https://lmarena.ai)
- 提供交互式多维度评测，包括 Coding 专项

### 5. **OpenCompass**（司南）
- **地址**: [https://opencompass.org.cn/leaderboard](https://opencompass.org.cn/leaderboard)
- 上海人工智能实验室出品，中文友好，综合评测

如下所示为司南的权威排行榜：
![](../../_assets/Pasted%20image%2020260709193704.png)

## 第二章：国产大模型 Code 能力排行

> 数据来源：OpenCompass 司南、SuperCLUE、Arena Code Arena、Artificial Analysis 等权威评测（2026年7月整理）。

| 位次 | 模型 | 厂商 | 参数量 | OpenCompass 代码得分 | 其他权威来源 |
|:---:|------|------|:-----:|:-----------------:|------------|
| ≈2 | **GLM-5.2** | 智谱AI | 753B MoE | **≈62**（估）① | Code Arena #2(1595), SWE-bench Pro 62.1, AA #6(51), SuperCLUE 64.13 |
| 3 | Kimi-K2.6 | 月之暗面 | 1T | **62.4** | AA #18(43), Code Arena #12 |
| 4 | Qwen3.6-Max-Preview | 阿里巴巴（通义千问） | N/A | **61.6** | AA #11(46), Code Arena #10 |
| 5 | **MiniMax-M3**② | MiniMax（稀宇科技） | 428B MoE | **≈60**（估） | SWE-bench Pro 59.0, Terminal-Bench 66.0, DeepSWE 20.4% |
| 6 | DeepSeek-V4-Pro | 深度求索 | 1.6T | **59.4** | AA #14(44), SWE-bench Pro 55.4 |
| 8 | Qwen3.5-397B-A17B | 阿里巴巴（通义千问） | 397B | **57.4** | — |
| 9 | Doubao-Seed-2-0-Pro | 字节跳动（豆包） | N/A | **57.0** | — |
| 11 | DeepSeek-V4-Flash | 深度求索 | 284B | **56.4** | — |
| 12 | MiniMax-M2.7③ | MiniMax（稀宇科技） | 230B | **56.2** | AA #13(44) |
| 13 | GLM-5.1 | 智谱AI | 744B | **55.7** | AA #25(40), Code Arena #9(1531) |
| 14 | Step-3.5-Flash | 阶跃星辰 | 196B | **54.9** | — |
| 15 | Doubao-Seed-2-0-Lite | 字节跳动（豆包） | N/A | **54.6** | — |
| 16 | Ring-2.5-1T | 蚂蚁集团 | 1T | **53.6** | — |
| 20 | Hy3-preview | 腾讯 | 295B | **51.9** | AA #50(34) |
| 21 | Qwen3.6-27B | 阿里巴巴（通义千问） | 27B | **50.8** | AA #37(37) |
| 23 | JT-MINI | 中国移动 | N/A | **38.5** | — |

> **注：**
> ① GLM-5.2（2026-06-17 发布，MIT开源）晚于 OpenCompass 榜单快照，位次为综合多源估算。
> ② MiniMax-M3（2026-06-01 发布）同样晚于旧版 OpenCompass 快照，未出现在原始榜单中；其 SWE-bench Pro 59.0 为开源模型最高分，综合能力与 Kimi-K2.6 / Qwen3.6-Max 同级。
> ③ MiniMax-M2.7 为前代模型，已有的 OpenCompass 得分 56.2 低于 M3，但榜单中仍有记录。

### 总结推荐

| 如果你想看 | 推荐去 |
| ------- | ----- |
| 模型解决真实 bug 的能力 | **SWE-bench** |
| 多语言代码编辑综合排名 | **Aider Leaderboard** |
| 综合中文视角的排名 | **OpenCompass** |
