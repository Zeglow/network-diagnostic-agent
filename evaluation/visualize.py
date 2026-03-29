# evaluation/visualize.py
#
# Reads eval results JSON and generates charts:
#   1. Accuracy vs Cost scatter plot (one dot per model)
#   2. Per-scenario accuracy heatmap (model x scenario)
#   3. React vs Baseline comparison bar chart (if both results provided)
#
# Usage:
#   python evaluation/visualize.py evaluation/results/react_20260328.json
#   python evaluation/visualize.py react.json --baseline baseline.json
#   python evaluation/visualize.py react.json --output charts/

import sys
import os
import json
import argparse
from collections import defaultdict

try:
    import matplotlib
    matplotlib.use("Agg")  # no display needed, just save to file
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    sys.exit(1)


# color palette — one per model so charts are consistent
MODEL_COLORS = {
    "gpt-4o-mini":               "#10a37f",
    "gpt-4o":                    "#1a7f5a",
    "claude-haiku-4-5-20251001": "#d97706",
    "gemini-2.5-flash":          "#4285f4",
    "llama-3.3-70b-versatile":   "#8b5cf6",
}

# shorter names for chart labels
MODEL_SHORT = {
    "gpt-4o-mini":               "GPT-4o-mini",
    "gpt-4o":                    "GPT-4o",
    "claude-haiku-4-5-20251001": "Claude Haiku",
    "gemini-2.5-flash":          "Gemini Flash",
    "llama-3.3-70b-versatile":   "Llama 3.3 70B",
}


def load_results(path):
    with open(path) as f:
        return json.load(f)


def aggregate_by_model(results):
    """Group results by model and compute accuracy + avg cost."""
    by_model = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    stats = {}
    for model, records in by_model.items():
        total = len(records)
        correct = sum(1 for r in records if r["correct"])
        avg_cost = sum(r.get("cost_estimate_usd", 0) for r in records) / total
        avg_steps = sum(r.get("steps_taken", 0) for r in records) / total
        stats[model] = {
            "accuracy": correct / total * 100,
            "avg_cost": avg_cost,
            "avg_steps": avg_steps,
            "correct": correct,
            "total": total,
        }
    return stats


def aggregate_by_model_scenario(results):
    """Build a model x scenario accuracy matrix."""
    combos = defaultdict(list)
    for r in results:
        combos[(r["model"], r["scenario"])].append(r["correct"])

    # get unique models and scenarios in order
    models = sorted(set(r["model"] for r in results), key=lambda m: list(MODEL_SHORT.keys()).index(m) if m in MODEL_SHORT else 99)
    scenarios = sorted(set(r["scenario"] for r in results))

    matrix = []
    for model in models:
        row = []
        for scenario in scenarios:
            runs = combos.get((model, scenario), [])
            acc = sum(runs) / len(runs) * 100 if runs else 0
            row.append(acc)
        matrix.append(row)

    return models, scenarios, matrix


# ---------------------------------------------------------------------------
# chart 1: accuracy vs cost scatter
# ---------------------------------------------------------------------------

def plot_accuracy_vs_cost(stats, output_dir):
    fig, ax = plt.subplots(figsize=(8, 5))

    for model, s in stats.items():
        color = MODEL_COLORS.get(model, "#666666")
        label = MODEL_SHORT.get(model, model)
        ax.scatter(
            s["avg_cost"] * 1000,  # convert to millicents for readability
            s["accuracy"],
            s=120, c=color, label=label, zorder=5, edgecolors="white", linewidth=1.5,
        )

    ax.set_xlabel("Avg Cost per Diagnosis (x $0.001)", fontsize=11)
    ax.set_ylabel("Accuracy (%)", fontsize=11)
    ax.set_title("Diagnostic Accuracy vs Cost by Model", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(output_dir, "accuracy_vs_cost.png")
    fig.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# chart 2: per-scenario heatmap
# ---------------------------------------------------------------------------

def plot_scenario_heatmap(results, output_dir):
    models, scenarios, matrix = aggregate_by_model_scenario(results)

    fig, ax = plt.subplots(figsize=(12, max(3, len(models) * 0.8 + 1)))

    # use green for correct, red for wrong
    cmap = plt.cm.RdYlGn
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    # labels
    short_models = [MODEL_SHORT.get(m, m) for m in models]
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels(scenarios, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(short_models, fontsize=9)

    # put accuracy % in each cell
    for i in range(len(models)):
        for j in range(len(scenarios)):
            val = matrix[i][j]
            text_color = "white" if val < 50 else "black"
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                    fontsize=8, color=text_color, fontweight="bold")

    ax.set_title("Accuracy by Model x Scenario", fontsize=13, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Accuracy %", shrink=0.8)

    plt.tight_layout()
    path = os.path.join(output_dir, "scenario_heatmap.png")
    fig.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# chart 3: react vs baseline comparison
# ---------------------------------------------------------------------------

def plot_react_vs_baseline(react_stats, baseline_stats, output_dir):
    # only plot models that appear in both
    common = set(react_stats.keys()) & set(baseline_stats.keys())
    if not common:
        print("  No common models between react and baseline, skipping comparison chart")
        return

    models = sorted(common, key=lambda m: list(MODEL_SHORT.keys()).index(m) if m in MODEL_SHORT else 99)
    labels = [MODEL_SHORT.get(m, m) for m in models]
    react_acc = [react_stats[m]["accuracy"] for m in models]
    base_acc = [baseline_stats[m]["accuracy"] for m in models]

    x = range(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar([i - width/2 for i in x], base_acc, width, label="Baseline (naive LLM)", color="#ef4444", alpha=0.8)
    bars2 = ax.bar([i + width/2 for i in x], react_acc, width, label="ReAct Agent", color="#22c55e", alpha=0.8)

    ax.set_ylabel("Accuracy (%)", fontsize=11)
    ax.set_title("ReAct Agent vs Naive LLM Baseline", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    # add value labels on bars
    for bar in bars1 + bars2:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                f"{height:.0f}%", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    path = os.path.join(output_dir, "react_vs_baseline.png")
    fig.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Visualize evaluation results")
    parser.add_argument("results", help="Path to react eval results JSON")
    parser.add_argument("--baseline", default=None, help="Path to baseline eval results JSON")
    parser.add_argument("--output", default="evaluation/charts", help="Output directory for charts")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print("Loading results...")
    react_results = load_results(args.results)
    react_stats = aggregate_by_model(react_results)

    print("\nGenerating charts...")
    plot_accuracy_vs_cost(react_stats, args.output)
    plot_scenario_heatmap(react_results, args.output)

    if args.baseline:
        baseline_results = load_results(args.baseline)
        baseline_stats = aggregate_by_model(baseline_results)
        plot_react_vs_baseline(react_stats, baseline_stats, args.output)

    print(f"\nDone. Charts saved to {args.output}/")


if __name__ == "__main__":
    main()