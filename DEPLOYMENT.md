# Railway 部署指南

## 数据库持久化配置

### 方法1：使用Railway PostgreSQL插件（推荐）

1. **在Railway控制台添加PostgreSQL**
   - 进入你的Railway项目
   - 点击 "New" → "Database" → "PostgreSQL"
   - Railway会自动创建PostgreSQL数据库并设置 `DATABASE_URL` 环境变量

2. **代码已配置支持PostgreSQL**
   - 应用会自动检测 `DATABASE_URL` 环境变量
   - 如果存在，使用PostgreSQL；否则使用SQLite（本地开发）

3. **部署步骤**
   ```bash
   # 链接到Railway项目
   railway link -p YOUR_PROJECT_ID
   
   # 部署代码
   railway up
   ```

### 方法2：使用外部数据库

如果你有自己的PostgreSQL数据库：

1. **设置环境变量**
   ```bash
   railway variables set DATABASE_URL=postgresql://username:password@host:port/database
   ```

2. **部署应用**
   ```bash
   railway up
   ```

## 环境变量配置

### 必需的环境变量
- `DATABASE_URL`: PostgreSQL连接字符串（Railway会自动设置）
- `RAILWAY_ENVIRONMENT`: 设置为 `production`
- `PORT`: Railway会自动设置

### 可选的环境变量
- `FLASK_ENV`: 设置为 `production`

## 部署验证

1. **检查应用状态**
   ```bash
   railway status
   ```

2. **查看日志**
   ```bash
   railway logs
   ```

3. **测试功能**
   - 访问应用URL
   - 测试库存录入功能
   - 测试数据导出功能

## 数据迁移

如果从SQLite迁移到PostgreSQL：

1. **备份现有数据**
   ```bash
   # 导出SQLite数据
   sqlite3 inventory.db .dump > backup.sql
   ```

2. **导入到PostgreSQL**
   ```bash
   # 连接到PostgreSQL并导入数据
   psql $DATABASE_URL < backup.sql
   ```

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 `DATABASE_URL` 环境变量
   - 确保PostgreSQL服务正在运行

2. **表创建失败**
   - 检查数据库权限
   - 查看应用日志

3. **CSV导入失败**
   - 确保 `BIN.csv` 文件存在
   - 检查文件编码格式

### 日志查看
```bash
railway logs --tail
```

## 性能优化

1. **数据库连接池**
   - 考虑使用连接池库如 `psycopg2-pool`

2. **缓存策略**
   - 对于频繁查询的数据考虑添加缓存

3. **监控**
   - 使用Railway的监控功能跟踪应用性能
