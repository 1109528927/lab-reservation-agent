"""确保演示老师账号存在：teacher / 123456"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pymysql
from utils.security import hash_password

USERNAME = "teacher"
PASSWORD = "123456"
EMPLOYEE_NO = "T10001"

# 兼容本机与 Docker：优先 DATABASE_URL，否则 MYSQL_HOST
_db = os.getenv("DATABASE_URL", "").replace("mysql+aiomysql://", "mysql://").replace(
    "mysql+pymysql://", "mysql://"
)
if _db:
    u = urlparse(_db)
    _host = u.hostname or "localhost"
    _user = u.username or "root"
    _password = u.password or "123456"
    _database = (u.path or "/lab_access").lstrip("/") or "lab_access"
    _port = u.port or 3306
else:
    _host = os.getenv("MYSQL_HOST", "localhost")
    _user = os.getenv("MYSQL_USER", "root")
    _password = os.getenv("MYSQL_PASSWORD", "123456")
    _database = os.getenv("MYSQL_DATABASE", "lab_access")
    _port = int(os.getenv("MYSQL_PORT", "3306"))

conn = pymysql.connect(
    host=_host,
    port=_port,
    user=_user,
    password=_password,
    database=_database,
    charset="utf8mb4",
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id, role FROM user WHERE username=%s", (USERNAME,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE user SET role='teacher' WHERE id=%s", (row[0],))
            print(f"updated existing user id={row[0]} -> teacher")
        else:
            cur.execute(
                "INSERT INTO user (username, password, employee_no, role) "
                "VALUES (%s,%s,%s,'teacher')",
                (USERNAME, hash_password(PASSWORD), EMPLOYEE_NO),
            )
            print(f"created {USERNAME} / {PASSWORD}")
        conn.commit()
        cur.execute(
            "SELECT id, username, role, employee_no FROM user WHERE username=%s",
            (USERNAME,),
        )
        print("user:", cur.fetchone())
finally:
    conn.close()
