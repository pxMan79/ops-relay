import subprocess
import json
import re
import socket
import struct
import shutil
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from sqlalchemy import func, and_

from ..config import config_loader
from ..schemas.models import DatabaseManager, Server, HistorySnapshot, AlertLog


def run_ansible_tree(group: str, module: str, args: str) -> Dict[str, Any]:
    out_dir = f"/tmp/ansible_out_{group}"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    cmd = ["ansible", group, "-m", module, "-a", args, "-t", out_dir]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    results = {}
    for fname in os.listdir(out_dir):
        try:
            with open(os.path.join(out_dir, fname), "r", encoding="utf-8") as f:
                results[fname] = json.load(f)
        except Exception:
            pass
    return results


def format_uptime(secs_str: str) -> str:
    try:
        secs = float(secs_str.split()[0])
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        return f"{d:>2d}天 {h:>2d}小时"
    except Exception:
        return "获取失败"


def clean_os_name(raw_name: str) -> str:
    clean = re.sub(r" Linux release | release ", " ", raw_name).split(" (")[0].strip()
    match = re.match(r"^([a-zA-Z\s]+ \d+\.\d+)", clean)
    if match:
        return match.group(1)
    return clean


def check_alert_status(value: float, alert_type: str) -> str:
    thresholds = config_loader.get_alert_thresholds()
    if alert_type == "memory":
        warning = thresholds.memory.warning
        critical = thresholds.memory.critical
    elif alert_type == "disk":
        warning = thresholds.disk.warning
        critical = thresholds.disk.critical
    else:  # cpu
        warning = thresholds.cpu.warning
        critical = thresholds.cpu.critical

    if value >= critical:
        return "critical"
    elif value >= warning:
        return "warning"
    return "normal"


def get_linux_data() -> List[Dict[str, Any]]:
    cpu_cmd = (
        "(awk '/^cpu / {print $2+$3+$4, $2+$3+$4+$5+$6+$7+$8}' /proc/stat; "
        "sleep 0.2; awk '/^cpu / {print $2+$3+$4, $2+$3+$4+$5+$6+$7+$8}' /proc/stat) | "
        "'{if(NR==1){u1=$1;t1=$2} else if(NR==2){if($2-t1==0) printf \"0.0\\n\"; "
        'else printf "%.1f\\n", ($1-u1)/($2-t1)*100}}"'
    )
    cmd = (
        f'echo "---OS---"; cat /etc/redhat-release 2>/dev/null; '
        f"echo "---CPU---"; {cpu_cmd}; "
        f"echo "---MEM---"; free -m; "
        f'echo "---DISK---"; df -hP; '
        f'echo "---UPTIME---"; cat /proc/uptime'
    )

    groups = config_loader.get_server_groups()
    linux_group = groups.get("all_linux", [])

    if not linux_group:
        return []

    json_data = run_ansible_tree("all_linux", "raw", cmd)
    data_list = []

    for host, info in json_data.items():
        if info.get("failed") or info.get("unreachable"):
            continue

        stdout = info.get("stdout", "")
        os_ver = cpu = mem_str = sys_disk = data_disk_str = uptime = "获取失败"
        data_disks = []
        mode = ""

        for line in stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("---"):
                mode = line.replace("-", "")
                continue

            if mode == "OS":
                os_ver = clean_os_name(line)
                mode = ""
            elif mode == "CPU":
                try:
                    cpu = f"{float(line):>5.1f}%"
                except Exception:
                    cpu = line
                mode = ""
            elif mode == "MEM" and line.startswith("Mem:"):
                parts = line.split()
                total, used = float(parts[1]), float(parts[2])
                remain = total - used
                mem_pct = (used / total) * 100 if total > 0 else 0
                mem_str = (
                    f"{mem_pct:>4.1f}% (余 {remain / 1024:>5.1f}G / 共 {total / 1024:>5.1f}G)"
                )
            elif mode == "DISK" and line.startswith("/dev/"):
                parts = line.split()
                size, used, avail, use_pct, mount = (
                    parts[1],
                    parts[2],
                    parts[3],
                    parts[4],
                    parts[5],
                )
                if mount == "/":
                    sys_disk = f"{use_pct:>4} (余 {avail:>5} / 共 {size:>5})"
                elif not mount.startswith("/boot"):
                    data_disks.append(
                        f"{mount+':':<12} {use_pct:>4} (余 {avail:>5} / 共 {size:>5})"
                    )
            elif mode == "UPTIME":
                uptime = format_uptime(line)
                mode = ""

        data_disk_str = "\n".join(data_disks) if data_disks else "无数据盘"
        data_list.append(
            {
                "服务器IP": host,
                "系统版本": os_ver,
                "运行时间": uptime,
                "CPU状态": cpu,
                "内存状态": mem_str,
                "系统盘(/或C盘)": sys_disk,
                "数据盘": data_disk_str,
            }
        )

    return data_list


