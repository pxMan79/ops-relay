#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重启 /root/ops-relay 后端并等健康（只读+启动，不碰密码）。"""
import os, sys, time
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.0.0.15", username="root", key_filename=KEY, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=120):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")

print("=== 启动后端 ==="); print(run("docker start ops-relay-backend 2>&1"))
print("等待健康...")
healthy = False
for i in range(20):
    out = run("docker exec ops-relay-backend curl -sf http://localhost:8000/health 2>&1")
    if out.strip() and "error" not in out.lower() and "not" not in out.lower():
        print(f"  就绪({i*2}s): {out.strip()}"); healthy = True; break
    time.sleep(2)
if not healthy:
    print("  ⚠ 未就绪，看日志："); print(run("docker logs ops-relay-backend --tail 20 2>&1"))
print("=== 容器状态 ==="); print(run("docker ps --format '{{.Names}}\\t{{.Status}}' | grep ops-relay"))
print("=== 后端日志末尾 ==="); print(run("docker logs ops-relay-backend --tail 12 2>&1"))
c.close()
