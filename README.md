# Smart Network Troubleshooting Agent

> AI-powered network diagnostics for non-technical users.
> Describe your problem in plain English — the agent figures out what's wrong.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Iter%201%20complete-orange)

---

## What It Does

Most people don't know what `ping`, `traceroute`, or `nslookup` mean.
When their network breaks, they're stuck.

This agent bridges that gap:

1. You describe your problem: `"I can't load any websites"`
2. The agent automatically runs network diagnostic tools
3. An LLM interprets the results
4. You get a plain-English explanation and specific recommendations

---

## Demo

<!-- Add screenshot or GIF here after end-to-end is working -->

**Web Interface:**

[screenshot of app.py running]

**CLI:**
```
python src/cli.py diagnose "I can't load any websites"

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
1. Try flushing your DNS cache: sudo dscacheutil -flushcache
2. Switch your DNS server to 8.8.8.8 in your network settings
3. Restart your router if the issue persists
```

---

## Architecture

```
User input (symptom)
│
▼
CLI or Web Interface
│
▼
core.diagnose()
├── extract_target()          simple heuristic (Iter 1)
│                             LLM-based extraction (Iter 2)
│
├── [Iter 1] run all tools in fixed order
│   PingTool → DNSTool → TracerouteTool
│
├── [Iter 2] ReAct loop
│   Think → Act → Observe → Think → Act → Stop when ready
│
└── llm.get_diagnosis()
        │
        OpenAI / Anthropic / Google / Groq
        │
        Structured JSON response
        │
        Plain-English output
```

---

## Supported LLM Providers

| Model | Provider | Cost/run | Free tier |
|-------|----------|----------|-----------|
| `gpt-4o-mini` | OpenAI | ~$0.0005 | ❌ |
| `gpt-4o` | OpenAI | ~$0.008 | ❌ |
| `claude-haiku-4-5` | Anthropic | ~$0.001 | ❌ |
| `gemini-2.5-flash` | Google | ~$0.0002 | ✅ |
| `llama-3.3-70b` | Groq | ~$0.0004 | ✅ |

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
# Edit .env and add your keys
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

**CLI:**
```bash
# Default model (gpt-4o-mini)
python src/cli.py diagnose "I can't load any websites"

# Choose a specific model
python src/cli.py diagnose "My video calls keep dropping" --model gemini-2.5-flash

# See all available models
python src/cli.py diagnose
```

**Web Interface:**
```bash
python app.py
# Open http://localhost:5000
```

---

## Project Status

| Iteration | Feature | Status |
|-----------|---------|--------|
| Iter 1 | Basic diagnostics + LLM explanation + web UI | ✅ Complete |
| Iter 2 | ReAct loop — adaptive tool selection | 🔄 In progress |
| Iter 3 | Docker fault injection + multi-model evaluation | ⬜ Planned |

---

## Evaluation (Iter 3)

We evaluate against 10 Docker-injected fault scenarios with ground truth labels.
Accuracy is measured by comparing the agent's structured `root_cause` field
against the known fault type — not keyword matching.

<!-- Add accuracy chart here after Iter 3 -->

---

## Team

**Ashley (Yongqi) Ou** — Agent core, LLM integration, prompt engineering,
web interface, evaluation framework

**Avery (Weiyu) Qiu** — Diagnostic tool wrappers, Docker sandbox,
fault injection scripts, demo videos

CS 5700 Fundamentals of Computer Networking — Northeastern University, Spring 2026
