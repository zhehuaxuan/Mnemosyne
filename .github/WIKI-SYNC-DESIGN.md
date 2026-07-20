# Wiki 同步系统设计报告

> 版本：1.0 | 日期：2026-07-09

---

## 1. 概述

### 1.1 背景

Mnemosyne 是一个基于 Obsidian 的个人知识库。仓库中的笔记分为两类：

- **私有笔记**：仅供个人使用，只在仓库中可见
- **公开笔记**：希望发布到 GitHub Wiki，与社区分享

本系统允许作者通过一个简单的 `wiki: true` 标记，推送到 `main` 分支后自动将笔记同步到 GitHub Wiki。

### 1.2 优势

| 优势 | 说明 |
|------|------|
| **选择性发布** | 笔记作者通过 frontmatter 主动标记哪些笔记对外公开 |
| **零操作同步** | `git push` 后全自动，无需额外步骤 |
| **链接完整性** | Obsidian 双链自动转化为 Wiki 内可点击链接 |
| **图片跟随** | 笔记中的图片自动复制到 Wiki，路径自动修正 |
| **自动导航** | 按 PARA 目录结构自动生成 Wiki 侧边栏 |

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Mnemosyne 仓库 (main)                     │
│                                                               │
│  00-收件箱/1-灵感/Token Plan对比.md                            │
│    wiki: true  ←── frontmatter 标记                           │
│    ![[Pasted image.png]]  ←── Obsidian 嵌入                   │
│    [[AI Agent面试题]]     ←── 双链                            │
│                                                               │
│  _assets/Pasted image.png  ←── 图片资源                       │
└────────────────────┬────────────────────────────────────────┘
                     │ git push to main
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Runner                      │
│                                                               │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  Checkout    │──▶│  sync-wiki   │──▶│  Push to Wiki    │  │
│  │  Repo        │   │  .py         │   │  repo            │  │
│  └─────────────┘   └──────┬───────┘   └──────────────────┘  │
│                            │                                   │
│               ┌────────────┼────────────┐                     │
│               ▼            ▼            ▼                     │
│         扫描&筛选    转换链接&图片   生成导航                    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Wiki 仓库 (.wiki.git)                  │
│                                                               │
│  Token-Plan-对比.md      ← 标题 → slug                        │
│  AI-Agent面试题.md       ← 标题 → slug                        │
│  images/                 ← 图片目录                            │
│    Pasted image.png                                           │
│  _Sidebar.md             ← 导航侧边栏                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 组件清单

```
.github/
├── workflows/
│   └── wiki-sync.yml        # GitHub Action 工作流定义
├── scripts/
│   └── sync-wiki.py         # 同步引擎（Python）
└── WIKI-SYNC-DESIGN.md      # 本文档
```

---

## 3. 触发机制

### 3.1 自动触发

```yaml
on:
  push:
    branches: [main]
    paths:
      - '**.md'         # 任何 markdown 变更
      - '_assets/**'     # 图片资源变更
```

- 仅 `main` 分支触发，保护分支不受影响
- `paths` 过滤避免无关变更浪费 CI 资源

### 3.2 手动触发

支持 `workflow_dispatch`，可在 GitHub Actions 页面手动执行。

### 3.3 权限

```yaml
permissions:
  contents: write    # 需要写入 <repo>.wiki.git
```

### 3.4 关键配置说明

| 配置 | 值 | 说明 |
|------|-----|------|
| `fetch-depth: 0` | 完整历史 | 确保能获取所有分支历史，兼容 `git push` |
| `timeout-minutes: 10` | 10 分钟 | 防止同步脚本卡死占用资源 |
| `python-version` | '3.12' | 使用稳定版 Python |

---

## 4. 工作流执行细节（wiki-sync.yml → sync-wiki.py）

### 4.1 环境变量传递

```yaml
- name: Sync to Wiki
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}      # 自动注入的 PAT
    GITHUB_REPOSITORY: ${{ github.repository }}    # 仓库全名（user/repo）
    GITHUB_WORKSPACE: ${{ github.workspace }}      # 仓库克隆路径
  run: python .github/scripts/sync-wiki.py
```

脚本内部接收方式：

```python
repo_root = Path(os.environ.get('GITHUB_WORKSPACE',
                Path(__file__).resolve().parents[2]))  # 本地调试时用相对路径
repo = os.environ.get('GITHUB_REPOSITORY', '')
token = os.environ.get('GITHUB_TOKEN', '')

# 构造 Wiki 仓库的 HTTPS URL（含 Token 认证）
wiki_url = f'https://x-access-token:{token}@github.com/{repo}.wiki.git'
```

