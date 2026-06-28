#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重启前端容器，让 nginx 重新解析后端 IP（修 502）。"""
import os, sys, time
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.0.0.15", username="root", key_filename=KEY, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=60):
    _, so, se = c.exec_command(cmd, timeout=t)
    return so.read().decode(errors="replace") + se.read().decode(errors="replace")

print("=== 重启前端 ==="); print(run("docker restart ops-relay-frontend 2>&1"))
print("等待 nginx 起来...")
for i in range(10):
    out = run("docker exec ops-relay-frontend sh -c 'wget -qO- http://backend:8000/health 2>&1' 2>&1")
    if "healthy" in out:
        print(f"  前端→后端通({i*2}s): {out.strip()}"); break
    time.sleep(2)
else:
    print("  仍未通:", out.strip()[:200])
print("=== nginx 最新日志 ==="); print(run("docker logs ops-relay-frontend --tail 5 2>&1"))
c.close()
