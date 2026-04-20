"""LLM-as-judge for grading agent text replies.

For each scenario step that defines a `judge` block, the runner calls
`run_judge(...)` after the agent completes. The judge is a stronger/neutral
model that decides whether the reply satisfies the author-provided criteria,
given the same ground-truth context the agent had access to.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


DEFAULT_JUDGE_MODEL = "google/gemini-3-flash-preview"
JUDGE_TEMPERATURE = 0  # hardcoded — judge must be deterministic


JUDGE_SYSTEM_PROMPT = """Sei un giudice imparziale. Valuti la risposta di un agente AI
che gestisce dati del palio dei borghi.

Regole:
- Valuta SOLO contro i criteri forniti. Non giudicare stile o formattazione a meno
  che un criterio non lo richieda esplicitamente.
- TUTTI i criteri devono essere soddisfatti. Se anche uno solo non lo è, la risposta
  FALLISCE.
- Quando valuti la correttezza di numeri o nomi citati, confrontali con il
  CONTESTO DELL'AGENTE. Se un valore citato nella risposta non compare nel
  contesto, è un'allucinazione → FALLISCE.

Rispondi SOLO con JSON nel formato:
{"passed": true|false, "reasoning": "...", "failed_criteria": ["..."]}
"""


def _build_judge_user_prompt(
    step_prompt: str,
    agent_reply: str,
    ground_truth_files: dict[str, Any],
    expected_behavior: str | None,
    criteria: list[str],
    good_examples: list[str],
    bad_examples: list[str],
) -> str:
    parts: list[str] = []

    parts.append("### CONTESTO DELL'AGENTE")
    parts.append("Questi sono i file che l'agente aveva a disposizione al momento della risposta.\n")
    for name, content in ground_truth_files.items():
        parts.append(f"[{name}]")
        parts.append(json.dumps(content, ensure_ascii=False, indent=2))
        parts.append("")

    parts.append("### TASK")
    parts.append(f"Prompt dell'utente: {step_prompt!r}")
    if expected_behavior:
        parts.append(f"\nComportamento atteso: {expected_behavior}")

    if criteria:
        parts.append("\nCriteri (TUTTI devono essere soddisfatti):")
        for c in criteria:
            parts.append(f"  - {c}")

    if good_examples:
        parts.append("\nEsempi ACCETTABILI:")
        for ex in good_examples:
            parts.append(f"  + {ex}")

    if bad_examples:
        parts.append("\nEsempi NON accettabili:")
        for ex in bad_examples:
            parts.append(f"  - {ex}")

    parts.append("\n### RISPOSTA DELL'AGENTE")
    parts.append(agent_reply if agent_reply.strip() else "(nessuna risposta testuale)")

    parts.append("\n### ISTRUZIONI FINALI")
    parts.append(
        "Valuta rigorosamente contro ogni criterio. Rispondi SOLO con JSON "
        '{"passed": bool, "reasoning": str, "failed_criteria": [str]}.'
    )
    return "\n".join(parts)


async def run_judge(
    *,
    step_prompt: str,
    agent_reply: str,
    ground_truth_files: dict[str, Any],
    judge_config: dict[str, Any],
    api_key: str,
    base_url: str = "https://openrouter.ai/api",
) -> dict[str, Any]:
    """Call the judge model and return its structured verdict.

    On any failure (network, parse error) returns
    `{"passed": False, "reasoning": "<error>", "failed_criteria": []}`
    so that a broken judge never silently passes a step.
    """
    model = judge_config.get("model") or DEFAULT_JUDGE_MODEL

    user_prompt = _build_judge_user_prompt(
        step_prompt=step_prompt,
        agent_reply=agent_reply,
        ground_truth_files=ground_truth_files,
        expected_behavior=judge_config.get("expected_behavior"),
        criteria=judge_config.get("criteria") or [],
        good_examples=judge_config.get("good_examples") or [],
        bad_examples=judge_config.get("bad_examples") or [],
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": JUDGE_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{base_url.rstrip('/')}/v1/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            return _failure(f"judge http {r.status_code}: {r.text[:300]}")

        body = r.json()
        content = body["choices"][0]["message"].get("content") or ""
        try:
            verdict = json.loads(content)
        except json.JSONDecodeError as e:
            return _failure(f"judge returned non-json: {e}; raw={content[:300]}")

        return {
            "model": model,
            "passed": bool(verdict.get("passed", False)),
            "reasoning": str(verdict.get("reasoning", "")).strip(),
            "failed_criteria": list(verdict.get("failed_criteria") or []),
        }
    except Exception as e:
        return _failure(f"judge call raised: {type(e).__name__}: {e}")


def _failure(msg: str) -> dict[str, Any]:
    logger.warning(f"Judge failed — {msg}")
    return {
        "model": None,
        "passed": False,
        "reasoning": msg,
        "failed_criteria": [],
    }