**认证原理**：`GITHUB_TOKEN` 是 GitHub Actions 自动注入的 Secrets，格式为 `github-actions[bot]` 身份的有效 Token。使用 `x-access-token:` 前缀嵌入 URL 可让 `git clone/push` 通过 HTTPS 完成认证，无需配置 SSH 密钥。

### 4.2 Python 依赖处理

脚本内嵌了依赖检查逻辑，无需在 workflow 中预装：

```python
try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyyaml', '-q'])
    import yaml
```

Workflow 中只安装了 `pyyaml`，因为这是唯一需要的外部依赖。

### 4.3 工作流步骤详解

完整的 workflow 包含以下 4 个 step：

```yaml
jobs:
  sync-wiki:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      # ── Step 1: 克隆仓库 ──────────────────────────────────
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0    # 获取完整历史，兼容 git push

      # ── Step 2: 安装 Python ──────────────────────────────
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      # ── Step 3: 安装依赖 ─────────────────────────────────
      - name: Install dependencies
        run: pip install pyyaml

      # ── Step 4: 执行同步脚本 ─────────────────────────────
      - name: Sync to Wiki
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_WORKSPACE: ${{ github.workspace }}
        run: python .github/scripts/sync-wiki.py
```

| Step | 名称 | 作用 |
|------|------|------|
| 1 | Checkout repository | 将仓库代码克隆到 runner，支持 git push |
| 2 | Setup Python | 在 runner 上准备 Python 3.12 环境 |
| 3 | Install dependencies | 安装 `pyyaml`（YAML 解析库） |
| 4 | Sync to Wiki | 执行同步脚本，完成所有同步逻辑 |

**Step 1 补充说明**：`fetch-depth: 0` 是必须的，因为同步脚本会向 Wiki 仓库执行 `git push`。如果只获取 shallow clone（默认 depth=1），GitHub Actions bot 可能没有完整的提交历史，导致 push 失败或产生不连贯的历史记录。

### 4.4 处理流水线（脚本执行顺序）

```
                    输入：GITHUB_WORKSPACE
                           │
                  ┌────────▼────────┐
                  │  Step 1: 扫描     │
                  │  scan_pages()    │
                  │  rglob *.md      │
                  │  排除系统目录      │
                  │  解析 frontmatter │
                  │  过滤 wiki: true │
                  └────────┬────────┘
                           │ pages[]
                  ┌────────▼────────┐
                  │  Step 2: 分配    │
                  │  assign_slugs()  │
                  │  标题 → slug     │
                  │  重名处理        │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Step 3: 映射     │
                  │  build_link_map()│
                  │  title/stem → slug│
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Step 4: 克隆     │
                  │  clone_or_init() │
                  │  .wiki.git       │
                  │  (GitHub Actions │
                  │   Bot 认证)      │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Step 5: 清空     │
                  │  保留 .git 目录   │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Step 6: 生成     │
                  │  ├ 转换双链       │
                  │  ├ 复制图片       │
                  │  └ 写入 .md      │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Step 7: 导航     │
                  │  _Sidebar.md     │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Step 8: 推送     │
                  │  git add/commit  │
                  │  无变更则 skip    │
                  │  push origin master│
                  └──────────────────┘
```

#### 为什么是这个顺序？

| 步骤 | WHY（原因） |
|------|-------------|
| **Step 1 扫描** | Wiki 不知道仓库里有哪些页面，必须先扫描。只有 `wiki: true` 的才需要同步 |
| **Step 2 分配 slug** | Wiki 页面用 slug（URL 友好名）作为文件名，需要先确定每个页面的 slug 才能构建链接映射 |
| **Step 3 构建映射** | 双链转换需要知道「标题 → slug」的对应关系，但这个映射只来自 Wiki 页面（`[[私有笔记]]` 不会被转换） |
| **Step 4 克隆 Wiki** | 克隆到本地才能修改。Wiki 仓库是独立的 `.wiki.git`，不是主仓库的一部分 |
| **Step 5 清空** | GitHub Wiki 是静态页面托管，不能删除单个页面。只能用「先删全部再重建」的方式实现同步 |
| **Step 6 生成页面** | 有了 slug 映射和图片路径，才能正确生成转换后的 markdown 文件 |
| **Step 7 生成导航** | 导航依赖目录结构，需要知道有哪些页面后才能按 PARA 分类排序 |
| **Step 8 推送** | 最终把本地改动提交到 Wiki 仓库，触发 GitHub 渲染页面 |

#### 关键设计决策解释

