# evaluation/run_eval.py
#
# Runs the agent against each Docker fault scenario and scores
# predicted root_cause vs ground truth. Outputs a JSON report.
#
# Tools run INSIDE the Docker client container via "docker exec".
# ping and traceroute target the container IP (172.19.0.2) directly,
# dns tests resolution of a real hostname (google.com).

import sys
import os
import re
import json
import time
import subprocess
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.llm import (
    get_react_decision, parse_react_response, _parse_json,
    _call_openai, _call_anthropic, _call_google, _call_groq,
    DEFAULT_MODEL, MODEL_OPTIONS,
    OPENAI_MODELS, ANTHROPIC_MODELS, GOOGLE_MODELS, GROQ_MODELS,
)
from src.agent.prompts import (
    REACT_SYSTEM_PROMPT, ROOT_CAUSE_LABELS,
    build_react_observation, build_react_initial_message,
)

# target container IP on the testnet bridge — use IP not hostname
# so ping/traceroute don't depend on DNS working
TARGET_IP = "172.18.0.2"
DNS_TEST_DOMAIN = "google.com"


SCENARIOS = [
    {"id": 1,  "name": "DNS Failure",       "ground_truth": "dns_failure",       "symptom": "I can't load any websites, nothing resolves",              "script": "01_dns_failure.sh"},
    {"id": 2,  "name": "High Packet Loss",  "ground_truth": "packet_loss",       "symptom": "My internet is really unreliable, pages half-load",        "script": "02_packet_loss.sh"},
    {"id": 3,  "name": "High Latency",      "ground_truth": "high_latency",      "symptom": "Everything loads but it takes forever",                    "script": "03_high_latency.sh"},
    {"id": 4,  "name": "Route Failure",      "ground_truth": "route_failure",     "symptom": "I can't reach the server at all, connection refused",      "script": "04_route_failure.sh"},
    {"id": 5,  "name": "Port Blocked",       "ground_truth": "port_blocked",      "symptom": "I can ping the server but the website won't load",        "script": "05_port_blocked.sh"},
    {"id": 6,  "name": "Complete Outage",    "ground_truth": "no_connectivity",   "symptom": "Nothing works at all, no internet",                       "script": "06_complete_outage.sh"},
    {"id": 7,  "name": "Intermittent Loss",  "ground_truth": "intermittent_loss", "symptom": "My connection keeps cutting in and out randomly",          "script": "07_intermittent_loss.sh"},
    {"id": 8,  "name": "Bandwidth Throttle", "ground_truth": "bandwidth_throttle","symptom": "Downloads are extremely slow, pages load partially",       "script": "08_bandwidth_throttle.sh"},
    {"id": 9,  "name": "High Jitter",        "ground_truth": "high_jitter",       "symptom": "Video calls keep freezing and audio is choppy",            "script": "09_high_jitter.sh"},
    {"id": 10, "name": "Duplicate Packets",  "ground_truth": "duplicate_packets", "symptom": "Web pages load weirdly, some things appear twice or glitch","script": "10_duplicate_packets.sh"},
]

COST_PER_CALL = {
    "gpt-4o-mini":               0.0005,
    "gpt-4o":                    0.008,
    "claude-haiku-4-5-20251001": 0.001,
    "gemini-2.5-flash":          0.0002,
    "llama-3.3-70b-versatile":   0.0004,
}

SANDBOX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sandbox")