def get_windows_data() -> List[Dict[str, Any]]:
    ps_cmd = (
        '$os=(Get-WmiObject Win32_OperatingSystem).Caption.Replace("Microsoft Windows ","Win ").Replace(" 专业版"," Pro"); '
        "$cpu=(Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average; "
        "$mem=Get-WmiObject Win32_OperatingSystem; "
        "$memTotal=[math]::Round($mem.TotalVisibleMemorySize/1024,0); "
        "$memUsed=$memTotal-[math]::Round($mem.FreePhysicalMemory/1024,0); "
        "$memRemain=$memTotal-$memUsed; "
        "if($memTotal -eq 0){$pct=0}else{$pct=[math]::Round(($memUsed/$memTotal)*100,1)}; "
        '$disks=Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3"; '
        '$diskStr=""; '
        "foreach($d in $disks){$size=[math]::Round($d.Size/1GB,0);$free=[math]::Round($d.FreeSpace/1GB,0);if($size -eq 0){$dpct=0}else{$dpct=[math]::Round((($size-$free)/$size)*100,0)};$diskStr+=\"$($d.DeviceID)|$($size)|$($free)|$dpct,\"}; "
        "$boot=$mem.LastBootUpTime; $now=Get-Date; $up=$now-[System.Management.ManagementDateTimeConverter]::ToDateTime($boot); $upSecs=[math]::Round($up.TotalSeconds,0); "
        'Write-Output "---OS---`n$os`n---CPU---`n$cpu`n---MEM---`n$memTotal $memRemain $pct`n---DISK---`n$diskStr`n---UPTIME---`n$upSecs"'
    )

    json_data = run_ansible_tree("windows", "win_shell", ps_cmd)
    data_list = []

    for host, info in json_data.items():
        if info.get("failed") or info.get("unreachable"):
            continue

        stdout = info.get("stdout", "")
        os_ver = cpu = mem_str = sys_disk = data_disk_str = uptime = "获取失败"
        data_disks = []
        mode = ""

        for line in stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("---"):
                mode = line.replace("-", "")
                continue

            if mode == "OS":
                os_ver = line
                mode = ""
            elif mode == "CPU":
                try:
                    cpu = f"{float(line):>5.1f}%"
                except Exception:
                    cpu = line
                mode = ""
            elif mode == "MEM":
                parts = line.split()
                if len(parts) >= 3:
                    total, remain, pct = float(parts[0]), float(parts[1]), float(parts[2])
                    mem_str = (
                        f"{pct:>4.1f}% (余 {remain / 1024:>5.1f}G / 共 {total / 1024:>5.1f}G)"
                    )
            elif mode == "DISK":
                for d in line.split(","):
                    if d:
                        parts = d.split("|")
                        if len(parts) == 4:
                            drive, size, free, pct = parts[0], parts[1], parts[2], parts[3]
                            format_str = (
                                f"{pct:>3}% (余 {str(free)+'G':>5} / 共 {str(size)+'G':>5})"
                            )
                            if drive == "C:":
                                sys_disk = format_str
                            else:
                                data_disks.append(f"{drive:<12} {format_str}")
            elif mode == "UPTIME":
                uptime = format_uptime(line)
                mode = ""

        data_disk_str = "\n".join(data_disks) if data_disks else "无数据盘"
        data_list.append(
            {
                "服务器IP": host,
                "系统版本": os_ver,
                "运行时间": uptime,
                "CPU状态": cpu,
                "内存状态": mem_str,
                "系统盘(/或C盘)": sys_disk,
                "数据盘": data_disk_str,
            }
        )

    return data_list


def parse_cpu_value(cpu_str: str) -> float:
    try:
        return float(cpu_str.replace("%", "").strip())
    except Exception:
        return 0.0


def parse_memory_value(mem_str: str) -> tuple:
    try:
        pct = float(mem_str.split("%")[0].strip())
        return pct
    except Exception:
        return 0.0


def parse_disk_value(disk_str: str) -> float:
    try:
        for line in disk_str.split("\n"):
            if "%" in line:
                pct_str = line.split("%")[0].split()[-1]
                return float(pct_str)
    except Exception:
        pass
    return 0.0


def ip_to_int(ip_str: str) -> int:
    try:
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]
    except Exception:
        return 0


