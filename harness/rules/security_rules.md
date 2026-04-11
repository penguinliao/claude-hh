# 安全编码规则

> 来源：Wiz安全规则文件 + OpenSSF AI安全编码指南
> 复制以下内容到项目的CLAUDE.md中

## 认证与授权
- 所有API端点必须有认证（除非明确标注为public）
- JWT密钥必须从环境变量读取，无默认值，未配置则拒绝启动
- 不要在query参数中传递user_id作为认证凭据
- 管理后台禁止使用MD5+固定密码

## 输入验证
- 所有用户输入必须通过Pydantic模型验证（strict=True）
- SQL查询必须参数化（禁止字符串拼接和.format()）
- 文件路径必须sanitize（移除..和路径穿越字符）
- XML解析必须禁用外部实体（使用defusedxml）
- LIKE查询的%和_必须转义

## 输出安全
- HTML输出必须转义用户内容（防XSS）
- API响应不要返回内部错误堆栈（生产环境）
- 日志禁止记录密钥/密码/token/API Key

## 配置安全
- CORS不允许*通配符（必须指定具体origins）
- 禁止yaml.dump重写config.yaml（会清空敏感配置）
- 生产环境禁止开启debug模式
- 禁止硬编码密钥/密码/API Key（必须从环境变量读取）

## 密码学
- 禁止使用MD5/SHA1做密码哈希（使用bcrypt）
- 随机数使用secrets模块（不用random）
- 邀请码/token长度至少12位

## 依赖安全
- 有官方SDK就不要手写API调用
- 第三方API中转站需评估数据安全合规性
- 禁止eval()/exec()处理外部输入
