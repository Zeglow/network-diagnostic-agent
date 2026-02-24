import subprocess
import time
import re

def run_traceroute(host: str, max_hops: int = 30) -> dict:
    """
    target -> host
    cmd -> traceroute
    host:     "google.com"
    max_hops: 30
    """
    start = time.time()

    result = subprocess.run(
        ["traceroute", "-m", str(max_hops), host],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return {
            "tool_name": "traceroute",
            "target": host,
            "success": False,
            "data": {},
            "raw_output": result.stdout + result.stderr,
            "error": f"traceroute failed for {host}",
            "duration_seconds": duration
        }
    
    duration = time.time() - start

    lines = result.stdout.split("\n")
    hops = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # extract hops
        # skip intent
        hop_match = re.match(r"^(\d+)\s", line)
        if not hop_match:
            continue
        hop_num = int(hop_match.group(1))

        # extract ip
        ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
        ip = ip_match.group(1) if ip_match else None

        # extract delays
        times = re.findall(r"(\d+\.\d+)\s+ms", line)
        avg_rtt = round(sum(float(t) for t in times) / len(times), 3) if times else None

        # identify timeout
        timed_out = "*" in line

        hops.append({
            "hop": hop_num,
            "ip": ip,
            "avg_rtt_ms": avg_rtt,
            "timed_out": timed_out
        })

    return {
        "tool_name": "traceroute",
        "target": host,
        "success": True,
        "data": {
            "hops": hops,
            "total_hops": len(hops),
            "completed": hops[-1]["ip"] is not None and hops[-1]["avg_rtt_ms"] is not None
        },
        "raw_output": result.stdout,
        "error": "",
        "duration_seconds": duration
    }