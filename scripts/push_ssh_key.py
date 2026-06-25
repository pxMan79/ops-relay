#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_ssh_key.py — 批量把多套公钥分发到内网 Linux 服务器的 authorized_keys。

设计目标:
    让"用户 PC"和"监控机 10.0.0.15"都能免密 SSH 到所有被控机。
    因此分发两套公钥:
      1. 本机 ~/.ssh/id_ed25519.pub      (用户 PC 的公钥)
      2. 监控机 15 的 ~/.ssh/*.pub        (SSH 登录 15 拉取; 若 15 无密钥则自动生成 ed25519)
    每台目标机的 authorized_keys 都会包含上述全部公钥。

用法:
    pip install paramiko
    python scripts/push_ssh_key.py --dry-run              # 仅验证连通 + 拉取15公钥，不写
    python scripts/push_ssh_key.py                        # 正式分发(幂等)
    python scripts/push_ssh_key.py --only 10.0.0.5 10.0.0.7
    python scripts/push_ssh_key.py --no-fetch-monitor     # 只推本机公钥, 不拉15的

凭据文件 scripts/.servers.secret.json (已 gitignore, 跑完请删除):
    [{"ip":"10.0.0.5","port":22,"user":"root","password":"..."}, ...]

安全:
    - 永不传输私钥; 只读公钥并写入 authorized_keys。
    - 幂等: 公钥已存在则跳过。
    - 单台失败不影响其他。
    - 自动建 ~/.ssh(700) 与 authorized_keys(600)。
    - 不写日志文件, 不回显密码。
"""

import argparse
import glob
import json
import os
import sys

# Windows 控制台默认 GBK，输出 emoji/中文会崩。强制 UTF-8 + 容错。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CREDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".servers.secret.json")
DEFAULT_MONITOR = "10.0.0.15"
# 本机两把公钥都推: id_ed25519 给现代系统, id_rsa 给 CentOS 6.8(65) 等老系统。
LOCAL_PUBKEY_NAMES = ("id_ed25519.pub", "id_rsa.pub")


def require_paramiko():
    try:
        import paramiko  # noqa: F401
        return paramiko
    except ImportError:
        sys.exit("❌ 缺少 paramiko，请先运行: pip install paramiko")


def connect(paramiko, host):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host["ip"],
        port=int(host.get("port", 22)),
        username=host["user"],
        password=host["password"],
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
        auth_timeout=15,
    )
    return client


def run(client, cmd, timeout=30):
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return (
        stdout.read().decode(errors="replace"),
        stderr.read().decode(errors="replace"),
    )


def load_local_pubkeys():
    """读取本机 id_ed25519.pub 与 id_rsa.pub，返回去重保序的公钥列表。
    两把都推: id_ed25519 给现代系统(5/7/9/15/18/198/199), id_rsa 给 CentOS 6.8(65)。"""
    keys = []
    for name in LOCAL_PUBKEY_NAMES:
        path = os.path.expanduser(f"~/.ssh/{name}")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln.startswith("ssh-") or ln.startswith("ecdsa-"):
                    keys.append(ln)
    if not keys:
        sys.exit("❌ 本机找不到任何公钥 (~/.ssh/id_ed25519.pub 或 id_rsa.pub)")
    return list(dict.fromkeys(keys))


def load_creds():
    if not os.path.exists(CREDS_PATH):
        sys.exit(f"❌ 找不到凭据文件: {CREDS_PATH}\n   请按脚本头注释创建。")
    with open(CREDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        sys.exit("❌ 凭据文件必须是 JSON 数组。")
    return {h["ip"]: h for h in data}


def fetch_monitor_pubkeys(paramiko, creds, monitor_ip):
    """SSH 登录监控机, 读取它 ~/.ssh/*.pub; 若没有则自动生成 ed25519。返回 [pubkey,...]"""
    host = creds.get(monitor_ip)
    if not host:
        print(f"⚠️  凭据文件里没有监控机 {monitor_ip}，跳过拉取它的公钥。")
        return []
    try:
        client = connect(paramiko, host)
    except Exception as exc:
        print(f"⚠️  连接监控机 {monitor_ip} 失败: {exc} —— 跳过它的公钥。")
        return []
    try:
        out, _ = run(client, "cat ~/.ssh/*.pub 2>/dev/null")
        keys = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("ssh-")]
        if keys:
            print(f"📥  监控机 {monitor_ip} 现有公钥 {len(keys)} 把")
            return keys
        # 没有则生成(非交互)
        print(f"🔧  监控机 {monitor_ip} 无密钥对，自动生成 ed25519 ...")
        run(client, 'ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -q -C "ops-relay-monitor"', timeout=30)
        out, _ = run(client, "cat ~/.ssh/id_ed25519.pub 2>/dev/null")
        keys = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("ssh-")]
        print(f"📥  监控机 {monitor_ip} 生成公钥 {len(keys)} 把")
        return keys
    finally:
        client.close()


def ensure_keys(paramiko, host, pubkeys, dry_run=False):
    """把 pubkeys 全部写入 host 的 authorized_keys(幂等)。返回 (status, detail)"""
    try:
        client = connect(paramiko, host)
    except Exception as exc:
        return ("FAIL", f"连接失败: {type(exc).__name__}: {exc}")
    try:
        if dry_run:
            return ("OK", "连通性验证通过（dry-run 未写入）")

        appended, skipped = 0, 0
        for key in pubkeys:
            remote = (
                'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; '
                "grep -qxF '" + key + "' ~/.ssh/authorized_keys && echo HAVE || "
                "{ echo '" + key + "' >> ~/.ssh/authorized_keys && echo NEW; }; "
                'chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
            )
            out, _ = run(client, remote, timeout=30)
            if "NEW" in out:
                appended += 1
            else:
                skipped += 1
        return ("OK", f"新增 {appended} 把 / 已存在 {skipped} 把")
    except Exception as exc:
        return ("FAIL", f"执行失败: {type(exc).__name__}: {exc}")
    finally:
        client.close()


def main():
    ap = argparse.ArgumentParser(description="批量分发 SSH 公钥到内网 Linux 服务器")
    ap.add_argument("--dry-run", action="store_true", help="只验证连通与拉取, 不写 authorized_keys")
    ap.add_argument("--only", nargs="*", default=None, help="只处理指定 IP")
    ap.add_argument("--monitor-ip", default=DEFAULT_MONITOR, help=f"拉取公钥的监控机(默认 {DEFAULT_MONITOR})")
    ap.add_argument("--no-fetch-monitor", action="store_true", help="不拉取监控机公钥, 只推本机公钥")
    args = ap.parse_args()

    paramiko = require_paramiko()
    creds = load_creds()

    local_keys = load_local_pubkeys()
    for k in local_keys:
        print(f"🔑 本机公钥: {k[:38]}...{k.split()[-1]}")
    pubkeys = list(local_keys)
    if not args.no_fetch_monitor:
        pubkeys += fetch_monitor_pubkeys(paramiko, creds, args.monitor_ip)
    pubkeys = list(dict.fromkeys(pubkeys))  # 去重保序
    print(f"🔑 待分发公钥合计 {len(pubkeys)} 把")
    print("-" * 64)

    targets = list(creds.values())
    if args.only:
        want = set(args.only)
        targets = [t for t in targets if t["ip"] in want]

    print(f"目标 {len(targets)} 台主机   模式: {'DRY-RUN' if args.dry_run else '写入'}")
    print("-" * 64)

    tally = {"OK": 0, "SKIP": 0, "FAIL": 0}
    for host in targets:
        status, detail = ensure_keys(paramiko, host, pubkeys, dry_run=args.dry_run)
        tally[status] += 1
        mark = {"OK": "✅", "SKIP": "⏭️ ", "FAIL": "❌"}[status]
        print(f"{mark} {host['ip']:<14} [{host['user']}] {status}  {detail}")

    print("-" * 64)
    print(f"汇总: 成功 {tally['OK']}  跳过 {tally['SKIP']}  失败 {tally['FAIL']}")
    if tally["FAIL"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
