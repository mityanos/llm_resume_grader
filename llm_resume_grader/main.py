# llm_resume_grader/main.py
#!/usr/bin/env python3
"""
LLM-powered résumé grader (single-message edition).
Reads inputs from llm_resume_grader/data/input/, writes outputs to llm_resume_grader/data/output/
and generates per-candidate Markdown files in data/output/candidates_md/.
"""

from __future__ import annotations

import os
import json
import logging
import re
import time
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

# --- утилита для перевода относительных путей в абсолютные ------------------
# Каталог llm_resume_grader/ — единственный «корень» для относительных путей
BASE_DIR = Path(__file__).resolve().parent          # .../llm_resume_grader

def abs_path(rel: str | Path) -> Path:
    """Сделать абсолютный путь относительно llm_resume_grader/."""
    return (BASE_DIR / rel).resolve()


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
    load_dotenv(dotenv_path=BASE_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing in .env")


def read_text(path: str | Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def load_system_prompt(path: str | Path) -> str:
    return read_text(path)


def candidate_id(text: str, fallback: str) -> str:
    """
    Extracts "Candidate ID: <ID>" from the text, or uses fallback (filename) if not found.
    """
    match = re.search(r"Candidate ID:\s*([^\s\n]+)", text)
    return match.group(1) if match else fallback


def build_message(sys_prompt: str, cand_doc: str) -> List[Dict[str, str]]:
    """
    Combines the system prompt and candidate Markdown into one chat message sequence.
    """
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"```markdown\n{cand_doc}\n```"}
    ]


def safe_chat(
    client: OpenAI,
    messages: list[dict[str, str]],
    model: str,
    retry_max: int,
    **params,  # temperature, top_p, max_tokens, …
) -> str:
    """
    Sends messages to OpenAI Chat API with retries on RateLimitError or APIError.
    """
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
    Returns None on failure or if schema is unexpected.
    """
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    depth = None
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth is None:
                depth = 0
                start = i
            depth += 1
        elif ch == "}":
            if depth is not None:
                depth -= 1
                if depth == 0 and start is not None:
                    snippet = text[start : i + 1]
                    try:
                        parsed = json.loads(snippet)
                        required = {
                            "common_checklist",
                            "common_score",
                            "common_score_comment",
                            "local_checklist",
                            "local_score",
                            "local_score_comment",
                            "total_score",
                            "total_score_comment",
                            "grade",
                            "grade_explanation",
                            "comment",
                        }
                        if not required.issubset(parsed.keys()):
                            logging.error(
                                "Unexpected JSON schema: missing fields %s",
                                required - parsed.keys(),
                            )
                            return None
                        return parsed
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
    Extract "grade" and "grade_explanation" from the model's response.
    If JSON found, use fields; otherwise, fallback to regex parsing of "Grade: X – explanation".
    """
    parsed = extract_json_object(answer)
    if parsed is not None:
        grade = parsed.get("grade", "?")
        expl = parsed.get("grade_explanation", "") or parsed.get("explanation", "")
        return grade, expl.strip().replace("\n", " ")
    regex = re.compile(r"Grade:\s*([A-D])\s*[-–]\s*(.+)", re.IGNORECASE | re.DOTALL)
    m = regex.search(answer)
    if m:
        grade = m.group(1).upper()
        expl = m.group(2).strip()
        return grade, expl
    return "?", answer.strip().replace("\n", " ")


def sanitize_filename(name: str) -> str:
    """
    Replace spaces with underscores and remove characters that cannot appear in filenames.
    """
    return re.sub(r"[^\w\-]", "_", name.replace(" ", "_"))


def render_candidate_md(entry: Dict[str, Any]) -> str:
    """
    Create a per-candidate Markdown file with detailed, human-readable analysis.
    """
    data = entry.get("parsed_response", {})
    candidate = entry["candidate"]
    grade = data.get("grade", entry.get("grade", "?"))
    total_score = data.get("total_score", entry.get("score", 0))

    lines: List[str] = []
    lines.append(f"**Grade:** {grade} (total_score: {total_score})  \n")
    lines.append(f"## {candidate}\n")
    lines.append(f"**Company-fit = {data.get('common_score', 0)}**  ")
    lines.append(f"“{data.get('common_score_comment', '')}”\n")
    lines.append(f"**Vacancy-fit = {data.get('local_score', 0)}**  ")
    lines.append(f"“{data.get('local_score_comment', '')}”\n")
    lines.append(f"**Grade Explanation**  ")
    lines.append(f"“{data.get('grade_explanation', '')}”\n\n")

    lines.append(f"**Pros**  ")
    pros = data.get("comment", {}).get("pros", [])
    if pros:
        for p in pros:
            lines.append(f"- {p}  ")
    else:
        lines.append("- (нет)  ")

    lines.append(f"\n**Cons**  ")
    cons = data.get("comment", {}).get("cons", [])
    if cons:
        for c in cons:
            lines.append(f"- {c}  ")
    else:
        lines.append("- (нет)  ")

    return "\n".join(lines)


