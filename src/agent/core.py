# src/agent/core.py

from src.tools.ping import PingTool
from src.tools.dns import DNSTool
from src.tools.traceroute import TracerouteTool
from src.agent.llm import get_diagnosis, DEFAULT_MODEL


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
