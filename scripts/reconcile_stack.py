#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docker compose up -d 重建网络归属，修 frontend 解析不到 backend。"""
import os, sys, time
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.0.0.15", username="root", key_filename=KEY, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=180):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")

print("=== docker compose up -d ==="); print(run("cd /root/ops-relay && docker compose up -d 2>&1"))
print("等待...")
for i in range(20):
    out = run("docker exec ops-relay-frontend sh -c 'wget -qO- http://backend:8000/health 2>&1' 2>&1")
    if "healthy" in out:
        print(f"  前端→后端通({i*3}s): {out.strip()}"); break
    time.sleep(3)
else:
    print("  仍未通:", out.strip()[:300])
print("=== 容器状态 ==="); print(run("docker ps --format '{{.Names}}\\t{{.Status}}' | grep ops-relay"))
print("=== 前端日志末尾 ==="); print(run("docker logs ops-relay-frontend --tail 6 2>&1"))
c.close()
