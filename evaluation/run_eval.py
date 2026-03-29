# evaluation/run_eval.py
#
# Runs the agent against each Docker fault scenario and scores
# predicted root_cause vs ground truth. Outputs a JSON report.
#
# Usage:
#   python evaluation/run_eval.py                          # single run, default model
#   python evaluation/run_eval.py --model gpt-4o           # single run, specific model
#   python evaluation/run_eval.py --all-models              # full benchmark (5 models x 10 scenarios x 3 runs)
#   python evaluation/run_eval.py --all-models --runs 5     # 5 runs per combo instead of 3
#   python evaluation/run_eval.py --baseline                # naive LLM baseline (no ReAct, no tools)
#
# Prerequisites:
#   cd sandbox && docker compose up -d
#   Make sure .env has all API keys set

import sys
import os
import json
import time
import glob
import subprocess
import argparse
from datetime import datetime

# let imports work from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.core import diagnose_react
from src.agent.llm import get_diagnosis, DEFAULT_MODEL, MODEL_OPTIONS
from src.agent.prompts import ROOT_CAUSE_LABELS


# ---------------------------------------------------------------------------
# scenario definitions — must match Avery's sandbox/faults/ scripts
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "id": 1,
        "name": "DNS Failure",
        "ground_truth": "dns_failure",
        "symptom": "I can't load any websites, nothing resolves",
        "script": "01_dns_failure.sh",
    },
    {
        "id": 2,
        "name": "High Packet Loss",
        "ground_truth": "packet_loss",
        "symptom": "My internet is really unreliable, pages half-load",
        "script": "02_packet_loss.sh",
    },
    {
        "id": 3,
        "name": "High Latency",
        "ground_truth": "high_latency",
        "symptom": "Everything loads but it takes forever",
        "script": "03_high_latency.sh",
    },
    {
        "id": 4,
        "name": "Route Failure",
        "ground_truth": "route_failure",
        "symptom": "I can't reach the server at all, connection refused",
        "script": "04_route_failure.sh",
    },
    {
        "id": 5,
        "name": "Port Blocked",
        "ground_truth": "port_blocked",
        "symptom": "I can ping the server but the website won't load",
        "script": "05_port_blocked.sh",
    },
    {
        "id": 6,
        "name": "Complete Outage",
        "ground_truth": "no_connectivity",
        "symptom": "Nothing works at all, no internet",
        "script": "06_complete_outage.sh",
    },
    {
        "id": 7,
        "name": "Intermittent Loss",
        "ground_truth": "intermittent_loss",
        "symptom": "My connection keeps cutting in and out randomly",
        "script": "07_intermittent_loss.sh",
    },
    {
        "id": 8,
        "name": "Bandwidth Throttle",
        "ground_truth": "bandwidth_throttle",
        "symptom": "Downloads are extremely slow, pages load partially",
        "script": "08_bandwidth_throttle.sh",
    },
    {
        "id": 9,
        "name": "High Jitter",
        "ground_truth": "high_jitter",
        "symptom": "Video calls keep freezing and audio is choppy",
        "script": "09_high_jitter.sh",
    },
    {
        "id": 10,
        "name": "Duplicate Packets",
        "ground_truth": "duplicate_packets",
        "symptom": "Web pages load weirdly, some things appear twice or glitch",
        "script": "10_duplicate_packets.sh",
    },
]

# rough cost per call — used for the accuracy-vs-cost chart
# these are estimates, actual cost depends on token usage
COST_PER_CALL = {
    "gpt-4o-mini":               0.0005,
    "gpt-4o":                    0.008,
    "claude-haiku-4-5-20251001": 0.001,
    "gemini-2.5-flash":          0.0002,
    "llama-3.3-70b-versatile":   0.0004,
}


# ---------------------------------------------------------------------------
# sandbox helpers
# ---------------------------------------------------------------------------

SANDBOX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sandbox")


