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

from config import config_loader
from schemas.models import DatabaseManager, Server, HistorySnapshot, AlertLog
from models import DiskInfo


def run_ansible_command(
    group: str,
    module: str,
    args: str,
    raw_mode: str = "bash",
) -> Dict[str, Any]:
    """
    执行Ansible命令并返回结果
    raw 模块默认使用 base64 + bash 规避引号问题。
    对于 Windows over SSH 之类不能走 bash 的目标，可用 raw_mode="native"。
    """
    inventory_path = "/etc/ansible/hosts"
    cmd = ["ansible", group]
    if os.path.exists(inventory_path):
        cmd.extend(["-i", inventory_path])

    if module == "raw":
        if raw_mode == "bash":
            import base64

            encoded_cmd = base64.b64encode(args.encode("utf-8")).decode("ascii")
            remote_script = f"base64 -d << 'B64EOF' | bash\n{encoded_cmd}\nB64EOF"
            cmd.extend(["-m", "raw", "-a", remote_script])
        else:
            cmd.extend(["-m", "raw", "-a", args])
    else:
        cmd.extend(["-m", module, "-a", args])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120
    )

    if result.returncode != 0 and not result.stdout.strip():
        stderr = result.stderr.strip() or "未知错误"
        raise RuntimeError(f"Ansible 执行失败 [{group}/{module}]: {stderr}")

    results = {}
    if result.stdout:
        lines = result.stdout.split("\n")
        current_host = None
        current_output = []

        for line in lines:
            if " | " in line and ("CHANGED" in line or "SUCCESS" in line or "FAILED" in line or "UNREACHABLE" in line):
                if current_host:
                    results[current_host] = {
                        "stdout": "\n".join(current_output),
                        "failed": False,
                        "unreachable": False
                    }

                parts = line.split(" | ")
                if len(parts) >= 1:
                    current_host = parts[0].strip()
                    current_output = []

                    if "FAILED" in line or "UNREACHABLE" in line:
                        results[current_host] = {
                            "stdout": "",
                            "failed": "FAILED" in line,
                            "unreachable": "UNREACHABLE" in line,
                            "msg": line
                        }
                        current_host = None
            elif current_host and line.strip():
                if not line.startswith("Shared connection") and not line.startswith("Warning"):
                    current_output.append(line)

        if current_host and current_host not in results:
            results[current_host] = {
                "stdout": "\n".join(current_output),
                "failed": False,
                "unreachable": False
            }

    return results


def format_uptime(secs_str: str) -> str:
    try:
        secs = float(secs_str.split()[0])
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        return f"{d:>2d}天 {h:>2d}小时"
    except Exception:
        return "获取失败"


def parse_uptime_seconds(secs_str: str) -> int:
    try:
        return int(float(secs_str.split()[0]))
    except Exception:
        return 0


def clean_os_name(raw_name: str) -> str:
    clean = re.sub(r" Linux release | release ", " ", raw_name).split(" (")[0].strip()
    match = re.match(r"^([a-zA-Z\s]+ \d+\.\d+)", clean)
    if match:
        return match.group(1)
    return clean


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def bytes_to_gb(size_bytes: Any) -> float:
    value = safe_float(size_bytes)
    if value <= 0:
        return 0.0
    return round(value / (1024 ** 3), 1)


def format_gb_value(size_gb: float) -> str:
    if size_gb <= 0:
        return ""
    if abs(size_gb - round(size_gb)) < 0.05:
        return f"{int(round(size_gb))} GB"
    return f"{size_gb:.1f} GB"


def format_mb_value(size_mb: float) -> str:
    if size_mb <= 0:
        return ""
    if size_mb >= 1024:
        return format_gb_value(round(size_mb / 1024, 1))
    return f"{int(round(size_mb))} MB"


def build_memory_status(total_mb: float, used_mb: float, remain_mb: float) -> str:
    if total_mb <= 0:
        return "获取失败"
    mem_pct = (used_mb / total_mb) * 100 if total_mb > 0 else 0
    return f"{mem_pct:>4.1f}% (余 {remain_mb / 1024:>5.1f}G / 共 {total_mb / 1024:>5.1f}G)"


