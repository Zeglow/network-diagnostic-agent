# Smart Network Troubleshooting Agent

> An autonomous AI agent that diagnoses network failures like a Senior Network Engineer
> and explains them in plain English — so non-technical users don't need to know
> what `ping` or `traceroute` even means.

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-Iter%201%20complete-orange)]()
[![CS5700](https://img.shields.io/badge/Northeastern-CS%205700-red)]()

---

## The Problem

When a home network breaks, most users are completely lost.

Traditional tools like `ping`, `traceroute`, and `nslookup` generate raw technical output
that requires networking expertise to interpret. Worse, users don't even know
*which* tool to run first — or in what order.

```
$ ping google.com
Request timeout for icmp_seq 0
Request timeout for icmp_seq 1
^C

--- google.com ping statistics ---
2 packets transmitted, 0 packets received, 100.0% packet loss
```

What does this mean? Is it DNS? Routing? A local adapter?
For 90% of users, this is an alien language.

Existing solutions don't help:
- **Raw CLI tools** (iputils, RIPE Atlas) — powerful, but require expert interpretation
- **Consumer troubleshooters** — just say "check your connection"
- **AI log analysis** (LogPAI, OpenTelemetry) — designed for backend operators, not end users

**The gap:** there are plenty of tools that *generate* network data.
What's missing is an intelligent layer that *reads* that data
and tells a non-technical user exactly what's wrong and what to do.

---

## Our Solution

A diagnostic agent that:

1. Accepts a natural language symptom: `"I can't load any websites"`
2. Automatically selects and runs the right diagnostic tools
3. Reasons about the results to identify the root cause
4. Returns a plain-English explanation with actionable recommendations

**No terminal knowledge required. No manual tool selection. No raw output to interpret.**

---

## How It Works

### Iter 1 — Foundation (Current)

```
User: "I can't load any websites"
         │
         ▼
   CLI or Web Interface
         │
         ▼
   extract_target()          →  finds "8.8.8.8" or a domain from the symptom
         │
         ▼
   run all 3 tools (fixed order)
   PingTool → DNSTool → TracerouteTool
         │
         ▼
   assemble results into structured message
         │
         ▼
   LLM API call (OpenAI / Anthropic / Google / Groq)
         │
         ▼
   structured JSON response
   { summary, root_cause, recommendations }
         │
         ▼
   plain-English output to user
```

### Iter 2 — ReAct Loop (In Progress)

Instead of running all tools blindly, the agent uses a
**ReAct (Reasoning + Acting)** loop to make decisions between each tool call:

```
Think: "General connectivity issue — check baseline first"
Act:   run PingTool
Observe: 0% packet loss — network layer is fine

Think: "Network OK, issue might be DNS"
Act:   run DNSTool
Observe: DNS resolution failing — NXDOMAIN

Think: "Root cause identified. No need for traceroute."
Stop → deliver diagnosis
```

This mirrors how a human network engineer actually troubleshoots —
adaptively, based on evidence — rather than running every tool every time.

---

## Features & User Stories

### Feature 1 — Symptom-Based Automated Diagnosis ✅ (Iter 1)
> **Who:** As a non-expert home user experiencing connectivity problems
>
> **Why:** So that I can understand what is wrong and fix it without networking knowledge
>
> **What:** I want to describe my problem in plain English and receive a clear diagnosis
> with specific next steps

**Acceptance criteria:**
- User inputs symptoms in natural language via CLI or web interface
- System automatically runs appropriate diagnostic commands
- LLM output is in plain English — no raw command output shown
- At least 2 specific, actionable recommendations provided

---

### Feature 2 — Intelligent Tool Selection with Visible Reasoning 🔄 (Iter 2)
> **Who:** As a networking student learning how to troubleshoot
>
> **Why:** So that I can observe how an expert systematically narrows down problems
>
> **What:** I want the agent to show its reasoning before each tool execution

**Acceptance criteria:**
- Agent displays "Thought:" reasoning before each tool run
- Tool selection adapts based on previous results — not a fixed sequence
- Different symptoms lead to different diagnostic paths
- Agent stops when it has enough evidence, not always running all 3 tools

---

### Feature 3 — Reproducible Fault Injection Testing Environment ⬜ (Iter 3)
> **Who:** As a developer or instructor evaluating the agent
>
> **Why:** So that I can validate the agent's diagnostic accuracy objectively
>
> **What:** I want a controlled environment to inject specific faults
> and measure how accurately the agent diagnoses them

**Acceptance criteria:**
- Docker environment starts with `docker compose up`
- 10 fault scenarios injectable (DNS failure, packet loss, high latency, etc.)
- Accuracy measured by `predicted root_cause == ground truth label` — not keyword matching
- Benchmark across 5 LLM providers with accuracy-vs-cost comparison

---

## Supported LLM Providers

| Model | Provider | Cost/run | Free Tier | Notes |
|-------|----------|----------|-----------|-------|
| `gpt-4o-mini` | OpenAI | ~$0.0005 | ❌ | Default — best value |
| `gpt-4o` | OpenAI | ~$0.008 | ❌ | Final evaluation |
| `claude-haiku-4-5-20251001` | Anthropic | ~$0.001 | ❌ | Agent-task optimized |
| `gemini-2.5-flash` | Google | ~$0.0002 | ✅ | Cheapest capable model |
| `llama-3.3-70b-versatile` | Groq | ~$0.0004 | ✅ | Open source, data stays local |

All providers use the same interface — swap models with a single `--model` flag.

---

## Setup

```bash
# Clone
git clone https://github.com/Zeglow/network-diagnostic-agent.git
cd network-diagnostic-agent

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env — add the keys for whichever providers you want to use
```

**.env format:**
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
GROQ_API_KEY=gsk_...
```

---

## Usage

### CLI

```bash
# Default model (gpt-4o-mini)
python src/cli.py diagnose "I can't load any websites"

# Specific model
python src/cli.py diagnose "My video calls keep dropping" --model gemini-2.5-flash

# List all available models
python src/cli.py diagnose
```

**Example output:**
```
Analyzing: I can't load any websites
Running diagnostics...

  Target identified: 8.8.8.8
  Running PingTool on 8.8.8.8...
  Running DNSTool on 8.8.8.8...
  Running TracerouteTool on 8.8.8.8...

Generating diagnosis...

## Summary
Ping to 8.8.8.8 is succeeding but DNS resolution is failing,
suggesting your DNS server is unreachable.

## Root Cause
DNS failure — your device cannot resolve hostnames to IP addresses.

## Recommendations
1. Flush your DNS cache: sudo dscacheutil -flushcache (macOS)
2. Switch your DNS server to 8.8.8.8 in your network settings
3. Restart your router if the issue persists
```

### Web Interface

```bash
python app.py
# Open http://localhost:5000
```

The web interface includes a model selector — no terminal knowledge required.

---

## Project Status

| Iteration | Weeks | Feature | Status |
|-----------|-------|---------|--------|
| Iter 1 | 5–7 | Basic diagnostics + LLM explanation + web UI | ✅ Complete |
| Iter 2 | 8–9 | ReAct loop — adaptive tool selection | 🔄 In progress |
| Iter 3 | 10–11 | Docker fault injection + multi-model evaluation | ⬜ Planned |
| Final | 12–13 | Report + presentation + public dataset | ⬜ Planned |

---

## Evaluation Strategy (Iter 3)

We evaluate against **10 Docker-injected fault scenarios** with ground truth labels:

| # | Scenario | Injected Fault | Ground Truth Label |
|---|----------|---------------|-------------------|
| 1 | DNS Failure | Block UDP port 53 | `dns_failure` |
| 2 | High Packet Loss | `tc netem loss 30%` | `packet_loss` |
| 3 | High Latency | `tc netem delay 500ms` | `high_latency` |
| 4 | Route Failure | Drop packets at hop N | `route_failure` |
| 5 | Port Blocked | `iptables REJECT port 443` | `port_blocked` |
| 6 | Complete Outage | Block all egress | `no_connectivity` |
| 7 | Intermittent Loss | `tc netem loss 10% 25%` | `intermittent_loss` |
| 8 | Bandwidth Throttle | `tc tbf rate 100kbit` | `bandwidth_throttle` |
| 9 | High Jitter | `tc netem delay 100ms 80ms` | `high_jitter` |
| 10 | Duplicate Packets | `tc netem duplicate 20%` | `duplicate_packets` |

Accuracy is measured by comparing `predicted["root_cause"] == ground_truth_label` —
not keyword matching.

Multi-model benchmark produces an accuracy-vs-cost chart across all 5 providers.

---

## Why This Is Not Just a Wrapper

Most "AI + networking" projects simply pass raw tool output to ChatGPT and display the response. This project differs in three ways:

**1. Adaptive reasoning (Iter 2):** The ReAct loop makes decisions between tool calls based on accumulated evidence — the same pattern used in production systems like GitHub Copilot Workspace and AWS Q Developer.

**2. Rigorous evaluation:** Structured JSON output with `root_cause` enum enables automated accuracy measurement against ground truth labels. This is how production AI systems are evaluated, not how demos are built.

**3. Multi-provider, open-source support:** The same agent runs across 5 LLM providers including local open-source models (Llama via Groq). No data needs to leave your machine.

---

## Team

**Ashley (Yongqi) Ou** — Agent core, LLM integration (multi-provider), prompt engineering, web interface, evaluation framework, project coordination

**Avery (Weiyu) Qiu** — Diagnostic tool wrappers, Docker sandbox, fault injection scripts, CLI interface, demo videos

*CS 5700 Fundamentals of Computer Networking — Northeastern University, Spring 2026*