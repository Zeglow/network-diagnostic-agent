import subprocess
import time
import re
from src.tools.base import BaseTool


class CurlTool(BaseTool):
    """
    target -> host or url
    cmd -> curl
    tests HTTP connectivity and measures download speed
    """

    def run(self, target: str) -> dict:

        start = time.time()

        # build url if target is just a hostname or ip
        if not target.startswith("http"):
            url = f"http://{target}/"
        else:
            url = target

        result = subprocess.run(
            [
                "curl", "-s", "-o", "/dev/null",
                "-w", "%{http_code} %{time_total} %{speed_download} %{size_download}",
                "--max-time", "10",
                url,
            ],
            capture_output=True,
            text=True,
        )

        duration = time.time() - start

        # deal with error (curl returns non-zero on connection failure)
        if result.returncode != 0:
            return {
                "tool_name": "curl",
                "target": target,
                "success": False,
                "data": {},
                "raw_output": result.stdout + result.stderr,
                "error": f"HTTP request failed for {target}: {result.stderr.strip()}",
                "duration_seconds": duration,
            }

        # parse -w output: "200 0.003 12345.000 615"
        parts = result.stdout.strip().split()
        http_code = None
        time_total = None
        speed_download = None
        size_download = None

        try:
            http_code = int(parts[0])
            time_total = float(parts[1])
            speed_download = float(parts[2])
            size_download = int(float(parts[3]))
        except (IndexError, ValueError):
            pass

        return {
            "tool_name": "curl",
            "target": target,
            "success": True,
            "data": {
                "http_code": http_code,
                "time_total_seconds": time_total,
                "speed_download_bytes_per_sec": speed_download,
                "size_download_bytes": size_download,
            },
            "raw_output": result.stdout,
            "error": "",
            "duration_seconds": duration,
        }