def parse_linux_storage_devices(lines: List[str]) -> List[Dict[str, Any]]:
    devices = []
    for line in lines:
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        name, size_bytes, model = parts
        devices.append(
            {
                "name": name.strip(),
                "model": model.strip() or "未知型号",
                "size_gb": bytes_to_gb(size_bytes),
            }
        )
    return devices


def parse_windows_storage_devices(lines: List[str]) -> List[Dict[str, Any]]:
    devices = []
    for line in lines:
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        name, size_gb, model = parts
        devices.append(
            {
                "name": name.strip(),
                "model": model.strip() or "未知型号",
                "size_gb": safe_float(size_gb),
            }
        )
    return devices


def parse_gpu_devices(lines: List[str]) -> List[Dict[str, Any]]:
    devices = []
    for line in lines:
        parts = line.split("|", 3)
        if not parts:
            continue
        name = parts[0].strip()
        if not name:
            continue
        memory_mb = safe_float(parts[1].strip()) if len(parts) > 1 else 0.0
        vendor = parts[2].strip() if len(parts) > 2 else ""
        driver = parts[3].strip() if len(parts) > 3 else ""
        devices.append(
            {
                "name": name,
                "vendor": vendor,
                "memory_mb": memory_mb,
                "memory_text": format_mb_value(memory_mb),
                "driver": driver,
            }
        )
    return devices


def build_windows_ps_cmd() -> str:
    return (
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
        '$diskHwStr=""; '
        '$diskHw=Get-CimInstance Win32_DiskDrive; '
        'foreach($d in $diskHw){$name=($d.DeviceID -replace "[`r`n|]"," ").Trim();$model=($d.Model -replace "[`r`n|]"," ").Trim();$size=[math]::Round($d.Size/1GB,1);$diskHwStr+="$name|$size|$model`n"}; '
        '$gpuStr=""; '
        '$gpus=Get-CimInstance Win32_VideoController; '
        'foreach($g in $gpus){$name=($g.Name -replace "[`r`n|]"," ").Trim();$vendor=($g.AdapterCompatibility -replace "[`r`n|]"," ").Trim();$driver=($g.DriverVersion -replace "[`r`n|]"," ").Trim();if($g.AdapterRAM){$ram=[math]::Round($g.AdapterRAM/1MB,0)}else{$ram=0};$gpuStr+="$name|$ram|$vendor|$driver`n"}; '
        "$boot=$mem.LastBootUpTime; $now=Get-Date; $up=$now-[System.Management.ManagementDateTimeConverter]::ToDateTime($boot); $upSecs=[math]::Round($up.TotalSeconds,0); "
        'Write-Output "---OS---"; Write-Output $os; '
        'Write-Output "---CPU---"; Write-Output $cpu; '
        'Write-Output "---MEM---"; Write-Output "$memTotal $memRemain $pct"; '
        'Write-Output "---DISK---"; Write-Output $diskStr; '
        'Write-Output "---DISKHW---"; Write-Output $diskHwStr; '
        'Write-Output "---GPU---"; Write-Output $gpuStr; '
        'Write-Output "---UPTIME---"; Write-Output $upSecs'
    )


