import subprocess
import time

def run_ping(host: str, count: int = 4) -> dict:
    """
    target -> host 
    cmd -> ping
    host:  "google.com" or "8.8.8.8"
    count: ping 4 times by default
    """

    start = time.time()

    result = subprocess.run(
        ["ping", "-c", str(count), host],
        capture_output=True,
        text=True
    )

    # deal with error situations

    '''
    4 packets transmitted, 4 received, 0% packet loss
    round-trip min/avg/max/stddev = 11.8/12.0/12.3/0.2 ms
    '''

    if result.returncode != 0:

        return {
            "tool_name": "ping",
            "target": host,
            "success": False,
            "data": {},
            "raw_output": result.stdout + result.stderr,
            "error": f"ping failed for {host}",
            "duration_seconds": duration
        }
    lines = result.stdout.split("\n")
    
    packet_loss = None
    avg_rtt = None
    for line in lines:
        if "packet loss" in line:
            for part in line.split():
                if "%" in part:
                    packet_loss = float(part.replace("%", ""))
            
        if "round-trip" in line and "/" in line:
            avg_rtt = float(line.split("/")[4])

    duration = time.time() - start

    return {
        "tool_name": "ping",
        "target": host,
        "success": True,
        "data": {
            "packet_loss_percent": packet_loss,
            "avg_rtt_ms": avg_rtt
        },
        "raw_output": result.stdout,
        "error": "",
        "duration_seconds": duration
    }