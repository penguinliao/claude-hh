# 单步聚焦流水线演示

## 场景：给博客系统添加标签功能

### Stage 1: UNDERSTAND

> 我理解的需求是：给现有博客系统添加文章标签功能，用户可以给文章打标签，也可以按标签筛选文章。
>
> **疑问：**
> 1. 标签是预定义的还是用户自由输入的？→ 假设自由输入
> 2. 一篇文章最多几个标签？→ 假设不限
>
> ✅ 用户确认：理解正确，标签自由输入不限数量。

### Stage 2: SPEC

> **验收标准：**
> 1. 当用户编辑文章时，可以输入逗号分隔的标签
> 2. 当文章保存时，标签应存储到数据库关联表
> 3. 当用户点击标签时，应显示该标签下的所有文章
> 4. 当标签为空时，不应显示标签区域
>
> **修改范围：**
> | 文件 | 修改内容 | 风险 |
> |------|---------|------|
> | db.py | 新增tags表和article_tags关联表 | 低 |
> | api/articles.py | 新增标签CRUD端点 | 中 |
> | frontend/article.js | 添加标签输入组件 | 低 |
>
> ✅ 用户确认：开始。

### Stage 3: DESIGN（跳过 — 3文件小改动）

### Stage 4: IMPLEMENT（只写db.py的标签表）

```python
# 只做这一个模块
def create_tags_tables():
    with db_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_tags (
                article_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (article_id, tag_id)
            )
        """)
```

### Stage 5: SELF-TEST（只测db.py的标签表）

```python
# 自测：创建表→插入标签→查询
create_tags_tables()
with db_conn() as conn:
    conn.execute("INSERT INTO tags (name) VALUES (?)", ("Python",))
    result = conn.execute("SELECT name FROM tags").fetchone()
    assert result[0] == "Python"  # ✅ PASS
```

→ 重复 Stage 4-5 处理 api/articles.py 和 frontend/article.js

### Stage 6: INTEGRATE

> 运行 `python main.py` → 无报错 ✅
> Ruff check → 0 warnings ✅
> mypy → 0 errors ✅
> Bandit → 0 issues ✅
>
> 验收标准逐条检查：
> 1. 编辑文章可输入标签 → ✅
> 2. 保存后标签存到DB → ✅（查article_tags表确认）
> 3. 点击标签显示文章列表 → ✅
> 4. 空标签不显示 → ✅

### Stage 7: REVIEW

> **审查清单：**
> - [✅] API端点有认证
> - [✅] 错误有前端可见提示
> - [✅] DB用context manager
> - [✅] 前端调用的API后端都实现了
> - [✅] tags表有CREATE TABLE IF NOT EXISTS
> - [✅] 验收标准全部满足
>
> **结论：PASS，可交付。**