def inject_fault(scenario):
    script_path = os.path.join("faults", scenario["script"])
    print(f"  Injecting fault: {scenario['name']}...")
    result = subprocess.run(["bash", script_path], cwd=SANDBOX_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Warning: fault script error: {result.stderr.strip()}")
    time.sleep(2)


def reset_fault():
    print("  Resetting faults...")
    subprocess.run(["bash", "faults/reset.sh"], cwd=SANDBOX_DIR, capture_output=True, text=True)
    time.sleep(2)


# ---------------------------------------------------------------------------
# docker tool execution — runs inside the client container
# ---------------------------------------------------------------------------

def docker_exec(cmd, timeout=30):
    try:
        result = subprocess.run(
            ["docker", "exec", "client"] + cmd,
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1


def run_ping_docker(target=TARGET_IP, count=10):
    """Ping the target IP inside the container. Uses 10 packets to detect packet loss."""
    start = time.time()
    stdout, stderr, rc = docker_exec(["ping", "-c", str(count), "-W", "3", target], timeout=45)
    duration = time.time() - start

    if rc != 0 and "100% packet loss" not in stdout:
        return {
            "tool_name": "ping", "target": target, "success": False,
            "data": {}, "raw_output": stdout + stderr,
            "error": f"ping failed for {target}", "duration_seconds": duration,
        }

    lines = stdout.split("\n")
    packet_loss = avg_rtt = min_rtt = max_rtt = mdev = None

    for line in lines:
        if "packet loss" in line:
            for part in line.split():
                if "%" in part:
                    try: packet_loss = float(part.replace("%", ""))
                    except ValueError: pass
        if "min/avg/max" in line and "/" in line:
            stats = line.split("=")[-1].strip().split("/")
            try:
                min_rtt = float(stats[0])
                avg_rtt = float(stats[1])
                max_rtt = float(stats[2])
                if len(stats) > 3:
                    mdev = float(stats[3].split()[0])
            except (IndexError, ValueError):
                pass

    return {
        "tool_name": "ping", "target": target, "success": True,
        "data": {"packet_loss_percent": packet_loss, "avg_rtt_ms": avg_rtt,
                 "min_rtt_ms": min_rtt, "max_rtt_ms": max_rtt, "mdev_ms": mdev},
        "raw_output": stdout, "error": "", "duration_seconds": duration,
    }


def run_dns_docker(target=DNS_TEST_DOMAIN):
    """Test DNS resolution of a real domain inside the container."""
    start = time.time()
    stdout, stderr, rc = docker_exec(["nslookup", target], timeout=15)
    duration = time.time() - start

    if rc != 0:
        return {
            "tool_name": "dns", "target": target, "success": False,
            "data": {}, "raw_output": stdout + stderr,
            "error": f"DNS lookup failed for {target}", "duration_seconds": duration,
        }

    lines = stdout.split("\n")
    ip_addresses = []
    in_answer = False
    for line in lines:
        if "Non-authoritative answer" in line or "Name:" in line:
            in_answer = True
        if in_answer and line.strip().startswith("Address:"):
            ip_addresses.append(line.split()[1])

    return {
        "tool_name": "dns", "target": target, "success": True,
        "data": {"resolved": len(ip_addresses) > 0, "ip_addresses": ip_addresses,
                 "response_time_ms": round(duration * 1000, 2)},
        "raw_output": stdout, "error": "", "duration_seconds": duration,
    }


def run_traceroute_docker(target=TARGET_IP):
    """Traceroute to target IP inside the container."""
    start = time.time()
    stdout, stderr, rc = docker_exec(["traceroute", "-m", "10", "-w", "2", target], timeout=60)
    duration = time.time() - start

    if rc != 0:
        return {
            "tool_name": "traceroute", "target": target, "success": False,
            "data": {}, "raw_output": stdout + stderr,
            "error": f"traceroute failed for {target}", "duration_seconds": duration,
        }

    lines = stdout.split("\n")
    hops = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        hop_match = re.match(r"^(\d+)\s", line)
        if not hop_match:
            continue
        hop_num = int(hop_match.group(1))
        ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
        ip = ip_match.group(1) if ip_match else None
        times = re.findall(r"(\d+\.\d+)\s+ms", line)
        rtt_ms = round(sum(float(t) for t in times) / len(times), 3) if times else None
        timed_out = "*" in line
        hops.append({"hop_num": hop_num, "ip": ip, "rtt_ms": rtt_ms, "timed_out": timed_out})

    return {
        "tool_name": "traceroute", "target": target, "success": True,
        "data": {"hops": hops, "total_hops": len(hops),
                 "reached_destination": len(hops) > 0 and hops[-1]["ip"] is not None},
        "raw_output": stdout, "error": "", "duration_seconds": duration,
    }


DOCKER_TOOLS = {
    "ping":       run_ping_docker,
    "dns":        run_dns_docker,
    "traceroute": run_traceroute_docker,
}

MAX_STEPS = 5


def diagnose_react_docker(symptom, model=DEFAULT_MODEL):
    """ReAct loop with tools running inside the Docker client container."""
    print(f"\nAnalyzing: {symptom}")
    print(f"Model: {model}")
    print("Starting ReAct loop (Docker mode)...\n")

    conversation = [
        {"role": "system",    "content": REACT_SYSTEM_PROMPT},
        {"role": "user",      "content": build_react_initial_message(symptom)},
    ]

    tools_used = set()
    react_trace = []

    for step in range(MAX_STEPS):
        print(f"  Step {step + 1}: asking LLM what to do next...")

        raw_response = get_react_decision(conversation, model=model)
        parsed = parse_react_response(raw_response)
        conversation.append({"role": "assistant", "content": raw_response})

        if parsed["type"] == "action":
            tool_name = parsed["tool"]
            thought = parsed["thought"]
            print(f"  Thought: {thought}")
            print(f"  Action:  run {tool_name}")

            react_trace.append({"step": step + 1, "thought": thought, "action": tool_name})

            if tool_name not in DOCKER_TOOLS:
                observation = f"OBSERVATION: Unknown tool '{tool_name}'. Available: ping, dns, traceroute"
            elif tool_name in tools_used:
                observation = f"OBSERVATION: {tool_name} already ran. Use a different tool or provide diagnosis."
            else:
                result = DOCKER_TOOLS[tool_name]()
                tools_used.add(tool_name)
                observation = build_react_observation(tool_name, result)
                react_trace[-1]["observation"] = result

            print(f"  Observation: {observation[:150]}...")
            conversation.append({"role": "user", "content": observation})

        elif parsed["type"] == "diagnosis":
            thought = parsed["thought"]
            diagnosis = parsed["diagnosis"]
            print(f"  Thought: {thought}")
            print(f"  -> Diagnosis ready after {step + 1} step(s), {len(tools_used)} tool(s) used\n")

            react_trace.append({"step": step + 1, "thought": thought, "action": "DIAGNOSE"})
            diagnosis["react_trace"] = react_trace
            diagnosis["tools_used"] = list(tools_used)
            diagnosis["steps_taken"] = step + 1
            return diagnosis
        else:
            print(f"  Warning: could not parse LLM response at step {step + 1}")
            conversation.append({
                "role": "user",
                "content": "OBSERVATION: Could not parse your response. Please follow the exact format."
            })

    # safety fallback
    print(f"  Warning: reached MAX_STEPS ({MAX_STEPS}), forcing conclusion...")
    raw_response = get_react_decision(conversation + [{
        "role": "user",
        "content": "You have reached the maximum number of steps. Provide your DIAGNOSIS now based on what you have."
    }], model=model)
    parsed = parse_react_response(raw_response)
    diagnosis = parsed.get("diagnosis", {
        "summary": "Diagnosis incomplete — maximum steps reached.",
        "root_cause": "unknown",
        "recommendations": ["Please try again with a more specific symptom description."]
    })
    diagnosis["react_trace"] = react_trace
    diagnosis["tools_used"] = list(tools_used)
    diagnosis["steps_taken"] = MAX_STEPS
    return diagnosis


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------

NAIVE_SYSTEM_PROMPT = """You are a network diagnostic assistant.

A user has reported a network problem. Based ONLY on their description (no diagnostic tools available),
guess the most likely root cause.

Respond with a JSON object:
{
    "summary": "your best guess explanation",
    "root_cause": "<label>",
    "recommendations": ["suggestion 1", "suggestion 2"]
}

root_cause must be exactly one of:
dns_failure | packet_loss | high_latency | route_failure | port_blocked |
no_connectivity | intermittent_loss | bandwidth_throttle | high_jitter |
duplicate_packets | unknown
"""


def run_baseline(symptom, model=DEFAULT_MODEL):
    messages = [
        {"role": "system", "content": NAIVE_SYSTEM_PROMPT},
        {"role": "user",   "content": f"User reported: {symptom}"},
    ]
    if model in OPENAI_MODELS:
        raw = _call_openai(messages, model)
    elif model in ANTHROPIC_MODELS:
        raw = _call_anthropic(messages, model)
    elif model in GOOGLE_MODELS:
        raw = _call_google(messages, model)
    elif model in GROQ_MODELS:
        raw = _call_groq(messages, model)
    else:
        raw = _call_openai(messages, model)
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# eval loop
# ---------------------------------------------------------------------------

def run_single(scenario, model=DEFAULT_MODEL, baseline=False):
    inject_fault(scenario)
    start = time.time()
    try:
        if baseline:
            diagnosis = run_baseline(scenario["symptom"], model=model)
        else:
            diagnosis = diagnose_react_docker(scenario["symptom"], model=model)
    except Exception as e:
        print(f"  Error during diagnosis: {e}")
        diagnosis = {"summary": f"Error: {e}", "root_cause": "unknown", "recommendations": []}
    elapsed = time.time() - start

    predicted = diagnosis.get("root_cause", "unknown").strip().lower()
    if predicted not in ROOT_CAUSE_LABELS:
        print(f"  Warning: invalid root_cause '{predicted}', treating as unknown")
        predicted = "unknown"

    correct = predicted == scenario["ground_truth"]
    record = {
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario["name"], "scenario_id": scenario["id"],
        "ground_truth": scenario["ground_truth"], "model": model,
        "mode": "baseline" if baseline else "react",
        "predicted_root_cause": predicted, "correct": correct,
        "tools_used": diagnosis.get("tools_used", []),
        "steps_taken": diagnosis.get("steps_taken", 0),
        "duration_seconds": round(elapsed, 2),
        "cost_estimate_usd": COST_PER_CALL.get(model, 0) * diagnosis.get("steps_taken", 1),
        "summary": diagnosis.get("summary", ""),
    }
    reset_fault()
    status = "CORRECT" if correct else "WRONG"
    print(f"  [{status}] predicted={predicted}  truth={scenario['ground_truth']}  ({elapsed:.1f}s)\n")
    return record


def run_eval(models, scenarios, runs=1, baseline=False):
    all_results = []
    for model in models:
        print(f"\n{'='*60}")
        print(f"Model: {model} ({'baseline' if baseline else 'react'})")
        print(f"{'='*60}\n")
        for run_num in range(1, runs + 1):
            if runs > 1:
                print(f"--- Run {run_num}/{runs} ---\n")
            for scenario in scenarios:
                record = run_single(scenario, model=model, baseline=baseline)
                record["run"] = run_num
                all_results.append(record)
    return all_results


def print_summary(results):
    from collections import defaultdict
    by_model = defaultdict(list)
    for r in results:
        key = f"{r['model']} ({r['mode']})"
        by_model[key].append(r)
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}\n")
    for model_key, records in sorted(by_model.items()):
        correct = sum(1 for r in records if r["correct"])
        total = len(records)
        acc = correct / total * 100 if total > 0 else 0
        avg_steps = sum(r["steps_taken"] for r in records) / total if total > 0 else 0
        avg_cost = sum(r["cost_estimate_usd"] for r in records) / total if total > 0 else 0
        print(f"  {model_key}")
        print(f"    Accuracy:   {correct}/{total} ({acc:.1f}%)")
        print(f"    Avg steps:  {avg_steps:.1f}")
        print(f"    Avg cost:   ${avg_cost:.4f}")
        print()
    by_scenario = defaultdict(list)
    for r in results:
        by_scenario[r["scenario"]].append(r)
    print("Per-scenario breakdown:")
    for scenario, records in sorted(by_scenario.items()):
        correct = sum(1 for r in records if r["correct"])
        total = len(records)
        print(f"  {scenario:25s}  {correct}/{total}")
    print()


def save_results(results, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate the network diagnostic agent")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use (default: gpt-4o-mini)")
    parser.add_argument("--all-models", action="store_true", help="Run all 5 models")
    parser.add_argument("--runs", type=int, default=3, help="Runs per model/scenario combo")
    parser.add_argument("--baseline", action="store_true", help="Run naive LLM baseline")
    parser.add_argument("--scenario", type=int, default=None, help="Run only this scenario ID (1-10)")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    if args.all_models:
        models = list(MODEL_OPTIONS.keys())
    else:
        models = [args.model]
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"No scenario with id={args.scenario}. Valid: 1-10")
            sys.exit(1)
    else:
        scenarios = SCENARIOS

    check = subprocess.run(["docker", "exec", "client", "echo", "ok"], capture_output=True, text=True)
    if check.returncode != 0:
        print("Error: Docker sandbox not running.")
        print("  cd sandbox && docker compose up -d")
        sys.exit(1)

    print(f"Running eval: {len(models)} model(s) x {len(scenarios)} scenario(s) x {args.runs} run(s)")
    print(f"Mode: {'baseline (naive LLM)' if args.baseline else 'react (full agent)'}")
    print()

    results = run_eval(models, scenarios, runs=args.runs, baseline=args.baseline)
    print_summary(results)

    if args.output:
        output_path = args.output
    else:
        mode = "baseline" if args.baseline else "react"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"evaluation/results/{mode}_{timestamp}.json"
    save_results(results, output_path)


if __name__ == "__main__":
    main()