"""确保演示老师账号存在：teacher / 123456"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pymysql
from utils.security import hash_password

USERNAME = "teacher"
PASSWORD = "123456"
EMPLOYEE_NO = "T10001"

conn = pymysql.connect(
    host="localhost",
    user="root",
    password="123456",
    database="lab_access",
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
