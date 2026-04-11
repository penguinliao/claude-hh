# Stage 3: IMPLEMENT

## 架构：Opus 调度，Sonnet 执行

**Opus（主Agent）不直接写代码。** 所有代码编写通过 Agent tool 派 Sonnet 子agent 完成。

### Opus 的工作

1. **拆分任务**：根据 spec.md 和 design.md，把实现拆成独立的模块级任务
2. **逐个派发**：每次派一个 Sonnet agent 实现一个模块，完成后再派下一个
3. **Sonnet 自测**：每个 Sonnet agent 在返回前必须验证代码语法正确、基本功能可用
4. **冲突检查**：多个 Sonnet 改同一文件时，合并后检查语法和关键函数存在

### 派发 Sonnet 的 Prompt 模板

```
你是代码实现工程师。直接写代码，不要分析确认。

## 流水线规则（必须遵守，违反=交付作废）

1. **开工前先检查流水线状态**：运行 `python3 -m harness.pipeline status`
   - 必须处于 Stage 3 IMPLEMENT 阶段才能写代码
   - 如果不在 Stage 3 → 立即停止，返回"当前不在IMPLEMENT阶段，无法写代码"
   - 如果没有活跃的pipeline → 立即停止，返回"没有活跃的pipeline"
2. **只改 spec 列出的文件**：不在 spec.md 影响文件列表里的文件，不要动
3. **不做 Stage 4/5 的事**：不做代码审查、不做测试验收、不评价自己代码质量
4. **不修改 pipeline.json**：不要运行 advance/retreat/reset，流水线控制是 Opus 的事

## 任务

任务：[具体要实现什么]
文件：[要修改的文件路径]
项目根目录：[project_root 的绝对路径]
接口要求：[从 design.md 或 spec.md 摘取的接口定义]
验收标准：[从 spec.md 摘取的相关验收标准]

## 编码要求

1. 严格按接口要求实现，不自行扩展
2. 写完整代码，不留 TODO
3. 处理异常情况
4. 完成后运行 python3 -c "import ast; ast.parse(open('文件路径').read())" 验证语法
```

### Agent tool 参数

```python
Agent(
    subagent_type="general-purpose",
    model="sonnet",  # 关键：用 Sonnet 写代码
    prompt="...",     # 上面的模板，project_root 必须填实际路径
)
```

### 验证条件

- 所有 spec.md 中的影响文件都已实现
- 每个文件语法正确
- Opus 不直接 Edit/Write 代码文件（pre_edit hook 拦截）

### Opus 绝对不做

- **不直接写代码**：所有代码改动通过 Sonnet 完成
- **不做测试**：测试是 Stage 5 的事
- **不做审查**：审查是 Stage 4 的事（且要用新上下文）
