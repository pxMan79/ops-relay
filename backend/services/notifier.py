import httpx
import hashlib
import hmac
import base64
import time
import urllib.parse
from datetime import datetime, timezone

from config import config_loader


def _kw_prefix(dingtalk) -> str:
    """钉钉"关键词"安全设置：消息须含关键词才不会被拒。返回带空格前缀(无则空串)。"""
    return (dingtalk.keyword + " ") if getattr(dingtalk, "keyword", "") else ""


def send_dingtalk_alert_sync(
    server_ip: str,
    alert_type: str,
    severity: str,
    actual_value: float,
    threshold_value: float,
    message: str,
):
    dingtalk = config_loader.get_dingtalk_config()
    if not dingtalk.enabled or not dingtalk.webhook_url:
        return

    severity_text = "⚠️ 警告" if severity == "warning" else "🔴 严重"
    type_text = {"memory": "内存", "disk": "磁盘", "cpu": "CPU"}.get(alert_type, alert_type)

    title = f"{severity_text} {type_text}告警 - {server_ip}"
    text = (
        f"### {_kw_prefix(dingtalk)}{title}\n\n"
        f"- **服务器**: {server_ip}\n"
        f"- **指标**: {type_text}使用率\n"
        f"- **当前值**: {actual_value:.1f}%\n"
        f"- **阈值**: {threshold_value:.1f}%\n"
        f"- **级别**: {severity_text}\n"
        f"- **时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )

    url = dingtalk.webhook_url
    if dingtalk.secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{dingtalk.secret}"
        hmac_code = hmac.new(
            dingtalk.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
        url = f"{url}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }

    if dingtalk.mention_all:
        payload["at"] = {"isAtAll": True}
    elif dingtalk.mention_mobiles:
        payload["at"] = {"atMobiles": dingtalk.mention_mobiles}

    try:
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"📢 钉钉告警已推送: {server_ip} {type_text} {severity}")
    except Exception as e:
        print(f"❌ 钉钉推送失败: {e}")


def send_dingtalk_recovery_sync(server_ip: str, alert_type: str):
    dingtalk = config_loader.get_dingtalk_config()
    if not dingtalk.enabled or not dingtalk.webhook_url:
        return

    type_text = {"memory": "内存", "disk": "磁盘", "cpu": "CPU"}.get(alert_type, alert_type)
    title = f"✅ 恢复通知 - {server_ip}"
    text = (
        f"### {_kw_prefix(dingtalk)}{title}\n\n"
        f"- **服务器**: {server_ip}\n"
        f"- **指标**: {type_text}使用率已恢复正常\n"
        f"- **时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }

    try:
        resp = httpx.post(dingtalk.webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ 钉钉恢复通知推送失败: {e}")


async def send_dingtalk_alert(
    server_ip: str,
    alert_type: str,
    severity: str,
    actual_value: float,
    threshold_value: float,
    message: str,
):
    dingtalk = config_loader.get_dingtalk_config()
    if not dingtalk.enabled or not dingtalk.webhook_url:
        return

    severity_text = "⚠️ 警告" if severity == "warning" else "🔴 严重"
    type_text = {"memory": "内存", "disk": "磁盘", "cpu": "CPU"}.get(alert_type, alert_type)

    title = f"{severity_text} {type_text}告警 - {server_ip}"
    text = (
        f"### {_kw_prefix(dingtalk)}{title}\n\n"
        f"- **服务器**: {server_ip}\n"
        f"- **指标**: {type_text}使用率\n"
        f"- **当前值**: {actual_value:.1f}%\n"
        f"- **阈值**: {threshold_value:.1f}%\n"
        f"- **级别**: {severity_text}\n"
        f"- **时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )

    url = dingtalk.webhook_url
    if dingtalk.secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{dingtalk.secret}"
        hmac_code = hmac.new(
            dingtalk.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
        url = f"{url}&timestamp={timestamp}&sign={sign}"

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }

    if dingtalk.mention_all:
        payload["at"] = {"isAtAll": True}
    elif dingtalk.mention_mobiles:
        payload["at"] = {"atMobiles": dingtalk.mention_mobiles}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            print(f"📢 钉钉告警已推送: {server_ip} {type_text} {severity}")
    except Exception as e:
        print(f"❌ 钉钉推送失败: {e}")


async def send_dingtalk_recovery(server_ip: str, alert_type: str):
    dingtalk = config_loader.get_dingtalk_config()
    if not dingtalk.enabled or not dingtalk.webhook_url:
        return

    type_text = {"memory": "内存", "disk": "磁盘", "cpu": "CPU"}.get(alert_type, alert_type)
    title = f"✅ 恢复通知 - {server_ip}"
    text = (
        f"### {_kw_prefix(dingtalk)}{title}\n\n"
        f"- **服务器**: {server_ip}\n"
        f"- **指标**: {type_text}使用率已恢复正常\n"
        f"- **时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(dingtalk.webhook_url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        print(f"❌ 钉钉恢复通知推送失败: {e}")
