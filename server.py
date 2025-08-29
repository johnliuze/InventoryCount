from flask import Flask, request, jsonify, send_file
import sqlite3
import csv
from flask_cors import CORS
import os
import traceback
import pandas as pd
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
CORS(app)

# 获取环境变量
is_production = os.getenv('RAILWAY_ENVIRONMENT') == 'production'
port = int(os.getenv('PORT', '5001'))  # 本地开发使用5001，生产环境使用环境变量
host = '0.0.0.0' if is_production else 'localhost'

# gunicorn 配置会从环境变量获取

# 错误处理
@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Not found", error_en="Resource not found"), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Server error", error_en="Internal server error"), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Origin', '*')
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
    db_path = os.path.join(os.path.dirname(__file__), 'inventory.db')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

# 确保数据库目录存在
def ensure_db_directory():
    db_dir = os.path.dirname(os.path.join(os.path.dirname(__file__), 'inventory.db'))
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

# 初始化数据库
def init_db():
    ensure_db_directory()
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 检查数据库是否已经初始化
        cursor.execute(''' SELECT name FROM sqlite_master 
                        WHERE type='table' AND name IN ('bins', 'items', 'inventory', 'input_history') ''')
        existing_tables = cursor.fetchall()
        if len(existing_tables) == 4:
            print("数据库已存在且包含所有必要的表")
            return
        
        print("开始初始化数据库...")
        
        # 创建缺失的表
        if 'bins' not in [row[0] for row in existing_tables]:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bins (
                    bin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bin_code TEXT UNIQUE NOT NULL
                )
            ''')
        
        if 'items' not in [row[0] for row in existing_tables]:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT UNIQUE NOT NULL
                )
            ''')
        
        if 'inventory' not in [row[0] for row in existing_tables]:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bin_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    customer_po TEXT,
                    BT TEXT,
                    box_count INTEGER NOT NULL,
                    pieces_per_box INTEGER NOT NULL,
                    total_pieces INTEGER NOT NULL,
                    FOREIGN KEY (bin_id) REFERENCES bins (bin_id),
                    FOREIGN KEY (item_id) REFERENCES items (item_id)
                )
            ''')
        else:
            # 检查是否需要添加customer_po字段
            cursor.execute("PRAGMA table_info(inventory)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'customer_po' not in columns:
                print("为inventory表添加customer_po字段...")
                cursor.execute('ALTER TABLE inventory ADD COLUMN customer_po TEXT')
            # 检查是否需要添加BT字段
            if 'BT' not in columns:
                print("为inventory表添加BT字段...")
                cursor.execute('ALTER TABLE inventory ADD COLUMN BT TEXT')
        
        if 'input_history' not in [row[0] for row in existing_tables]:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS input_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bin_code TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    customer_po TEXT,
                    BT TEXT,
                    box_count INTEGER NOT NULL,
                    pieces_per_box INTEGER NOT NULL,
                    total_pieces INTEGER NOT NULL,
                    input_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            # 检查是否需要添加customer_po字段
            cursor.execute("PRAGMA table_info(input_history)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'customer_po' not in columns:
                print("为input_history表添加customer_po字段...")
                cursor.execute('ALTER TABLE input_history ADD COLUMN customer_po TEXT')
            # 检查是否需要添加BT字段
            if 'BT' not in columns:
                print("为input_history表添加BT字段...")
                cursor.execute('ALTER TABLE input_history ADD COLUMN BT TEXT')
        
        # 只有在相应的表不存在时才导入初始数据
        if 'bins' not in [row[0] for row in existing_tables]:
            print("导入库位数据...")
            with open('BIN.csv', 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                next(csv_reader)  # 跳过标题行
                bin_data = [(row[0],) for row in csv_reader]
                print(f"从CSV读取到 {len(bin_data)} 个库位")
                cursor.executemany('INSERT INTO bins (bin_code) VALUES (?)', bin_data)
        '''
        #No need since no need to check item anymore
        if 'items' not in [row[0] for row in existing_tables]:
            print("导入商品数据...")
            try:
                encodings = ['utf-8', 'gbk', 'latin-1', 'iso-8859-1', 'cp1252']
                items = set()  # 使用集合去重
                duplicates = {}  # 记录重复的商品及其行号
                invalid_items = []  # 记录不合格的商品及原因
                empty_lines = []  # 记录空行的行号
                total_lines = 0  # 总行数
                processed_codes = {}  # 用于检测重复，存储商品编码及其首次出现的行号
                successful_encoding = None
                
                for encoding in encodings:
                    try:
                        with open('Item.CSV', 'r', encoding=encoding) as f:
                            content = f.read()
                            successful_encoding = encoding
                            break
                    except UnicodeDecodeError:
                        continue
                
                if not successful_encoding:
                    raise Exception("无法读取Item.CSV文件，请检查文件编码和格式")
                
                # 直接使用已读取的内容
                csv_reader = csv.reader(content.splitlines(), 
                    quoting=csv.QUOTE_ALL,
                    skipinitialspace=True,
                    strict=True
                )
                
                # 跳过标题行
                next(csv_reader)
                
                # 读取每一行
                for row in csv_reader:
                    total_lines += 1
                    try:
                        # 检查空行
                        if not row or len(row) == 0:
                            empty_lines.append(total_lines)
                            continue
                        
                        # 检查第一列是否为空
                        if len(row[0].strip()) == 0:
                            invalid_items.append((total_lines, "", "空商品编码"))
                            continue
                        
                        if row and len(row) > 0:
                            item_code = row[0].strip()
                            normalized_code = item_code.upper().strip()
                            
                            # 检查是否以 "Item" 开头
                            if item_code.lower().startswith('item'):
                                invalid_items.append((total_lines, item_code, "以'Item'开头"))
                                continue
                            
                            # 检查重复
                            if normalized_code in processed_codes:
                                if normalized_code not in duplicates:
                                    duplicates[normalized_code] = [processed_codes[normalized_code]]
                                duplicates[normalized_code].append(total_lines)
                            else:
                                processed_codes[normalized_code] = total_lines
                                items.add(normalized_code)
                    except Exception as e:
                        invalid_items.append((total_lines, str(row), f"处理错误: {str(e)}"))
                
                print(f"从CSV读取到 {len(items)} 个商品")
                print(f"\n处理统计:")
                print(f"总行数: {total_lines}")
                print(f"有效商品数: {len(items)}")
                print(f"重复商品数: {len(duplicates)} (共 {sum(len(lines) for lines in duplicates.values())} 行)")
                print(f"不合格商品数: {len(invalid_items)}")
                print(f"空行数: {len(empty_lines)}")
                
                if duplicates:
                    print("\n重复的商品编码:")
                    for code in sorted(duplicates.keys()):
                        print(f"- {code} (出现在第 {', '.join(map(str, duplicates[code]))} 行)")
                
                if invalid_items:
                    print("\n不合格的商品:")
                    for line, code, reason in sorted(invalid_items):
                        print(f"第 {line} 行: {code} - {reason}")
                
                if empty_lines:
                    print("\n空行:")
                    print(f"第 {', '.join(map(str, empty_lines))} 行")
                
                # 插入数据
                items = [(item,) for item in items]
                cursor.executemany('INSERT INTO items (item_code) VALUES (?)', items)
                
            except Exception as e:
                print(f"导入商品数据时出错: {e}")
                raise
        '''
        db.commit()
        print("数据库初始化完成")
        
    except Exception as e:
        print(f"初始化数据库时出错: {str(e)}")
        print(traceback.format_exc())
        raise
    finally:
        db.close()

# 在应用启动时初始化数据库
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"启动时初始化数据库失败: {str(e)}")

@app.route('/api/bins', methods=['GET'])
def get_bins():
    search = request.args.get('search', '')
    db = get_db()
    cursor = db.cursor()
    search_pattern = f'%{search}%'
    start_pattern = f'{search}%'
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
    return jsonify(bins)

@app.route('/api/items', methods=['GET'])
def get_items():
    search = request.args.get('search', '')
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
    return jsonify(items)

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 先检查 bin_id 是否存在
        cursor.execute('SELECT bin_id FROM bins WHERE bin_code = ?', (data['bin_code'],))
        bin_result = cursor.fetchone()
        if not bin_result:
            return jsonify({'error': '库位不存在', 'error_en': 'Bin location does not exist'}), 400
        bin_id = bin_result['bin_id']

        # 检查商品是否存在，如果不存在则自动添加
        cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (data['item_code'],))
        item_result = cursor.fetchone()
        if not item_result:
            # 商品不存在，自动添加到items表
            cursor.execute('INSERT INTO items (item_code) VALUES (?)', (data['item_code'],))
            item_id = cursor.lastrowid
        else:
            item_id = item_result['item_id']

        # 计算总件数
        box_count = int(data['box_count'])
        pieces_per_box = int(data['pieces_per_box'])
        total_pieces = box_count * pieces_per_box

        # 获取客户订单号和BT，如果不存在则为None
        customer_po = data.get('customer_po', None)
        BT = data.get('BT', None)
        
        # 插入库存记录
        cursor.execute('''
            INSERT INTO inventory (bin_id, item_id, customer_po, BT, box_count, pieces_per_box, total_pieces)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (bin_id, item_id, customer_po, BT, box_count, pieces_per_box, total_pieces))
        
        # 记录输入历史
        cursor.execute('''
            INSERT INTO input_history (bin_code, item_code, customer_po, BT, box_count, pieces_per_box, total_pieces)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['bin_code'], data['item_code'], customer_po, BT, box_count, pieces_per_box, total_pieces))
        
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
        # 商品不存在，返回空结果
        return jsonify({
            'item_code': item_id,
            'total': 0,
            'total_boxes': 0,
            'box_details': []
        })
    
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
        return jsonify({'error': '库位不存在', 'error_en': 'Bin location does not exist', 'inventory': []}), 404
    
    # 按商品分组，保持PO和BT的对应关系
    cursor.execute('''
        WITH item_inventory AS (
            SELECT 
                i.item_code,
                inv.customer_po,
                inv.BT,
                inv.pieces_per_box,
                SUM(inv.box_count) as box_count,
                SUM(inv.total_pieces) as total_pieces
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.bin_id = ?
            GROUP BY i.item_code, inv.customer_po, inv.BT, inv.pieces_per_box
        ),
        item_summary AS (
            SELECT
                item_code,
                customer_po,
                BT,
                SUM(total_pieces) as po_bt_total_pieces,
                GROUP_CONCAT(box_count || 'x' || pieces_per_box) as po_bt_box_details
            FROM item_inventory
            GROUP BY item_code, customer_po, BT
        )
        SELECT 
            item_code,
            SUM(po_bt_total_pieces) as total_pieces,
            GROUP_CONCAT(
                CASE 
                    WHEN customer_po IS NOT NULL AND BT IS NOT NULL THEN customer_po || '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                    WHEN customer_po IS NOT NULL THEN customer_po || '||' || po_bt_total_pieces || '|' || po_bt_box_details
                    WHEN BT IS NOT NULL THEN '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                    ELSE '||' || po_bt_total_pieces || '|' || po_bt_box_details
                END
            ) as po_bt_details
        FROM item_summary
        GROUP BY item_code
        ORDER BY item_code
    ''', (bin_result['bin_id'],))
    
    inventory = []
    for row in cursor.fetchall():
        item_info = {
            'item_code': row['item_code'],
            'total_pieces': row['total_pieces'],
            'total_boxes': 0,  # 将在后面计算
            'po_bt_groups': [],
            'box_details': []
        }
        
        # 解析PO-BT对应关系
        if row['po_bt_details']:
            details = row['po_bt_details'].split(',')
            for detail in details:
                parts = detail.split('|')
                if len(parts) >= 4:
                    customer_po = parts[0] if parts[0] else None
                    BT = parts[1] if parts[1] else None
                    pieces = int(parts[2]) if parts[2] else 0
                    box_details_str = parts[3] if parts[3] else ''
                    
                    # 解析这个PO-BT组合的箱规
                    group_box_details = []
                    if box_details_str:
                        box_details_list = box_details_str.split(',') if ',' in box_details_str else [box_details_str]
                        for box_detail in box_details_list:
                            if 'x' in box_detail:
                                box_count, pieces_per_box = box_detail.split('x')
                                group_box_details.append({
                    'box_count': int(box_count),
                                    'pieces_per_box': int(pieces_per_box)
                                })
                    
                    item_info['po_bt_groups'].append({
                        'customer_po': customer_po,
                        'BT': BT,
                        'pieces': pieces,
                        'box_details': group_box_details
                    })
        
        # 合并所有箱规到总的box_details中，同时计算总箱数
        all_box_details = {}
        total_boxes = 0
        for group in item_info['po_bt_groups']:
            for box_detail in group['box_details']:
                key = f"{box_detail['pieces_per_box']}"
                if key not in all_box_details:
                    all_box_details[key] = {'box_count': 0, 'pieces_per_box': box_detail['pieces_per_box']}
                all_box_details[key]['box_count'] += box_detail['box_count']
                total_boxes += box_detail['box_count']
        
        item_info['box_details'] = list(all_box_details.values())
        item_info['total_boxes'] = total_boxes
        inventory.append(item_info)
    
    return jsonify(inventory)

@app.route('/api/inventory/locations/<item_id>', methods=['GET'])
def get_item_locations(item_id):
    db = get_db()
    cursor = db.cursor()
    
    item_id = item_id.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    
    cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (item_id,))
    item_result = cursor.fetchone()
    
    if not item_result:
        # 商品不存在，返回空结果
        return jsonify({'locations': []})
    
    # 按库位分组，保持PO和BT的对应关系
    cursor.execute('''
        WITH location_inventory AS (
            SELECT 
                b.bin_code,
                inv.customer_po,
                inv.BT,
                inv.pieces_per_box,
                SUM(inv.box_count) as box_count,
                SUM(inv.total_pieces) as total_pieces
            FROM inventory inv
            JOIN bins b ON inv.bin_id = b.bin_id
            WHERE inv.item_id = ?
            GROUP BY b.bin_code, inv.customer_po, inv.BT, inv.pieces_per_box
        ),
        location_summary AS (
            SELECT
                bin_code,
                customer_po,
                BT,
                SUM(total_pieces) as po_bt_total_pieces,
                GROUP_CONCAT(box_count || 'x' || pieces_per_box) as po_bt_box_details
            FROM location_inventory
            GROUP BY bin_code, customer_po, BT
        )
        SELECT 
            bin_code,
            SUM(po_bt_total_pieces) as total_pieces,
            GROUP_CONCAT(
                CASE 
                    WHEN customer_po IS NOT NULL AND BT IS NOT NULL THEN customer_po || '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                    WHEN customer_po IS NOT NULL THEN customer_po || '||' || po_bt_total_pieces || '|' || po_bt_box_details
                    WHEN BT IS NOT NULL THEN '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                    ELSE '||' || po_bt_total_pieces || '|' || po_bt_box_details
                END
            ) as po_bt_details
        FROM location_summary
        GROUP BY bin_code
        ORDER BY bin_code
    ''', (item_result['item_id'],))
    
    locations = []
    for row in cursor.fetchall():
        location_info = {
            'bin_code': row['bin_code'],
            'total_pieces': row['total_pieces'],
            'total_boxes': 0,  # 将在后面计算
            'po_bt_groups': [],
            'box_details': []
        }
        
        # 解析PO-BT对应关系
        if row['po_bt_details']:
            details = row['po_bt_details'].split(',')
            for detail in details:
                parts = detail.split('|')
                if len(parts) >= 4:
                    customer_po = parts[0] if parts[0] else None
                    BT = parts[1] if parts[1] else None
                    pieces = int(parts[2]) if parts[2] else 0
                    box_details_str = parts[3] if parts[3] else ''
                    
                    # 解析这个PO-BT组合的箱规
                    group_box_details = []
                    if box_details_str:
                        box_details_list = box_details_str.split(',') if ',' in box_details_str else [box_details_str]
                        for box_detail in box_details_list:
                            if 'x' in box_detail:
                                box_count, pieces_per_box = box_detail.split('x')
                                group_box_details.append({
                    'box_count': int(box_count),
                                    'pieces_per_box': int(pieces_per_box)
                                })
                    
                    location_info['po_bt_groups'].append({
                        'customer_po': customer_po,
                        'BT': BT,
                        'pieces': pieces,
                        'box_details': group_box_details
                    })
        
        # 合并所有箱规到总的box_details中，同时计算总箱数
        all_box_details = {}
        total_boxes = 0
        for group in location_info['po_bt_groups']:
            for box_detail in group['box_details']:
                key = f"{box_detail['pieces_per_box']}"
                if key not in all_box_details:
                    all_box_details[key] = {'box_count': 0, 'pieces_per_box': box_detail['pieces_per_box']}
                all_box_details[key]['box_count'] += box_detail['box_count']
                total_boxes += box_detail['box_count']
        
        location_info['box_details'] = list(all_box_details.values())
        location_info['total_boxes'] = total_boxes
        locations.append(location_info)
    
    return jsonify(locations)

@app.route('/api/inventory/BT/<BT>', methods=['GET'])
def get_BT_inventory(BT):
    db = get_db()
    cursor = db.cursor()
    
    BT = BT.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    
    # 按商品分组，每个商品下按库位分组，保持PO和BT的对应关系
    cursor.execute('''
        WITH bt_inventory AS (
            SELECT 
                i.item_code,
                b.bin_code,
                inv.customer_po,
                inv.BT,
                inv.pieces_per_box,
                SUM(inv.box_count) as box_count,
                SUM(inv.total_pieces) as total_pieces
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            JOIN bins b ON inv.bin_id = b.bin_id
            WHERE inv.BT = ?
            GROUP BY i.item_code, b.bin_code, inv.customer_po, inv.BT, inv.pieces_per_box
        ),
        location_summary AS (
            SELECT
                item_code,
                bin_code,
                customer_po,
                BT,
                SUM(total_pieces) as po_bt_total_pieces,
                GROUP_CONCAT(box_count || 'x' || pieces_per_box) as po_bt_box_details
            FROM bt_inventory
            GROUP BY item_code, bin_code, customer_po, BT
        ),
        item_location_summary AS (
            SELECT 
                item_code,
                bin_code,
                SUM(po_bt_total_pieces) as total_pieces,
                GROUP_CONCAT(
                    CASE 
                        WHEN customer_po IS NOT NULL AND BT IS NOT NULL THEN customer_po || '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                        WHEN customer_po IS NOT NULL THEN customer_po || '||' || po_bt_total_pieces || '|' || po_bt_box_details
                        WHEN BT IS NOT NULL THEN '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                        ELSE '||' || po_bt_total_pieces || '|' || po_bt_box_details
                    END
                ) as po_bt_details
            FROM location_summary
            GROUP BY item_code, bin_code
        )
        SELECT 
            item_code,
            SUM(total_pieces) as item_total_pieces,
            GROUP_CONCAT(bin_code || '||' || total_pieces || '||' || po_bt_details, '|||') as location_details
        FROM item_location_summary
        GROUP BY item_code
        ORDER BY item_code
    ''', (BT,))
    
    results = cursor.fetchall()
    
    if not results:
        return jsonify({
            'BT': BT,
            'total_items': 0,
            'total_pieces': 0,
            'total_boxes': 0,
            'items': []
        })
    
    # 按商品分组整理数据
    items_list = []
    total_pieces = 0
    total_boxes = 0
    
    for row in results:
        item_info = {
            'item_code': row['item_code'],
            'total_pieces': row['item_total_pieces'],
            'total_boxes': 0,  # 将在后面计算
            'locations': []
        }
        
        # 解析location详情
        if row['location_details']:
            location_groups = row['location_details'].split('|||')
            for location_group in location_groups:
                if location_group:
                    parts = location_group.split('||')
                    if len(parts) >= 3:
                        bin_code = parts[0]
                        location_pieces = int(parts[1])
                        po_bt_details = parts[2]
                        
                        location_info = {
                            'bin_code': bin_code,
                            'total_pieces': location_pieces,
                            'total_boxes': 0,  # 将在后面计算
                            'po_bt_groups': []
                        }
                        
                        # 解析PO-BT对应关系
                        if po_bt_details:
                            details = po_bt_details.split(',')
                            for detail in details:
                                detail_parts = detail.split('|')
                                if len(detail_parts) >= 4:
                                    customer_po = detail_parts[0] if detail_parts[0] else None
                                    bt = detail_parts[1] if detail_parts[1] else None
                                    pieces = int(detail_parts[2]) if detail_parts[2] else 0
                                    box_details_str = detail_parts[3] if detail_parts[3] else ''
                                    
                                    # 解析这个PO-BT组合的箱规
                                    group_box_details = []
                                    group_total_boxes = 0
                                    if box_details_str:
                                        box_details_list = box_details_str.split(',') if ',' in box_details_str else [box_details_str]
                                        for box_detail in box_details_list:
                                            if 'x' in box_detail:
                                                box_count, pieces_per_box = box_detail.split('x')
                                                box_count = int(box_count)
                                                group_box_details.append({
                                                    'box_count': box_count,
                                                    'pieces_per_box': int(pieces_per_box)
                                                })
                                                group_total_boxes += box_count
                                    
                                    location_info['po_bt_groups'].append({
                                        'customer_po': customer_po,
                                        'BT': bt,
                                        'pieces': pieces,
                                        'total_boxes': group_total_boxes,
                                        'box_details': group_box_details
                                    })
                                    
                                    location_info['total_boxes'] += group_total_boxes
                        
                        item_info['locations'].append(location_info)
                        item_info['total_boxes'] += location_info['total_boxes']
        
        items_list.append(item_info)
        total_pieces += item_info['total_pieces']
        total_boxes += item_info['total_boxes']
    
    return jsonify({
        'BT': BT,
        'total_items': len(items_list),
        'total_pieces': total_pieces,
        'total_boxes': total_boxes,
        'items': items_list
    })

@app.route('/api/BTs', methods=['GET'])
def get_BTs():
    db = get_db()
    cursor = db.cursor()
    
    search_term = request.args.get('search', '').strip()
    
    if not search_term:
        # 如果没有搜索词，返回所有BT
        cursor.execute('''
            SELECT DISTINCT BT 
            FROM inventory 
            WHERE BT IS NOT NULL AND BT != ''
            ORDER BY BT
        ''')
    else:
        # 如果有搜索词，进行模糊搜索
        search_pattern = f'%{search_term}%'
        cursor.execute('''
            SELECT DISTINCT BT 
            FROM inventory 
            WHERE BT IS NOT NULL 
            AND BT != '' 
            AND BT LIKE ?
            ORDER BY BT
        ''', (search_pattern,))
    
    BTs = []
    for row in cursor.fetchall():
        BTs.append({
            'BT': row['BT']
        })
    
    return jsonify(BTs)

@app.route('/api/inventory/PO/<PO>', methods=['GET'])
def get_PO_inventory(PO):
    db = get_db()
    cursor = db.cursor()
    
    PO = PO.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    
    # 按商品分组，每个商品下按库位分组，保持PO和BT的对应关系
    cursor.execute('''
        WITH po_inventory AS (
            SELECT 
                i.item_code,
                b.bin_code,
                inv.customer_po,
                inv.BT,
                inv.pieces_per_box,
                SUM(inv.box_count) as box_count,
                SUM(inv.total_pieces) as total_pieces
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            JOIN bins b ON inv.bin_id = b.bin_id
            WHERE inv.customer_po = ?
            GROUP BY i.item_code, b.bin_code, inv.customer_po, inv.BT, inv.pieces_per_box
        ),
        location_summary AS (
            SELECT
                item_code,
                bin_code,
                customer_po,
                BT,
                SUM(total_pieces) as po_bt_total_pieces,
                GROUP_CONCAT(box_count || 'x' || pieces_per_box) as po_bt_box_details
            FROM po_inventory
            GROUP BY item_code, bin_code, customer_po, BT
        ),
        item_location_summary AS (
            SELECT 
                item_code,
                bin_code,
                SUM(po_bt_total_pieces) as total_pieces,
                GROUP_CONCAT(
                    CASE 
                        WHEN customer_po IS NOT NULL AND BT IS NOT NULL THEN customer_po || '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                        WHEN customer_po IS NOT NULL THEN customer_po || '||' || po_bt_total_pieces || '|' || po_bt_box_details
                        WHEN BT IS NOT NULL THEN '|' || BT || '|' || po_bt_total_pieces || '|' || po_bt_box_details
                        ELSE '||' || po_bt_total_pieces || '|' || po_bt_box_details
                    END
                ) as po_bt_details
            FROM location_summary
            GROUP BY item_code, bin_code
        )
        SELECT 
            item_code,
            SUM(total_pieces) as item_total_pieces,
            GROUP_CONCAT(bin_code || '||' || total_pieces || '||' || po_bt_details, '|||') as location_details
        FROM item_location_summary
        GROUP BY item_code
        ORDER BY item_code
    ''', (PO,))
    
    results = cursor.fetchall()
    
    if not results:
        return jsonify({
            'PO': PO,
            'total_items': 0,
            'total_pieces': 0,
            'total_boxes': 0,
            'items': []
        })
    
    # 按商品分组整理数据
    items_list = []
    total_pieces = 0
    total_boxes = 0
    
    for row in results:
        item_info = {
            'item_code': row['item_code'],
            'total_pieces': row['item_total_pieces'],
            'total_boxes': 0,  # 将在后面计算
            'locations': []
        }
        
        # 解析location详情
        if row['location_details']:
            location_groups = row['location_details'].split('|||')
            for location_group in location_groups:
                if location_group:
                    parts = location_group.split('||')
                    if len(parts) >= 3:
                        bin_code = parts[0]
                        location_pieces = int(parts[1])
                        po_bt_details = parts[2]
                        
                        location_info = {
                            'bin_code': bin_code,
                            'total_pieces': location_pieces,
                            'total_boxes': 0,  # 将在后面计算
                            'po_bt_groups': []
                        }
                        
                        # 解析PO-BT对应关系
                        if po_bt_details:
                            details = po_bt_details.split(',')
                            for detail in details:
                                detail_parts = detail.split('|')
                                if len(detail_parts) >= 4:
                                    customer_po = detail_parts[0] if detail_parts[0] else None
                                    bt = detail_parts[1] if detail_parts[1] else None
                                    pieces = int(detail_parts[2]) if detail_parts[2] else 0
                                    box_details_str = detail_parts[3] if detail_parts[3] else ''
                                    
                                    # 解析这个PO-BT组合的箱规
                                    group_box_details = []
                                    group_total_boxes = 0
                                    if box_details_str:
                                        box_details_list = box_details_str.split(',') if ',' in box_details_str else [box_details_str]
                                        for box_detail in box_details_list:
                                            if 'x' in box_detail:
                                                box_count, pieces_per_box = box_detail.split('x')
                                                box_count = int(box_count)
                                                group_box_details.append({
                                                    'box_count': box_count,
                                                    'pieces_per_box': int(pieces_per_box)
                                                })
                                                group_total_boxes += box_count
                                    
                                    location_info['po_bt_groups'].append({
                                        'customer_po': customer_po,
                                        'BT': bt,
                                        'pieces': pieces,
                                        'total_boxes': group_total_boxes,
                                        'box_details': group_box_details
                                    })
                                    
                                    location_info['total_boxes'] += group_total_boxes
                        
                        item_info['locations'].append(location_info)
                        item_info['total_boxes'] += location_info['total_boxes']
        
        items_list.append(item_info)
        total_pieces += item_info['total_pieces']
        total_boxes += item_info['total_boxes']
    
    return jsonify({
        'PO': PO,
        'total_items': len(items_list),
        'total_pieces': total_pieces,
        'total_boxes': total_boxes,
        'items': items_list
    })

@app.route('/api/POs', methods=['GET'])
def get_POs():
    db = get_db()
    cursor = db.cursor()
    
    search_term = request.args.get('search', '').strip()
    
    if not search_term:
        # 如果没有搜索词，返回所有PO
        cursor.execute('''
            SELECT DISTINCT customer_po 
            FROM inventory 
            WHERE customer_po IS NOT NULL AND customer_po != ''
            ORDER BY customer_po
        ''')
    else:
        # 如果有搜索词，进行模糊搜索
        search_pattern = f'%{search_term}%'
        cursor.execute('''
            SELECT DISTINCT customer_po 
            FROM inventory 
            WHERE customer_po IS NOT NULL 
            AND customer_po != '' 
            AND customer_po LIKE ?
            ORDER BY customer_po
        ''', (search_pattern,))
    
    POs = []
    for row in cursor.fetchall():
        POs.append({
            'PO': row['customer_po']
        })
    
    return jsonify(POs)

@app.route('/api/export/items', methods=['GET'])
def export_items():
    db = get_db()
    cursor = db.cursor()
    
    # 使用迭代器而不是一次性获取所有数据
    cursor.execute('''
        WITH merged_locations AS (
            SELECT 
                i.item_code,
                b.bin_code,
                inv.customer_po,
                inv.BT,
                SUM(inv.total_pieces) as bin_total,
                SUM(inv.box_count) as bin_boxes
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            JOIN bins b ON inv.bin_id = b.bin_id
            GROUP BY i.item_code, b.bin_code, inv.customer_po, inv.BT
        )
        SELECT 
            item_code,
            SUM(bin_total) as total_quantity,
            SUM(bin_boxes) as total_boxes,
            GROUP_CONCAT(DISTINCT bin_code) as bin_locations,
            GROUP_CONCAT(DISTINCT customer_po) as customer_po_list,
            GROUP_CONCAT(DISTINCT BT) as BT_list
        FROM merged_locations
        GROUP BY item_code
        ORDER BY item_code
    ''')
    
    # 使用生成器创建数据
    def generate_rows():
        while True:
            rows = cursor.fetchmany(1000)  # 每次获取1000行
            if not rows:
                break
            for row in rows:
                # 处理客户订单号列表，移除NULL值并去重
                customer_po_list = row['customer_po_list'] if row['customer_po_list'] else ''
                if customer_po_list:
                    # 分割、去重、过滤空值
                    customer_po_items = [po.strip() for po in customer_po_list.split(',') if po.strip() and po.strip() != 'None']
                    customer_po_items = list(set(customer_po_items))  # 去重
                    customer_po_list = ', '.join(customer_po_items)
                
                # 处理BT列表，移除NULL值并去重
                bt_list = row['BT_list'] if row['BT_list'] else ''
                if bt_list:
                    # 分割、去重、过滤空值
                    bt_items = [bt.strip() for bt in bt_list.split(',') if bt.strip() and bt.strip() != 'None']
                    bt_items = list(set(bt_items))  # 去重
                    bt_list = ', '.join(bt_items)
                
                # 创建包含处理后数据的行
                processed_row = {
                    'Item Code': row['item_code'],
                    'Total Quantity': row['total_quantity'],
                    'Total Boxes': row['total_boxes'],
                    'Bin Locations': row['bin_locations'],
                    'Customer PO': customer_po_list,
                    'BT': bt_list
                }
                yield processed_row
    
    # 创建DataFrame，使用迭代器
    df = pd.DataFrame(generate_rows(), columns=['Item Code', 'Total Quantity', 'Total Boxes', 'Bin Locations', 'Customer PO', 'BT'])
    
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
        worksheet.set_column('E:E', 20)  # Customer PO
        worksheet.set_column('F:F', 30)  # BT
        
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
        
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        
        bt_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        
        # 应用格式到整列
        worksheet.set_column('A:A', 20, item_format)   # Item Code
        worksheet.set_column('B:B', 15, number_format) # Total Quantity
        worksheet.set_column('C:C', 12, number_format) # Total Boxes
        worksheet.set_column('D:D', 40, bin_format)    # Bin Locations
        worksheet.set_column('E:E', 20, customer_po_format) # Customer PO
        worksheet.set_column('F:F', 30, bt_format)     # BT
        
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
    
    # 查询所有库位的库存信息，包含客户订单号和BT信息
    cursor.execute('''
        SELECT 
            b.bin_code,
            i.item_code,
            inv.customer_po,
            inv.BT,
            inv.box_count,
            inv.pieces_per_box,
            SUM(inv.total_pieces) as total_pieces
        FROM bins b
        LEFT JOIN inventory inv ON b.bin_id = inv.bin_id
        LEFT JOIN items i ON inv.item_id = i.item_id
        GROUP BY b.bin_code, i.item_code, inv.customer_po, inv.BT, inv.box_count, inv.pieces_per_box
        ORDER BY b.bin_code, i.item_code, inv.customer_po, inv.BT, inv.box_count, inv.pieces_per_box
    ''')
    
    bins_data = cursor.fetchall()
    
    # 创建DataFrame，包含客户订单号和BT信息
    df = pd.DataFrame(bins_data, columns=['Bin Location', 'Item Code', 'Customer PO', 'BT Number', 'Box Count', 'Pieces per Box', 'Total Pieces'])
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Bins Inventory', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Bins Inventory']
        
        # 设置列宽
        worksheet.set_column('A:A', 15)  # Bin Location
        worksheet.set_column('B:B', 20)  # Item Code
        worksheet.set_column('C:C', 15)  # Customer PO
        worksheet.set_column('D:D', 18)  # BT Number
        worksheet.set_column('E:G', 12)  # Box Count, Pieces per Box, Total Pieces
        
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
        
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        
        BT_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 应用格式到整列
        worksheet.set_column('A:A', 15, bin_format)    # Bin Location
        worksheet.set_column('B:B', 20, item_format)   # Item Code
        worksheet.set_column('C:C', 15, customer_po_format) # Customer PO
        worksheet.set_column('D:D', 18, BT_format) # BT Number
        worksheet.set_column('E:G', 12, number_format) # Box Count, Pieces per Box, Total Pieces
        
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
        download_name= f'Bins-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

@app.route('/api/logs', methods=['GET'])
def get_logs():
    db = get_db()
    cursor = db.cursor()
    
    # 检查是否有日期过滤参数
    date_filter = request.args.get('date', '').strip()
    
    if date_filter:
        # 如果有日期过滤，只返回指定日期的记录
        cursor.execute('''
            SELECT 
                bin_code,
                item_code,
                            customer_po,
                            BT,
                            box_count,
                            pieces_per_box,
                            total_pieces,
                            input_time
                        FROM input_history
                        WHERE DATE(datetime(input_time, 'localtime')) = ?
                        ORDER BY input_time DESC
                    ''', (date_filter,))
    else:
        # 否则返回所有记录
        cursor.execute('''
            SELECT 
                bin_code,
                item_code,
                customer_po,
                BT,
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
            'customer_po': row['customer_po'],
            'BT': row['BT'],
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
            return jsonify({'error': '库位不存在', 'error_en': 'Bin location does not exist'}), 404
        
        # 获取商品ID
        cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (data['item_code'],))
        item_result = cursor.fetchone()
        if not item_result:
            return jsonify({'error': '商品不存在', 'error_en': 'Item does not exist'}), 404
        
        # 计算总件数
        total_pieces = data['box_count'] * data['pieces_per_box']
        
        # 检查是否已存在相同商品、库位和箱规的记录
        cursor.execute('''
            SELECT inventory_id, total_pieces 
            FROM inventory 
            WHERE bin_id = ? AND item_id = ? AND pieces_per_box = ?
        ''', (bin_result['bin_id'], item_result['item_id'], data['pieces_per_box']))
        
        existing_record = cursor.fetchone()
        
        if existing_record:
            # 更新现有记录
            cursor.execute('''
                UPDATE inventory 
                SET box_count = box_count + ?,
                    total_pieces = total_pieces + ?
                WHERE inventory_id = ?
            ''', (data['box_count'], total_pieces, existing_record['inventory_id']))
        else:
            # 插入新记录
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

