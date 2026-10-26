# -*- coding: utf-8 -*-
"""A2 通行闭环冒烟：预约→审批→须知→发码→核验。"""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pymysql

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"


def req(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def main():
    user, pwd = "a2demo", "123456"
    st, body = req("POST", "/api/user/login", {"username": user, "password": pwd})
    if st != 200 or body.get("code") != 200:
        st, body = req(
            "POST",
            "/api/user/register",
            {
                "username": user,
                "password": pwd,
                "repassword": pwd,
                "employee_no": "A20001",
                "role": "student",
            },
        )
        print("register", st, body.get("message"))
        st, body = req("POST", "/api/user/login", {"username": user, "password": pwd})
    print("login", st, body.get("message"))
    if body.get("code") != 200:
        raise SystemExit(body)

    uid = body["data"]["user"]["id"]
    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="123456",
        database="lab_access",
        charset="utf8mb4",
        autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("UPDATE user SET role=%s WHERE id=%s", ("admin", uid))

    st, body = req("POST", "/api/user/login", {"username": user, "password": pwd})
    token = body["data"]["token"]

    # 取消该用户未结束预约，避免冲突
    st, mine = req("GET", "/api/reservations/mine", token=token)
    for it in (mine.get("data") or {}).get("items") or []:
        if it["status"] in ("pending", "approved", "in_use"):
            st_c, b_c = req(
                "POST", f"/api/reservations/{it['id']}/cancel", {}, token=token
            )
            print("cancel", it["id"], st_c, b_c.get("message"))

    st, body = req("GET", "/api/labs", token=token)
    labs = body["data"]["items"]
    lab_id = next(x["id"] for x in labs if x.get("need_approve") == 0) if labs else None
    if lab_id is None:
        lab_id = labs[0]["id"]
    print("lab", lab_id)

    now = datetime.now()
    start = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
    end = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
    st, body = req(
        "POST",
        "/api/reservations",
        {"lab_id": lab_id, "start_time": start, "end_time": end, "purpose": "A2联调"},
        token=token,
    )
    print("create", st, body.get("message"), body.get("data"))
    if body.get("code") != 200:
        raise SystemExit(body)

    res_id = body["data"]["id"]
    if body["data"]["status"] == "pending":
        st, body = req("POST", f"/api/reservations/{res_id}/approve", {}, token=token)
        print("approve", st, body.get("message"))

    st, body = req("POST", "/api/access/safety/ack", {"reservation_id": res_id}, token=token)
    print("ack", st, body.get("message"), body.get("data"))
    if body.get("code") != 200:
        raise SystemExit(body)

    st, body = req(
        "POST", "/api/access/passcode/issue", {"reservation_id": res_id}, token=token
    )
    print("issue", st, body.get("message"), body.get("data"))
    if body.get("code") != 200:
        raise SystemExit(body)
    code = body["data"]["code"]

    # 错门口应拒绝
    st, body = req(
        "POST", "/api/access/verify", {"code": code, "device_id": "DOOR-LAB-1"}
    )
    print("verify_wrong_door", st, body.get("data"))
    if (body.get("data") or {}).get("allowed"):
        raise SystemExit("wrong door should deny")

    # 对门口应通过（lab_id=2 → DOOR-LAB-2）
    st, body = req(
        "POST", "/api/access/verify", {"code": code, "device_id": "DOOR-LAB-2"}
    )
    print("verify_right_door", st, body.get("message"), body.get("data"))
    if not (body.get("data") or {}).get("allowed"):
        raise SystemExit("verify failed")

    st, body = req("GET", "/api/access/logs?limit=3", token=token)
    items = (body.get("data") or {}).get("items") or []
    print("logs", items[0] if items else None)
    print("A2_SMOKE_OK", code)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