def sort_logic(item: Dict[str, Any]) -> tuple:
    ip = item.get("服务器IP", "")
    priority_list = config_loader.get_priority_list()

    for p in priority_list:
        if p.ip == ip:
            return (p.priority, ip_to_int(ip))

    return (0, ip_to_int(ip))


class CollectorService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def collect_all(self) -> List[Dict[str, Any]]:
        all_data = get_linux_data() + get_windows_data()

        if not all_data:
            return []

        all_data.sort(key=sort_logic)
        return all_data

    def save_to_database(self, data: List[Dict[str, Any]]) -> None:
        db_session = self.db.get_session()

        try:
            for item in data:
                ip = item.get("服务器IP", "")

                # 查找或创建服务器记录
                server = db_session.query(Server).filter_by(ip=ip).first()
                if not server:
                    server = Server(
                        ip=ip,
                        hostname=item.get("系统版本", ""),
                        os_type="linux",
                        os_version=item.get("系统版本", ""),
                        is_active=True,
                    )
                    db_session.add(server)
                    db_session.flush()

                # 解析监控数据
                cpu_usage = parse_cpu_value(item.get("CPU状态", "0%"))
                memory_pct = parse_memory_value(item.get("内存状态", "0%"))
                disk_pct = parse_disk_value(item.get("系统盘(/或C盘)", "0%"))

                # 创建历史快照
                snapshot = HistorySnapshot(
                    server_id=server.id,
                    cpu_usage=cpu_usage,
                    memory_percent=memory_pct,
                    disks_info={
                        "system_disk": item.get("系统盘(/或C盘)", ""),
                        "data_disks": item.get("数据盘", ""),
                    },
                    collected_at=datetime.utcnow(),
                )
                db_session.add(snapshot)

                # 检查告警并记录
                self._check_and_create_alert(
                    db_session, server.id, "memory", memory_pct
                )
                self._check_and_create_alert(
                    db_session, server.id, "disk", disk_pct
                )
                self._check_and_create_alert(
                    db_session, server.id, "cpu", cpu_usage
                )

                # 更新服务器最后更新时间
                server.updated_at = datetime.utcnow()

            db_session.commit()
        except Exception as e:
            db_session.rollback()
            raise e
        finally:
            db_session.close()

    def _check_and_create_alert(
        self,
        db_session,
        server_id: int,
        alert_type: str,
        value: float,
    ) -> None:
        status = check_alert_status(value, alert_type)

        if status in ("warning", "critical"):
            thresholds = config_loader.get_alert_thresholds()

            if alert_type == "memory":
                threshold = (
                    thresholds.memory.critical
                    if status == "critical"
                    else thresholds.memory.warning
                )
            elif alert_type == "disk":
                threshold = (
                    thresholds.disk.critical
                    if status == "critical"
                    else thresholds.disk.warning
                )
            else:
                threshold = (
                    thresholds.cpu.critical
                    if status == "critical"
                    else thresholds.cpu.warning
                )

            # 检查是否已有未解决的同类告警
            existing_alert = (
                db_session.query(AlertLog)
                .filter_by(
                    server_id=server_id,
                    alert_type=alert_type,
                    is_resolved=False,
                )
                .first()
            )

            if not existing_alert:
                alert = AlertLog(
                    server_id=server_id,
                    alert_type=alert_type,
                    severity=status,
                    threshold_value=threshold,
                    actual_value=value,
                    message=f"{alert_type.upper()} 使用率 {value:.1f}% 超过阈值 {threshold:.1f}%",
                )
                db_session.add(alert)

    def get_latest_status(self) -> List[Dict]:
        db_session = self.db.get_session()

        try:
            # 获取每台服务器的最新快照
            subquery = (
                db_session.query(
                    HistorySnapshot.server_id,
                    func.max(HistorySnapshot.collected_at).label("max_time"),
                )
                .group_by(HistorySnapshot.server_id)
                .subquery()
            )

            latest_snapshots = (
                db_session.query(HistorySnapshot)
                .join(subquery, and_(
                    HistorySnapshot.server_id == subquery.c.server_id,
                    HistorySnapshot.collected_at == subquery.c.max_time,
                ))
                .all()
            )

            result = []
            for snap in latest_snapshots:
                server = db_session.query(Server).get(snap.server_id)
                result.append({
                    "id": server.id,
                    "ip": server.ip,
                    "hostname": server.hostname,
                    "os_version": server.os_version,
                    "cpu_usage": snap.cpu_usage,
                    "memory_percent": snap.memory_percent,
                    "disks_info": snap.disks_info,
                    "last_update": snap.collected_at.isoformat(),
                })

            return result
        finally:
            db_session.close()