def render_md_summary(rows: List[Dict[str, Any]], candidate_md_dir: str = ".") -> str:
    """
    Markdown table with clickable links to per-candidate files (relative to summary's location).
    """
    lines = [
        "| Candidate | Grade | Explanation |",
        "|-----------|-------|-------------|",
    ]
    for r in rows:
        candidate = r["candidate"]
        grade = r["parsed_response"].get("grade", "?") if r.get("parsed_response") else r["grade"]
        data = r.get("parsed_response", {})
        grade_expl = data.get("grade_explanation", "")
        pros = data.get("comment", {}).get("pros", [])
        cons = data.get("comment", {}).get("cons", [])

        expl_lines: List[str] = []
        expl_lines.append(f"**Grade Explanation**<br>“{grade_expl}”")
        expl_lines.append(f"<br>**Pros**")
        if pros:
            for p in pros:
                expl_lines.append(f"<br>- {p}")
        else:
            expl_lines.append(f"<br>- (нет)")
        expl_lines.append(f"<br>**Cons**")
        if cons:
            for c in cons:
                expl_lines.append(f"<br>- {c}")
        else:
            expl_lines.append(f"<br>- (нет)")

        explanation_cell = "".join(expl_lines)
        filename = sanitize_filename(candidate) + ".md"
        candidate_link = f"[{candidate}]({candidate_md_dir}/{filename})"
        lines.append(f"| {candidate_link} | {grade} | {explanation_cell} |")

    return "\n".join(lines)


# ───────────────────────── main ─────────────────────────────

def main() -> None:
    setup_logging()
    cfg = load_config(BASE_DIR / "config.yaml")
    load_env()

    # 1) Создаём все каталоги, упомянутые в конфиге
    for key in ("out_json", "out_md_summary", "out_md_full", "candidate_md_dir"):
        abs_path(cfg["paths"][key]).parent.mkdir(parents=True, exist_ok=True)
    candidate_md_dir = abs_path(cfg["paths"]["candidate_md_dir"])
    candidate_md_dir.mkdir(parents=True, exist_ok=True)      # ←  ❗ обязательно

    client = OpenAI()

    sys_prompt = load_system_prompt(abs_path(cfg["paths"]["system_prompt"]))
    files = sorted(glob(str(abs_path(cfg["paths"]["candidates_glob"]))))

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

        parsed = extract_json_object(answer)
        grade, expl = extract_grade_expl(answer)
        score = cfg["grading"]["scale"].get(grade, 0)

        entry: Dict[str, Any] = {
            "candidate": cid,
            "grade": grade,
            "score": score,
            "explanation": expl,
            "raw_response": answer,
        }
        if parsed:
            entry["parsed_response"] = parsed

        results.append(entry)
        logging.info("✓ %s → %s", cid, grade)

    sorted_results = sorted(results, key=lambda r: -r["score"])

    # Write results.json into data/output
    full_json = json.dumps(sorted_results, indent=2, ensure_ascii=False)
    abs_path(cfg["paths"]["out_json"]).write_text(full_json, encoding="utf-8")

    # Write per-candidate MD files into data/output/candidates_md
    for r in sorted_results:
        candidate = r["candidate"]
        filename = candidate_md_dir / (sanitize_filename(candidate) + ".md")
        content = render_candidate_md(r)
        Path(filename).write_text(content, encoding="utf-8")

    # Write summary table into data/output/results_summary.md
    # Относительная ссылка = «подкаталог рядом с summary»
    rel_link = Path(cfg["paths"]["candidate_md_dir"]).name   # "candidates_md"
    summary_md = render_md_summary(sorted_results, candidate_md_dir=rel_link)
    abs_path(cfg["paths"]["out_md_summary"]).write_text(summary_md, encoding="utf-8")


    logging.info("Finished: %d candidates", len(results))


if __name__ == "__main__":
    main()