from flask import Flask, request, jsonify, send_file
import sqlite3
import csv
from flask_cors import CORS
import os
import traceback
import pandas as pd
from io import BytesIO

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 错误处理
@app.errorhandler(Exception)
def handle_error(e):
    print("Error occurred:", str(e))
    print(traceback.format_exc())
    return jsonify(error=str(e)), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# 添加路由来提供前端文件
@app.route('/')
def index():
    try:
        return send_file('index.html')
    except Exception as e:
        print(f"Error serving index.html: {str(e)}")
        print(traceback.format_exc())
        return str(e), 500

@app.route('/inventory.js')
def inventory_js():
    try:
        return send_file('inventory.js')
    except Exception as e:
        print(f"Error serving inventory.js: {str(e)}")
        return str(e), 500

# 数据库连接
def get_db():
    db = sqlite3.connect('inventory.db')
    db.row_factory = sqlite3.Row
    return db

# 初始化数据库
def init_db():
    db = get_db()
    cursor = db.cursor()
    
    # 检查数据库是否已经初始化
    cursor.execute(''' SELECT name FROM sqlite_master 
                      WHERE type='table' AND name IN ('bins', 'items', 'inventory', 'input_history') ''')
    existing_tables = cursor.fetchall()
    existing_table_names = [row[0] for row in existing_tables]
    
    if len(existing_tables) == 4:
        print("数据库已存在且包含所有必要的表，跳过初始化")
        return
    
    print("开始初始化数据库...")
    
    # 创建缺失的表
    if 'bins' not in existing_table_names:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bins (
                bin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_code TEXT UNIQUE NOT NULL
            )
        ''')
    
    if 'items' not in existing_table_names:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT UNIQUE NOT NULL
            )
        ''')
    
    if 'inventory' not in existing_table_names:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                box_count INTEGER NOT NULL,
                pieces_per_box INTEGER NOT NULL,
                total_pieces INTEGER NOT NULL,
                FOREIGN KEY (bin_id) REFERENCES bins (bin_id),
                FOREIGN KEY (item_id) REFERENCES items (item_id)
            )
        ''')
    
    if 'input_history' not in existing_table_names:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS input_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_code TEXT NOT NULL,
                item_code TEXT NOT NULL,
                box_count INTEGER NOT NULL,
                pieces_per_box INTEGER NOT NULL,
                total_pieces INTEGER NOT NULL,
                input_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    # 只有在相应的表不存在时才导入初始数据
    if 'bins' not in existing_table_names:
        print("导入库位数据...")
        with open('BIN.csv', 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            next(csv_reader)  # 跳过标题行
            bin_data = [(row[0],) for row in csv_reader]
            print(f"从CSV读取到 {len(bin_data)} 个库位")
            cursor.executemany('INSERT INTO bins (bin_code) VALUES (?)', bin_data)
    
    if 'items' not in existing_table_names:
        print("导入商品数据...")
        try:
            encodings = ['utf-8', 'gbk', 'latin-1', 'iso-8859-1', 'cp1252']
            content = None
            
            for encoding in encodings:
                try:
                    with open('Item.CSV', 'r', encoding=encoding) as f:
                        content = f.read()
                        break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise Exception("无法读取Item.CSV文件，请检查文件编码")
            
            # 手动处理CSV内容
            lines = content.split('\n')
            items = set()  # 使用集合去重
            for line in lines[1:]:  # 跳过标题行
                if ',' in line:
                    item_code = line.split(',')[0].strip().strip('"')  # 移除引号
                    if item_code and not item_code.startswith('"Item No"'):
                        items.add(item_code)
            
            # 插入数据
            items = [(item,) for item in items]  # 转换回元组列表
            print(f"从CSV读取到 {len(items)} 个商品")
            cursor.executemany('INSERT INTO items (item_code) VALUES (?)', items)
            
        except Exception as e:
            print(f"导入商品数据时出错: {e}")
            raise
    
    db.commit()
    print("数据库初始化完成")

# 导入CSV数据
def import_data():
    db = get_db()
    cursor = db.cursor()
    
    # 导入库位数据
    print("开始导入库位数据...")
    with open('BIN.csv', 'r', encoding='utf-8') as f:
        csv_reader = csv.reader(f)
        next(csv_reader)  # 跳过标题行
        bin_data = [(row[0],) for row in csv_reader]
        print(f"从CSV读取到 {len(bin_data)} 个库位")
        print("示例库位:", bin_data[:5])  # 打印前5个库位
        cursor.executemany('INSERT INTO bins (bin_code) VALUES (?)', 
                          bin_data)
        print("库位数据导入完成")
    
    # 导入商品数据
    print("开始导入商品数据...")
    try:
        encodings = ['utf-8', 'gbk', 'latin-1', 'iso-8859-1', 'cp1252']
        content = None
        
        for encoding in encodings:
            try:
                with open('Item.CSV', 'r', encoding=encoding) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise Exception("无法读取Item.CSV文件，请检查文件编码")
        
        # 手动处理CSV内容
        lines = content.split('\n')
        print(f"从CSV读取到 {len(lines)} 行数据")
        print("前几行数据:", lines[:5])  # 打印前5行
        items = set()  # 使用集合去重
        for line in lines[1:]:  # 跳过标题行
            if ',' in line:
                item_code = line.split(',')[0].strip().strip('"')  # 移除引号
                if item_code and not item_code.startswith('"Item No"'):
                    # 规范化商品编号格式
                    item_code = item_code.strip()
                    items.add(item_code)
                    print(f"添加商品: {item_code}")  # 打印每个添加的商品
        
        # 测试数据
        test_items = ['A3422/H GREY', 'A3422/H/GREY']
        for test_item in test_items:
            items.add(test_item)
            print(f"添加测试商品: {test_item}")
        
        # 插入数据
        items = [(item,) for item in items]  # 转换回元组列表
        print(f"处理后的商品数: {len(items)}")
        print("示例商品:", items[:5])  # 打印前5个商品
        cursor.executemany('INSERT INTO items (item_code) VALUES (?)', items)
        print(f"成功导入 {len(items)} 个商品")
        
        # 验证数据是否正确导入
        cursor.execute('SELECT COUNT(*) FROM bins')
        bin_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM items')
        item_count = cursor.fetchone()[0]
        print(f"数据库中的库位数: {bin_count}")
        print(f"数据库中的商品数: {item_count}")
        
        # 检查商品数据的格式
        cursor.execute('SELECT item_code FROM items LIMIT 5')
        sample_items = cursor.fetchall()
        print("商品编号示例:", [row['item_code'] for row in sample_items])
        
        # 检查商品查询是否正常工作
        test_item = 'A3422/H GREY'  # 使用一个实际的商品编号
        cursor.execute('SELECT * FROM items WHERE item_code = ?', (test_item,))
        test_result = cursor.fetchone()
        print(f"测试查询商品 '{test_item}' 结果:", test_result)
        
        # 打印一些示例数据
        cursor.execute('SELECT bin_code FROM bins LIMIT 5')
        print("数据库中的库位示例:", [row[0] for row in cursor.fetchall()])
        cursor.execute('SELECT item_code FROM items LIMIT 5')
        print("数据库中的商品示例:", [row[0] for row in cursor.fetchall()])
    
    except Exception as e:
        print(f"导入商品数据时出错: {str(e)}")
        raise
    
    db.commit()

@app.route('/api/bins', methods=['GET'])
def get_bins():
    search = request.args.get('search', '')
    print(f"Searching bins with term: {search}")
    db = get_db()
    cursor = db.cursor()
    search_pattern = f'%{search}%'
    start_pattern = f'{search}%'
    print(f"Search patterns: {search_pattern}, {start_pattern}")
    cursor.execute('''
        SELECT * FROM bins 
        WHERE bin_code LIKE ? 
        ORDER BY 
            CASE 
                WHEN bin_code LIKE ? THEN 1
                ELSE 2
            END,
            bin_code
        LIMIT 10
    ''', (search_pattern, start_pattern))
    bins = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(bins)} bins")
    print("Results:", bins)
    return jsonify(bins)

@app.route('/api/items', methods=['GET'])
def get_items():
    search = request.args.get('search', '')
    print(f"Searching items with term: {search}")
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT * FROM items 
        WHERE item_code LIKE ? 
        ORDER BY 
            CASE 
                WHEN item_code LIKE ? THEN 1
                ELSE 2
            END,
            item_code
        LIMIT 10
    ''', (f'%{search}%', f'{search}%'))
    items = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(items)} items")
    return jsonify(items)

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.json
    print("收到的数据:", data)
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 先检查 bin_id 和 item_id 是否存在
        cursor.execute('SELECT bin_id FROM bins WHERE bin_code = ?', (data['bin_code'],))
        bin_result = cursor.fetchone()
        if not bin_result:
            return jsonify({'error': '库位不存在'}), 400
        bin_id = bin_result['bin_id']

        cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (data['item_code'],))
        item_result = cursor.fetchone()
        if not item_result:
            return jsonify({'error': '商品不存在'}), 400
        item_id = item_result['item_id']

        # 计算总件数
        box_count = int(data['box_count'])
        pieces_per_box = int(data['pieces_per_box'])
        total_pieces = box_count * pieces_per_box

        cursor.execute('''
            INSERT INTO inventory (bin_id, item_id, box_count, pieces_per_box, total_pieces)
            VALUES (?, ?, ?, ?, ?)
        ''', (bin_id, item_id, box_count, pieces_per_box, total_pieces))
        
        db.commit()
        print("库存记录添加成功")
        
        # 添加日志记录
        cursor.execute('''
            INSERT INTO input_history (bin_code, item_code, box_count, pieces_per_box, total_pieces)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['bin_code'],
            data['item_code'],
            data['box_count'],
            data['pieces_per_box'],
            data['box_count'] * data['pieces_per_box']
        ))
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"添加库存记录时出错: {str(e)}")
        db.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/item/<item_id>', methods=['GET'])
def get_item_inventory(item_id):
    db = get_db()
    cursor = db.cursor()
    
    item_id = item_id.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    
    # 先检查商品是否存在
    cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (item_id,))
    item_result = cursor.fetchone()
    if not item_result:
        return jsonify({
            'error': '商品不存在',
            'error_en': 'Item does not exist'
        }), 404
    
    cursor.execute('''
        SELECT 
            i.item_code,
            SUM(inv.total_pieces) as total_pieces,
            SUM(inv.box_count) as total_boxes,
            GROUP_CONCAT(inv.box_count || 'x' || inv.pieces_per_box) as box_details
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        WHERE i.item_code = ?
        GROUP BY i.item_code
    ''', (item_id,))
    
    result = cursor.fetchone()
    if not result or result['total_pieces'] is None:
        return jsonify({
            'item_code': item_id,
            'total': 0,
            'total_boxes': 0,
            'box_details': []
        })
    
    return jsonify({
        'item_code': result['item_code'],
        'total': result['total_pieces'],
        'total_boxes': result['total_boxes'],
        'box_details': result['box_details'].split(',') if result['box_details'] else []
    })

@app.route('/api/inventory/bin/<bin_id>', methods=['GET'])
def get_bin_inventory(bin_id):
    db = get_db()
    cursor = db.cursor()
    
    # 先通过库位编号获取库位ID
    cursor.execute('SELECT bin_id FROM bins WHERE bin_code = ?', (bin_id,))
    bin_result = cursor.fetchone()
    
    if not bin_result:
        return jsonify({'error': '库位不存在', 'inventory': []}), 404
    
    # 先获取每个商品的总数和合并后的箱规
    cursor.execute('''
        WITH merged_inventory AS (
            SELECT 
                i.item_code,
                inv.pieces_per_box,
                SUM(inv.box_count) as merged_box_count,
                SUM(inv.total_pieces) as pieces_for_box_size
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.bin_id = ?
            GROUP BY i.item_code, inv.pieces_per_box
        ),
        total_by_item AS (
            SELECT
                item_code,
                SUM(pieces_for_box_size) as total_pieces
            FROM merged_inventory
            GROUP BY item_code
        )
        SELECT 
            m.item_code,
            t.total_pieces,
            GROUP_CONCAT(m.merged_box_count || 'x' || m.pieces_per_box) as box_details
        FROM merged_inventory m
        JOIN total_by_item t ON m.item_code = t.item_code
        GROUP BY m.item_code
        ORDER BY m.item_code
    ''', (bin_result['bin_id'],))
    
    inventory = []
    for row in cursor.fetchall():
        item_info = {
            'item_code': row['item_code'],
            'total_pieces': row['total_pieces'],
            'box_details': []
        }
        
        # 解析箱规细节
        if row['box_details']:
            details = row['box_details'].split(',')
            for detail in details:
                box_count, pieces = detail.split('x')
                item_info['box_details'].append({
                    'box_count': int(box_count),
                    'pieces_per_box': int(pieces)
                })
        
        inventory.append(item_info)
    
    return jsonify(inventory)

@app.route('/api/inventory/locations/<item_id>', methods=['GET'])
def get_item_locations(item_id):
    db = get_db()
    cursor = db.cursor()
    
    item_id = item_id.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    print(f"查询商品库位，商品编号: {item_id}")
    
    cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (item_id,))
    item_result = cursor.fetchone()
    
    if not item_result:
        return jsonify({'error': '商品不存在', 'locations': []}), 404
    
    cursor.execute('''
        WITH merged_inventory AS (
            SELECT 
                b.bin_code,
                inv.pieces_per_box,
                SUM(inv.box_count) as merged_box_count,
                SUM(inv.total_pieces) as pieces_for_box_size
            FROM inventory inv
            JOIN bins b ON inv.bin_id = b.bin_id
            WHERE inv.item_id = ?
            GROUP BY b.bin_code, inv.pieces_per_box
        ),
        total_by_bin AS (
            SELECT
                bin_code,
                SUM(pieces_for_box_size) as total_pieces
            FROM merged_inventory
            GROUP BY bin_code
        )
        SELECT 
            m.bin_code,
            t.total_pieces,
            GROUP_CONCAT(m.merged_box_count || 'x' || m.pieces_per_box) as box_details
        FROM merged_inventory m
        JOIN total_by_bin t ON m.bin_code = t.bin_code
        GROUP BY m.bin_code
        ORDER BY m.bin_code
    ''', (item_result['item_id'],))
    
    locations = []
    for row in cursor.fetchall():
        location_info = {
            'bin_code': row['bin_code'],
            'total_pieces': row['total_pieces'],
            'box_details': []
        }
        
        if row['box_details']:
            details = row['box_details'].split(',')
            for detail in details:
                box_count, pieces = detail.split('x')
                location_info['box_details'].append({
                    'box_count': int(box_count),
                    'pieces_per_box': int(pieces)
                })
        
        locations.append(location_info)
    
    return jsonify(locations)

@app.route('/api/export/items', methods=['GET'])
def export_items():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        WITH merged_locations AS (
            SELECT 
                i.item_code,
                b.bin_code,
                SUM(inv.total_pieces) as bin_total,
                SUM(inv.box_count) as bin_boxes
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            JOIN bins b ON inv.bin_id = b.bin_id
            GROUP BY i.item_code, b.bin_code
        )
        SELECT 
            item_code,
            SUM(bin_total) as total_quantity,
            SUM(bin_boxes) as total_boxes,
            GROUP_CONCAT(DISTINCT bin_code) as bin_locations
        FROM merged_locations
        GROUP BY item_code
        ORDER BY item_code
    ''')
    
    items_data = cursor.fetchall()
    
    # 创建DataFrame，添加总箱数列
    df = pd.DataFrame(items_data, columns=['Item Code', 'Total Quantity', 'Total Boxes', 'Bin Locations'])
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Items Inventory', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Items Inventory']
        
        # 设置列宽
        worksheet.set_column('A:A', 20)  # Item Code
        worksheet.set_column('B:B', 15)  # Total Quantity
        worksheet.set_column('C:C', 12)  # Total Boxes
        worksheet.set_column('D:D', 40)  # Bin Locations
        
        # 定义格式
        item_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2962ff'  # 蓝色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        bin_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#e67e22'  # 橙色
        })
        
        # 应用格式到整列
        worksheet.set_column('A:A', 20, item_format)   # Item Code
        worksheet.set_column('B:B', 15, number_format) # Total Quantity
        worksheet.set_column('C:C', 12, number_format) # Total Boxes
        worksheet.set_column('D:D', 40, bin_format)    # Bin Locations
        
        # 设置标题行格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa'
        })
        worksheet.set_row(0, None, header_format)
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='items_inventory.xlsx'
    )