@app.route('/api/export/item-details', methods=['GET'])
def export_item_details():
    db = get_db()
    cursor = db.cursor()
    
    # 查询所有有库存的商品在各库位的详细信息
    cursor.execute('''
        WITH item_location_details AS (
            SELECT 
                i.item_code,
                b.bin_code,
                inv.customer_po,
                inv.BT,
                inv.pieces_per_box,
                inv.box_count,
                inv.total_pieces as box_total,
                FIRST_VALUE(inv.total_pieces) OVER (
                    PARTITION BY i.item_code, b.bin_code
                    ORDER BY inv.pieces_per_box DESC, inv.box_count DESC
                ) as box_total_first,
                SUM(inv.total_pieces) OVER (
                    PARTITION BY i.item_code, b.bin_code
                ) as total_pieces_in_bin,
                SUM(inv.total_pieces) OVER (
                    PARTITION BY i.item_code
                ) as total_pieces_all_bins
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            JOIN bins b ON inv.bin_id = b.bin_id
            WHERE inv.box_count > 0
        )
        SELECT DISTINCT
            ild.item_code,
            ild.bin_code,
            ild.customer_po,
            ild.BT,
            ild.pieces_per_box,
            ild.box_count,
            ild.box_total,
            ild.total_pieces_in_bin as bin_total,
            ild.total_pieces_all_bins as item_total
        FROM item_location_details ild
        ORDER BY item_code, bin_code, customer_po, pieces_per_box DESC, box_count DESC
    ''')
    
    # 使用生成器创建数据
    def generate_rows():
        current_item = None
        current_bin = None
        rows = []
        
        while True:
            row = cursor.fetchone()
            if not row:
                if rows:
                    yield rows
                break
            
            if current_item != row['item_code']:
                if rows:
                    yield rows
                current_item = row['item_code']
                current_bin = None
                rows = []
            
            rows.append(row)
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet('Item Details')
        
        # 设置标题格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa'
        })
        
        # 设置单元格格式
        item_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2962ff'  # 蓝色
        })
        bin_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#e67e22'  # 橙色
        })
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        bt_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 写入标题
        headers = ['Item Code', 'Bin Location', 'Customer PO', 'BT', 'Box Count', 'Pieces/Box', 
                  'Total in Box', 'Bin Total', 'Item Total']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # 设置列宽
        worksheet.set_column('A:A', 20)  # Item Code
        worksheet.set_column('B:B', 15)  # Bin Location
        worksheet.set_column('C:C', 15)  # Customer PO
        worksheet.set_column('D:D', 15)  # BT
        worksheet.set_column('E:I', 12)  # Numeric columns
        
        # 写入数据
        row_num = 1
        for group in generate_rows():
            start_row = row_num
            current_bin = None
            bin_start = start_row
            current_bin_total = None
            
            for data in group:
                worksheet.write(row_num, 0, data['item_code'], item_format)
                worksheet.write(row_num, 1, data['bin_code'], bin_format)
                worksheet.write(row_num, 2, data['customer_po'] or '-', customer_po_format)
                worksheet.write(row_num, 3, data['BT'], bt_format)
                worksheet.write(row_num, 4, data['box_count'], number_format)
                worksheet.write(row_num, 5, data['pieces_per_box'], number_format)
                worksheet.write(row_num, 6, data['box_total'], number_format)
                
                # 处理bin_total和bin_code的写入和合并
                if current_bin != data['bin_code']:
                    if current_bin is not None and row_num - bin_start > 1:
                        # 合并前一个bin的单元格
                        worksheet.merge_range(f'H{bin_start+1}:H{row_num}', 
                                              current_bin_total, number_format)
                        worksheet.merge_range(f'B{bin_start+1}:B{row_num}',
                                              current_bin, bin_format)
                    current_bin = data['bin_code']
                    current_bin_total = data['bin_total']
                    bin_start = row_num
                    worksheet.write(row_num, 7, current_bin_total, number_format)
                    worksheet.write(row_num, 1, data['bin_code'], bin_format)
                else:
                    # 对于同一个bin的后续行，使用相同的bin_total
                    worksheet.write(row_num, 7, current_bin_total, number_format)
                
                row_num += 1
            
            # 处理最后一个bin的合并
            if row_num - bin_start > 1:
                worksheet.merge_range(f'H{bin_start+1}:H{row_num}', 
                                      current_bin_total, number_format)
                worksheet.merge_range(f'B{bin_start+1}:B{row_num}',
                                      data['bin_code'], bin_format)
            elif row_num == bin_start + 1:
                # 如果只有一行，直接写入而不合并
                worksheet.write(bin_start, 1, data['bin_code'], bin_format)
                worksheet.write(bin_start, 7, current_bin_total, number_format)
            
            # 合并item_total - 确保总是显示商品总数量
            worksheet.merge_range(f'I{start_row+1}:I{row_num}', 
                                  data['item_total'], number_format)
            
            # 合并item_code - 确保总是显示商品编码
            if row_num - start_row > 1:
                worksheet.merge_range(f'A{start_row+1}:A{row_num}', 
                                      data['item_code'], item_format)
            else:
                # 如果只有一行，确保item_code和item_total都正确显示
                worksheet.write(start_row, 0, data['item_code'], item_format)
                worksheet.write(start_row, 7, data['item_total'], number_format)
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name= f'Details-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

