# Five-Stage Pipeline (v3.0)

> 核心原则：
> 1. AI注意力有限，每步只做一件事
> 2. 写代码的和查代码的不能是同一个上下文（认知隔离）
> 3. Opus 监工调度，Sonnet 执行写码，PM 只在起点和终点参与

---

## 架构

```
PM给需求 → Opus对齐需求 → PM说"开始"
                ↓
    ┌─── Pipeline 自动运行（PM不参与）───┐
    │                                      │
    │  Stage 1  SPEC       验收标准+文件清单 │
    │  Stage 2  DESIGN     架构设计(大改动)  │
    │  Stage 3  IMPLEMENT  Sonnet写代码     │
    │  Stage 4  REVIEW     新agent审查代码   │
    │  Stage 5  TEST       白盒+黑盒测试    │
    │     ↑                    │            │
    │     └── 发现问题回Stage3 ──┘            │
    │                                      │
    └──────────────────────────────────────┘
                ↓
    通知PM验收（macOS通知）
```

## 角色分工

| 角色 | 模型 | 职责 | 绝不做 |
|------|------|------|--------|
| Opus（主Agent） | opus 4.6 | 理解需求、出方案、调度、审查 | 写代码 |
| Sonnet（子Agent） | sonnet 4.6 | 写代码、自测 | 架构决策 |
| 小测 | 继承 | 白盒审计 | 写代码 |
| 浊龙 | 继承 | 黑盒验收 | 读代码 |

## 阶段总览

| # | 名称 | 谁做 | 只做什么 | 绝不做 |
|---|------|------|---------|--------|
| 1 | SPEC | Opus | 验收标准、文件清单 | 写代码、设计架构 |
| 2 | DESIGN | Opus | 数据模型、接口契约、模块划分 | 写实现代码 |
| 3 | IMPLEMENT | Sonnet | 写代码、自测语法 | 架构决策、测试 |
| 4 | REVIEW | 新Agent | 审查代码（认知隔离） | 改代码 |
| 5 | TEST | 小测+浊龙 | 白盒+黑盒找bug | 写代码 |

## 路由

| 路由 | 适用场景 | 阶段 |
|------|---------|------|
| micro | typo/样式/文案（1文件几行） | 3 → 4 → 5 |
| standard | 功能改动（1-3文件） | 1 → 3 → 4 → 5 |
| full | 新功能/跨模块（4+文件） | 1 → 2 → 3 → 4 → 5 |

## 循环与回退

```
Stage 4 REVIEW 发现问题 → retreat 到 Stage 3 → Sonnet修复 → 重新 REVIEW
Stage 5 TEST 发现问题   → retreat 到 Stage 3 → Sonnet修复 → REVIEW → TEST
最多循环 3 次，超过停下报告 PM
```

## 物理控制（Hook 强制执行）

| 规则 | 机制 | 效果 |
|------|------|------|
| 无pipeline不能写代码 | pre_edit hook | 强制先启动pipeline |
| Stage 1-2不能写代码 | pre_edit hook | 强制先出spec再动手 |
| Stage 4-5不能写代码 | pre_edit hook | 审查和测试不能偷偷改代码 |
| 代码质量门禁 | post_edit hook | 每次编辑后自动检查 |
| 提交前完整检查 | pre_commit hook | git commit前跑完整质量门禁 |

## Stage Prompts

```
stage_prompts/
├── 01_spec.md
├── 02_design.md
├── 03_implement.md
├── 04_review.md
└── 05_test.md
```
