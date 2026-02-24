import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.ping import run_ping
from src.tools.dns import run_dns
from src.tools.traceroute import run_traceroute

def main():
    print("=" * 50)
    print("  Network Diagnostic Agent")
    print("=" * 50)
    print("Describe your network issue and I will run")
    print("the appropriate diagnostics for you.")
    print("Type 'exit' to quit.")
    print("=" * 50)

    while True:
        user_input = input("\nWhat's your network issue? > ").strip()

        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        if not user_input:
            print("Please describe your issue.")
            continue

        diagnose(user_input)

def diagnose(user_input: str):
    print(f"\nAnalyzing: '{user_input}'")
    print("Running diagnostics...\n")

    # 从用户输入里提取目标 host
    # 现在用简单方法：找输入里有没有域名，没有就默认 google.com
    words = user_input.lower().split()
    host = "google.com"  # 默认目标
    for word in words:
        if "." in word and not word.startswith("."):
            host = word
            break

    print(f"Target host: {host}\n")

    # 运行三个工具
    print("[1/3] Running ping...")
    ping_result = run_ping(host)
    print(f"      Packet loss: {ping_result['data'].get('packet_loss_percent')}%")
    print(f"      Avg RTT: {ping_result['data'].get('avg_rtt_ms')} ms")

    print("\n[2/3] Running DNS lookup...")
    dns_result = run_dns(host)
    print(f"      DNS server: {dns_result['data'].get('dns_server')}")
    print(f"      Resolved IP: {dns_result['data'].get('resolved_ip')}")

    print("\n[3/3] Running traceroute...")
    traceroute_result = run_traceroute(host)
    print(f"      Total hops: {traceroute_result['data'].get('total_hops')}")
    print(f"      Completed: {traceroute_result['data'].get('completed')}")

    print("\n--- Diagnostic Summary ---")
    print(f"Host:         {host}")
    print(f"Reachable:    {ping_result['success']}")
    print(f"DNS resolved: {dns_result['success']}")
    print(f"Route traced: {traceroute_result['success']}")
    print("--------------------------")
    print("(Agent interpretation coming in Iter 2)")
    
if __name__ == "__main__":
    main()