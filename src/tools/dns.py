import subprocess
import time

def run_dns(host: str) -> dict:
    """
    target -> host
    cmd -> nslookup
    host: "google.com"
    """

    start = time.time()

    result = subprocess.run(
        ["nslookup", host],
        capture_output=True,
        text=True
    )

    duration = time.time() - start

    # deal with error
    if result.returncode != 0:
        return {
            "tool_name": "dns",
            "target": host,
            "success": False,
            "data": {},
            "raw_output": result.stdout + result.stderr,
            "error": f"DNS lookup failed for {host}",
            "duration_seconds": duration
        }
    
    lines = result.stdout.split("\n")

    dns_server = None
    resolved_ip = None

    for line in lines:
        if line.startswith("Server:"):
            dns_server = line.split()[1]
        
        if line.startswith("Address:") and "#" not in line:
            resolved_ip = line.split()[1]
    return {
        "tool_name": "dns",
        "target": host,
        "success": True,
        "data": {
            "dns_server": dns_server,
            "resolved_ip": resolved_ip
        },
        "raw_output": result.stdout,
        "error": "",
        "duration_seconds": duration
    }