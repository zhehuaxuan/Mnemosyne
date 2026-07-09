#!/usr/bin/env python3
"""
将带有 `wiki: true` 标记的笔记同步到 GitHub Wiki。

功能：
- 扫描所有 .md 文件，筛选 frontmatter 中 wiki: true 的笔记
- 转换 Obsidian [[双链]] 为标准 markdown 链接
- 处理图片嵌入（![[image]] 和 ![](path)）→ 复制到 wiki
- 自动生成 _Sidebar.md 导航
- 增量提交到 <repo>.wiki.git
"""

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from collections import defaultdict

# ── 依赖检查 ────────────────────────────────────────────────────
try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyyaml', '-q'])
    import yaml

# ── 配置 ────────────────────────────────────────────────────────
EXCLUDE_DIRS = {'.git', '.github', '.obsidian', '.claude', '__pycache__', '90-模板'}
WIKI_CLONE_DIR = Path('/tmp/wiki-repo')
ASSETS_DIR_NAME = '_assets'


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter。返回 (metadata, body)。"""
    if not text.startswith('---\n'):
        return {}, text
    end = text.find('\n---\n', 4)
    if end == -1:
        return {}, text
    try:
        fm = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, text[end + 5:]


def slugify(text: str) -> str:
    """将标题转换为 URL 友好的 slug，支持中文。"""
    # 保留中文字符、字母、数字
    text = re.sub(r'[^\w一-鿿-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    slug = text.strip('-')
    return slug or 'untitled'


def scan_pages(repo_root: Path) -> list[dict]:
    """扫描所有 wiki: true 的笔记。"""
    pages = []

    for md_file in sorted(repo_root.rglob('*.md')):
        # 跳过排除目录
        parts = set(md_file.relative_to(repo_root).parts)
        if parts & EXCLUDE_DIRS:
            continue

        relpath = md_file.relative_to(repo_root)

        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        fm, body = parse_frontmatter(content)

        if fm.get('wiki') is not True:
            continue

        title = fm.get('title') or md_file.stem
        dir_parts = list(relpath.parts[:-1])  # 不含文件名

        pages.append({
            'title': title,
            'dir_parts': dir_parts,
            'relpath': str(relpath),
            'source_file': md_file,
            'fm': fm,
            'body': body,
        })

    return pages


def assign_slugs(pages: list[dict]) -> None:
    """为每页分配唯一 slug，处理重名。"""
    used = set()

    for p in pages:
        slug = slugify(p['title'])

        # 处理重名：加上目录前缀
        if slug in used:
            prefix = '-'.join(slugify(d) for d in p['dir_parts'])
            slug = f"{prefix}-{slug}" if prefix else f"{slug}-{len(used)}"

        used.add(slug)
        p['slug'] = slug


def build_link_map(pages: list[dict]) -> dict[str, str]:
    """构建 标题/文件名 → wiki-slug 的映射。"""
    link_map = {}
    for p in pages:
        link_map[p['title']] = p['slug']
        link_map[Path(p['relpath']).stem] = p['slug']
    return link_map


def convert_wikilinks(body: str, link_map: dict[str, str]) -> str:
    """将 [[wikilinks]] 转为 [text](slug)。"""

    def replace(m: re.Match) -> str:
        target = m.group(1)
        display = target
        heading = ''

        # [[target#heading]]
        if '#' in target:
            target, heading = target.split('#', 1)
            heading = '#' + slugify(heading)

        # [[target|display]]
        if '|' in target:
            target, display = target.split('|', 1)

        # 查找映射
        if target in link_map:
            return f'[{display}]({link_map[target]}{heading})'

        # 大小写不敏感再试一次
        for k, v in link_map.items():
            if k.lower() == target.lower():
                return f'[{display}]({v}{heading})'

        # 未找到 → 纯文本
        return display

    return re.sub(r'\[\[([^\]]+)\]\]', replace, body)


def handle_images(body: str, source_dir: Path, repo_root: Path,
                  image_dir: Path) -> str:
    """复制引用的图片到 wiki images/ 目录，并修正路径。"""

    # ── 模式 1: ![[image.png]] ──
    def replace_embed(m: re.Match) -> str:
        name = m.group(1)
        assets = repo_root / ASSETS_DIR_NAME
        found = None

        if assets.is_dir():
            for f in assets.iterdir():
                if f.name == name or f.stem == name:
                    found = f
                    break

        if found:
            dest = image_dir / found.name
            shutil.copy2(found, dest)
            return f'![{name}](images/{found.name})'

        return f'![{name}]({name})'

    body = re.sub(r'!\[\[([^\]]+)\]\]', replace_embed, body)

    # ── 模式 2: ![](relative/path) ──
    def replace_img_path(m: re.Match) -> str:
        alt = m.group(1)
        img_path = m.group(2)

        # 跳过外部 URL
        if img_path.startswith(('http://', 'https://', 'data:')):
            return m.group(0)

        # 解析相对路径
        src = (source_dir / img_path).resolve()
        if src.exists() and src.is_relative_to(repo_root):
            dest = image_dir / src.name
            shutil.copy2(src, dest)
            return f'![{alt}](images/{src.name})'

        return m.group(0)

    body = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_img_path, body)

    return body


def generate_sidebar(pages: list[dict]) -> str:
    """生成 _Sidebar.md，按目录层级导航。"""
    lines = [
        '# Mnemosyne 知识库',
        '',
        '> 基于 PARA + Zettelkasten 的个人知识管理系统',
        '',
        '---',
        '',
    ]

    # 按顶层目录分组
    groups = defaultdict(list)
    for p in pages:
        top = p['dir_parts'][0] if p['dir_parts'] else '(根目录)'
        groups[top].append(p)

    # 按预设顺序排列
    ORDER = ['00-收件箱', '10-项目', '20-领域', '30-资源', '40-归档', '50-笔记']
    sorted_groups = sorted(
        groups.items(),
        key=lambda x: ORDER.index(x[0]) if x[0] in ORDER else 99
    )

    for group_name, group_pages in sorted_groups:
        lines.append(f'## {group_name}')
        for p in sorted(group_pages, key=lambda x: x['title']):
            indent = '  ' * (len(p['dir_parts']) - 1) if len(p['dir_parts']) > 1 else ''
            lines.append(f'{indent}- [{p["title"]}]({p["slug"]})')
        lines.append('')

    return '\n'.join(lines)


def clone_or_init_wiki(wiki_url: str) -> Path:
    """克隆 Wiki 仓库，若不存在则初始化。"""
    wiki_dir = WIKI_CLONE_DIR
    if wiki_dir.exists():
        shutil.rmtree(wiki_dir)

    result = subprocess.run(
        ['git', 'clone', '--depth', '1', wiki_url, str(wiki_dir)],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"  Clone failed: {result.stderr.strip()}")
        print("  Wiki may not exist yet. Initializing new repo...")
        wiki_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', '-C', str(wiki_dir), 'init'], check=True,
                       capture_output=True)
        subprocess.run(
            ['git', '-C', str(wiki_dir), 'remote', 'add', 'origin', wiki_url],
            check=True, capture_output=True
        )

    return wiki_dir


def main() -> int:
    # ── 环境变量 ──
    repo_root = Path(os.environ.get('GITHUB_WORKSPACE',
                    Path(__file__).resolve().parents[2]))
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    token = os.environ.get('GITHUB_TOKEN', '')

    if not repo or not token:
        print("ERROR: GITHUB_REPOSITORY and GITHUB_TOKEN are required.")
        return 1

    wiki_url = f'https://x-access-token:{token}@github.com/{repo}.wiki.git'

    print(f"Repo root : {repo_root}")
    print(f"Wiki repo : github.com/{repo}.wiki.git")
    print()

    # ── Step 1: 扫描 wiki 页面 ──
    pages = scan_pages(repo_root)

    if not pages:
        print("No wiki-enabled pages found (wiki: true). Nothing to sync.")
        return 0

    assign_slugs(pages)

    print(f"Found {len(pages)} wiki page(s):")
    for p in pages:
        path_hint = '/'.join(p['dir_parts'])
        print(f"  [{path_hint}] {p['title']}  →  {p['slug']}.md")
    print()

    # ── Step 2: 构建链接映射 ──
    link_map = build_link_map(pages)

    # ── Step 3: 克隆 Wiki 仓库 ──
    print("Cloning wiki repo...")
    wiki_dir = clone_or_init_wiki(wiki_url)

    # ── Step 4: 清空 Wiki（保留 .git） ──
    for item in list(wiki_dir.iterdir()):
        if item.name == '.git':
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # ── Step 5: 生成 Wiki 页面 ──
    image_dir = wiki_dir / 'images'
    image_dir.mkdir(exist_ok=True)

    for p in pages:
        body = p['body']

        # 转换 wikilinks
        body = convert_wikilinks(body, link_map)

        # 处理图片
        body = handle_images(body, p['source_file'].parent, repo_root, image_dir)

        # 写入 wiki 页面
        page_path = wiki_dir / f"{p['slug']}.md"
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(body)

        print(f"  ✓ {page_path.name}")

    # ── Step 6: 生成 _Sidebar.md ──
    sidebar_content = generate_sidebar(pages)
    sidebar_path = wiki_dir / '_Sidebar.md'
    with open(sidebar_path, 'w', encoding='utf-8') as f:
        f.write(sidebar_content)
    print(f"  ✓ _Sidebar.md")

    # ── Step 7: 提交并推送 ──
    subprocess.run(['git', '-C', str(wiki_dir), 'add', '-A'], check=True)

    # 检查是否有变更
    diff_result = subprocess.run(
        ['git', '-C', str(wiki_dir), 'diff', '--cached', '--quiet'],
        capture_output=True
    )
    if diff_result.returncode == 0:
        print("\nNo changes to wiki. Skipping push.")
        return 0

    subprocess.run(
        ['git', '-C', str(wiki_dir), 'config', 'user.name',
         'github-actions[bot]'], check=True
    )
    subprocess.run(
        ['git', '-C', str(wiki_dir), 'config', 'user.email',
         'github-actions[bot]@users.noreply.github.com'], check=True
    )
    subprocess.run(
        ['git', '-C', str(wiki_dir), 'commit', '-m',
         '📝 Sync wiki from main repo'], check=True
    )
    subprocess.run(
        ['git', '-C', str(wiki_dir), 'push', 'origin', 'master'],
        check=True
    )

    print("\n✅ Wiki sync complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