@app.route('/api/export/bins', methods=['GET'])
def export_bins():
    db = get_db()
    cursor = db.cursor()
    
    # 查询所有库位的库存信息，调整列顺序
    cursor.execute('''
        SELECT 
            b.bin_code,
            i.item_code,
            inv.box_count,           -- 调换顺序
            inv.pieces_per_box,      -- 调换顺序
            SUM(inv.total_pieces) as total_pieces
        FROM bins b
        LEFT JOIN inventory inv ON b.bin_id = inv.bin_id
        LEFT JOIN items i ON inv.item_id = i.item_id
        GROUP BY b.bin_code, i.item_code, inv.pieces_per_box, inv.box_count
        ORDER BY b.bin_code, i.item_code, inv.pieces_per_box
    ''')
    
    bins_data = cursor.fetchall()
    
    # 创建DataFrame，调整列顺序
    df = pd.DataFrame(bins_data, columns=['Bin Location', 'Item Code', 'Box Count', 'Pieces per Box', 'Total Pieces'])
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Bins Inventory', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Bins Inventory']
        
        # 设置列宽
        worksheet.set_column('A:A', 15)  # Bin Location
        worksheet.set_column('B:B', 20)  # Item Code
        worksheet.set_column('C:E', 12)  # Box Count, Pieces per Box, Total Pieces
        
        # 定义格式
        bin_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#e67e22'  # 橙色
        })
        
        item_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2962ff'  # 蓝色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 应用格式到整列
        worksheet.set_column('A:A', 15, bin_format)    # Bin Location
        worksheet.set_column('B:B', 20, item_format)   # Item Code
        worksheet.set_column('C:E', 12, number_format) # Box Count, Pieces per Box, Total Pieces
        
        # 合并相同库位的单元格
        current_bin = None
        start_row = 1  # 从第二行开始（跳过标题行）
        
        for row in range(1, len(df) + 1):
            bin_loc = df.iloc[row-1]['Bin Location'] if row <= len(df) else None
            
            if current_bin != bin_loc:
                if current_bin is not None and row - start_row > 1:
                    # 合并前一个库位的单元格
                    worksheet.merge_range(f'A{start_row+1}:A{row}', current_bin, bin_format)
                current_bin = bin_loc
                start_row = row
        
        # 处理最后一组
        if start_row < len(df) and row - start_row > 0:
            worksheet.merge_range(f'A{start_row+1}:A{len(df)+1}', current_bin, bin_format)
        
        # 设置标题行格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa'
        })
        worksheet.set_row(0, None, header_format)
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='bins_inventory.xlsx'
    )

