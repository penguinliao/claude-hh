"""
Mutation Test — 验证harness自身是否可靠

原理：故意注入已知Bug，检查harness能不能发现。
如果harness连已知Bug都拦不住，就不能信任它对未知Bug的判断。

用法：
    from harness.mutation_test import run_mutation_test
    report = run_mutation_test(["your_file.py"])
    print(report)
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MutationResult:
    """单个突变的检测结果"""
    name: str           # 突变名称
    description: str    # PM能看懂的描述
    injected: bool      # 是否成功注入
    detected: bool      # harness是否发现了
    details: str = ""   # 检测详情


@dataclass
class MutationReport:
    """突变测试总报告"""
    results: list[MutationResult]
    total: int = 0
    detected: int = 0
    missed: int = 0
    detection_rate: float = 0.0

    def __post_init__(self) -> None:
        self.total = len(self.results)
        injected_count = sum(1 for r in self.results if r.injected)
        self.detected = sum(1 for r in self.results if r.detected)
        self.missed = sum(1 for r in self.results if r.injected and not r.detected)
        self.detection_rate = (self.detected / injected_count * 100) if injected_count > 0 else 0.0


# ---------------------------------------------------------------------------
# 突变定义：5种常见Bug模式
# ---------------------------------------------------------------------------

MUTATIONS = [
    # --- 安全漏洞类（5种）---
    {
        "name": "hardcoded_password",
        "description": "硬编码密码（password = 'admin123'）",
        "inject_line": '\nDB_PASSWORD = "admin123456"  # mutation: hardcoded password\n',
    },
    {
        "name": "hardcoded_api_key",
        "description": "硬编码API Key（sk-开头的密钥）",
        "inject_line": '\nAPI_KEY = "sk-proj-abc123def456ghi789"  # mutation: hardcoded api key\nSECRET_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"\n',
    },
    {
        "name": "sql_injection",
        "description": "SQL注入（f-string拼接SQL查询）",
        "inject_line": '\ndef _mutation_query(name):\n    import sqlite3\n    conn = sqlite3.connect(":memory:")\n    conn.execute(f"SELECT * FROM users WHERE name = \'{name}\'")\n',
    },
    {
        "name": "command_injection",
        "description": "命令注入（os.system执行用户输入）",
        "inject_line": '\ndef _mutation_cmd(user_input):\n    import os\n    os.system(f"echo {user_input}")\n',
    },
    {
        "name": "eval_usage",
        "description": "不安全的eval（可执行任意代码）",
        "inject_line": '\ndef _mutation_eval(data):\n    return eval(data)\n',
    },
    # --- 代码质量类（3种）---
    {
        "name": "bare_except",
        "description": "裸except（吞掉所有异常，问题被隐藏）",
        "inject_line": '\ndef _mutation_catch_all():\n    try:\n        result = 1 / 0\n    except:\n        pass\n',
    },
    {
        "name": "wildcard_import",
        "description": "通配符import（污染命名空间）",
        "inject_line": '\nfrom os import *\nfrom sys import *\n',
    },
    {
        "name": "unused_import_and_var",
        "description": "未使用的import和变量（死代码）",
        "inject_line": '\nimport json, csv, xml\n_mutation_unused_var = "this is never used"\n',
    },
    # --- 逻辑风险类（2种）---
    {
        "name": "shell_true",
        "description": "subprocess shell=True（命令注入风险）",
        "inject_line": '\ndef _mutation_shell():\n    import subprocess\n    subprocess.run("ls -la", shell=True)\n',
    },
    {
        "name": "cors_wildcard",
        "description": "CORS允许所有来源（安全配置错误）",
        "inject_line": '\n_MUTATION_CORS = {"allow_origins": ["*"], "allow_credentials": True}\n',
    },
    # --- 补充安全类（6种，基于审查报告建议）---
    {
        "name": "path_traversal",
        "description": "路径穿越（用户输入拼接文件路径）",
        "inject_line": '\ndef _mutation_path_traversal(user_path):\n    with open(f"/data/{user_path}") as f:\n        return f.read()\n',
    },
    {
        "name": "unsafe_pickle",
        "description": "不安全的pickle.loads（可执行任意代码）",
        "inject_line": '\ndef _mutation_pickle(data):\n    import pickle\n    return pickle.loads(data)\n',
    },
    {
        "name": "unsafe_yaml_load",
        "description": "不安全的yaml.load（无SafeLoader，可执行任意代码）",
        "inject_line": '\ndef _mutation_yaml(data):\n    import yaml\n    return yaml.load(data)\n',
    },
    {
        "name": "assert_security",
        "description": "用assert做安全检查（python -O 会跳过assert）",
        "inject_line": '\ndef _mutation_assert_auth(user):\n    assert user.is_admin, "Not authorized"\n    return "admin_data"\n',
    },
    {
        "name": "http_no_verify",
        "description": "HTTPS不验证证书（中间人攻击风险）",
        "inject_line": '\ndef _mutation_http_no_verify():\n    import requests\n    return requests.get("https://api.example.com", verify=False)\n',
    },
    {
        "name": "hardcoded_tmp",
        "description": "硬编码/tmp路径写敏感数据（竞态条件风险）",
        "inject_line": '\ndef _mutation_tmp():\n    with open("/tmp/secret_data.txt", "w") as f:\n        f.write("sensitive_token_here")\n',
    },
    # --- v2.0 harness 自身健壮性测试（2种）---
    {
        "name": "pipeline_bypass",
        "description": "绕过流水线门禁（直接返回True跳过阶段检查）",
        "inject_line": '\ndef is_code_write_allowed_bypass(project_root, file_path=""):\n    return True, ""  # Bypass pipeline gate\n',
        "target_mode": "full",
    },
    {
        "name": "telemetry_crash",
        "description": "遥测崩溃不影响hook（模拟DB写入异常）",
        "inject_line": '\ndef _mutation_telemetry_crash():\n    import sqlite3\n    conn = sqlite3.connect("/nonexistent/path/db.sqlite")\n    conn.execute("INSERT INTO check_events VALUES (1)")\n',
        "target_mode": "full",
    },
]

# Add target_mode to all mutations that don't have it
# All mutations target quick mode — custom regex checks in score_security
# now cover patterns that ruff/bandit miss (path_traversal, cors_wildcard)
for _m in MUTATIONS:
    if "target_mode" not in _m:
        _m["target_mode"] = "quick"


def _inject_mutation(original_path: str, mutation: dict, tmp_dir: str) -> str | None:
    """将一个突变注入到文件副本中，返回副本路径"""
    try:
        original = Path(original_path)
        if not original.exists():
            return None

        # 复制到临时目录
        tmp_file = Path(tmp_dir) / original.name
        shutil.copy2(original_path, tmp_file)

        # 在文件末尾注入突变代码
        with open(tmp_file, "a", encoding="utf-8") as f:
            f.write(mutation["inject_line"])

        return str(tmp_file)
    except Exception:
        return None


def _check_detection(
    mutated_file: str,
    mode: str = "quick",
    baseline_scores: dict[str, int] | None = None,
) -> tuple[bool, str]:
    """用harness检查突变文件，返回(是否检测到问题, 详情)

    Detection strategy: compare mutated file scores against baseline.
    A mutation is "detected" if ANY dimension score drops by >= 5 points,
    or if any hard gate triggers, or if total score drops below threshold.

    Args:
        mutated_file: 注入了突变的文件路径
        mode: 检测模式
        baseline_scores: 原始文件的各维度分数 {dim_name: score}
    """
    try:
        from harness.runner import check
        report = check([mutated_file], mode=mode)

        # Check 1: hard gate triggered or not passed
        if not report.passed or report.blocked_by:
            failed_dims = [
                f"{d.name}={d.score}"
                for d in report.dimensions
                if d.status == "evaluated" and d.score < 80
            ]
            return True, f"harness拦截({mode})：总分{report.total_score:.0f}, 问题维度: {', '.join(failed_dims)}"

        # Check 2: any dimension score dropped >= 5 points from baseline
        if baseline_scores:
            degraded = []
            for dim in report.dimensions:
                if dim.status != "evaluated":
                    continue
                baseline = baseline_scores.get(dim.name)
                if baseline is not None and baseline - dim.score >= 5:
                    degraded.append(f"{dim.name}: {baseline}->{dim.score}")
            if degraded:
                return True, f"harness拦截({mode})：分数下降: {', '.join(degraded)}"

        # Check 3: absolute threshold (any dim < 80)
        weak_dims = [
            f"{d.name}={d.score}"
            for d in report.dimensions
            if d.status == "evaluated" and d.score < 80
        ]
        if weak_dims:
            return True, f"harness拦截({mode})：弱维度: {', '.join(weak_dims)}"

        return False, f"harness未拦截({mode})：总分{report.total_score:.0f} PASS"
    except Exception as e:
        return False, f"harness执行出错: {e}"


def run_mutation_test(files: list[str], mode: str = "quick") -> MutationReport:
    """对指定文件运行突变测试

    流程：
    1. 对每种Bug模式，注入到文件副本
    2. 用harness检查副本（使用突变的target_mode或指定mode中较高的）
    3. 验证harness是否发现了注入的Bug
    4. 清理临时文件
    5. 返回检测率报告

    Args:
        files: 要测试的源文件列表（至少1个.py文件）
        mode: 最大检测模式 - "quick"只测quick突变, "standard"测quick+standard,
              "full"测所有突变。默认"quick"保持向后兼容。

    Returns:
        MutationReport: 检测率报告
    """
    if not files:
        return MutationReport(results=[])

    # 选第一个.py文件作为注入目标
    target = None
    for f in files:
        if f.endswith(".py") and Path(f).exists():
            target = f
            break

    if target is None:
        return MutationReport(results=[
            MutationResult(
                name="no_target",
                description="没有找到可注入的.py文件",
                injected=False, detected=False
            )
        ])

    # Mode hierarchy: quick < standard < full
    _MODE_LEVEL = {"quick": 0, "standard": 1, "full": 2}
    max_level = _MODE_LEVEL.get(mode, 0)

    # Get baseline scores from the ORIGINAL file (before mutation)
    # This allows detecting score degradation even when absolute scores are high
    baseline_scores: dict[str, dict[str, int]] = {}  # mode -> {dim: score}
    try:
        from harness.runner import check as _check
        for m in set(mut.get("target_mode", "quick") for mut in MUTATIONS):
            if _MODE_LEVEL.get(m, 0) <= max_level:
                base_report = _check([target], mode=m)
                baseline_scores[m] = {
                    d.name: d.score
                    for d in base_report.dimensions
                    if d.status == "evaluated"
                }
    except Exception:
        pass  # If baseline fails, detection still works via absolute thresholds

    results: list[MutationResult] = []

    with tempfile.TemporaryDirectory(prefix="harness_mutation_") as tmp_dir:
        for mutation in MUTATIONS:
            # Filter: only run mutations whose target_mode <= requested mode
            target_mode = mutation.get("target_mode", "quick")
            if _MODE_LEVEL.get(target_mode, 0) > max_level:
                results.append(MutationResult(
                    name=mutation["name"],
                    description=mutation["description"],
                    injected=False, detected=False,
                    details=f"跳过：需要{target_mode}模式（当前{mode}）"
                ))
                continue

            # 注入突变
            mutated_file = _inject_mutation(target, mutation, tmp_dir)
            if mutated_file is None:
                results.append(MutationResult(
                    name=mutation["name"],
                    description=mutation["description"],
                    injected=False, detected=False,
                    details="注入失败"
                ))
                continue

            # 检测：使用突变的目标模式，对比baseline
            detected, details = _check_detection(
                mutated_file,
                mode=target_mode,
                baseline_scores=baseline_scores.get(target_mode),
            )
            results.append(MutationResult(
                name=mutation["name"],
                description=mutation["description"],
                injected=True,
                detected=detected,
                details=details,
            ))

    return MutationReport(results=results)


def print_mutation_report(report: MutationReport) -> None:
    """打印PM友好的突变测试报告"""
    print("━━━ Harness 安检门自测 ━━━")
    print(f"测试方法：往代码里故意藏{report.total}种已知Bug，看harness能拦住几个")
    print()

    for r in report.results:
        if not r.injected:
            icon = "⏭"
            status = "跳过"
        elif r.detected:
            icon = "✅"
            status = "拦住了"
        else:
            icon = "❌"
            status = "漏过了"

        print(f"  {icon} {r.description} → {status}")
        if r.details:
            print(f"     {r.details}")

    print()
    print(f"━━━ 拦截率: {report.detected}/{report.total} = {report.detection_rate:.0f}% ━━━")

    if report.missed > 0:
        print(f"⚠️  有{report.missed}种Bug漏过了安检门，harness需要加强！")
    else:
        print("✅ 所有已知Bug都被拦住了，安检门有效。")
