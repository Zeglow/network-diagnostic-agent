# src/agent/prompts.py

SYSTEM_PROMPT = """You are an expert network diagnostic assistant.

Your job is to analyze network diagnostic results and explain them to users
who may not have technical networking knowledge.

You MUST respond with a valid JSON object in exactly this format — no other text:
{
    "summary": "1-2 sentences explaining what the diagnostics found in plain English",
    "root_cause": "The single most likely cause of the issue",
    "recommendations": [
        "First specific, actionable recommendation",
        "Second specific, actionable recommendation",
        "Third recommendation if applicable"
    ]
}

Rules:
- Respond ONLY with the JSON object — no markdown, no extra text
- Be concise, clear, and avoid unnecessary jargon
- recommendations must be a list of 2-3 strings
"""


def build_user_prompt(symptom, tool_results):
    # build the message we send to the llm with the symptom + all tool outputs
    prompt = f"User reported issue: {symptom}\n\n"
    prompt += "Diagnostic Results:\n"
    prompt += "=" * 40 + "\n"

    for result in tool_results:
        tool_name = result["tool_name"]
        target = result["target"]
        success = result["success"]

        prompt += f"\n[{tool_name.upper()}] Target: {target}\n"

        if not success:
            prompt += f"Status: FAILED\n"
            prompt += f"Error: {result['error']}\n"
        else:
            # include both parsed data and raw output so the llm has full context
            prompt += f"Status: SUCCESS\n"
            prompt += f"Data: {result['data']}\n"
            prompt += f"Raw Output:\n{result['raw_output']}\n"

        prompt += "-" * 40 + "\n"

    prompt += "\nBased on the above diagnostic results, please analyze the network issue."

    return prompt


# ---------------------------------------------------------------------------
# Iter 2 — ReAct prompt scaffolding
# ---------------------------------------------------------------------------

REACT_SYSTEM_PROMPT = """You are an expert network diagnostic assistant using the ReAct (Reasoning + Acting) framework.

You diagnose network problems by reasoning step-by-step and running diagnostic tools one at a time.
Stop as soon as you have enough evidence — do not run all three tools by default.

## Response format

Every response must follow EXACTLY one of these two formats:

### Format 1 — Run a tool:
THOUGHT: <your reasoning about what to check next and why>
ACTION: <tool_name>

Where <tool_name> is one of: ping, dns, traceroute

### Format 2 — Provide final diagnosis (when you have enough information):
THOUGHT: <your reasoning about why you have enough information to diagnose>
DIAGNOSIS:
{
    "summary": "1-2 sentences explaining what the diagnostics found in plain English",
    "root_cause": "The single most likely cause of the issue",
    "recommendations": [
        "First specific, actionable recommendation",
        "Second specific, actionable recommendation",
        "Third recommendation if applicable"
    ]
}

## Decision rules
- Start with ping to check basic IP connectivity
- If ping succeeds and the problem is web/hostname related, check DNS next
- Use traceroute only if you suspect a routing or hop-level problem
- If ping fails completely, you likely have enough to diagnose — skip remaining tools
- Never run the same tool twice
- The DIAGNOSIS JSON must be valid JSON with exactly the keys shown above
- Do not include any text outside the specified format
"""


def build_react_initial_message(symptom: str) -> str:
    """Build the first user message that kicks off the ReAct loop."""
    return (
        f"A user has reported the following network problem:\n\n"
        f'"{symptom}"\n\n'
        f"Please begin diagnosing this issue step by step. "
        f"Available tools: ping, dns, traceroute."
    )


def build_react_observation(tool_name: str, result: dict) -> str:
    """Format a ToolResult dict as an OBSERVATION string for the LLM."""
    lines = [f"OBSERVATION: {tool_name} result:"]

    if result["success"]:
        lines.append("Status: SUCCESS")
        lines.append(f"Data: {result['data']}")
        lines.append(f"Raw Output:\n{result['raw_output']}")
    else:
        lines.append("Status: FAILED")
        lines.append(f"Error: {result['error']}")

    return "\n".join(lines)