def parse_windows_collection_output(
    host: str,
    stdout: str,
    group_name: str = "windows",
) -> Dict[str, Any]:
    os_ver = cpu = mem_str = sys_disk = data_disk_str = uptime = "获取失败"
    data_disks = []
    storage_hw_lines = []
    gpu_lines = []
    memory_total_mb = 0.0
    memory_used_mb = 0.0
    uptime_seconds = 0
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
                memory_total_mb = total
                memory_used_mb = total - remain
                mem_str = build_memory_status(total, total - remain, remain)
        elif mode == "DISK":
            for d in line.split(","):
                if d:
                    parts = d.split("|")
                    if len(parts) == 4:
                        drive, size, free, pct = parts[0], parts[1], parts[2], parts[3]
                        format_str = f"{pct:>3}% (余 {str(free)+'G':>5} / 共 {str(size)+'G':>5})"
                        if drive == "C:":
                            sys_disk = format_str
                        else:
                            data_disks.append(f"{drive:<12} {format_str}")
        elif mode == "DISKHW":
            storage_hw_lines.append(line)
        elif mode == "GPU":
            gpu_lines.append(line)
        elif mode == "UPTIME":
            uptime = format_uptime(line)
            uptime_seconds = parse_uptime_seconds(line)
            mode = ""

    data_disk_str = "\n".join(data_disks) if data_disks else "无数据盘"
    return make_collection_record(
        host=host,
        os_type="windows",
        group_name=group_name,
        status="success",
        os_ver=os_ver,
        uptime=uptime,
        cpu=cpu,
        mem_str=mem_str,
        sys_disk=sys_disk,
        data_disk_str=data_disk_str,
        memory_total_mb=memory_total_mb,
        memory_used_mb=memory_used_mb,
        uptime_seconds=uptime_seconds,
        storage_devices=parse_windows_storage_devices(storage_hw_lines),
        gpu_devices=parse_gpu_devices(gpu_lines),
    )


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


def make_collection_record(
    host: str,
    os_type: str,
    group_name: str,
    status: str = "success",
    error: str = "",
    os_ver: str = "获取失败",
    uptime: str = "获取失败",
    cpu: str = "获取失败",
    mem_str: str = "获取失败",
    sys_disk: str = "获取失败",
    data_disk_str: str = "获取失败",
    memory_total_mb: float = 0.0,
    memory_used_mb: float = 0.0,
    uptime_seconds: int = 0,
    storage_devices: Optional[List[Dict[str, Any]]] = None,
    gpu_devices: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "服务器IP": host,
        "系统版本": os_ver,
        "运行时间": uptime,
        "CPU状态": cpu,
        "内存状态": mem_str,
        "系统盘(/或C盘)": sys_disk,
        "数据盘": data_disk_str,
        "os_type": os_type,
        "group_name": group_name,
        "采集状态": status,
        "错误信息": error,
        "memory_total_mb": memory_total_mb,
        "memory_used_mb": memory_used_mb,
        "uptime_seconds": uptime_seconds,
        "storage_devices": storage_devices or [],
        "gpu_devices": gpu_devices or [],
    }


