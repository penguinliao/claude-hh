#!/bin/bash
# Harness Engineering — 一键创建新项目
# 用法: bash <harness-dir>/bin/new-project.sh 项目名
# 效果: 在 ~/Desktop/ 下创建带安全默认值的新项目

set -e

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$HARNESS_DIR/foundation/project-template"
TARGET_DIR="$HOME/Desktop/${1}"

if [ -z "$1" ]; then
    echo "用法: bash $0 <项目名>"
    echo "示例: bash $0 my-new-app"
    exit 1
fi

if [ -d "$TARGET_DIR" ]; then
    echo "错误: $TARGET_DIR 已存在"
    exit 1
fi

echo "Harness Engineering — 创建新项目"
echo "================================"
echo "项目名: $1"
echo "路径: $TARGET_DIR"
echo ""

# 复制模板
cp -r "$TEMPLATE_DIR" "$TARGET_DIR"

# 替换项目名
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/my-project/$1/g" "$TARGET_DIR/pyproject.toml"
    sed -i '' "s/My Project/$1/g" "$TARGET_DIR/src/api/app.py"
else
    sed -i "s/my-project/$1/g" "$TARGET_DIR/pyproject.toml"
    sed -i "s/My Project/$1/g" "$TARGET_DIR/src/api/app.py"
fi

# 初始化git
cd "$TARGET_DIR"
git init -q
echo "__pycache__/" > .gitignore
echo "*.pyc" >> .gitignore
echo ".env" >> .gitignore
echo "*.db" >> .gitignore
echo ".pytest_cache/" >> .gitignore

echo "✅ 项目创建完成！"
echo ""
echo "内置安全配置："
echo "  ✅ Pre-commit (ruff + bandit + detect-secrets)"
echo "  ✅ pyproject.toml (ruff + mypy 统一配置)"
echo "  ✅ CLAUDE.md (规格先行 + 安全规则)"
echo "  ✅ FastAPI 安全默认值 (CORS严格 + 全局错误处理)"
echo "  ✅ JWT 必须配置 (无默认密钥)"
echo "  ✅ 测试 fixtures (dev_前缀隔离)"
echo ""
echo "下一步："
echo "  cd $TARGET_DIR"
echo "  pip install pre-commit && pre-commit install"
echo "  # 开始开发！"
