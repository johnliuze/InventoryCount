import os
import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.messages = {
            'no_db': "数据库文件不存在\nDatabase file does not exist",
            'backup_success': "数据库已备份到\nDatabase backed up to:\n{}",
            'db_clean_success': "数据库清理完成\nDatabase cleaned successfully",
            'db_clean_error': "清理过程中出错\nError during cleaning:\n{}",
            'db_deleted': "数据库文件已删除\nDatabase file deleted",
            'delete_error': "删除数据库文件时出错\nError deleting database file:\n{}",
            'menu_title': "\n=== 数据库管理 / Database Management ===",
            'menu_1': "1. 备份当前数据库（包含库存和历史记录）\n   Backup current database (including inventory and history)",
            'menu_2': "2. 清空库存和历史记录（保留商品和库位数据）\n   Clear inventory and history (keep items and bins)",
            'menu_3': "3. 完全删除数据库（需要重新导入商品和库位数据）\n   Delete database completely (requires re-import of items and bins)",
            'input_prompt': "\n请输入选项\nEnter option (1-3): ",
            'invalid_choice': "无效的选项，请重新选择\nInvalid option, please try again",
            'press_enter': "\n按回车键退出\nPress Enter to exit..."
        }

    def msg(self, key):
        return self.messages[key]

    def check_db_exists(self):
        """检查数据库是否存在"""
        return os.path.exists('inventory.db')

    def backup_db(self):
        """备份数据库"""
        if not self.check_db_exists():
            print(self.msg('no_db'))
            return False
        
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/inventory_{timestamp}.db'
        
        with open('inventory.db', 'rb') as src, open(backup_file, 'wb') as dst:
            dst.write(src.read())
        
        print(self.msg('backup_success').format(backup_file))
        input(self.msg('press_enter'))
        return True

    def clean_db(self):
        """清理数据库内容"""
        if not self.check_db_exists():
            print(self.msg('no_db'))
            return
        
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM inventory')
            cursor.execute('DELETE FROM input_history')
            cursor.execute('DELETE FROM sqlite_sequence WHERE name IN ("inventory", "input_history")')
            conn.commit()
            print(self.msg('db_clean_success'))
            input(self.msg('press_enter'))
            
        except Exception as e:
            conn.rollback()
            print(self.msg('db_clean_error').format(e))
            input(self.msg('press_enter'))
        
        finally:
            conn.close()

    def delete_db(self):
        """完全删除数据库文件"""
        if not self.check_db_exists():
            print(self.msg('no_db'))
            return
            
        try:
            os.remove('inventory.db')
            print(self.msg('db_deleted'))
            input(self.msg('press_enter'))
        except Exception as e:
            print(self.msg('delete_error').format(e))
            input(self.msg('press_enter'))

    def run(self):
        """运行主程序"""
        # 首先检查数据库是否存在
        if not self.check_db_exists():
            print(self.msg('no_db'))
            input(self.msg('press_enter'))
            return

        while True:
            print(self.msg('menu_title'))
            print()  # 空行分隔
            print(self.msg('menu_1'))
            print()  # 空行分隔
            print(self.msg('menu_2'))
            print()  # 空行分隔
            print(self.msg('menu_3'))
            
            choice = input(self.msg('input_prompt')).strip()
            
            if choice == '1':
                self.backup_db()
                break
            elif choice == '2':
                self.clean_db()
                break
            elif choice == '3':
                self.delete_db()
                break
            else:
                print(self.msg('invalid_choice'))

if __name__ == '__main__':
    db_manager = DatabaseManager()
    db_manager.run() 