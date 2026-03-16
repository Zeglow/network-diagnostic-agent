# src/agent/core.py

from src.tools.ping import PingTool
from src.tools.dns import DNSTool
from src.tools.traceroute import TracerouteTool
from src.agent.llm import get_diagnosis, get_react_decision, parse_react_response, DEFAULT_MODEL
from src.agent.prompts import (
    REACT_SYSTEM_PROMPT,
    build_react_observation,
    build_react_initial_message,
)


DEFAULT_TARGET = "8.8.8.8"


def extract_target(symptom):
    """
    pull out a hostname or ip from the symptom string
    e.g. "I can't reach google.com" -> "google.com"
    falls back to 8.8.8.8 if nothing found
    """
    # TODO iter 2: replace this with LLM-based extraction
    # right now it just looks for words with dots, which misses cases like
    # "my VPN keeps dropping" where there's no hostname in the symptom at all
    words = symptom.split()
    for word in words:
        # if a word has a dot and is long enough, it's probably a domain or ip
        if "." in word and len(word) > 3:
            return word.strip(".,!?")
    return DEFAULT_TARGET


def run_diagnostics(target):
    """
    run all 3 tools against the target and return results
    in iter 2 this will be replaced by the react loop
    """
    # known limitation: we always run all 3 tools even if ping fails immediately
    # e.g. if there's a complete outage, running traceroute after a failed ping
    # is pointless and just adds ~30s of timeout waiting
    # the react loop in iter 2 fixes this by stopping early when it has enough info
    tools = [
        PingTool(),
        DNSTool(),
        TracerouteTool(),
    ]

    results = []
    for tool in tools:
        print(f"  Running {tool.__class__.__name__} on {target}...")
        result = tool.run(target)
        results.append(result)

    return results


def diagnose(symptom, model=DEFAULT_MODEL):
    """
    main function - takes a symptom string, runs diagnostics, returns diagnosis dict
    """
    print(f"\nAnalyzing: {symptom}")
    print("Running diagnostics...\n")

    target = extract_target(symptom)
    print(f"  Target identified: {target}")

    tool_results = run_diagnostics(target)

    print("\nGenerating diagnosis...\n")
    diagnosis = get_diagnosis(symptom, tool_results, model=model)

    return diagnosis


MAX_STEPS = 5  # safety limit — agent can't run more than 5 tool calls

AVAILABLE_TOOLS = {
    "ping":       PingTool,
    "dns":        DNSTool,
    "traceroute": TracerouteTool,
}


def diagnose_react(symptom: str, model: str = DEFAULT_MODEL) -> dict:
    """
    ReAct loop implementation — replaces the fixed 3-tool pipeline from Iter 1.
    
    The LLM decides which tool to run at each step based on accumulated evidence.
    It stops as soon as it has enough information, rather than always running all 3 tools.
    
    Args:
        symptom: Natural language problem description
        model:   LLM provider/model to use
    
    Returns:
        Dict with keys: summary, root_cause, recommendations, react_trace
        react_trace contains the full reasoning chain for display/debugging
    """
    print(f"\nAnalyzing: {symptom}")
    print(f"Model: {model}")
    print("Starting ReAct loop...\n")

    # Build initial conversation history
    conversation = [
        {"role": "system",    "content": REACT_SYSTEM_PROMPT},
        {"role": "user",      "content": build_react_initial_message(symptom)},
    ]

    tools_used = set()      # track which tools have run, prevent duplicates
    react_trace = []        # full reasoning chain for display
    target = extract_target(symptom)

    for step in range(MAX_STEPS):
        print(f"  Step {step + 1}: asking LLM what to do next...")

        # Ask LLM for next decision
        raw_response = get_react_decision(conversation, model=model)
        parsed = parse_react_response(raw_response)

        # Add LLM response to conversation history
        conversation.append({"role": "assistant", "content": raw_response})

        if parsed["type"] == "action":
            tool_name = parsed["tool"]
            thought = parsed["thought"]

            print(f"  Thought: {thought}")
            print(f"  Action:  run {tool_name}")

            react_trace.append({
                "step": step + 1,
                "thought": thought,
                "action": tool_name,
            })

            # Guard: don't run unknown or already-used tools
            if tool_name not in AVAILABLE_TOOLS:
                observation = f"OBSERVATION: Unknown tool '{tool_name}'. Available: ping, dns, traceroute"
            elif tool_name in tools_used:
                observation = f"OBSERVATION: {tool_name} already ran. Use a different tool or provide diagnosis."
            else:
                # Run the tool
                tool = AVAILABLE_TOOLS[tool_name]()
                result = tool.run(target)
                tools_used.add(tool_name)
                observation = build_react_observation(tool_name, result)
                react_trace[-1]["observation"] = result

            print(f"  Observation: {observation[:100]}...")  # truncate for readability
            
            # Add observation to conversation so LLM sees it next turn
            conversation.append({"role": "user", "content": observation})

        elif parsed["type"] == "diagnosis":
            thought = parsed["thought"]
            diagnosis = parsed["diagnosis"]

            print(f"  Thought: {thought}")
            print(f"  → Diagnosis ready after {step + 1} step(s), {len(tools_used)} tool(s) used\n")

            react_trace.append({
                "step": step + 1,
                "thought": thought,
                "action": "DIAGNOSE",
            })

            # Add trace info to the diagnosis for display
            diagnosis["react_trace"] = react_trace
            diagnosis["tools_used"] = list(tools_used)
            diagnosis["steps_taken"] = step + 1
            return diagnosis

        else:
            # Parsing failed — fallback
            print(f"  Warning: could not parse LLM response at step {step + 1}")
            conversation.append({
                "role": "user",
                "content": "OBSERVATION: Could not parse your response. Please follow the exact format."
            })

    # Safety fallback if we hit MAX_STEPS without a diagnosis
    print(f"  Warning: reached MAX_STEPS ({MAX_STEPS}) without diagnosis, forcing conclusion...")
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