#!/bin/bash
# Harness Engineering — 快速评分
# 用法: bash <harness-dir>/bin/score.sh file1.py file2.py ...
# 效果: 对指定文件运行六维奖励函数评分

set -e

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$1" ]; then
    echo "用法: bash $0 <file1.py> [file2.py ...]"
    echo "示例: bash $0 core/db.py core/auth.py"
    exit 1
fi

export PATH="$HOME/Library/Python/3.9/bin:$PATH"
cd "$HARNESS_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
from harness.reward import compute_reward, RewardConfig
from harness.reporter import print_report
files = sys.argv[1:]
report = compute_reward(files, RewardConfig())
print_report(report)
sys.exit(0 if report.passed else 1)
" "$@"