@app.route('/api/export/database', methods=['GET'])
def export_database():
    try:
        db = get_db()
        db.close()  # 关闭数据库连接以确保所有数据都已写入
        
        # 获取数据库文件路径
        db_path = os.path.join(os.path.dirname(__file__), 'inventory.db')
        
        # 创建内存中的临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_buffer = BytesIO()
        with open(db_path, 'rb') as f:
            temp_buffer.write(f.read())
        
        temp_buffer.seek(0)
        
        return send_file(
            temp_buffer,
            mimetype='application/x-sqlite3',
            as_attachment=True,
            download_name=f'inventory_{timestamp}.db'
        )
        
    except Exception as e:
        print(f"Error exporting database: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/bin/<bin_code>/clear', methods=['DELETE'])
def clear_bin_inventory(bin_code):
    try:
        db = get_db()
        cursor = db.cursor()
        
        # 先检查库位是否存在
        cursor.execute('SELECT bin_id FROM bins WHERE bin_code = ?', (bin_code,))
        bin_result = cursor.fetchone()
        if not bin_result:
            return jsonify({'error': '库位不存在', 'error_en': 'Bin location does not exist'}), 404
        
        # 获取要删除的所有库存信息用于历史记录（包含详细信息）
        cursor.execute('''
            SELECT inv.box_count, inv.pieces_per_box, inv.total_pieces, 
                   inv.customer_po, inv.BT, i.item_code
            FROM inventory inv 
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.bin_id = ?
        ''', (bin_result['bin_id'],))
        
        inventory_records = cursor.fetchall()
        
        # 删除该库位的所有库存记录
        cursor.execute('DELETE FROM inventory WHERE bin_id = ?', (bin_result['bin_id'],))
        
        # 记录清除操作到历史记录（为每个商品的每个PO-BT组合创建详细的历史记录）
        if inventory_records:
            # 按商品和PO-BT组合分组
            item_po_bt_groups = {}
            for record in inventory_records:
                item_key = record['item_code']
                po_bt_key = f"{record['customer_po'] or 'None'}|{record['BT'] or 'None'}"
                full_key = f"{item_key}|{po_bt_key}"
                
                if full_key not in item_po_bt_groups:
                    item_po_bt_groups[full_key] = {
                        'item_code': record['item_code'],
                        'customer_po': record['customer_po'],
                        'BT': record['BT'],
                        'total_pieces': 0,
                        'box_details': []
                    }
                item_po_bt_groups[full_key]['total_pieces'] += record['total_pieces']
                item_po_bt_groups[full_key]['box_details'].append({
                    'box_count': record['box_count'],
                    'pieces_per_box': record['pieces_per_box']
                })
            
            # 为每个商品的每个PO-BT组合创建历史记录
            for group_data in item_po_bt_groups.values():
                # 选择最大的箱规作为代表性信息显示
                max_box_detail = max(group_data['box_details'], 
                                   key=lambda x: x['box_count'] * x['pieces_per_box'])
                
                cursor.execute('''
                    INSERT INTO input_history (bin_code, item_code, customer_po, BT, box_count, pieces_per_box, total_pieces)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (bin_code, f'清空库位{group_data["item_code"]}', 
                     group_data['customer_po'], group_data['BT'],
                     max_box_detail['box_count'], max_box_detail['pieces_per_box'],  # 每箱件数保持正数
                     -group_data['total_pieces']))  # 只有总件数为负数
        else:
            # 如果库位为空，仍然记录一条清空操作
            cursor.execute('''
                INSERT INTO input_history (bin_code, item_code, box_count, pieces_per_box, total_pieces)
                VALUES (?, '清空库位', 0, 0, 0)
            ''', (bin_code,))
        
        db.commit()
        return jsonify({'success': True, 'message': f'已清空库位 {bin_code} 的所有库存'})
        
    except Exception as e:
        print(f"Error clearing bin inventory: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/bin/<bin_code>/item/<item_code>/clear', methods=['DELETE'])
def clear_item_at_bin(bin_code, item_code):
    try:
        db = get_db()
        cursor = db.cursor()
        
        # 先检查库位是否存在
        cursor.execute('SELECT bin_id FROM bins WHERE bin_code = ?', (bin_code,))
        bin_result = cursor.fetchone()
        if not bin_result:
            return jsonify({'error': '库位不存在', 'error_en': 'Bin location does not exist'}), 404
        
        # 检查商品是否存在
        cursor.execute('SELECT item_id FROM items WHERE item_code = ?', (item_code,))
        item_result = cursor.fetchone()
        if not item_result:
            return jsonify({'error': '商品不存在', 'error_en': 'Item does not exist'}), 404
        
        # 获取要删除的库存信息用于历史记录（包含详细信息）
        cursor.execute('''
            SELECT box_count, pieces_per_box, total_pieces, customer_po, BT
            FROM inventory 
            WHERE bin_id = ? AND item_id = ?
        ''', (bin_result['bin_id'], item_result['item_id']))
        
        inventory_records = cursor.fetchall()
        total_cleared = sum(record['total_pieces'] for record in inventory_records)
        
        # 删除该库位中特定商品的所有库存记录
        cursor.execute('''
            DELETE FROM inventory 
            WHERE bin_id = ? AND item_id = ?
        ''', (bin_result['bin_id'], item_result['item_id']))
        
        # 记录清除操作到历史记录（为每个不同的PO-BT组合创建单独的历史记录）
        if inventory_records:
            # 按PO-BT组合分组
            po_bt_groups = {}
            for record in inventory_records:
                key = f"{record['customer_po'] or 'None'}|{record['BT'] or 'None'}"
                if key not in po_bt_groups:
                    po_bt_groups[key] = {
                        'customer_po': record['customer_po'],
                        'BT': record['BT'],
                        'total_pieces': 0,
                        'box_details': []
                    }
                po_bt_groups[key]['total_pieces'] += record['total_pieces']
                po_bt_groups[key]['box_details'].append({
                    'box_count': record['box_count'],
                    'pieces_per_box': record['pieces_per_box']
                })
            
            # 为每个PO-BT组合创建历史记录
            for group_data in po_bt_groups.values():
                # 选择最大的箱规作为代表性信息显示
                max_box_detail = max(group_data['box_details'], 
                                   key=lambda x: x['box_count'] * x['pieces_per_box'])
                
                cursor.execute('''
                    INSERT INTO input_history (bin_code, item_code, customer_po, BT, box_count, pieces_per_box, total_pieces)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (bin_code, f'清空商品{item_code}', 
                     group_data['customer_po'], group_data['BT'],
                     max_box_detail['box_count'], max_box_detail['pieces_per_box'],  # 每箱件数保持正数
                     -group_data['total_pieces']))  # 只有总件数为负数
        
        db.commit()
        return jsonify({
            'success': True, 
            'message': f'已清空库位 {bin_code} 中商品 {item_code} 的所有库存'
        })
        
    except Exception as e:
        print(f"Error clearing item at bin: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/history', methods=['GET'])
def export_history():
    db = get_db()
    cursor = db.cursor()
    
    # 检查是否有日期过滤参数
    date_filter = request.args.get('date', '').strip()
    
    if date_filter:
        # 导出指定日期的历史记录
        cursor.execute('''
            SELECT 
                datetime(input_time, 'localtime') as input_time,
                bin_code,
                item_code,
                customer_po,
                BT,
                box_count,
                pieces_per_box,
                total_pieces
            FROM input_history
            WHERE DATE(datetime(input_time, 'localtime')) = ?
            ORDER BY input_time DESC
        ''', (date_filter,))
        filename = f'History-{date_filter}.xlsx'
    else:
        # 导出所有历史记录
        cursor.execute('''
            SELECT 
                datetime(input_time, 'localtime') as input_time,
                bin_code,
                item_code,
                customer_po,
                BT,
                box_count,
                pieces_per_box,
                total_pieces
            FROM input_history
            ORDER BY input_time DESC
        ''')
        filename = f'History-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    history_data = cursor.fetchall()
    
    # 处理历史数据，清理商品名
    processed_data = []
    for row in history_data:
        # 处理商品名，去掉"清空库位"和"清空商品"前缀
        item_code = row['item_code']
        if item_code.startswith('清空库位'):
            item_code = item_code.replace('清空库位', '')
        elif item_code.startswith('清空商品'):
            item_code = item_code.replace('清空商品', '')
        
        processed_data.append({
            'Time (UTC)': row['input_time'],
            'Bin Location': row['bin_code'],
            'Item (SKU)': item_code,
            'Customer PO': row['customer_po'] or '',
            'BT Number': row['BT'] or '',
            'Box Count': row['box_count'],
            'PCs/Box': row['pieces_per_box'],
            'Total Pieces': row['total_pieces']
        })
    
    # 创建DataFrame
    df = pd.DataFrame(processed_data)
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='History', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['History']
        
        # 定义格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa'
        })
        
        time_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'yyyy-mm-dd hh:mm:ss',
            'font_color': '#666666'  # 灰色
        })
        
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
        
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        
        bt_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'num_format': '#,##0',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 应用格式到表头
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # 设置列宽并应用格式
        worksheet.set_column('A:A', 20, time_format)    # Time column
        worksheet.set_column('B:B', 15 , bin_format)     # Bin Code column
        worksheet.set_column('C:C', 20, item_format)    # Item Code column
        worksheet.set_column('D:D', 15, customer_po_format) # Customer PO column
        worksheet.set_column('E:E', 10, bt_format)      # BT Number column
        worksheet.set_column('F:H', None, number_format) # Number columns
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/po/<PO>', methods=['GET'])
def export_po(PO):
    db = get_db()
    cursor = db.cursor()
    
    PO = PO.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    
    # 查询指定客户订单号的详细信息，包括每箱件数
    cursor.execute('''
        WITH po_item_totals AS (
            SELECT 
                inv.customer_po,
                i.item_code,
                SUM(inv.total_pieces) as item_total_in_po
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.customer_po = ?
            GROUP BY inv.customer_po, i.item_code
        )
        SELECT 
            inv.customer_po,
            i.item_code,
            b.bin_code,
            inv.BT,
            inv.box_count as boxes_in_bin,
            inv.pieces_per_box,
            inv.total_pieces as pieces_in_bin,
            pit.item_total_in_po
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        JOIN bins b ON inv.bin_id = b.bin_id
        JOIN po_item_totals pit ON inv.customer_po = pit.customer_po AND i.item_code = pit.item_code
        WHERE inv.customer_po = ?
        ORDER BY i.item_code, b.bin_code, inv.BT
    ''', (PO, PO))
    
    results = cursor.fetchall()
    
    if not results:
        return jsonify({
            'error': f'客户订单号 {PO} 不存在',
            'error_en': f'Customer PO {PO} does not exist'
        }), 404
    
    # 准备导出数据
    export_data = []
    for row in results:
        export_data.append({
            'Customer PO': row['customer_po'],
            'Item Code': row['item_code'], 
            'Bin Code': row['bin_code'],
            'BT Number': row['BT'] or '',
            'Boxes in Bin': row['boxes_in_bin'],
            'Pieces per Box': row['pieces_per_box'],
            'Pieces in Bin': row['pieces_in_bin'],
            'Item Total in PO': row['item_total_in_po']
        })
    
    # 创建DataFrame
    df = pd.DataFrame(export_data)
    
    # 生成文件名
    filename = f'PO-{PO}-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='PO Details', index=False)
        
        # 获取工作表和工作簿对象
        workbook = writer.book
        worksheet = writer.sheets['PO Details']
        
        # 定义格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f0f0f0',
            'border': 1
        })
        
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        
        item_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2962ff'  # 蓝色
        })
        
        bin_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#e67e22'  # 橙色
        })
        
        bt_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 设置列宽和格式
        worksheet.set_column('A:A', 15, customer_po_format)  # Customer PO
        worksheet.set_column('B:B', 20, item_format)         # Item Code
        worksheet.set_column('C:C', 15, bin_format)          # Bin Code
        worksheet.set_column('D:D', 12, bt_format)           # BT Number
        worksheet.set_column('E:E', 12, number_format)       # Boxes in Bin
        worksheet.set_column('F:F', 12, number_format)       # Pieces per Box
        worksheet.set_column('G:G', 12, number_format)       # Pieces in Bin
        worksheet.set_column('H:H', 15, number_format)       # Item Total in PO
        
        # 应用表头格式
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # 合并相同PO和相同商品的单元格
        if len(export_data) > 0:
            # 合并整个Customer PO列（所有行都是同一个PO）
            if len(export_data) > 1:
                po_value = export_data[0]['Customer PO']
                worksheet.merge_range(1, 0, len(export_data), 0, po_value, customer_po_format)
            
            # 合并相同Item Code的行
            current_item = None
            item_start_row = 1
            
            for row_idx, row_data in enumerate(export_data, start=1):
                item = row_data['Item Code']
                
                # 检查商品是否变化
                if current_item != item:
                    # 合并之前商品的Item Code列和Item Total in PO列（如果有多行）
                    if current_item is not None and row_idx - 1 > item_start_row:
                        # 合并Item Code列 (B列)
                        worksheet.merge_range(item_start_row, 1, row_idx - 1, 1, current_item, item_format)
                        # 合并Item Total in PO列 (H列)
                        item_total = export_data[row_idx - 2]['Item Total in PO']
                        worksheet.merge_range(item_start_row, 7, row_idx - 1, 7, item_total, number_format)
                    
                    current_item = item
                    item_start_row = row_idx
            
            # 处理最后一个商品的合并
            if len(export_data) > item_start_row:
                last_item = export_data[-1]['Item Code']
                last_item_total = export_data[-1]['Item Total in PO']
                # 合并Item Code列 (B列)
                worksheet.merge_range(item_start_row, 1, len(export_data), 1, last_item, item_format)
                # 合并Item Total in PO列 (H列)
                worksheet.merge_range(item_start_row, 7, len(export_data), 7, last_item_total, number_format)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/bt/<BT>', methods=['GET'])
