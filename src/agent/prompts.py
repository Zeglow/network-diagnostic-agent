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