@app.route('/api/logs', methods=['GET'])
def get_logs():
    db = get_db()
    cursor = db.cursor()
    
    # 获取所有记录
    cursor.execute('''
        SELECT 
            bin_code,
            item_code,
            box_count,
            pieces_per_box,
            total_pieces,
            input_time
        FROM input_history
        ORDER BY input_time DESC
    ''')
    
    logs = []
    for row in cursor.fetchall():
        log_entry = {
            'bin_code': row['bin_code'],
            'item_code': row['item_code'],
            'box_count': row['box_count'],
            'pieces_per_box': row['pieces_per_box'],
            'total_pieces': row['total_pieces'],
            'timestamp': row['input_time']
        }
        logs.append(log_entry)
    
    return jsonify(logs)

@app.route('/api/inventory/input', methods=['POST'])
def input_inventory():
    try:
        data = request.json
        db = get_db()
        cursor = db.cursor()
        
        # 获取库位ID
        cursor.execute('SELECT bin_id FROM bins WHERE bin_code = ?', (data['bin_code'],))
        bin_result = cursor.fetchone()
        if not bin_result:
            return jsonify({'error': '库位不存在'}), 404
        
        # 获取商品ID
        cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (data['item_code'],))
        item_result = cursor.fetchone()
        if not item_result:
            return jsonify({'error': '商品不存在'}), 404
        
        # 计算总件数
        total_pieces = data['box_count'] * data['pieces_per_box']
        
        # 插入库存记录
        cursor.execute('''
            INSERT INTO inventory (bin_id, item_id, box_count, pieces_per_box, total_pieces)
            VALUES (?, ?, ?, ?, ?)
        ''', (bin_result['bin_id'], item_result['item_id'], 
              data['box_count'], data['pieces_per_box'], total_pieces))
        
        # 记录输入历史
        cursor.execute('''
            INSERT INTO input_history (bin_code, item_code, box_count, pieces_per_box, total_pieces)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['bin_code'], data['item_code'], 
              data['box_count'], data['pieces_per_box'], total_pieces))
        
        db.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error in input_inventory: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting server...")
    print("Current working directory:", os.getcwd())
    print("Checking for required files:")
    for file in ['index.html', 'inventory.js', 'schema.sql', 'BIN.csv', 'Item.CSV']:
        if os.path.exists(file):
            print(f"  {file}: Found")
        else:
            print(f"  {file}: Missing!")
    
    try:
        init_db()
        print("Database initialized successfully")
        app.run(debug=True, port=5001)
    except Exception as e:
        print("Error starting server:", str(e))
        print(traceback.format_exc()) 