def get_linux_data() -> List[Dict[str, Any]]:
    # 通过 /proc/stat 计算瞬时 CPU 使用率，避免 top 输出受系统语言影响
    cpu_cmd = (
        "(awk '/^cpu / {print $2+$3+$4, $2+$3+$4+$5+$6+$7+$8}' /proc/stat; "
        "sleep 0.2; "
        "awk '/^cpu / {print $2+$3+$4, $2+$3+$4+$5+$6+$7+$8}' /proc/stat) | "
        "awk '{if(NR==1){u1=$1;t1=$2} else if(NR==2){if($2-t1==0) printf \"0.0\\n\"; "
        "else printf \"%.1f\\n\", ($1-u1)/($2-t1)*100}}'"
    )
    disk_hw_cmd = (
        'if command -v lsblk >/dev/null 2>&1; then '
        'lsblk -b -dn -o NAME,SIZE,MODEL,TYPE 2>/dev/null | '
        """awk '$NF=="disk"{name=$1; size=$2; $1=""; $2=""; $NF=""; sub(/^[ \t]+/, ""); sub(/[ \t]+$/, ""); model=$0; if(model=="") model="未知型号"; printf "%s|%s|%s\\n", name, size, model}'"""
        '; else '
        'for d in /sys/block/*; do n=$(basename "$d"); case "$n" in loop*|ram*) continue;; esac; '
        'sectors=$(cat "$d/size" 2>/dev/null || echo 0); bytes=$((sectors*512)); '
        'model=$(cat "$d/device/model" 2>/dev/null || echo 未知型号); '
        'printf "%s|%s|%s\\n" "$n" "$bytes" "$model"; done; '
        'fi'
    )
    gpu_cmd = (
        'if command -v nvidia-smi >/dev/null 2>&1; then '
        'nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null | '
        """awk -F',' '{name=$1; mem=$2; drv=$3; sub(/^[ \t]+/, "", name); sub(/[ \t]+$/, "", name); sub(/^[ \t]+/, "", mem); sub(/[ \t]+$/, "", mem); sub(/^[ \t]+/, "", drv); sub(/[ \t]+$/, "", drv); printf "%s|%s|%s|%s\\n", name, mem, "NVIDIA", drv}'"""
        '; elif command -v lspci >/dev/null 2>&1; then '
        """lspci 2>/dev/null | grep -Ei 'VGA compatible controller|3D controller|Display controller' | sed 's/^.*: //' | awk '{print $0 "|||"}'"""
        '; elif command -v lshw >/dev/null 2>&1; then '
        r"""lshw -C display 2>/dev/null | awk '/^[[:space:]]*\*-display/{if(seen){printf "%s||%s|%s\\n", name, vendor, driver} seen=1; name=""; vendor=""; driver=""} /^[[:space:]]*product: /{sub(/^[[:space:]]*product: /, ""); name=$0} /^[[:space:]]*vendor: /{sub(/^[[:space:]]*vendor: /, ""); vendor=$0} /^[[:space:]]*configuration: /{if(match($0, /driver=([^ ]+)/, a)) driver=a[1]} END{if(seen){printf "%s||%s|%s\\n", name, vendor, driver}}'"""
        '; else '
        'for f in /sys/class/drm/card*/device/vendor; do [ -f "$f" ] || continue; '
        'd=${f%/vendor}; vendor_id=$(cat "$d/vendor" 2>/dev/null || echo ""); '
        'case "$vendor_id" in 0x10de) vendor="NVIDIA";; 0x8086) vendor="Intel";; 0x1002|0x1022) vendor="AMD";; *) vendor="$vendor_id";; esac; '
        'driver=$(basename "$(readlink "$d/driver" 2>/dev/null)" 2>/dev/null || true); '
        'printf "%s 显卡||%s|%s\\n" "$vendor" "$vendor" "$driver"; '
        'done; '
        'fi'
    )

    cmd = (
        'echo "---OS---"; '
        '(cat /etc/redhat-release 2>/dev/null || { . /etc/os-release 2>/dev/null && echo "${PRETTY_NAME}"; } || uname -sr); '
        "echo ---CPU---; " + cpu_cmd + "; "
        'echo "---MEM---"; free -m; '
        'echo "---MEMINFO---"; grep -E "MemTotal|MemAvailable" /proc/meminfo 2>/dev/null || true; '
        'echo "---DISK---"; df -hP; '
        'echo "---DISKHW---"; ' + disk_hw_cmd + '; '
        'echo "---GPU---"; ' + gpu_cmd + '; '
        'echo "---UPTIME---"; cat /proc/uptime'
    )

    groups = config_loader.get_server_groups()
    linux_group = groups.get("all_linux", [])

    if not linux_group:
        return []

    try:
        json_data = run_ansible_command("all_linux", "raw", cmd)
    except Exception as exc:
        return [
            make_collection_record(
                host=host,
                os_type="linux",
                group_name="all_linux",
                status="failed",
                error=str(exc),
            )
            for host in linux_group
        ]

    data_list = []

    for host in linux_group:
        info = json_data.get(host)
        if not info:
            data_list.append(
                make_collection_record(
                    host=host,
                    os_type="linux",
                    group_name="all_linux",
                    status="missing",
                    error="Ansible 未返回该主机结果",
                )
            )
            continue

        if info.get("failed") or info.get("unreachable"):
            data_list.append(
                make_collection_record(
                    host=host,
                    os_type="linux",
                    group_name="all_linux",
                    status="unreachable" if info.get("unreachable") else "failed",
                    error=info.get("msg", "采集失败"),
                )
            )
            continue

        stdout = info.get("stdout", "")
        os_ver = cpu = mem_str = sys_disk = data_disk_str = uptime = "获取失败"
        data_disks = []
        storage_hw_lines = []
        gpu_lines = []
        memory_total_mb = 0.0
        memory_used_mb = 0.0
        uptime_seconds = 0
        mem_from_free_total = None
        mem_from_free_used = None
        mem_from_free_remain = None
        mem_from_legacy_used = None
        mem_from_legacy_remain = None
        mem_available_mb = None
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
                if len(parts) >= 4:
                    mem_from_free_total = safe_float(parts[1])
                    mem_from_free_used = safe_float(parts[2])
                    mem_from_free_remain = safe_float(parts[3])
            elif mode == "MEM" and ("buffers/cache:" in line or line.startswith("-/+")):
                parts = line.split()
                if len(parts) >= 2:
                    mem_from_legacy_used = safe_float(parts[-2])
                    mem_from_legacy_remain = safe_float(parts[-1])
            elif mode == "MEMINFO":
                if line.startswith("MemTotal:"):
                    memory_total_mb = safe_float(line.split()[1]) / 1024
                elif line.startswith("MemAvailable:"):
                    mem_available_mb = safe_float(line.split()[1]) / 1024
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
            elif mode == "DISKHW":
                storage_hw_lines.append(line)
            elif mode == "GPU":
                gpu_lines.append(line)
            elif mode == "UPTIME":
                uptime = format_uptime(line)
                uptime_seconds = parse_uptime_seconds(line)
                mode = ""

        if memory_total_mb <= 0 and mem_from_free_total is not None:
            memory_total_mb = mem_from_free_total

        if memory_total_mb > 0:
            if mem_available_mb is not None:
                memory_used_mb = max(memory_total_mb - mem_available_mb, 0.0)
                mem_str = build_memory_status(memory_total_mb, memory_used_mb, mem_available_mb)
            elif mem_from_legacy_used is not None and mem_from_legacy_remain is not None:
                memory_used_mb = mem_from_legacy_used
                mem_str = build_memory_status(memory_total_mb, mem_from_legacy_used, mem_from_legacy_remain)
            elif mem_from_free_used is not None and mem_from_free_remain is not None:
                memory_used_mb = mem_from_free_used
                mem_str = build_memory_status(memory_total_mb, mem_from_free_used, mem_from_free_remain)

        data_disk_str = "\n".join(data_disks) if data_disks else "无数据盘"
        storage_devices = parse_linux_storage_devices(storage_hw_lines)
        gpu_devices = parse_gpu_devices(gpu_lines)
        data_list.append(
            make_collection_record(
                host=host,
                os_type="linux",
                group_name="all_linux",
                status="success",
                os_ver=os_ver,
                uptime=uptime,
                cpu=cpu,
                mem_str=mem_str,
                sys_disk=sys_disk,
                data_disk_str=data_disk_str,
                memory_total_mb=memory_total_mb,
                memory_used_mb=memory_used_mb,
                uptime_seconds=uptime_seconds,
                storage_devices=storage_devices,
                gpu_devices=gpu_devices,
            )
        )

    return data_list