def export_bt(BT):
    db = get_db()
    cursor = db.cursor()
    
    BT = BT.replace('___SLASH___', '/').replace('___SPACE___', ' ')
    
    # 查询指定BT的所有商品
    cursor.execute('''
        SELECT 
            i.item_code,
            b.bin_code,
            inv.customer_po,
            inv.BT,
            SUM(inv.total_pieces) as total_pieces,
            SUM(inv.box_count) as total_boxes
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        JOIN bins b ON inv.bin_id = b.bin_id
        WHERE inv.BT = ?
        GROUP BY i.item_code, b.bin_code, inv.customer_po
        ORDER BY i.item_code, b.bin_code, inv.customer_po
    ''', (BT,))
    
    results = cursor.fetchall()
    
    if not results:
        return jsonify({
            'error': f'BT {BT} 不存在',
            'error_en': f'BT {BT} does not exist'
        }), 404
    
    # 准备导出数据
    export_data = []
    for row in results:
        export_data.append({
            'BT Number': row['BT'],
            'Item Code': row['item_code'], 
            'Bin Code': row['bin_code'],
            'Customer PO': row['customer_po'] or '',
            'Total Pieces': row['total_pieces'],
            'Box Count': row['total_boxes']
        })
    
    # 创建DataFrame
    df = pd.DataFrame(export_data)
    
    # 生成文件名
    filename = f'BT-{BT}-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='BT Details', index=False)
        
        # 获取工作表和工作簿对象
        workbook = writer.book
        worksheet = writer.sheets['BT Details']
        
        # 定义格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f0f0f0',
            'border': 1
        })
        
        bt_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        
        item_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2962ff'  # 蓝色
        })
        
        bin_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#e67e22'  # 橙色
        })
        
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 设置列宽和格式
        worksheet.set_column('A:A', 12, bt_format)           # BT Number
        worksheet.set_column('B:B', 20, item_format)         # Item Code
        worksheet.set_column('C:C', 15, bin_format)          # Bin Code
        worksheet.set_column('D:D', 15, customer_po_format)  # Customer PO
        worksheet.set_column('E:E', 12, number_format)       # Total Pieces
        worksheet.set_column('F:F', 12, number_format)       # Box Count
        
        # 应用表头格式
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # 合并相同BT和相同商品的单元格
        if len(export_data) > 0:
            # 合并整个BT Number列（所有行都是同一个BT）
            if len(export_data) > 1:
                bt_value = export_data[0]['BT Number']
                worksheet.merge_range(1, 0, len(export_data), 0, bt_value, bt_format)
            
            # 合并相同Item Code的行
            current_item = None
            item_start_row = 1
            
            for row_idx, row_data in enumerate(export_data, start=1):
                item = row_data['Item Code']
                
                # 检查商品是否变化
                if current_item != item:
                    # 合并之前商品的Item Code列（如果有多行）
                    if current_item is not None and row_idx - 1 > item_start_row:
                        worksheet.merge_range(item_start_row, 1, row_idx - 1, 1, current_item, item_format)
                    
                    current_item = item
                    item_start_row = row_idx
            
            # 处理最后一个商品的合并
            if len(export_data) > item_start_row:
                last_item = export_data[-1]['Item Code']
                worksheet.merge_range(item_start_row, 1, len(export_data), 1, last_item, item_format)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/all-pos', methods=['GET'])
