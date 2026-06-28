#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仅同步 config.yml（无密码）到监控机 15。密码文件由人工 scp。"""
import os, sys
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")
if not os.path.exists("config.yml"):
    sys.exit("❌ 当前目录没有 config.yml")
print("上传 config.yml -> root@10.0.0.15:/opt/ops-relay/config.yml")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("10.0.0.15", username="root", key_filename=KEY, timeout=15, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
sftp.put("config.yml", "/opt/ops-relay/config.yml")
sftp.close()
_, so, _ = c.exec_command("grep -E 'all_linux:|windows:' /opt/ops-relay/config.yml | head")
print("远端分组确认:"); print(so.read().decode(errors="replace"))
c.close()
print("✅ config.yml 已同步")
