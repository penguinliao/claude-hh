# Stage 1: SPEC

## 你现在只做一件事：把需求变成可验证的规格 + 验收测试

不写业务代码，不设计架构。PM已经给了需求，你的工作是：写出验收标准，并同时写好验收测试脚本和测试任务书。

### 为什么测试在这里写

测试标准必须在代码存在之前锁定。写代码的 AI（Sonnet）永远看不到测试脚本，也不能修改它。这保证了认知隔离：测试基于"应该做什么"（spec），不基于"怎么实现的"（代码）。

### 输入

- PM的需求描述（PRD或口头描述）
- 项目代码库（用于确认影响范围）

### 产出清单（全部保存到 .harness/ 目录）

#### 1. spec.md — 验收标准 + 接口契约

格式：

    ## 验收标准

    ### 功能点1：[名称]

    | # | 验收标准 | 优先级 | 类型 |
    |---|---------|--------|------|
    | 1 | 当[用户做X]时，应该[发生Y] | P0 | 正常路径 |
    | 2 | 当[异常情况A]时，应该[降级行为B] | P1 | 异常路径 |

    ## 接口契约

    ### [HTTP方法] [路径]
    - 入参: { field: type }
    - 出参: { field: type }
    - 错误: { code: number, message: string }

    ## 影响文件清单

    | 文件路径 | 操作 | 改动说明 |
    |----------|------|---------|
    | src/module/file.py | 修改 | 新增X函数 |

    ## 测试策略

    - 验收脚本: 需要
    - 小测审计: 需要 / 不需要（原因：...）
    - 浊龙验收: 需要 / 不需要（原因：...）

    ## 不在本次范围内

    - [明确不做的事情]

#### 2. test_ac_*.py — 验收测试脚本

每条 P0 验收标准至少对应一个测试脚本。脚本从用户视角写，测最终可见输出：

- 文件名格式：`.harness/test_ac_功能名.py`
- `exit 0` = 通过，非零 = 失败
- 测接口返回值、用户可见效果，不测内部函数
- 用 dev_/test_ 前缀测试账号，不用真实用户

##### 写测试的优先级（重要，决定测试是否鲁棒）

**第 1 优先：行为测试** — mock 或真实调用被测函数/接口，断言输出/副作用。**这是默认选项。**

**第 2 优先：AST 结构检查** — 用 `ast.parse` 解析代码，检查是否有某个调用/属性/赋值，而不是 grep 字符串。

**最后兜底：代码模式匹配（正则 grep）** — 只在行为测试和 AST 都做不到时才用。一旦使用，必须遵守以下规则：

1. **必须用 `or` 接多种合法写法**，不能只认一种实现
2. **跨行匹配用 `[\s\S]*?` 而不是 `\s*\n\s*`**（后者对换行和缩进的容忍度极低）
3. **宁可漏报也不要误报**：AC 测试是"Sonnet 写对了就过"，不是"Sonnet 按我期望的写法写了才过"

**反面教材**（真实案例，导致 retreat + 重走流水线）：

    # ❌ 错：只认同行写法，Sonnet 用 while True:\n chunk = ... 就误报
    has_stream = re.search(r"while\s+True:\s*\n\s*chunk\s*=\s*await\s+file\.read\(", content)

    # ✅ 对：跨行 + 多写法 or
    has_stream = (
        re.search(r"while\s+True:[\s\S]{0,300}?await[\s\S]{0,50}?\.read\(", content)
        or re.search(r"async\s+for\s+chunk\s+in", content)
    )

##### 示例：从优先到兜底的三种写法

**示例 A：行为测试（首选）**

    # test_ac_upload_size.py — AC "超过 100MB 上传返回 413"
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    big_payload = b"x" * (101 * 1024 * 1024)
    resp = client.post("/api/upload", files={"file": ("a.bin", big_payload)})
    assert resp.status_code == 413, f"应返回 413，实际 {resp.status_code}"

**示例 B：AST 结构检查（无法起服务时）**

    # test_ac_consume_energy.py — AC "扣费必须接收返回值"
    import ast
    tree = ast.parse(open("api/services/chat.py").read())
    n_assigned = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "consume_energy" for c in ast.walk(node.value))
    )
    assert n_assigned >= 2, f"consume_energy 返回值应被接收 ≥2 处，实际 {n_assigned}"

**示例 C：正则兜底（前两种都不行时）**

    # 必须 or 接多写法，必须跨行用 [\s\S]
    content = open("api/routes/chat.py").read()
    has_guard = (
        re.search(r"content[-_]length|Content-Length", content)
        or re.search(r"while\s+True:[\s\S]{0,300}?await[\s\S]{0,50}?\.read\(", content)
        or re.search(r"async\s+for\s+chunk\s+in", content)
    )
    assert has_guard, "上传大小校验缺失"

#### 3. xiaoce_brief.md — 小测审计任务书（如测试策略中标注"需要"）

    ## 审计范围
    文件：[从 spec 影响文件清单提取]

    ## 重点检查
    1. API 契约一致性：[具体检查什么]
    2. DB 读写正确性：[具体检查什么]
    3. 权限检查：[具体检查什么]
    4. 错误处理覆盖：[具体检查什么]
    5. 安全/性能：[具体检查什么]

#### 4. zhuolong_brief.md — 浊龙测试交付单（如测试策略中标注"需要"）

    ## 产品信息
    - 名称：[产品名]
    - 入口：[URL]
    - 测试账号：[Max权限账号 + 受限账号]

    ## 测试场景
    1. [用户做什么] → [最终预期结果]
    2. [用户做什么] → [最终预期结果]

### 验证条件（advance前自动检查）

- `.harness/spec.md` 存在且非空
- 每个功能点至少有1个P0验收标准
- `.harness/test_ac_*.py` 存在（数量 ≥ P0 验收标准数量）
- 测试策略字段已填写
- 如标注"需要"，对应 brief 文件存在

### 绝对不做

- **不写业务代码**：包括伪代码
- **不设计架构**：不定义类结构、不画模块图
- **不估时**
