# Harness Engineering v2.0 — PRD 与开发方案

## 产品使命

在AI时代，为非技术PM提供友好高效的开发环境，让他们可以用AI做出自己的产品。能做到这一点，也算是改变了世界一点点。

**核心指标**：功能讨论清楚之后，AI能高质量完成项目，不是做出来之后改了又改。

---

## 从 v1.2 到 v2.0：补什么？

v1.2 已经有了完整的"诊断能力"（8维评分、自动修复循环、突变自检）。v2.0 补的是"执行力"——让这些能力**稳定运行、强制生效、可被度量**。

| 问题 | 根因 | v2.0 解法 |
|------|------|-----------|
| Hook 闪退导致保护失效 | bash 脚本 `set -u` 炸空变量、timeout 太短、无日志 | Python 统一入口 + 防崩包装 + 30s timeout |
| 七阶流程被跳过 | 只写在 CLAUDE.md 里，AI 可以忽略 | 状态文件 + PreToolUse hook 拦截 |
| Spec 是对话文字不是文件 | Stage 2 没有产出物 | 强制生成 `.harness/spec.md` 才能进下一阶段 |
| 不知道 harness 有没有用 | 无任何数据记录 | SQLite 遥测 + 报告命令 |

**不改的**：reward.py（8维评分）、autofix.py（修复循环）、feedback.py（结构化反馈）、verdict.py（门禁决策）、mutation_test.py（突变自检）。这些已经验证过，保持不动。

---

## 架构设计

### 数据流

```
PM 描述需求
  ↓
AI 进入 Stage 1 UNDERSTAND
  ↓ pipeline.json 记录 stage=1
  ↓ AI 尝试写代码 → pre_edit.py 读 pipeline.json → 拦截 ✋
  ↓ AI 完成理解 → pipeline advance → stage=2
  ↓
AI 进入 Stage 2 SPEC
  ↓ AI 生成 .harness/spec.md
  ↓ AI 尝试写代码 → pre_edit.py → 拦截 ✋
  ↓ PM 确认 spec → pipeline advance（检查 spec.md 存在）→ stage=4
  ↓
AI 进入 Stage 4 IMPLEMENT
  ↓ AI 写代码 → pre_edit.py → 放行 ✅
  ↓ 代码写入 → post_edit.py → check_quick() → ruff+bandit
  ↓ 如果不过 → autofix 循环 → 反馈给 AI → AI 修
  ↓ telemetry.db 记录每次检查结果
  ↓
AI 进入 Stage 5-7
  ↓ git commit → pre_commit.py → check_standard() + spec 验证 → 门禁
  ↓
交付 ✅ （telemetry 可追溯整个过程）
```

### 新增文件清单

| 文件 | 作用 | 行数 | 依赖 |
|------|------|------|------|
| `harness/telemetry.py` | SQLite 遥测记录，永不阻塞 | ~150 | 无 |
| `harness/health.py` | 依赖健康检查（ruff/bandit/mypy 在不在） | ~80 | 无 |
| `harness/hook_runner.py` | 统一 hook 入口：解析 stdin、防崩包装、记日志 | ~120 | telemetry |
| `harness/spec_file.py` | 读取和验证 spec.md | ~80 | 无 |
| `harness/pipeline.py` | 流水线状态机：阶段推进、门禁检查 | ~200 | spec_file |
| `hooks/post_edit.py` | 替代 fix_loop_hook.sh（Python 版） | ~60 | hook_runner |
| `hooks/pre_edit.py` | **新增**：阶段门禁，阻止在 SPEC 阶段写代码 | ~40 | hook_runner, pipeline |
| `hooks/pre_commit.py` | 替代 pre_commit_gate.sh（Python 版） | ~70 | hook_runner, pipeline, spec_file |
| `hooks/stop_check.py` | 替代 stop_check.sh（Python 版） | ~30 | hook_runner |
| `hooks/install_v2.py` | 安装脚本：生成 settings.json hooks 配置 | ~100 | health |

**总计新增约 930 行代码，10 个文件。**

### 改动现有文件

