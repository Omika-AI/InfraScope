#!/usr/bin/env python3
"""InfraScope Agent — lightweight metric collector for dedicated servers."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    print("psutil is required. Install with: pip install psutil")
    sys.exit(1)

import urllib.request
import urllib.error

INFRASCOPE_URL = os.environ.get("INFRASCOPE_URL", "http://localhost:8000")
AGENT_SECRET = os.environ.get("AGENT_SECRET", "change-me")
REPORT_INTERVAL = int(os.environ.get("REPORT_INTERVAL", "60"))
QUEUE_DIR = Path("/tmp/infrascope-queue")


def get_hostname():
    return socket.gethostname()


def get_server_ip():
    """Get the primary external IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def collect_metrics():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    load = os.getloadavg() if hasattr(os, "getloadavg") else (None,)

    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "disk_percent": disk.percent,
        "network_in_mbps": round(net.bytes_recv / 1024 / 1024, 2),
        "network_out_mbps": round(net.bytes_sent / 1024 / 1024, 2),
        "load_avg_1m": load[0],
    }


def discover_docker_containers():
    """Discover running Docker containers."""
    services = []
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                container = json.loads(line)
                ports_str = container.get("Ports", "")
                port = None
                if ":" in ports_str and "->" in ports_str:
                    try:
                        port = int(ports_str.split(":")[1].split("->")[0])
                    except (ValueError, IndexError):
                        pass
                services.append({
                    "name": container.get("Names", "unknown"),
                    "service_type": "docker",
                    "port": port,
                    "status": "running",
                })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return services


def discover_systemd_services():
    """Discover running systemd services."""
    services = []
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain", "--no-legend"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if parts:
                    name = parts[0].replace(".service", "")
                    services.append({
                        "name": name,
                        "service_type": "systemd",
                        "status": "running",
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return services


def discover_listening_ports():
    """Discover listening TCP ports via ss."""
    services = []
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 4:
                    addr = parts[3]
                    try:
                        port = int(addr.rsplit(":", 1)[1])
                    except (ValueError, IndexError):
                        continue
                    process = parts[6] if len(parts) > 6 else "unknown"
                    name = process.split('"')[1] if '"' in process else f"port-{port}"
                    services.append({
                        "name": name,
                        "service_type": "port",
                        "port": port,
                        "status": "listening",
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return services


def build_report():
    metrics = collect_metrics()
    services = discover_docker_containers() + discover_systemd_services() + discover_listening_ports()

    return {
        "hostname": get_hostname(),
        "server_ip": get_server_ip(),
        **metrics,
        "services": services,
        "secret": AGENT_SECRET,
    }


def send_report(report):
    url = f"{INFRASCOPE_URL.rstrip('/')}/api/agent/report"
    data = json.dumps(report).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        print(f"Failed to send report: {e}")
        return False


def queue_report(report):
    """Queue a report locally if the server is unreachable."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    filename = QUEUE_DIR / f"report-{int(time.time())}.json"
    filename.write_text(json.dumps(report))


def flush_queue():
    """Try to send queued reports."""
    if not QUEUE_DIR.exists():
        return
    for f in sorted(QUEUE_DIR.glob("report-*.json")):
        try:
            report = json.loads(f.read_text())
            if send_report(report):
                f.unlink()
            else:
                break  # Server still down, stop trying
        except Exception:
            f.unlink()  # Corrupted file, remove it


def main():
    print(f"InfraScope Agent starting — reporting to {INFRASCOPE_URL}")
    print(f"Hostname: {get_hostname()}, IP: {get_server_ip()}")
    print(f"Interval: {REPORT_INTERVAL}s")

    while True:
        try:
            flush_queue()
            report = build_report()
            if not send_report(report):
                queue_report(report)
                print("Report queued (server unreachable)")
            else:
                print(f"Report sent — CPU: {report['cpu_percent']}%, MEM: {report['memory_percent']}%")
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(REPORT_INTERVAL)


if __name__ == "__main__":
    main()
