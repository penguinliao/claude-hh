# 项目开发规范

## 规格先行
- 写代码前先输出：需求理解 + 验收标准 + 修改范围
- 用户确认后才动手
- 复杂功能走5阶段流水线（SPEC→DESIGN→IMPLEMENT→REVIEW→TEST，可选+DEPLOY）

## 单步聚焦
- 每个阶段只做一件事
- 理解时不写代码，写代码时不测试，测试时不写新代码

## 安全编码
- 禁止硬编码密钥（从环境变量读）
- SQL必须参数化
- 用户输入必须Pydantic验证
- CORS禁止*通配符
- JWT无默认值
- 后端错误必须有前端可见提示
- DB连接必须用context manager
- 后台任务必须用safe_task

## 架构约束
- 通用功能用starpalace-shared
- Pydantic Optional必须显式声明
- format()不用于用户输入字符串
- asyncio.create_task必须加done_callback

## 交付标准
- 写完必须自己运行验证
- 交付前自查：认证？错误提示？事务？前后端对齐？
