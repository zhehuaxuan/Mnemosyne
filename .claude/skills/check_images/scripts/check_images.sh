#!/bin/bash
# check_images.sh - 检查并删除未被 markdown 引用的图片

set -e

ASSETS_DIR="_assets"
DRY_RUN=true
DELETE_MODE=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --delete)
            DELETE_MODE=true
            DRY_RUN=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            DELETE_MODE=false
            shift
            ;;
        --dir)
            ASSETS_DIR="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: check_images.sh [--delete] [--dry-run] [--dir <路径>]"
            exit 1
            ;;
    esac
done

cd "E:\knowledge\Mnemosyne"

echo "=== 检查未引用图片 ==="
echo "图片目录: $ASSETS_DIR"
echo "模式: $([ "$DRY_RUN" = true ] && echo "预览模式" || echo "删除模式")"
echo ""

# 检查目录是否存在
if [ ! -d "$ASSETS_DIR" ]; then
    echo "错误: 目录 $ASSETS_DIR 不存在"
    exit 1
fi

# 获取所有图片文件
mapfile -t images < <(find "$ASSETS_DIR" -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.gif" -o -iname "*.webp" -o -iname "*.svg" -o -iname "*.bmp" \) 2>/dev/null)

if [ ${#images[@]} -eq 0 ] || [ -z "${images[0]}" ]; then
    echo "未找到图片文件"
    exit 0
fi

image_count=${#images[@]}
echo "找到 $image_count 张图片"
echo ""

# 获取所有 md 文件
mapfile -t md_files < <(find . -name "*.md" -type f 2>/dev/null)

# 检查每张图片
orphaned=()
for img in "${images[@]}"; do
    img_name=$(basename "$img")
    # URL 编码文件名（将空格转为 %20）
    img_name_encoded=$(echo "$img_name" | sed 's/ /%20/g')
    found=false

    # 检查多种引用格式（原始名称和 URL 编码）
    for md in "${md_files[@]}"; do
        if grep -qE "!\[.*\]\([^)]*${img_name}(|\)|%20.*\))|!\[\[${img_name}(|\])|!\[.*\]\([^)]*${img_name_encoded}" "$md" 2>/dev/null; then
            found=true
            break
        fi
    done

    if [ "$found" = false ]; then
        orphaned+=("$img")
    fi
done

# 输出结果
if [ ${#orphaned[@]} -eq 0 ]; then
    echo "所有图片都已被引用 ✓"
else
    echo "未引用图片 (${#orphaned[@]} 张):"
    for img in "${orphaned[@]}"; do
        echo "  - $img"
    done
    echo ""

    if [ "$DELETE_MODE" = true ]; then
        deleted=0
        for img in "${orphaned[@]}"; do
            if rm "$img"; then
                echo "已删除: $img"
                ((deleted++))
            else
                echo "删除失败: $img"
            fi
        done
        echo ""
        echo "已删除 $deleted 张未引用图片"
    else
        echo "使用 --delete 参数执行删除"
    fi
fi
