#!/usr/bin/env python3
"""一次性脚本：补全 ~/.claude/settings.json 的权限白名单"""

import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
settings = json.loads(settings_path.read_text())

# 现有的 allow 列表
existing = set(settings["permissions"]["allow"])

# 要新增的权限
new_permissions = [
    # 文件操作
    "Bash(rm *)",
    "Bash(touch *)",
    "Bash(chmod *)",
    # 文件查看
    "Bash(head *)",
    "Bash(tail *)",
    # 搜索
    "Bash(find *)",
    "Bash(grep *)",
    "Bash(rg *)",
    # 文本处理
    "Bash(sed *)",
    "Bash(awk *)",
    "Bash(wc *)",
    "Bash(sort *)",
    "Bash(uniq *)",
    # 基础命令
    "Bash(pwd)",
    "Bash(which *)",
    "Bash(echo *)",
    "Bash(printf *)",
    # 远程操作
    "Bash(scp *)",
    "Bash(ssh *)",
    "Bash(curl *)",
    # 开发工具
    "Bash(python3 -m *)",
    "Bash(pytest *)",
    "Bash(make *)",
    "Bash(env *)",
    "Bash(date *)",
    "Bash(brew *)",
    # 管道工具
    "Bash(xargs *)",
    "Bash(tee *)",
    "Bash(diff *)",
    # 路径工具
    "Bash(realpath *)",
    "Bash(dirname *)",
    "Bash(basename *)",
    # macOS
    "Bash(osascript *)",
]

added = []
for perm in new_permissions:
    if perm not in existing:
        settings["permissions"]["allow"].append(perm)
        added.append(perm)

# 写回
settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")

print(f"✅ 新增了 {len(added)} 条权限：")
for p in added:
    print(f"  + {p}")
print(f"\n原有 {len(existing)} 条不变，现在共 {len(settings['permissions']['allow'])} 条")
print("deny 列表未改动（rm -rf、sudo、chmod 777 等仍被禁止）")
