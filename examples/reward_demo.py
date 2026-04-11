#!/usr/bin/env python3
"""
Harness Engineering — 奖励函数演示

演示如何对一个Python文件运行六维评分。
用法: python3 examples/reward_demo.py [文件路径]
"""

import sys
import os

# 将harness目录加入path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.reward import compute_reward, RewardConfig
from harness.reporter import print_report


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        # 默认对自身评分（演示用）
        files = [__file__]
        print(f"未指定文件，将对自身 ({__file__}) 进行评分演示\n")

    # 使用默认配置
    config = RewardConfig()

    print("=" * 50)
    print("  Harness Engineering — 多维奖励函数演示")
    print("=" * 50)
    print(f"\n评分文件: {', '.join(files)}\n")
    print(f"权重配置:")
    print(f"  功能正确性: {config.weight_functional}%")
    print(f"  规格合规:   {config.weight_spec}%")
    print(f"  类型安全:   {config.weight_type_safety}%")
    print(f"  安全性:     {config.weight_security}%")
    print(f"  架构合规:   {config.weight_architecture}%")
    print(f"  密钥安全:   {config.weight_secrets}%")
    print(f"  代码规范:   {config.weight_code_quality}%")
    print()

    # 运行评分
    report = compute_reward(files, config)

    # 打印报告
    print_report(report)

    # 返回退出码
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
