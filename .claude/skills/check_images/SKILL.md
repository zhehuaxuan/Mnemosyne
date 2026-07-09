---
name: check_images
description: 检查 _assets 目录中未被 markdown 引用的图片并删除
---

# Check Images Skill

检查 `E:\knowledge\Mnemosyne\_assets` 目录中的图片，如果没有任何 markdown 文件引用，则删除该图片。

## 使用方式

```
/check_images [选项]
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dry-run` | 仅预览，不删除 | true |
| `--delete` | 执行删除操作 | false |
| `--dir` | 图片目录路径 | _assets |

## 示例

```bash
# 仅预览未引用图片（默认）
/check_images

# 执行删除
/check_images --delete
```

## 输出示例

```
扫描中...
找到 15 张图片
检查引用...
未引用图片:
  - _assets/截图2024.png
  - _assets/未命名.jpg
已删除 2 张未引用图片
```
