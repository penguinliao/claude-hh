# Stage 5: TEST

## 目标：找出所有问题，直到可以交付

不写新代码。目标是找 bug、找遗漏，找到就回 Stage 3 修，修完再测，循环直到干净。

### 测试分两层

#### 第一层：白盒测试（小测 Agent）

小测是内部审计员，聚焦 API 契约、DB 状态、权限矩阵、错误处理、性能基线。

```python
Agent(
    subagent_type="小测",
    prompt="""## 流水线规则（必须遵守）
1. 你是测试员，不是开发者：只测试、只记录问题，绝对不修改任何代码文件
2. 不修改 pipeline.json：不要运行 advance/retreat/reset
3. 发现 bug 只记录，修复是 Stage 3 的事

## 审计任务
审计以下文件的内部逻辑：[文件列表]
项目根目录：[project_root 的绝对路径]
验收标准：[spec.md 内容]
重点：API契约一致性、DB读写正确性、权限检查、错误处理覆盖、性能基线""",
)
```

#### 第二层：黑盒测试（浊龙 Agent）

浊龙是用户视角验收员，纯用户操作，不读代码。

```python
Agent(
    subagent_type="浊龙",
    prompt="""## 流水线规则（必须遵守）
1. 你是验收测试员：纯用户视角操作，不修改任何代码文件
2. 不修改 pipeline.json：不要运行 advance/retreat/reset
3. 发现问题只记录

## 交付单
[完整交付单，包含功能点、场景、AI角色等]""",
)
```

### 测试结果处理

- **两层都 PASS** → Pipeline 完成，通知 PM 验收
- **有 FAIL** → retreat 回 Stage 3，Opus 派 Sonnet 修复
- **TEST→IMPLEMENT→REVIEW→TEST 最多循环 3 次**

### Pipeline 完成后

自动发 macOS 通知叫 PM：
```
osascript -e 'display notification "开发+测试全部通过，请验收" with title "Harness Pipeline" sound name "Glass"'
```

### 绝对不做

- **不写新代码**：发现 bug 只记录，修复回 Stage 3
- **不手动修复再重测**：必须正式回 Stage 3
- **不跳过任何测试层**：白盒和黑盒都要跑
