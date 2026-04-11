"""
风险分析引擎 — 根据改动量+敏感度自动分级
用于pipeline各阶段厚度调档：micro跳过Agent审查，standard走完整流程
"""
from __future__ import annotations

import os
import re
import subprocess
import logging
from typing import List, Literal

logger = logging.getLogger(__name__)

RiskLevel = Literal["micro", "small", "standard"]

# === 路径敏感度规则 ===

HIGH_SENSITIVITY_PATHS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'auth', r'admin', r'login', r'permission', r'role',
        r'key', r'token', r'secret', r'password', r'credential',
        r'pay', r'money', r'price', r'amount', r'quota', r'balance', r'billing',
        r'config\.ya?ml$', r'\.env', r'settings\.json$',
        r'middleware', r'security', r'crypto',
    ]
]

MEDIUM_SENSITIVITY_PATHS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'static/.*\.html$',   # 前端可能含fetch/header改动
        r'prompts/',            # AI行为变更
        r'migration',           # 数据库迁移
        r'docker', r'nginx',    # 基础设施配置
        r'requirements.*\.txt$', r'package\.json$',  # 依赖变更
    ]
]

# === 内容敏感度规则（扫描diff输出）===

HIGH_SENSITIVITY_CONTENT = [
    re.compile(p, re.IGNORECASE) for p in [
        r'\b(token|secret|password|api_key|private_key)\s*[=:]',
        r'\b(DELETE|DROP|TRUNCATE)\s',
        r'(price|amount|balance|quota)\s*[=<>!]',
        r'Header\s*\(.*[Kk]ey',
        r'compare_digest|hmac\.',
        r'\.env\b.*=',
    ]
]

MEDIUM_SENSITIVITY_CONTENT = [
    re.compile(p, re.IGNORECASE) for p in [
        r'\bfetch\s*\(.*header',
        r'system_prompt|system\.prompt',
        r'\.replace\(.*prompt',
        r'cors|origin|allow_',
        r'timeout|rate.?limit',
    ]
]


def _run_git(args: List[str], cwd: str) -> str:
    """运行git命令，失败返回空字符串"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        logger.debug(f"git命令失败: {e}")
        return ""


def get_changed_files(project_root: str) -> List[str]:
    """获取当前改动的文件列表（staged + unstaged + untracked）"""
    files = set()

    # staged
    staged = _run_git(["diff", "--cached", "--name-only"], project_root)
    if staged:
        files.update(staged.splitlines())

    # unstaged
    unstaged = _run_git(["diff", "--name-only"], project_root)
    if unstaged:
        files.update(unstaged.splitlines())

    # untracked (新文件)
    untracked = _run_git(["ls-files", "--others", "--exclude-standard"], project_root)
    if untracked:
        files.update(untracked.splitlines())

    return list(files)


def get_changed_line_count(project_root: str) -> int:
    """获取改动的总行数（新增+删除）"""
    stat = _run_git(["diff", "--stat", "--cached"], project_root)
    stat += "\n" + _run_git(["diff", "--stat"], project_root)

    total = 0
    for line in stat.splitlines():
        # 匹配 "5 insertions(+), 3 deletions(-)" 格式
        m = re.search(r'(\d+)\s+insertion', line)
        if m:
            total += int(m.group(1))
        m = re.search(r'(\d+)\s+deletion', line)
        if m:
            total += int(m.group(1))

    return total


def get_diff_content(project_root: str) -> str:
    """获取diff的实际内容（用于内容敏感度扫描）"""
    content = _run_git(["diff", "--cached", "-U0"], project_root)
    content += "\n" + _run_git(["diff", "-U0"], project_root)
    return content


def matches_high_sensitivity(filepath: str) -> bool:
    """检查文件路径是否匹配高敏感度规则"""
    return any(p.search(filepath) for p in HIGH_SENSITIVITY_PATHS)


def matches_medium_sensitivity(filepath: str) -> bool:
    """检查文件路径是否匹配中敏感度规则"""
    return any(p.search(filepath) for p in MEDIUM_SENSITIVITY_PATHS)


def diff_content_matches_high(content: str) -> bool:
    """检查diff内容是否包含高敏感度模式"""
    # 只扫描新增的行（以+开头）
    added_lines = "\n".join(
        line for line in content.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    return any(p.search(added_lines) for p in HIGH_SENSITIVITY_CONTENT)


def diff_content_matches_medium(content: str) -> bool:
    """检查diff内容是否包含中敏感度模式"""
    added_lines = "\n".join(
        line for line in content.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    return any(p.search(added_lines) for p in MEDIUM_SENSITIVITY_CONTENT)


def analyze_risk(project_root: str) -> RiskLevel:
    """
    分析当前改动的风险等级。

    规则：
    - 任何高敏感度命中 → 强制standard
    - 中敏感度 → 至少small
    - 改动量：<=1文件+<=10行+低敏感度 → micro
    - 改动量：<=2文件+<=50行+非高敏感度 → small
    - 其他 → standard
    """
    files = get_changed_files(project_root)
    if not files:
        return "micro"  # 无改动

    line_count = get_changed_line_count(project_root)
    diff_content = get_diff_content(project_root)

    # 维度2：路径敏感度
    path_high = any(matches_high_sensitivity(f) for f in files)
    path_medium = any(matches_medium_sensitivity(f) for f in files)

    # 维度3：内容敏感度
    content_high = diff_content_matches_high(diff_content)
    content_medium = diff_content_matches_medium(diff_content)

    # 任何高敏感度 → 强制standard
    if path_high or content_high:
        logger.info(f"[RiskAnalyzer] standard（高敏感度）: {len(files)}文件, {line_count}行, path_high={path_high}, content_high={content_high}")
        return "standard"

    has_medium = path_medium or content_medium

    # 改动量分级
    if len(files) <= 1 and line_count <= 10 and not has_medium:
        logger.info(f"[RiskAnalyzer] micro: {len(files)}文件, {line_count}行")
        return "micro"

    if len(files) <= 2 and line_count <= 50:
        logger.info(f"[RiskAnalyzer] small: {len(files)}文件, {line_count}行, medium={has_medium}")
        return "small"

    logger.info(f"[RiskAnalyzer] standard（改动量大）: {len(files)}文件, {line_count}行")
    return "standard"


def format_risk_summary(project_root: str) -> str:
    """格式化风险分析摘要（用于hook消息输出）"""
    files = get_changed_files(project_root)
    line_count = get_changed_line_count(project_root)
    level = analyze_risk(project_root)

    icon = {"micro": "🟢", "small": "🟡", "standard": "🔴"}
    return f"{icon.get(level, '⚪')} risk_level={level} ({len(files)}文件, {line_count}行)"