| 文件 | 改什么 | 行数变化 |
|------|--------|---------|
| `harness/__init__.py` | 加新模块的 export | +10 |
| `harness/runner.py` | check() 末尾加可选 telemetry 调用 | +5 |

---

## 每个新模块的关键设计

### telemetry.py — 永不阻塞的黑匣子

```python
# 核心原则：写入失败 = 静默丢弃，绝不影响 hook 执行
def log_check(event: CheckEvent) -> None:
    try:
        conn = sqlite3.connect("~/.harness/telemetry.db", timeout=1)
        conn.execute("INSERT INTO check_events ...")
        conn.commit()
    except Exception:
        pass  # 遥测丢了不要紧，hook 不能挂

def report(days=30) -> str:
    # 输出：通过率、最常失败的维度、平均修复轮次、按项目分组
```

### pipeline.py — 状态机 + 逃生门

```python
def is_code_write_allowed(project_root: str) -> tuple[bool, str]:
    state = get_state(project_root)
    if state is None:  # 没有 pipeline.json = 不受管
        return True, ""
    if state.current_stage <= 3:  # UNDERSTAND/SPEC/DESIGN
        return False, f"当前在 Stage {state.current_stage} ({state.stage_name})，请先完成此阶段"
    return True, ""

def advance(project_root: str) -> AdvanceResult:
    state = get_state(project_root)
    # Stage 2 → 4 时检查 spec.md 存在
    if state.current_stage == 2:
        spec = find_spec(project_root)
        if not spec:
            return AdvanceResult(ok=False, reason="请先生成 .harness/spec.md")
    # 更新 pipeline.json
    ...
```

**逃生门**：`python3 -m harness.pipeline reset` 清除状态，`skip` 跳过当前阶段。PM 不需要知道这些，AI 自己判断什么时候用。

### hook_runner.py — 防崩包装器

```python
def run_hook(handler: Callable) -> int:
    """包装任何 hook handler，保证：
    1. stdin 解析失败 → exit 0（放行）
    2. handler 抛异常 → exit 0（放行）+ 记日志
    3. handler 返回 (exit_code, message) → 正常执行
    原则：坏掉的 harness 比没有 harness 更糟。宁可放行也不要崩溃。
    """
```

### spec_file.py — Spec 文件验证

验证 `.harness/spec.md` 格式：
- 非空
- 至少包含一条验收标准（"当X时，应该Y" 或 "- [ ]" 格式）
- 有影响文件列表

### health.py — 一键自检

```bash
$ python3 -m harness.health
✅ ruff 0.8.1         installed
✅ bandit 1.7.9       installed
✅ mypy 1.11.0        installed
⚠️ detect-secrets     not installed (fallback to regex)
✅ telemetry.db       writable
✅ hooks              4/4 configured in settings.json
Overall: HEALTHY (1 warning)
```

---

