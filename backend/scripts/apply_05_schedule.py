"""Apply sql/05_schedule_block.sql via PyMySQL."""
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sql_text = (ROOT / "sql" / "05_schedule_block.sql").read_text(encoding="utf-8")

conn = pymysql.connect(
    host="localhost",
    user="root",
    password="123456",
    database="lab_access",
    charset="utf8mb4",
)
try:
    with conn.cursor() as cur:
        for stmt in sql_text.split(";"):
            lines = [ln for ln in stmt.splitlines() if not ln.strip().startswith("--")]
            s = "\n".join(lines).strip()
            if not s or s.upper().startswith("USE "):
                continue
            cur.execute(s)
        conn.commit()
        cur.execute("SHOW TABLES LIKE 'lab_schedule_block'")
        print("table:", cur.fetchall())
        cur.execute("SELECT id, username, role FROM user")
        print("users:", cur.fetchall())
finally:
    conn.close()
