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
from typing import Any, Dict, List, Optional

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
    **params,  # temperature, top_p, max_tokens, …
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
            logging.warning(
                "OpenAI error: %s (retry %d/%d, sleep %.1fs)",
                err,
                attempt,
                retry_max,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError("OpenAI failed after retries")


def extract_json_object(raw: str) -> Optional[dict[str, Any]]:
    """
    Pulls first balanced `{…}` object out of a string (Markdown-safe).
    Returns `None` on failure.
    """
    # 1) Убираем обёртки типа ```json ... ``` (игнорируем регистр). 
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)

    depth = None
    start = None
    # 2) Проходим посимвольно, отслеживая глубину вложенных фигурных скобок
    for i, ch in enumerate(text):
        if ch == "{":
            if depth is None:
                depth = 0
                start = i
            depth += 1
        elif ch == "}":
            if depth is not None:
                depth -= 1
                # 3) Если дошли до закрывающей скобки, сбалансированной на нулевой глубине
                if depth == 0 and start is not None:
                    snippet = text[start : i + 1]
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError as e:
                        logging.warning(
                            "json.parse_failed: %s\nsnippet: %s",
                            e,
                            snippet[:60],
                        )
                        return None
    return None


def extract_grade_expl(answer: str) -> tuple[str, str]:
    """
    Попытаться найти валидный JSON-объект внутри строки `answer`.
    Если удалось, разобрать и вернуть поля "grade" и "grade_explanation".
    Иначе — откатиться к regexp-парсингу вида "Grade: X – explanation".
    Если и это не сработает, вернуть "?" и первые 500 символов сырого ответа.
    """
    # 1) Пытаемся извлечь JSON-объект через глубокий парсер
    parsed = extract_json_object(answer)
    if parsed is not None:
        grade = parsed.get("grade", "?")
        expl = parsed.get("grade_explanation", "") or parsed.get("explanation", "")
        return grade, expl.strip().replace("\n", " ")[:500]

    # 2) Регулярка: "Grade: A – короткое объяснение"
    regex = re.compile(r"Grade:\s*([A-D])\s*[-–]\s*(.+)", re.IGNORECASE | re.DOTALL)
    m = regex.search(answer)
    if m:
        grade = m.group(1).upper()
        expl = m.group(2).strip()
        return grade, expl[:500]

    # 3) Если ни JSON, ни regexp не прокатили — fallback
    return "?", answer.strip().replace("\n", " ")[:500]


def render_md(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Candidate | Grade | Explanation |",
        "|-----------|-------|-------------|",
    ]
    for r in rows:
        # убираем переносы строк и |, чтобы не сломать Markdown-таблицу
        expl = r["explanation"].replace("\n", " ").replace("|", " ")
        lines.append(f"| {r['candidate']} | {r['grade']} | {expl} |")
    return "\n".join(lines)


# ───────────────────────── main ─────────────────────────────

def main() -> None:
    setup_logging()
    cfg = load_config("config.yaml")
    load_env()

    client = OpenAI()

    sys_prompt = load_system_prompt(cfg["paths"]["system_prompt"])
    files = sorted(glob(cfg["paths"]["candidates_glob"]))

    results: List[Dict[str, Any]] = []
    for path in files:
        cand_doc = read_text(path)
        cid = candidate_id(cand_doc, Path(path).stem)

        messages = build_message(sys_prompt, cand_doc)
        answer = safe_chat(
            client=client,
            messages=messages,
            model=cfg["llm"]["model"],
            retry_max=cfg["llm"]["retry_max"],
            **cfg["llm"]["params"],
        )

        grade, expl = extract_grade_expl(answer)
        score = cfg["grading"]["scale"].get(grade, 0)

        results.append({
            "candidate": cid,
            "grade": grade,
            "score": score,
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
