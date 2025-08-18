# Railway 部署指南

## 数据库持久化配置

本项目已配置为在Railway上使用PostgreSQL数据库，在本地开发时使用SQLite数据库。

### 自动数据库切换

- **本地开发**: 使用SQLite (`inventory.db`)
- **Railway生产环境**: 使用PostgreSQL (通过`DATABASE_URL`环境变量)

### 部署步骤

1. **在Railway上创建项目**
   - 登录Railway账号
   - 创建新项目
   - 连接GitHub仓库

2. **添加PostgreSQL数据库**
   - 在Railway项目仪表板中点击"New"
   - 选择"Database" → "PostgreSQL"
   - Railway会自动设置`DATABASE_URL`环境变量

3. **配置环境变量**
   - `RAILWAY_ENVIRONMENT=production`
   - `DATABASE_URL` (Railway自动设置)

4. **部署应用**
   ```bash
   railway up
   ```

### 数据库迁移

应用会自动检测数据库类型并创建相应的表结构：

- **PostgreSQL**: 使用`SERIAL`主键
- **SQLite**: 使用`AUTOINCREMENT`主键

### 初始数据导入

- 如果有`BIN.csv`文件，会自动导入库位数据
- 商品数据会在用户输入时自动创建

### 验证部署

1. 检查应用日志确认数据库初始化成功
2. 测试库存录入功能
3. 验证数据持久化（重启后数据仍然存在）

### 本地开发

本地开发时无需额外配置，直接运行：
```bash
python server.py
```

应用会自动使用SQLite数据库。