## settings.json hooks 配置（v2.0 目标状态）

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "python3 ~/Desktop/harness-engineering/hooks/pre_edit.py",
          "timeout": 5
        }]
      },
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "python3 ~/Desktop/harness-engineering/hooks/pre_commit.py",
          "timeout": 45
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{
          "type": "command",
          "command": "python3 ~/Desktop/harness-engineering/hooks/post_edit.py",
          "timeout": 30
        }]
      }
    ],
    "Stop": [{
      "hooks": [
        {"type": "command", "command": "osascript -e 'display notification \"✅ Claude 完成了\" with title \"Claude Code\" sound name \"Glass\"'"},
        {"type": "command", "command": "python3 ~/Desktop/harness-engineering/hooks/stop_check.py", "timeout": 10}
      ]
    }],
    "Notification": [{
      "hooks": [{"type": "command", "command": "osascript -e 'display notification \"💬 Claude 需要你的输入\" with title \"Claude Code\" sound name \"Ping\"'"}]
    }]
  }
}
```

**关键变化**：
- bash → python（稳定性）
- 新增 PreToolUse:Edit|Write（流水线门禁）
- timeout 15s → 30s（够用）
- 所有 hook 经过 hook_runner.py 的防崩包装

---

## 实施顺序

### 第一批：基础层（无用户感知变化）

```
Step 1: harness/telemetry.py     — SQLite 记录引擎
Step 2: harness/health.py        — 依赖自检
Step 3: harness/hook_runner.py   — 防崩包装器
Step 4: harness/spec_file.py     — spec 文件操作
```

每个独立可测，无外部依赖。完成后跑单元测试验证。

### 第二批：状态机

```
Step 5: harness/pipeline.py      — 流水线状态机
```

依赖 Step 4（spec_file）。完成后用 CLI 命令 `python3 -m harness.pipeline start/advance/status` 验证。

### 第三批：Hook 迁移

```
Step 6: hooks/post_edit.py       — 替代 fix_loop_hook.sh
Step 7: hooks/pre_edit.py        — 新增阶段门禁
Step 8: hooks/pre_commit.py      — 替代 pre_commit_gate.sh
Step 9: hooks/stop_check.py      — 替代 stop_check.sh
```

每个 hook 独立可测（echo mock JSON | python3 hook.py）。

### 第四批：集成

```
Step 10: hooks/install_v2.py     — 安装脚本
Step 11: 更新 harness/__init__.py 和 runner.py
Step 12: 运行 install_v2.py 切换到新 hooks
Step 13: 端到端验证（模拟完整 Stage 1-7 流程）
```

### 第五批：文档和自检

```
Step 14: 扩展突变测试（加 pipeline_bypass、telemetry_crash 模式）
Step 15: 更新 README.md
Step 16: 更新 CLAUDE.md 中的 harness 相关说明
```

---

## 验证方案

### 单元测试（每个模块完成后立即跑）

| 模块 | 关键测试 |
|------|---------|
| telemetry.py | 写入成功、DB不存在自动创建、写入失败不抛异常、report 正确计算 |
| pipeline.py | start 创建文件、advance 检查 spec、stage 1-3 禁止写代码、无 pipeline 文件放行 |
| hook_runner.py | stdin 解析、handler 异常被捕获、timeout 处理 |
| spec_file.py | 有效 spec 通过、空文件不通过、find 找到 .harness/spec.md |

### 集成测试（第四批完成后）

模拟完整流程：
1. `pipeline start` → 验证 pipeline.json 创建
2. 模拟 Edit → pre_edit.py 拦截（stage=2）
3. 写入 spec.md → `pipeline advance` → 进入 stage 4
4. 模拟 Edit → pre_edit.py 放行 + post_edit.py 检查
5. 模拟 git commit → pre_commit.py 门禁
6. 检查 telemetry.db 有记录

### 向后兼容验证

- 现有 pytest 测试全部通过
- `fix_and_report()` API 签名不变
- `check()` API 签名不变
- 没有 .harness/ 目录的项目行为完全不变

---

## 风险和应对

| 风险 | 严重度 | 应对 |
|------|--------|------|
| pre_edit hook 给每次编辑加延迟 | 中 | 只读一个 JSON 文件，<50ms，5s timeout 很宽裕 |
| pipeline.json 损坏 | 中 | 读取失败 = 不受管 = 放行（fail-open），有 reset 命令 |
| Python hook 比 bash 慢 | 低 | Python 启动 ~200ms，但总 budget 30s，绰绰有余 |
| PM 被困在错误阶段 | 中 | AI 可以 `pipeline reset/skip`，PM 不需要操心 |
| 迁移过程破坏现有 hook | 高 | 旧 bash 脚本保留，install_v2 显式切换，一键回滚 |

---

## 成功标准

做完 v2.0 后，达到以下状态就算成功：

1. **Hook 零崩溃**：连续使用一周，没有 "hook error" 导致闪退
2. **Stage 不可跳过**：AI 在 SPEC 阶段写代码会被物理拦截
3. **每次改动有 spec**：非微改动都有 `.harness/spec.md` 文件
4. **质量可度量**：`python3 -m harness.telemetry report` 能看到通过率和趋势
5. **PM 无感知**：PM 不需要学任何新命令，只管描述需求和确认 spec
