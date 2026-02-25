# src/cli.py

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.core import diagnose
from src.agent.llm import DEFAULT_MODEL, MODEL_OPTIONS


def format_diagnosis(result):
    # turn the result dict into readable terminal output
    lines = [
        "## Summary",
        result.get("summary", ""),
        "",
        "## Root Cause",
        result.get("root_cause", ""),
        "",
        "## Recommendations",
    ]
    for i, rec in enumerate(result.get("recommendations", []), 1):
        lines.append(f"{i}. {rec}")
    return "\n".join(lines)


def main():
    """
    usage:
        python src/cli.py diagnose "I can't load any websites"
        python src/cli.py diagnose "I can't load any websites" --model gpt-4o
    """
    args = sys.argv[1:]

    if len(args) < 2:
        print("Usage: python src/cli.py diagnose \"<symptom>\" [--model <model>]")
        print("\nAvailable models:")
        for model_id, label in MODEL_OPTIONS.items():
            print(f"  {model_id:35s} {label}")
        sys.exit(1)

    command = args[0]
    symptom = args[1]

    if command != "diagnose":
        print(f"Unknown command: {command}")
        print("Available commands: diagnose")
        sys.exit(1)

    # check if --model flag was passed
    model = DEFAULT_MODEL
    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 < len(args):
            model = args[idx + 1]
        else:
            print("Error: --model needs a model name after it")
            sys.exit(1)

    result = diagnose(symptom, model=model)
    print(format_diagnosis(result))


if __name__ == "__main__":
    main()
