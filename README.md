# Inventory Management System | 库存盘点系统

A bilingual (Chinese/English) web-based inventory management system designed for efficient warehouse operations.

一个双语（中文/英文）的网页版库存盘点系统，为高效的仓库运营而设计。

## Features | 功能特点

### Core Functions | 核心功能
- **Inventory Input | 库存录入**
  - Real-time input validation | 实时输入验证
  - Auto-completion for bin locations and item codes | 库位和商品编号自动补全
  - Confirmation dialog before submission | 提交前确认对话框
  - Recent input history display | 最近输入记录显示

- **Inventory Query | 库存查询**
  - Query total quantity by item | 按商品查询总数量
  - Query items by bin location | 按库位查询商品
  - Query bin locations by item | 查询商品所在库位
  - Export inventory data to Excel | 导出库存数据到Excel

- **History Tracking | 历史记录**
  - Real-time history updates | 实时历史更新
  - Complete input history log | 完整的输入历史记录
  - Recent activities display | 最近活动显示

### Special Features | 特色功能
- **Bilingual Support | 双语支持**
  - Complete Chinese/English interface | 完整的中英文界面
  - Language preference persistence | 语言偏好保持
  - Seamless language switching | 无缝语言切换

- **Responsive Design | 响应式设计**
  - Mobile-friendly interface | 移动设备友好界面
  - Adaptive layout | 自适应布局
  - Touch-optimized inputs | 触控优化输入

- **Data Visualization | 数据可视化**
  - Color-coded information | 颜色编码信息
  - Organized data display | 组织化数据显示
  - Clear visual hierarchy | 清晰的视觉层次

## Tech Stack | 技术栈

### Frontend | 前端
- HTML5/CSS3
- JavaScript/jQuery
- jQuery UI (Autocomplete)
- Responsive Design

### Backend | 后端
- Python
- Flask
- SQLite3
- Pandas (Data Processing)
- XlsxWriter (Excel Export)

### Database | 数据库
- SQLite3
- Structured Schema Design
- Foreign Key Constraints

## Advantages | 系统优势

1. **User-Friendly | 用户友好**
   - Intuitive interface | 直观的界面
   - Clear visual feedback | 清晰的视觉反馈
   - Minimal training required | 最小化培训需求

2. **High Performance | 高性能**
   - Fast response time | 快速响应
   - Efficient data processing | 高效数据处理
   - Optimized database queries | 优化的数据库查询

3. **Reliability | 可靠性**
   - Data validation | 数据验证
   - Error handling | 错误处理
   - Transaction management | 事务管理

4. **Maintainability | 可维护性**
   - Clean code structure | 清晰的代码结构
   - Modular design | 模块化设计
   - Well-documented | 完善的文档

5. **Scalability | 可扩展性**
   - Modular architecture | 模块化架构
   - Easy to add features | 易于添加功能
   - Flexible data model | 灵活的数据模型

## Getting Started | 开始使用

1. **Prerequisites | 前置要求**
   ```bash
   python -m pip install flask flask-cors pandas xlsxwriter
   ```

2. **Setup | 设置**
   ```bash
   # Clone the repository
   git clone https://github.com/johnliuze/InventoryCount.git
   cd inventory-system

   # Initialize the database
   python server.py
   ```

3. **Usage | 使用**
   - Access the system at `http://localhost:5001`
   - Import your bin locations (BIN.csv) and items (Item.CSV)
   - Start managing your inventory!

## License | 许可证
MIT License

## Contact | 联系方式
johnliuze04@gmail.com