**Q: 为什么先扫描再克隆？**
> 因为克隆 Wiki 仓库后要清空它。如果扫描结果是空的（没有 `wiki: true`），就直接退出，不用浪费一次克隆操作。

**Q: 为什么先构建映射再生成页面？**
> 双链 `[[AI Agent面试题]]` 需要知道目标页面的 slug 才能转换成 `[AI Agent面试题](AI-Agent面试题)`。如果顺序反过来，生成页面时就不知道该转成什么。

**Q: 为什么先清空再生成，而不是增量更新？**
> GitHub Wiki 没有 API 可以「删除页面」。只能通过清空后全量重建来保持一致。增量更新的代价是代码复杂度大幅增加（需要对比差异、处理删除），收益不大。

### 4.5 核心模块

#### 4.5.1 前端解析器

```
输入：文件原始文本
     ┌──────────────────┐
     │ ---               │
     │ title: 标题       │──▶ YAML.safe_load()
     │ wiki: true        │    → {"title": "标题", "wiki": True}
     │ ---               │
     │ # 正文内容         │──▶ body: "# 正文内容"
     └──────────────────┘
输出：(frontmatter_dict, body_text)
```

**wiki 字段兼容性**：

```python
wiki_val = fm.get('wiki')
if wiki_val is not True and str(wiki_val).lower() != 'true':
    continue
```

| 写法 | YAML 类型 | 是否通过 |
|------|-----------|----------|
| `wiki: true` | 布尔 | ✅ |
| `wiki: "true"` | 字符串 | ✅ |
| `wiki: false` | 布尔 | ❌ |
| （不写） | None | ❌ |

#### 4.5.2 什么是 Slug？

**slug** 是「用在 URL / 文件名里的简短标识符」。

| 概念 | 示例 |
|------|------|
| 原标题 | `Token Plan 对比` |
| **slug** | `Token-Plan-对比` |

**为什么需要 slug？**

GitHub Wiki 页面 URL 格式为：

```
https://github.com/zhehuaxuan/Mnemosyne/wiki/Token-Plan-对比
```

Wiki 页面文件名就是 URL 的一部分，因此需要：
- 空格/特殊字符替换为 `-`
- 保留中文
- 保证唯一性

> 简单理解：**slug = 能用在 URL 里的标题**

#### 4.5.3 Slug 生成器

```
标题    → URL 友好文件名
─────────────────────────────
"Token Plan 对比"  →  "Token-Plan-对比"
"如何让Obsidian+AI..."  →  "如何让ObsidianAI..."

重名处理：
  标题相同 + 不同目录 → {目录前缀}-{slug}
  标题相同 + 相同目录 → {slug}-{序号}
```

#### 4.5.4 双链转换器

```
Obsidian 语法              →  GitHub Wiki 语法
─────────────────────────────────────────────────
[[页面名]]                 →  [页面名](页面名)
[[页面名|显示文字]]         →  [显示文字](页面名)
[[页面名#标题]]            →  [页面名](页面名#标题)
[[不存在的页面]]            →  纯文本（降级）
```

**映射表构建**：

```python
link_map = {
    "Token Plan 对比": "Token-Plan-对比",      # title → slug
    "Token Plan对比":  "Token-Plan-对比",      # filename stem → slug
    "AI Agent面试题":  "AI-Agent面试题",
    ...
}
```

> ⚠️ 只有标记了 `wiki: true` 的页面才会进入映射表。如果一篇 Wiki 笔记通过 `[[]]` 链接了一篇非 Wiki 笔记，链接会降级为纯文本。

#### 4.5.5 图片处理器

支持两种图片嵌入语法：

| 模式 | 示例 | 处理 |
|------|------|------|
| Obsidian 嵌入 | `![[Pasted image.png]]` | 从 `_assets/` 查找并复制 |
| 标准 Markdown | `![](../../_assets/img.png)` | 按相对路径解析并复制 |

**处理流程**：

```
![[Pasted image.png]]
         │
         ▼
  在 _assets/ 中按文件名/扩展名匹配
         │
    ┌────┴────┐
    ▼         ▼
  找到      未找到
    │         │
    ▼         └──→ 保持原样
  复制到 wiki/images/
  路径改为 images/filename
    │
    ▼
![Pasted image.png](images/Pasted%20image.png)
```

**已知限制**：

- URL 编码路径（如 `%20`）尚未自动解码匹配 ← 待修复
- 只处理 `_assets/` 下的图片，不处理外部 URL

#### 4.5.6 导航生成器

