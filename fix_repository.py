import os

file_path = r'tap\infrastructure\database\repository.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '    except Error as e:\n        return False, f"Erreur de base de données : {e}"'
replacement = '    except Error as e:\n        if "conn" in locals() and conn.is_connected():\n            conn.rollback()\n        return False, f"Erreur de base de données : {e}"'

content = content.replace(target, replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
