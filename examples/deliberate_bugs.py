"""故意写的有问题的代码，用来测试harness能不能发现"""
import os
import sqlite3

# Bug1: 硬编码密钥
API_KEY = "sk-1234567890abcdef"
DB_PASSWORD = "admin123456"

# Bug2: SQL注入
def get_user(name):
    conn = sqlite3.connect("test.db")
    result = conn.execute(f"SELECT * FROM users WHERE name = '{name}'")
    return result.fetchone()

# Bug3: 命令注入
def run_command(user_input):
    os.system(f"echo {user_input}")

# Bug4: 没有错误处理
def divide(a, b):
    return a / b

# Bug5: 裸except
def process():
    try:
        result = eval(input("Enter expression: "))
    except:
        pass