def inject_fault(scenario):
    """Run the fault injection script from the sandbox directory."""
    script_path = os.path.join("faults", scenario["script"])
    print(f"  Injecting fault: {scenario['name']}...")
    result = subprocess.run(
        ["bash", script_path],
        cwd=SANDBOX_DIR,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Warning: fault injection returned non-zero: {result.stderr}")
    # give tc/iptables a moment to take effect
    time.sleep(2)


def reset_fault():
    """Clear all injected faults so the next scenario starts clean."""
    print("  Resetting faults...")
    subprocess.run(
        ["bash", "faults/reset.sh"],
        cwd=SANDBOX_DIR,
        capture_output=True, text=True,
    )
    time.sleep(2)


# ---------------------------------------------------------------------------
# baseline: naive LLM with no tools and no ReAct
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
    """
    Naive LLM baseline — just the symptom, no tools, no ReAct.
    This is what you'd get if you pasted the symptom into ChatGPT directly.
    We compare against this to show that ReAct + tools actually helps.
    """
    messages = [
        {"role": "system", "content": NAIVE_SYSTEM_PROMPT},
        {"role": "user",   "content": f"User reported: {symptom}"},
    ]

    # just call the llm directly with the naive prompt
    from src.agent.llm import (
        _call_openai, _call_anthropic, _call_google, _call_groq, _parse_json,
        OPENAI_MODELS, ANTHROPIC_MODELS, GOOGLE_MODELS, GROQ_MODELS,
    )

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
# main eval loop
# ---------------------------------------------------------------------------

def run_single(scenario, model=DEFAULT_MODEL, baseline=False):
    """
    Run one scenario: inject fault -> run agent (or baseline) -> check result -> reset.
    Returns a result record dict.
    """
    inject_fault(scenario)

    start = time.time()
    try:
        if baseline:
            diagnosis = run_baseline(scenario["symptom"], model=model)
        else:
            diagnosis = diagnose_react(scenario["symptom"], model=model)
    except Exception as e:
        print(f"  Error during diagnosis: {e}")
        diagnosis = {
            "summary": f"Error: {e}",
            "root_cause": "unknown",
            "recommendations": [],
        }
    elapsed = time.time() - start

    predicted = diagnosis.get("root_cause", "unknown").strip().lower()

    # normalize: if the model returned something outside the enum, mark as unknown
    if predicted not in ROOT_CAUSE_LABELS:
        print(f"  Warning: model returned invalid root_cause '{predicted}', treating as unknown")
        predicted = "unknown"

    correct = predicted == scenario["ground_truth"]

    record = {
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario["name"],
        "scenario_id": scenario["id"],
        "ground_truth": scenario["ground_truth"],
        "model": model,
        "mode": "baseline" if baseline else "react",
        "predicted_root_cause": predicted,
        "correct": correct,
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
    """
    Full evaluation loop. Returns list of result records.
    """
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
    """Print a quick accuracy summary grouped by model."""
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

    # per-scenario breakdown
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
    """Write results to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_path}")


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Evaluate the network diagnostic agent")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model to use (default: gpt-4o-mini)")
    parser.add_argument("--all-models", action="store_true", help="Run all 5 models")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per model/scenario combo")
    parser.add_argument("--baseline", action="store_true", help="Run naive LLM baseline instead of ReAct")
    parser.add_argument("--scenario", type=int, default=None, help="Run only this scenario ID (1-10)")
    parser.add_argument("--output", default=None, help="Output JSON path (default: evaluation/results/<timestamp>.json)")
    args = parser.parse_args()

    # pick models
    if args.all_models:
        models = list(MODEL_OPTIONS.keys())
    else:
        models = [args.model]

    # pick scenarios
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"No scenario with id={args.scenario}. Valid: 1-10")
            sys.exit(1)
    else:
        scenarios = SCENARIOS

    # sanity check: make sure sandbox is running
    check = subprocess.run(
        ["docker", "exec", "client", "echo", "ok"],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print("Error: Docker sandbox not running. Start it first:")
        print("  cd sandbox && docker compose up -d")
        sys.exit(1)

    print(f"Running eval: {len(models)} model(s) x {len(scenarios)} scenario(s) x {args.runs} run(s)")
    print(f"Mode: {'baseline (naive LLM)' if args.baseline else 'react (full agent)'}")
    print()

    results = run_eval(models, scenarios, runs=args.runs, baseline=args.baseline)
    print_summary(results)

    # save
    if args.output:
        output_path = args.output
    else:
        mode = "baseline" if args.baseline else "react"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"evaluation/results/{mode}_{timestamp}.json"

    save_results(results, output_path)


if __name__ == "__main__":
    main()