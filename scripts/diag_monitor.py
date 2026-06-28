#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""摸清 /root/ops-relay 真实部署（只读）。"""
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

print("=== /root/ops-relay 是否 git 仓库 ==="); print(run("cd /root/ops-relay && git remote -v 2>&1; git log --oneline -2 2>&1; git status -s 2>&1 | head"))
print("=== /root/ops-relay/docker-compose.yml ==="); print(run("cat /root/ops-relay/docker-compose.yml"))
print("=== /root/ops-relay/config.yml 分组 ==="); print(run("grep -E 'all_linux:|windows_ssh:|windows:' -A2 /root/ops-relay/config.yml | head -20"))
print("=== /root/ops-relay/inventory.ini ==="); print(run("cat /root/ops-relay/inventory.ini"))
print("=== 8001 端口占用 ==="); print(run("ss -tlnp 2>/dev/null | grep -E ':8001|:8081' || echo '无'"))
print("=== /opt/ops-relay 是否有 prod 容器残留 ==="); print(run("docker ps -a --format '{{.Names}} {{.Status}}' | grep -i prod || echo '无 prod 容器'"))
print("=== /root/ops-relay 目录 ==="); print(run("ls -la /root/ops-relay/ | head -20"))
c.close()
