import subprocess
import time
import re
from src.tools.base import BaseTool


class TracerouteTool(BaseTool):
    """
    target -> host
    cmd -> traceroute
    """

    def run(self, target: str, max_hops: int = 30) -> dict:

        start = time.time()

        result = subprocess.run(
            ["traceroute", "-m", str(max_hops), target],
            capture_output=True,
            text=True
        )

        duration = time.time() - start

        # deal with error
        if result.returncode != 0:
            return {
                "tool_name": "traceroute",
                "target": target,
                "success": False,
                "data": {},
                "raw_output": result.stdout + result.stderr,
                "error": f"traceroute failed for {target}",
                "duration_seconds": duration
            }

        # parse output
        lines = result.stdout.split("\n")
        hops = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # skip indented lines (multi-path hops)
            hop_match = re.match(r"^(\d+)\s", line)
            if not hop_match:
                continue
            hop_num = int(hop_match.group(1))

            # extract ip
            ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
            ip = ip_match.group(1) if ip_match else None

            # extract delays
            times = re.findall(r"(\d+\.\d+)\s+ms", line)
            rtt_ms = round(sum(float(t) for t in times) / len(times), 3) if times else None

            # identify timeout
            timed_out = "*" in line

            hops.append({
                "hop_num": hop_num,
                "ip": ip,
                "rtt_ms": rtt_ms,
                "timed_out": timed_out
            })

        return {
            "tool_name": "traceroute",
            "target": target,
            "success": True,
            "data": {
                "hops": hops,
                "total_hops": len(hops),
                "reached_destination": len(hops) > 0 and hops[-1]["ip"] is not None and hops[-1]["rtt_ms"] is not None
            },
            "raw_output": result.stdout,
            "error": "",
            "duration_seconds": duration
        }