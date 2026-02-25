import subprocess
import time
from src.tools.base import BaseTool


class PingTool(BaseTool):
    """
    target -> host
    cmd -> ping
    """

    def run(self, target: str, count: int = 4) -> dict:

        start = time.time()

        result = subprocess.run(
            ["ping", "-c", str(count), target],
            capture_output=True,
            text=True
        )

        duration = time.time() - start

        # deal with error situations
        if result.returncode != 0:
            return {
                "tool_name": "ping",
                "target": target,
                "success": False,
                "data": {},
                "raw_output": result.stdout + result.stderr,
                "error": f"ping failed for {target}",
                "duration_seconds": duration
            }

        # parse output
        '''
        4 packets transmitted, 4 received, 0.0% packet loss
        round-trip min/avg/max/stddev = 6.107/11.503/14.397/3.201 ms
        '''
        lines = result.stdout.split("\n")

        packet_loss = None
        avg_rtt = None
        min_rtt = None
        max_rtt = None

        for line in lines:
            if "packet loss" in line:
                for part in line.split():
                    if "%" in part:
                        packet_loss = float(part.replace("%", ""))

            if "round-trip" in line and "/" in line:
                parts = line.split("/")
                min_rtt = float(parts[3].split("= ")[1])
                avg_rtt = float(parts[4])
                max_rtt = float(parts[5])

        return {
            "tool_name": "ping",
            "target": target,
            "success": True,
            "data": {
                "packet_loss_percent": packet_loss,
                "avg_rtt_ms": avg_rtt,
                "min_rtt_ms": min_rtt,
                "max_rtt_ms": max_rtt
            },
            "raw_output": result.stdout,
            "error": "",
            "duration_seconds": duration
        }