#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 8081→后端 502（只读）。"""
import os, sys
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

print("=== 前端 nginx 错误日志 ==="); print(run("docker logs ops-relay-frontend --tail 20 2>&1"))
print("=== ops-network 成员 ==="); print(run("docker network inspect ops-network --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}' 2>&1"))
print("=== 前端能否连后端(按容器名) ==="); print(run("docker exec ops-relay-frontend sh -c 'getent hosts backend; getent hosts ops-relay-backend; wget -qO- http://backend:8000/health 2>&1 || wget -qO- http://ops-relay-backend:8000/health 2>&1 || echo CANT_REACH' 2>&1"))
print("=== nginx upstream 配置 ==="); print(run("docker exec ops-relay-frontend sh -c 'grep -rn \"proxy_pass\\|upstream\" /etc/nginx/ 2>/dev/null | head' 2>&1"))
print("=== 后端在哪些网络 ==="); print(run("docker inspect ops-relay-backend --format '{{range \$k,\$v := .NetworkSettings.Networks}}{{\$k}}={{\$v.IPAddress}} {{end}}' 2>&1"))
c.close()