```
Wiki 侧边栏结构：
┌──────────────────────────────┐
│ # Mnemosyne 知识库           │
│ ---                          │
│ ## 00-收件箱                 │
│   - [Token Plan对比](...)    │
│   - [如何让Obsidian...](...) │
│ ## 10-项目                   │
│   - [AI Agent面试题](...)    │
│ ## 20-领域                   │
│   ...                        │
└──────────────────────────────┘
```

按 PARA 固定顺序排列，子目录自动缩进。

### 4.6 Git 提交与推送

脚本最后阶段执行以下操作：

```python
# 1. 添加所有变更
subprocess.run(['git', '-C', str(wiki_dir), 'add', '-A'], check=True)

# 2. 检查是否有实际变更（无变更则跳过推送）
diff_result = subprocess.run(
    ['git', '-C', str(wiki_dir), 'diff', '--cached', '--quiet'],
    capture_output=True
)
if diff_result.returncode == 0:
    print("\nNo changes to wiki. Skipping push.")
    return 0

# 3. 配置 GitHub Actions bot 身份
subprocess.run(['git', '-C', str(wiki_dir), 'config', 'user.name',
     'github-actions[bot]'], check=True)
subprocess.run(['git', '-C', str(wiki_dir), 'config', 'user.email',
     'github-actions[bot]@users.noreply.github.com'], check=True)

# 4. 提交并推送
subprocess.run(['git', '-C', str(wiki_dir), 'commit', '-m',
     '📝 Sync wiki from main repo'], check=True)
subprocess.run(['git', '-C', str(wiki_dir), 'push', 'origin', 'master'],
     check=True)
```

**关键行为**：

| 场景 | 处理 |
|------|------|
| Wiki 中无 `wiki: true` 页面 | 静默退出，返回 0 |
| 本次无任何变更 | 打印 "Skipping push"，不产生 commit |
| 有变更 | 全量覆盖后提交，消息为 "📝 Sync wiki from main repo" |
| 推送失败 | GitHub Actions 报错，workflow 标记为失败 |

---

## 5. Wiki 仓库结构

```
<repo>.wiki.git/
├── Token-Plan-对比.md        # 页面正文（不含 frontmatter）
├── AI-Agent面试题.md
├── _Sidebar.md               # 自动生成的导航
└── images/                   # 图片资源
    └── Pasted image 20260709193704.png
```

**关键规则**：

- Wiki 页面**不包含** YAML frontmatter（GitHub Wiki 不需要）
- `_Sidebar.md` 是 GitHub Wiki 的保留文件名，自动作为侧边栏渲染
- 每次同步**全量覆盖** Wiki 内容（先清空再写入）

---

## 6. 数据流示意

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Obsidian │     │   Git    │     │  GitHub  │     │  GitHub  │
  │ 本地编辑  │────▶│  Push    │────▶│  Actions │────▶│   Wiki   │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                                  │                │
  编辑笔记                           1. 扫描            页面渲染
  加 wiki: true                      2. 分配 slug       侧边栏
  写 [[双链]]                        3. 构建映射         图片正常
  粘贴图片                           4. 克隆 wiki       链接可点击
                                     5. 全量覆盖
                                     6. 提交推送
```

---

## 7. 待改进项

| 优先级 | 问题 | 影响 |
|--------|------|------|
| 🔴 高 | URL 编码路径（`%20`）未解码匹配 | 含空格的图片名无法复制到 Wiki |
| 🟡 中 | 图片按 `stem` 匹配可能误匹配扩展名 | 同名不同格式的图片可能覆盖 |
| 🟡 中 | 全量覆盖而非增量更新 | 大 Wiki 时 git 历史膨胀 |
| 🟢 低 | 双链指向非 Wiki 页面时降级为纯文本 | 可加提示注释 |
| 🟢 低 | sidebar 仅支持一层缩进 | 深层目录导航体验一般 |

---

## 8. 使用示例

### 发布一篇笔记

```yaml
---
title: 我的技术分享
description: 关于某个主题的深入分析
date: 2026-07-09
tags: [技术, AI]
wiki: true          # ← 加这一行
---

# 内容...
```

### 取消发布

```yaml
wiki: false    # 或直接删除 wiki 字段
```

下次 push 后该页面会从 Wiki 中移除。

---

## 9. 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `.github/workflows/wiki-sync.yml` | 40 | 工作流定义（触发、环境、步骤） |
| `.github/scripts/sync-wiki.py` | 367 | 同步引擎（扫描、转换、推送） |
| `.github/WIKI-SYNC-DESIGN.md` | ~465 | 本文档 |
