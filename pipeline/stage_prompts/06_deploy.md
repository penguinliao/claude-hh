# Stage 6: DEPLOY（可选）

## 目标：安全地部署到生产环境

只有 `-deploy` 路由（standard-deploy / full-deploy）才包含此阶段。

### 部署前检查

1. **前置阶段全部通过**：REVIEW + TEST 的物理门禁已通过
2. **备份当前版本**：`ssh server "cp -r /项目路径 /项目路径.bak.$(date +%Y%m%d%H%M)"`
3. **确认配置差异**：`diff 本地配置 服务器配置`，看到凭证差异立即停手

### 部署步骤

1. **上传代码**：`scp` 或 `rsync`，注意子目录路径
2. **安装依赖**：`pip3 install --break-system-packages -r requirements.txt`
3. **数据库迁移**：新表用 `CREATE TABLE IF NOT EXISTS`，新字段手动 `ALTER TABLE`
4. **重启服务**：`kill → source .env → 启动 → sleep 5 → lsof 验证 → tail log`
5. **烟测验证**：curl 核心端点确认服务正常

### 绝对不做

- **不用 scp 整文件覆盖含凭证的配置**：会清空生产凭证
- **不用 yaml.dump 重写 config.yaml**：同上
- **不跳过备份**：出问题要能秒回退
- **不用 run_in_background 跑 SSH 命令**：断开 session 会 exit 255

### Pipeline 完成后

自动通知 PM 验收：
```
osascript -e 'display notification "部署完成，请验收" with title "Harness Pipeline" sound name "Glass"'
```
