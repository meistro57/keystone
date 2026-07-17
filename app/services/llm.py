# filename: app/services/llm.py
"""OpenAI-compatible chat + embedding calls (OpenRouter by default)."""

from __future__ import annotations
import json

import requests

import config


def chat(model: str, system: str, user: str, temperature: float = 0.4,
         base_url: str | None = None, api_key: str | None = None) -> str:
    base_url = base_url or config.OPENROUTER_BASE_URL
    api_key = api_key or config.OPENROUTER_API_KEY
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/meistro57/keystone",
            "X-Title": "Keystone",
        },
        json={
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=config.LLM_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def active_synth_model() -> str:
    """Which R1 we actually call — DeepSeek-direct model id if keyed, else OpenRouter."""
    return config.SYNTH_MODEL_DIRECT if config.DEEPSEEK_API_KEY else config.SYNTH_MODEL


def chat_synth(system: str, user: str, temperature: float = 0.5) -> str:
    """R1 forge call. Straight to DeepSeek if DEEPSEEK_API_KEY is set, else OpenRouter.
    (temperature is ignored by deepseek-reasoner, which is fine.)"""
    if config.DEEPSEEK_API_KEY:
        return chat(config.SYNTH_MODEL_DIRECT, system, user, temperature,
                    base_url=config.DEEPSEEK_BASE_URL, api_key=config.DEEPSEEK_API_KEY)
    return chat(config.SYNTH_MODEL, system, user, temperature)


def embed(text: str) -> list[float]:
    r = requests.post(
        f"{config.EMBED_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {config.EMBED_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": config.EMBED_MODEL, "input": text},
        timeout=config.LLM_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def parse_json(raw: str) -> dict:
    """R1/Gemma love wrapping JSON in prose or ```json fences. Dig it out."""
    s = raw.strip()
    if "```" in s:
        # grab the fenced block
        parts = s.split("```")
        for chunk in parts:
            chunk = chunk.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                s = chunk
                break
    # last-ditch: slice from first { to last }
    if not s.startswith("{"):
        i, j = s.find("{"), s.rfind("}")
        if i != -1 and j != -1:
            s = s[i:j + 1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # R1 occasionally emits an unescaped quote/newline inside a string value.
        # Repair it rather than lose the keystone.
        from json_repair import repair_json
        return repair_json(s, return_objects=True)