def get_windows_ssh_data() -> List[Dict[str, Any]]:
    """
    采集通过 OpenSSH（而非 WinRM）可达的 Windows 主机。

    仅处理 config 中显式声明的 windows_ssh 分组——不做任何
    "Linux 采集失败就当成 Windows 重试"的猜测，OS 类型完全由配置决定。
    """
    groups = config_loader.get_server_groups()
    ssh_group = groups.get("windows_ssh", [])
    if not ssh_group:
        return []

    ps_cmd = build_windows_ps_cmd()
    try:
        json_data = run_ansible_command(
            ",".join(ssh_group),
            "raw",
            ps_cmd,
            raw_mode="native",
        )
    except Exception as exc:
        return [
            make_collection_record(
                host=host,
                os_type="windows",
                group_name="windows_ssh",
                status="failed",
                error=str(exc),
            )
            for host in ssh_group
        ]

    data_list = []
    for host in ssh_group:
        info = json_data.get(host)
        if not info:
            data_list.append(
                make_collection_record(
                    host=host,
                    os_type="windows",
                    group_name="windows_ssh",
                    status="missing",
                    error="Ansible 未返回该主机结果",
                )
            )
            continue
        if info.get("failed") or info.get("unreachable"):
            data_list.append(
                make_collection_record(
                    host=host,
                    os_type="windows",
                    group_name="windows_ssh",
                    status="unreachable" if info.get("unreachable") else "failed",
                    error=info.get("msg", "采集失败"),
                )
            )
            continue
        data_list.append(
            parse_windows_collection_output(host, info.get("stdout", ""), "windows_ssh")
        )

    return data_list


