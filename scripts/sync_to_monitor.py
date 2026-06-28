#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地 gitignore 的 config.yml 和 host_vars/*.yml 用 SFTP 同步到监控机 15。
走 paramiko + 密钥（与 push_ssh_key.py 同路），避免交互式 ssh/scp。"""
import os, sys, glob
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

import paramiko

MONITOR = "10.0.0.15"
USER = "root"
KEY = os.path.expanduser("~/.ssh/id_ed25519")
REMOTE_DIR = "/opt/ops-relay"

files = {"config.yml": f"{REMOTE_DIR}/config.yml"}
for f in sorted(glob.glob("host_vars/*.yml")):
    files[f] = f"{REMOTE_DIR}/{f}"

if not os.path.exists(KEY):
    sys.exit(f"❌ 找不到私钥 {KEY}")
print(f"待同步 {len(files)} 个文件 -> {MONITOR}:{REMOTE_DIR}")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(MONITOR, username=USER, key_filename=KEY, timeout=15, allow_agent=False, look_for_keys=False)
c.exec_command(f"mkdir -p {REMOTE_DIR}/host_vars")
sftp = c.open_sftp()
for local, remote in files.items():
    sftp.put(local, remote)
    print(f"  ✅ {local} -> {remote}")
sftp.close()
_, so, _ = c.exec_command(f"echo === host_vars ===; ls -1 {REMOTE_DIR}/host_vars/; echo === config.yml 分组 ===; grep -E 'all_linux:|windows_ssh:|windows:' -A1 {REMOTE_DIR}/config.yml | head -20")
print(so.read().decode(errors="replace"))
c.close()
print("同步完成")