def export_all_pos():
    db = get_db()
    cursor = db.cursor()
    
    # 查询所有客户订单号的详细信息，包括每箱件数
    cursor.execute('''
        WITH po_item_totals AS (
            SELECT 
                inv.customer_po,
                i.item_code,
                SUM(inv.total_pieces) as item_total_in_po
            FROM inventory inv
            JOIN items i ON inv.item_id = i.item_id
            WHERE inv.customer_po IS NOT NULL AND inv.customer_po != ''
            GROUP BY inv.customer_po, i.item_code
        )
        SELECT 
            inv.customer_po,
            i.item_code,
            b.bin_code,
            inv.BT,
            inv.box_count as boxes_in_bin,
            inv.pieces_per_box,
            inv.total_pieces as pieces_in_bin,
            pit.item_total_in_po
        FROM inventory inv
        JOIN items i ON inv.item_id = i.item_id
        JOIN bins b ON inv.bin_id = b.bin_id
        JOIN po_item_totals pit ON inv.customer_po = pit.customer_po AND i.item_code = pit.item_code
        WHERE inv.customer_po IS NOT NULL AND inv.customer_po != ''
        ORDER BY inv.customer_po, i.item_code, b.bin_code, inv.BT
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        return jsonify({
            'error': '没有找到任何客户订单号数据',
            'error_en': 'No customer PO data found'
        }), 404
    
    # 准备导出数据
    export_data = []
    for row in results:
        export_data.append({
            'Customer PO': row['customer_po'],
            'Item Code': row['item_code'], 
            'Bin Code': row['bin_code'],
            'BT Number': row['BT'] or '',
            'Boxes in Bin': row['boxes_in_bin'],
            'Pieces per Box': row['pieces_per_box'],
            'Pieces in Bin': row['pieces_in_bin'],
            'Item Total in PO': row['item_total_in_po']
        })
    
    # 创建DataFrame
    df = pd.DataFrame(export_data)
    
    # 生成文件名
    filename = f'POs-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    # 创建Excel文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='All POs Details', index=False)
        
        # 获取工作表和工作簿对象
        workbook = writer.book
        worksheet = writer.sheets['All POs Details']
        
        # 定义格式
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f0f0f0',
            'border': 1
        })
        
        customer_po_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#ff5722'  # 橘红色
        })
        
        item_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2962ff'  # 蓝色
        })
        
        bin_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#e67e22'  # 橙色
        })
        
        bt_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#9c27b0'  # 紫色
        })
        
        number_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#27ae60'  # 绿色
        })
        
        # 设置列宽和格式
        worksheet.set_column('A:A', 15, customer_po_format)  # Customer PO
        worksheet.set_column('B:B', 20, item_format)         # Item Code
        worksheet.set_column('C:C', 15, bin_format)          # Bin Code
        worksheet.set_column('D:D', 12, bt_format)           # BT Number
        worksheet.set_column('E:E', 12, number_format)       # Boxes in Bin
        worksheet.set_column('F:F', 12, number_format)       # Pieces per Box
        worksheet.set_column('G:G', 12, number_format)       # Pieces in Bin
        worksheet.set_column('H:H', 15, number_format)       # Item Total in PO
        
        # 应用表头格式
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # 合并相同PO和相同商品的单元格
        if len(export_data) > 0:
            current_po = None
            current_item = None
            po_start_row = 1
            item_start_row = 1
            
            for row_idx, row_data in enumerate(export_data, start=1):
                po = row_data['Customer PO']
                item = row_data['Item Code']
                
                # 检查PO是否变化
                if current_po != po:
                    # 合并之前PO的单元格（如果有多行）
                    if current_po is not None and row_idx - 1 > po_start_row:
                        worksheet.merge_range(po_start_row, 0, row_idx - 1, 0, current_po, customer_po_format)
                        # 同时合并该PO下最后一个商品的Item Code列和总数量列
                        if row_idx - 1 > item_start_row:
                            # 合并Item Code列 (B列)
                            worksheet.merge_range(item_start_row, 1, row_idx - 1, 1, current_item, item_format)
                            # 合并Item Total in PO列 (H列)
                            last_item_total = export_data[row_idx - 2]['Item Total in PO']
                            worksheet.merge_range(item_start_row, 7, row_idx - 1, 7, last_item_total, number_format)
                    
                    current_po = po
                    po_start_row = row_idx
                    current_item = item
                    item_start_row = row_idx
                
                # 检查商品是否变化（在同一PO内）
                elif current_item != item:
                    # 合并之前商品的Item Code列和Item Total in PO列（如果有多行）
                    if row_idx - 1 > item_start_row:
                        # 合并Item Code列 (B列)
                        worksheet.merge_range(item_start_row, 1, row_idx - 1, 1, current_item, item_format)
                        # 合并Item Total in PO列 (H列)
                        item_total = export_data[row_idx - 2]['Item Total in PO']
                        worksheet.merge_range(item_start_row, 7, row_idx - 1, 7, item_total, number_format)
                    
                    current_item = item
                    item_start_row = row_idx
            
            # 处理最后一个PO和商品的合并
            if len(export_data) > po_start_row:
                last_po = export_data[-1]['Customer PO']
                worksheet.merge_range(po_start_row, 0, len(export_data), 0, last_po, customer_po_format)
                
                # 合并最后一个商品的Item Code列和Item Total in PO列
                if len(export_data) > item_start_row:
                    last_item = export_data[-1]['Item Code']
                    last_item_total = export_data[-1]['Item Total in PO']
                    # 合并Item Code列 (B列)
                    worksheet.merge_range(item_start_row, 1, len(export_data), 1, last_item, item_format)
                    # 合并Item Total in PO列 (H列)
                    worksheet.merge_range(item_start_row, 7, len(export_data), 7, last_item_total, number_format)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


if __name__ == '__main__':
    print("Starting server...")
    print("Current working directory:", os.getcwd())
    print("Checking for required files:")
    # for file in ['index.html', 'inventory.js', 'schema.sql', 'BIN.csv', 'Item.CSV']:
    for file in ['index.html', 'inventory.js', 'schema.sql', 'BIN.csv']:
        if os.path.exists(file):
            print(f"  {file}: Found")
        else:
            print(f"  {file}: Missing!")
    
    try:
        init_db()
        print("Database initialized successfully")
        
        # 关闭Flask的访问日志
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        # 关闭调试模式，避免重复启动信息
        app.run(host=host, port=port, debug=False)
    except Exception as e:
        print("Error starting server:", str(e))
        print(traceback.format_exc()) 