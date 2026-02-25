import subprocess
import time
from src.tools.base import BaseTool


class DNSTool(BaseTool):
    """
    target -> host
    cmd -> nslookup
    """

    def run(self, target: str) -> dict:

        start = time.time()

        result = subprocess.run(
            ["nslookup", target],
            capture_output=True,
            text=True
        )

        duration = time.time() - start

        # deal with error
        if result.returncode != 0:
            return {
                "tool_name": "dns",
                "target": target,
                "success": False,
                "data": {},
                "raw_output": result.stdout + result.stderr,
                "error": f"DNS lookup failed for {target}",
                "duration_seconds": duration
            }

        # parse output
        '''
        Server:         10.152.120.248
        Address:        10.152.120.248#53

        Non-authoritative answer:
        Name:   google.com
        Address: 142.250.189.238
        '''
        lines = result.stdout.split("\n")

        ip_addresses = []

        for line in lines:
            if line.startswith("Address:") and "#" not in line:
                ip_addresses.append(line.split()[1])

        return {
            "tool_name": "dns",
            "target": target,
            "success": True,
            "data": {
                "resolved": len(ip_addresses) > 0,
                "ip_addresses": ip_addresses,
                "response_time_ms": round(duration * 1000, 2)
            },
            "raw_output": result.stdout,
            "error": "",
            "duration_seconds": duration
        }