def _winrm_conn_vars(host: str) -> Dict[str, Any]:
    """用 ansible-inventory 解析某 Windows 主机的 WinRM 连接参数（复用 inventory/host_vars 配置）。"""
    try:
        result = subprocess.run(
            ["ansible-inventory", "-i", "/etc/ansible/hosts", "--host", host],
            capture_output=True, text=True, timeout=30,
        )
        vars_map = json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception:
        vars_map = {}
    scheme = vars_map.get("ansible_winrm_scheme", "http")
    port = int(vars_map.get("ansible_port", 5985))
    return {
        "endpoint": "%s://%s:%d/wsman" % (scheme, host, port),
        "user": vars_map.get("ansible_user", "Administrator"),
        "password": vars_map.get("ansible_password", ""),
        "transport": vars_map.get("ansible_winrm_transport", "ntlm"),
        "server_cert_validation": "ignore"
        if vars_map.get("ansible_winrm_server_cert_validation", "ignore") == "ignore"
        else "validate",
    }


def collect_one_via_winrm(host: str, ps_script: str) -> tuple:
    """
    不走 Ansible，直接用 pywinrm 跑 PowerShell 脚本。
    用途：老 Windows（PowerShell < 5.1，Ansible 模块门禁过不去）的兜底采集。
    不改目标服务器——PS3.0+ 即可运行（采集脚本仅用 Get-WmiObject / Get-CimInstance）。
    成功返回 (stdout, None)，失败返回 (None, errmsg)。
    """
    try:
        import winrm
    except ImportError:
        return None, "容器未安装 pywinrm"
    cv = _winrm_conn_vars(host)
    if not cv["password"]:
        return None, "WinRM 兜底：host_vars 缺 ansible_password"
    try:
        session = winrm.Session(
            cv["endpoint"],
            auth=(cv["user"], cv["password"]),
            transport=cv["transport"],
            server_cert_validation=cv["server_cert_validation"],
        )
        resp = session.run_ps(ps_script)
    except Exception as exc:
        return None, "WinRM 连接失败: %s" % exc
    if resp.status_code != 0:
        err = resp.std_err.decode(errors="replace") if resp.std_err else ""
        return None, "WinRM 执行失败 rc=%d %s" % (resp.status_code, err[:200])
    return resp.std_out.decode(errors="replace"), None


def get_windows_data() -> List[Dict[str, Any]]:
    ps_cmd = build_windows_ps_cmd()

    groups = config_loader.get_server_groups()
    windows_group = groups.get("windows", [])
    if not windows_group:
        return []

    # 先尝试 Ansible win_shell（要求目标 PowerShell >= 5.1）
    ansible_results: Dict[str, Any] = {}
    try:
        ansible_results = run_ansible_command("windows", "win_shell", ps_cmd)
    except Exception:
        ansible_results = {}

    data_list = []
    for host in windows_group:
        info = ansible_results.get(host)

        # 1) Ansible 直通成功
        if info and not info.get("failed") and not info.get("unreachable"):
            data_list.append(parse_windows_collection_output(host, info.get("stdout", ""), "windows"))
            continue

        # 2) 真不可达（网络/认证）—— Ansible 和 WinRM 都救不了
        if info and info.get("unreachable"):
            data_list.append(
                make_collection_record(
                    host=host, os_type="windows", group_name="windows",
                    status="unreachable", error=info.get("msg", "采集失败"),
                )
            )
            continue

        # 3) Ansible 失败（如老系统 PowerShell<5.1 的模块门禁）→ raw WinRM 兜底，不改目标机
        stdout, err = collect_one_via_winrm(host, ps_cmd)
        if stdout is None:
            ansible_err = info.get("msg", "Ansible 未返回该主机结果") if info else "Ansible 未返回该主机结果"
            data_list.append(
                make_collection_record(
                    host=host, os_type="windows", group_name="windows",
                    status="failed", error="%s | %s" % (ansible_err, err),
                )
            )
            continue
        data_list.append(parse_windows_collection_output(host, stdout, "windows"))

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


