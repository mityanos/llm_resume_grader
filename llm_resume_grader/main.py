## 6  `main.py`
#!/usr/bin/env python3
"""
LLM-powered résumé grader (single-message edition).
Sends system_prompt + candidate doc as one system message and saves
raw JSON answer plus derived grade/explanation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from glob import glob
from pathlib import Path
from typing import Dict, List

import yaml
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError


# ───────────────────────── helpers ──────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_env() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing in .env")


def read_text(path: str | Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def load_system_prompt(path: str | Path) -> str:
    return read_text(path)


def candidate_id(text: str, fallback: str) -> str:
    match = re.search(r"Candidate ID:\s*([^\s\n]+)", text)
    return match.group(1) if match else fallback


def build_message(sys_prompt: str, cand_doc: str) -> List[Dict[str, str]]:
    combined = f"{sys_prompt}\n\n---\n\n{cand_doc}"
    return [{"role": "system", "content": combined}]


def safe_chat(
    client: OpenAI,
    messages: list[dict[str, str]],
    model: str,
    retry_max: int,
    **params,                       # temperature, top_p, max_tokens, …
) -> str:
    for attempt in range(1, retry_max + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                **params,
            )
            return resp.choices[0].message.content
        except (RateLimitError, APIError) as err:
            wait = 1.5 * attempt
            logging.warning("OpenAI error: %s (retry %d/%d, sleep %.1fs)",
                            err, attempt, retry_max, wait)
            time.sleep(wait)
    raise RuntimeError("OpenAI failed after retries")


def extract_grade_expl(answer: str) -> tuple[str, str]:
    try:
        data = json.loads(answer)
        return data.get("grade", "?"), data.get("grade_explanation", "")[:500]
    except Exception:
        m = re.search(r"Grade:\s*([A-D])\s*[-–]\s*(.+)$", answer, re.S)
        if m:
            return m.group(1), m.group(2)[:500]
    return "?", answer[:500]


def render_md(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Candidate | Grade | Explanation |",
        "|-----------|-------|-------------|",
    ]
    for r in rows:
        expl = r["explanation"].replace("\n", " ").replace("|", " ")
        lines.append(f"| {r['candidate']} | {r['grade']} | {expl[:120]} |")
    return "\n".join(lines)


# ───────────────────────── main ─────────────────────────────

def main() -> None:
    setup_logging()
    cfg = load_config("config.yaml")
    load_env()

    client = OpenAI()

    sys_prompt = load_system_prompt(cfg["paths"]["system_prompt"])
    files = sorted(glob(cfg["paths"]["candidates_glob"]))
    if not files:
        logging.error("No résumé files in %s", cfg["paths"]["candidates_glob"])
        return

    scale   = cfg["grading"]["scale"]
    params  = cfg["llm"]["params"]
    retry   = cfg["llm"]["retry_max"]
    model   = cfg["llm"]["model"]

    results: List[Dict[str, str]] = []

    for f in files:
        cand_doc = read_text(f)
        cid = candidate_id(cand_doc, Path(f).stem)

        messages = build_message(sys_prompt, cand_doc)
        try:
            answer = safe_chat(client, messages, model=model,
                               retry_max=retry, **params)
        except Exception as e:
            logging.error("❌ %s: %s", cid, e)
            answer = "API ERROR"

        grade, expl = extract_grade_expl(answer)
        results.append({
            "candidate": cid,
            "grade": grade,
            "score": scale.get(grade, 0),
            "explanation": expl,
            "raw_response": answer,
        })
        logging.info("✓ %s → %s", cid, grade)

    results.sort(key=lambda r: -r["score"])
    Path(cfg["paths"]["out_md"]).write_text(render_md(results), encoding="utf-8")
    Path(cfg["paths"]["out_json"]).write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logging.info("Finished: %d candidates", len(results))


if __name__ == "__main__":
    main()