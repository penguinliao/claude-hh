# CLAUDE.md 新增板块（补丁预览）

> 以下内容应追加到 ~/.claude/CLAUDE.md 的合适位置。

---

## A. 规格先行工作流

每次开发必须走完这5步，跳步 = 返工：

1. **需求确认**：AI先输出——"我理解的需求是X"、验收标准（当A时应该B）、要改哪些文件每个改什么
2. **用户确认**：用户说"开始"才写代码。用户没说开始，一行代码都不写
3. **分模块实现**：复杂功能拆成独立模块，每个模块写完立即自测（py_compile + 核心函数调用）
4. **自主验证**：写完必须自己运行验证，不要让用户替你跑。能curl就curl，能python就python
5. **交付前自查**：切换到"审查者"视角，过一遍清单：
   - 所有新增函数有调用方吗？
   - 所有新增路由在前端有入口吗？
   - 所有数据库写入有对应的读取吗？
   - 错误路径有前端可见提示吗？
   - 配额/权限变更有扣减/校验吗？

---

## B. 单步聚焦原则

AI每个阶段只做一件事，混着做 = 每件都做不好：

| 阶段 | 只做 | 不做 |
|------|------|------|
| 理解需求 | 分析、提问、确认 | 写代码 |
| 写代码 | 实现功能 | 测试、优化 |
| 测试 | 运行、验证、记录 | 写新代码 |
| 审查 | 检查、报告 | 改逻辑 |

- 复杂功能（涉及3+文件）必须走分步流水线，每步有明确的输入输出
- 发现前一步有问题，回到前一步重做，不要在当前步骤偷偷补

---

## C. 安全编码规则

10条铁律，违反任何一条 = 代码审查不通过：

1. **禁止硬编码密钥**：所有密钥/token/密码从环境变量或配置文件读取，代码里出现明文密钥直接打回
2. **SQL必须参数化**：用 `?` 或 `%s` 占位符，禁止f-string拼SQL。SQLAlchemy的ORM查询除外
3. **用户输入必须验证**：FastAPI用Pydantic model，Flask用marshmallow或手动校验。不验证 = 信任攻击者
4. **CORS禁止通配符**：`allow_origins=["*"]` 只允许在本地开发环境。生产环境必须指定具体域名
5. **JWT无默认值**：SECRET_KEY未配置时拒绝启动（raise而非fallback），不允许`SECRET_KEY = os.getenv("SECRET_KEY", "default")`
6. **后端错误必须有前端提示**：禁止静默catch。catch后必须return有意义的错误信息，前端必须显示给用户
7. **DB连接用context manager**：`with session_scope() as session:` 或 `async with get_db() as db:`，禁止手动open/close
8. **后台任务用safe_task**：`asyncio.create_task`必须加`done_callback`处理异常，或用封装好的`safe_task`。裸create_task的异常会被静默吞掉
9. **XML禁用外部实体**：解析XML时设置`defusedxml`或手动禁用DTD。防止XXE攻击
10. **日志禁止敏感信息**：logger不记录密钥、密码、token、手机号。脱敏后才能记录

---

## D. 架构约束

- **新项目从template创建**：`cp -r project-template/ 新项目名/`，不从零开始
- **通用功能用starpalace-shared**：记忆、路由、压缩等跨项目共享模块统一维护，不在各项目重复实现
- **Pydantic Optional显式声明**：写`Optional[str] = None`，不写`str = None`。后者在Pydantic v2中行为不同
- **format()不用于用户输入**：含用户输入的字符串用f-string或`%s`参数化，不用`.format()`（防止格式化字符串注入）
- **asyncio.create_task必须加回调**：
  ```python
  task = asyncio.create_task(do_something())
  task.add_done_callback(handle_task_exception)
  ```
  不加回调 = 异常被静默吞掉，线上出了问题没人知道
