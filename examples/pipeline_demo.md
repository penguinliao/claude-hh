# 单步聚焦流水线演示

## 场景：给博客系统添加标签功能

### Stage 1: SPEC

> **验收标准：**
> 1. 当用户编辑文章时，可以输入逗号分隔的标签
> 2. 当文章保存时，标签应存储到数据库关联表
> 3. 当用户点击标签时，应显示该标签下的所有文章
> 4. 当标签为空时，不应显示标签区域
>
> **影响文件：**
> | 文件 | 操作 | 改动说明 |
> |------|------|---------|
> | db.py | 修改 | 新增tags表和article_tags关联表 |
> | api/articles.py | 修改 | 新增标签CRUD端点 |
> | frontend/article.js | 修改 | 添加标签输入组件 |
>
> ✅ 用户确认：开始。

### Stage 2: DESIGN（跳过 — 3文件小改动，走standard路由）

### Stage 3: IMPLEMENT

Opus 派 Sonnet 写代码 + 测试脚本：

```python
# Sonnet 产出 1: db.py 标签表实现
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

```python
# Sonnet 产出 2: .harness/test_tags.py（必须同时写）
# exit 0 = 通过，非零 = 失败
import sys
sys.path.insert(0, ".")
from db import db_conn, create_tags_tables

create_tags_tables()
with db_conn() as conn:
    conn.execute("INSERT INTO tags (name) VALUES (?)", ("Python",))
    result = conn.execute("SELECT name FROM tags").fetchone()
    assert result[0] == "Python", f"Expected 'Python', got {result[0]}"

    # 验证关联表
    conn.execute("INSERT INTO article_tags VALUES (1, 1)")
    row = conn.execute("SELECT * FROM article_tags WHERE article_id=1").fetchone()
    assert row is not None, "article_tags insert failed"

print("All tests passed")
# exit 0 = success
```

→ 重复派 Sonnet 处理 api/articles.py 和 frontend/article.js

### Stage 4: REVIEW

harness 自动运行 `check_standard` 检查所有影响文件：

> harness 输出：
> ✅ REVIEW自动检查通过（78/100）
> - code_quality: 92/100
> - security: 85/100
> - type_safety: 70/100
> - functional: 80/100

### Stage 5: TEST

harness 自动执行 `.harness/test_*.py` 测试脚本：

> harness 输出：
> ✅ TEST通过：3个测试脚本全部exit 0
>
> 验收标准逐条覆盖：
> 1. 编辑文章可输入标签 → test_tags.py ✅
> 2. 保存后标签存到DB → test_tags.py ✅
> 3. 点击标签显示文章列表 → test_tag_filter.py ✅
> 4. 空标签不显示 → test_tag_filter.py ✅

### Pipeline 完成

> 通知 PM 验收。
