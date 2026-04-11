# 架构约束规则

> 复制以下内容到项目的CLAUDE.md中

## 数据库
- 连接必须用context manager（`with db_conn() as conn:`），禁止手动open/close
- 新增表用CREATE TABLE IF NOT EXISTS，重启自动创建
- 新增字段需要手动迁移脚本（SQLAlchemy的create_all不会ALTER）
- SQLite开启WAL模式
- 连接池配置：pool_pre_ping=True防止死连接

## 异步任务
- asyncio.create_task必须用safe_task包装（异常不能静默丢失）
- 后台任务异常必须记录日志
- 长时间任务必须有超时机制

## 数据模型
- Pydantic v2的Optional字段必须显式声明 `Optional[str] = None`
- 不要用 `field: str = None`（Pydantic v2会ValidationError）
- 基础模型继承StrictBaseModel（strict=True，禁止隐式类型转换）

## 字符串处理
- format()不得用于包含用户输入的字符串（用.replace()或f-string）
- .strip()前先检查是否为None（`(value or "").strip()`）

## 项目结构
- 新项目从project-template创建，不从零搭建
- 通用功能用starpalace-shared（db/auth/security/errors/tasks），不重复造轮子
- 多模块协作先出协议再写代码（标准化接口文档）

## 错误处理
- 每个降级链的最后一环也要有try/except
- 熔断器半开状态需要流量控制（不要一下全放）
- 第三方API调用：超时+重试+降级三层防护

## 部署
- 部署前备份（.bak），出问题秒回退
- 功能做完要主动审计：前端有没有调、后端有没有存、定时任务有没有注册、配额有没有扣
- scp上传子目录文件注意路径
