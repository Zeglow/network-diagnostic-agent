# src/agent/llm.py

import json
import os
from .prompts import SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "gpt-4o-mini"

# all supported models and their display names
MODEL_OPTIONS = {
    "gpt-4o-mini":               "gpt-4o-mini (OpenAI, default)",
    "gpt-4o":                    "gpt-4o (OpenAI)",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5 (Anthropic)",
    "gemini-2.5-flash":          "gemini-2.5-flash (Google)",
    "llama-3.3-70b-versatile":   "llama-3.3-70b (Groq)",
}

OPENAI_MODELS    = {"gpt-4o-mini", "gpt-4o"}
ANTHROPIC_MODELS = {"claude-haiku-4-5-20251001"}
GOOGLE_MODELS    = {"gemini-2.5-flash"}
GROQ_MODELS      = {"llama-3.3-70b-versatile"}


def _call_openai(messages, model):
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=500,
        response_format={"type": "json_object"},  # force json
    )
    return response.choices[0].message.content


def _call_anthropic(messages, model):
    import anthropic
    client = anthropic.Anthropic()
    # anthropic takes system separately, not in messages list
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_messages = [m for m in messages if m["role"] != "system"]
    # prefill trick from anthropic docs - start response with { to force json output
    # note: anthropic doesn't return the prefilled part, so we add it back below
    user_messages = user_messages + [{"role": "assistant", "content": "{"}]
    response = client.messages.create(
        model=model,
        system=system,
        messages=user_messages,
        max_tokens=500,
        temperature=0.3,
    )
    return "{" + response.content[0].text


def _call_google(messages, model):
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user   = next((m["content"] for m in messages if m["role"] == "user"),   "")
    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            temperature=0.3,
            response_mime_type="application/json",  # force json like openai does
        ),
    )
    response = gen_model.generate_content(user)
    return response.text


def _call_groq(messages, model):
    from groq import Groq
    client = Groq()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content


def _parse_json(raw):
    # try to parse the llm response as json
    # some models wrap it in ```json ... ``` so strip that first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        stripped = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return {
                "summary": raw,
                "root_cause": "Could not parse response from model.",
                "recommendations": ["Please try again or use a different model."],
            }


def get_diagnosis(symptom, tool_results, model=DEFAULT_MODEL):
    """
    send symptom + tool results to the llm and get back a diagnosis dict
    returns: { summary, root_cause, recommendations }
    """
    user_prompt = build_user_prompt(symptom, tool_results)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
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
        raw = _call_openai(messages, model)  # default to openai

    return _parse_json(raw)