def parse_disk_entries(system_disk: str, data_disks: str) -> List[DiskInfo]:
    disks_list = []

    if system_disk and "%" in system_disk:
        try:
            sys_pct = float(system_disk.split("%")[0].split()[-1])
            size_part = system_disk.split("共")[-1].strip().replace("G", "")
            disks_list.append(
                DiskInfo(
                    mount_point="/",
                    size_gb=float(size_part) if size_part else 0.0,
                    used_gb=0.0,
                    usage_percent=sys_pct,
                    status="normal" if sys_pct < 80 else ("warning" if sys_pct < 90 else "critical"),
                )
            )
        except Exception:
            pass

    if isinstance(data_disks, str) and data_disks and data_disks != "无数据盘":
        for disk_line in data_disks.split("\n"):
            if disk_line.strip() and "%" in disk_line:
                try:
                    mount_point = disk_line.split(":")[0].strip()
                    pct = float(disk_line.split("%")[0].split()[-1])
                    disks_list.append(
                        DiskInfo(
                            mount_point=mount_point,
                            size_gb=0.0,
                            used_gb=0.0,
                            usage_percent=pct,
                            status="normal" if pct < 80 else ("warning" if pct < 90 else "critical"),
                        )
                    )
                except Exception:
                    pass

    return disks_list


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
        self._pending_alerts = []

    def collect_all(self) -> List[Dict[str, Any]]:
        all_data = get_linux_data() + get_windows_ssh_data() + get_windows_data()

        if not all_data:
            return []

        all_data.sort(key=sort_logic)
        return all_data

    def save_to_database(self, data: List[Dict[str, Any]]) -> None:
        db_session = self.db.get_session()

        try:
            for item in data:
                ip = item.get("服务器IP", "")
                collection_status = item.get("采集状态", "success")
                collection_error = item.get("错误信息", "")
                os_type = item.get("os_type", "linux")
                group_name = item.get("group_name", "default")
                os_version = item.get("系统版本", "")

                # 查找或创建服务器记录
                server = db_session.query(Server).filter_by(ip=ip).first()
                if not server:
                    server = Server(
                        ip=ip,
                        hostname=os_version if os_version != "获取失败" else ip,
                        os_type=os_type,
                        os_version=os_version if os_version != "获取失败" else "",
                        group_name=group_name,
                        is_active=True,
                    )
                    db_session.add(server)
                    db_session.flush()
                else:
                    server.os_type = os_type
                    server.group_name = group_name
                    if os_version and os_version != "获取失败":
                        server.hostname = os_version
                        server.os_version = os_version

                # 解析监控数据
                cpu_usage = parse_cpu_value(item.get("CPU状态", "0%"))
                memory_pct = parse_memory_value(item.get("内存状态", "0%"))
                disk_pct = parse_disk_value(item.get("系统盘(/或C盘)", "0%"))

                # 创建历史快照
                snapshot = HistorySnapshot(
                    server_id=server.id,
                    cpu_usage=cpu_usage,
                    memory_total_mb=float(item.get("memory_total_mb", 0.0) or 0.0),
                    memory_used_mb=float(item.get("memory_used_mb", 0.0) or 0.0),
                    memory_percent=memory_pct,
                    disks_info={
                        "cpu_text": item.get("CPU状态", ""),
                        "memory_text": item.get("内存状态", ""),
                        "system_disk": item.get("系统盘(/或C盘)", ""),
                        "data_disks": item.get("数据盘", ""),
                        "storage_devices": item.get("storage_devices", []),
                        "gpu_devices": item.get("gpu_devices", []),
                        "uptime_text": item.get("运行时间", ""),
                        "collection_status": collection_status,
                        "collection_error": collection_error,
                        "group_name": group_name,
                        "os_type": os_type,
                    },
                    uptime_seconds=int(item.get("uptime_seconds", 0) or 0),
                    collected_at=datetime.utcnow(),
                )
                db_session.add(snapshot)

                # 检查告警并记录
                if collection_status == "success":
                    self._check_and_create_alert(
                        db_session, server.id, "memory", memory_pct, ip
                    )
                    self._check_and_create_alert(
                        db_session, server.id, "disk", disk_pct, ip
                    )
                    self._check_and_create_alert(
                        db_session, server.id, "cpu", cpu_usage, ip
                    )

                # 更新服务器最后更新时间
                server.updated_at = datetime.utcnow()
                server.is_active = collection_status == "success"

            db_session.commit()

            # 发送钉钉告警通知
            if self._pending_alerts:
                try:
                    from services.notifier import send_dingtalk_alert_sync
                    for alert_info in self._pending_alerts:
                        send_dingtalk_alert_sync(**alert_info)
                except Exception:
                    pass
                finally:
                    self._pending_alerts.clear()

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
        server_ip: str = "",
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

                self._pending_alerts.append({
                    "server_ip": server_ip,
                    "alert_type": alert_type,
                    "severity": status,
                    "actual_value": value,
                    "threshold_value": threshold,
                    "message": f"{alert_type.upper()} 使用率 {value:.1f}% 超过阈值 {threshold:.1f}%",
                })

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

                # 处理disks_info（可能是字符串或字典）
                disks_info = snap.disks_info
                if isinstance(disks_info, str):
                    try:
                        disks_info = json.loads(disks_info)
                    except Exception:
                        disks_info = {}

                # 解析内存信息（从原始数据重新提取）
                mem_pct = float(snap.memory_percent) if snap.memory_percent else 0.0
                cpu_text = disks_info.get("cpu_text", "")
                memory_text = disks_info.get("memory_text", "")
                system_disk = disks_info.get("system_disk", "")
                data_disks = disks_info.get("data_disks", "")
                storage_devices = disks_info.get("storage_devices", [])
                gpu_devices = disks_info.get("gpu_devices", [])
                uptime_text = disks_info.get("uptime_text", "")
                collection_status = disks_info.get("collection_status", "success")
                collection_error = disks_info.get("collection_error", "")

                # 解析磁盘信息为列表格式
                disks_list = parse_disk_entries(system_disk, data_disks)

                result.append({
                    "id": server.id,
                    "ip": server.ip,
                    "hostname": server.hostname,
                    "os_type": server.os_type or disks_info.get("os_type", ""),
                    "group_name": server.group_name or disks_info.get("group_name", ""),
                    "os_version": server.os_version,
                    "uptime": uptime_text or (format_uptime(str(snap.uptime_seconds)) if snap.uptime_seconds else ""),
                    "cpu_usage": snap.cpu_usage or 0.0,
                    "cpu_text": cpu_text or (f"{snap.cpu_usage:.1f}%" if snap.cpu_usage else ""),
                    "memory": {
                        "total_gb": round((snap.memory_total_mb or 0.0) / 1024, 1),
                        "used_gb": round((snap.memory_used_mb or 0.0) / 1024, 1),
                        "usage_percent": mem_pct,
                        "status": "normal" if mem_pct < 80 else ("warning" if mem_pct < 90 else "critical")
                    },
                    "memory_text": memory_text,
                    "disks": [d.dict() for d in disks_list],
                    "system_disk_text": system_disk,
                    "data_disk_text": data_disks,
                    "hardware": {
                        "memory_size_gb": round((snap.memory_total_mb or 0.0) / 1024, 1),
                        "storage_devices": storage_devices if isinstance(storage_devices, list) else [],
                        "gpu_devices": gpu_devices if isinstance(gpu_devices, list) else [],
                    },
                    "last_update": snap.collected_at.isoformat(),
                    "collection_status": collection_status,
                    "collection_error": collection_error,
                })

            result.sort(key=lambda item: sort_logic({"服务器IP": item.get("ip", "")}))
            return result
        finally:
            db_session.close()
