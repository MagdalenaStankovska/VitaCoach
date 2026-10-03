"""LLM-as-a-judge evaluation harness for VitaCoach's RAG chat pipeline.

Answers the reviewer's main methodological objection: retrieval metrics
(MRR/P@8) only measure whether the *right documents* were retrieved, not
whether the *generated answer* is faithful to them, actually answers the
question, or makes efficient use of the retrieved context. This script runs
the real retrieval + generation path from app.py for each query in
eval/queries.jsonl, then asks Gemini to score the result on three metrics:

  - faithfulness (1-5):      is every claim in the answer supported by the
                              retrieved context?
  - answer_relevance (1-5):  does the answer actually answer the question?
  - context_precision (0-1): what fraction of the retrieved documents were
                              actually used/reflected in the answer?

Usage (run from fitness-rag-backend/):
    python eval/judge_eval.py --limit 10 --out eval/results.json
    python eval/judge_eval.py --out eval/results.json   # resumes, skips scored IDs

The full 200-query set will be supplied separately; eval/queries.jsonl ships
with a handful of example rows (2 per category) so the harness can be
exercised end-to-end today.

Every Gemini call (answer generation and judging) goes through app.py's
existing _generate_text_with_retry, which already retries on retryable
errors (503/UNAVAILABLE/RESOURCE_EXHAUSTED/DEADLINE) with backoff — reused
here rather than reimplemented, per the "never propagate, always substitute"
convention already used throughout the codebase. A single query's judge
failure never aborts the run; it's recorded as null scores and the harness
continues.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402  (import triggers real model/Postgres/Chroma startup)

METRICS = ["faithfulness", "answer_relevance", "context_precision"]
CATEGORIES = ["muscle-group", "equipment-constrained", "goal-directed", "injury-aware", "mixed-constraint"]


def load_queries(path: Path) -> list[dict]:
    queries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            queries.append(json.loads(line))
    return queries


def load_existing_results(path: Path) -> dict:
    """Returns {query_id: record} for resumable runs. Missing/corrupt file -> {}."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {row["id"]: row for row in data.get("results", [])}
    except Exception:
        return {}


def save_results(path: Path, results: list[dict]) -> None:
    """Atomic write, matching the save_json_file pattern used elsewhere in the repo."""
    payload = {"results": results}
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def retrieve_and_answer(query: str) -> tuple[str, list[str], dict]:
    """Runs the exact same retrieval + chat-generation path as /ask's chat
    branch (app.py), returning (answer_text, retrieved_docs, diagnostics)."""
    query_embedding = app_module.model.encode([query]).tolist()
    results = app_module.collection.query(
        query_embeddings=query_embedding,
        n_results=app_module.VECTOR_SEARCH_RESULTS,
        include=["documents", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    selected = app_module.select_recommended_documents(docs, distances)

    if selected:
        context_block = "Context:\n" + " ".join(selected)
    else:
        context_block = "No specific exercise context available."

    prompt = f"""
You are a certified professional fitness coach.

{context_block}

Question:
{query}

Instructions:
- Answer in English.
- If context exists, use it; otherwise use general fitness knowledge.
"""
    answer, error = app_module._generate_text_with_retry(prompt)
    if not answer:
        answer = f"[generation failed: {error}]"

    return answer, selected, {"retrieved_count": len(selected)}


def build_judge_prompt(query: str, context_docs: list[str], answer: str) -> str:
    context_text = "\n".join(f"- {d}" for d in context_docs) if context_docs else "(no documents retrieved)"
    return f"""
You are a strict evaluation judge for a fitness RAG assistant. Score the
ANSWER below against the QUESTION and the RETRIEVED CONTEXT it was supposed
to be grounded in.

QUESTION:
{query}

RETRIEVED CONTEXT (numbered documents actually given to the assistant):
{context_text}

ANSWER:
{answer}

Score on exactly these three metrics:
- faithfulness: integer 1-5. 5 = every claim in the answer is directly
  supported by the retrieved context or is uncontroversial general fitness
  knowledge; 1 = the answer contradicts or fabricates against the context.
- answer_relevance: integer 1-5. 5 = directly and completely answers the
  question asked; 1 = off-topic or non-responsive.
- context_precision: number between 0.0 and 1.0. The fraction of the
  RETRIEVED CONTEXT documents that were actually used or reflected in the
  answer (documents retrieved but never used lower this score).

Respond with STRICT JSON ONLY, no markdown fences, no commentary, in exactly
this shape:
{{"faithfulness": <int>, "answer_relevance": <int>, "context_precision": <float>, "rationale": "<one sentence>"}}
"""


def parse_judge_response(text: str) -> dict | None:
    """Defensive JSON parsing: strips common markdown code-fence wrapping,
    then json.loads. Returns None (never raises) on any failure."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    try:
        return {
            "faithfulness": int(data["faithfulness"]),
            "answer_relevance": int(data["answer_relevance"]),
            "context_precision": float(data["context_precision"]),
            "rationale": str(data.get("rationale", ""))[:500],
        }
    except (KeyError, TypeError, ValueError):
        return None


def judge_call(query: str, context_docs: list[str], answer: str) -> tuple[dict | None, str]:
    """(scores_or_None, error_str). Rate-limit backoff and retryable-error
    handling are inherited from _generate_text_with_retry — not
    reimplemented here."""
    prompt = build_judge_prompt(query, context_docs, answer)
    text, error = app_module._generate_text_with_retry(prompt)
    if not text:
        return None, error or "Judge call returned no text"
    scores = parse_judge_response(text)
    if scores is None:
        return None, f"Judge returned non-JSON or malformed output: {text[:200]!r}"
    return scores, ""


def run(queries_path: Path, out_path: Path, limit: int | None) -> list[dict]:
    queries = load_queries(queries_path)
    if limit:
        queries = queries[:limit]

    existing = load_existing_results(out_path)
    results = list(existing.values())
    skipped = 0

    for q in queries:
        if q["id"] in existing:
            skipped += 1
            continue

        print(f"[EVAL] scoring {q['id']} ({q['category']}): {q['query'][:60]!r}")
        answer, context_docs, diag = retrieve_and_answer(q["query"])
        scores, error = judge_call(q["query"], context_docs, answer)

        record = {
            "id": q["id"],
            "category": q["category"],
            "query": q["query"],
            "retrieved_count": diag["retrieved_count"],
            "scores": scores,  # None on judge failure — never aborts the run
            "judge_error": error or None,
        }
        results.append(record)
        save_results(out_path, results)  # write incrementally so a crash mid-run still resumes cleanly

        if error:
            print(f"[EVAL]   judge failed: {error}")
            time.sleep(1)  # small courtesy pause after a failure before the next call

    print(f"[EVAL] done. {len(results) - skipped} newly scored, {skipped} skipped (already in {out_path}).")
    return results


def print_summary(results: list[dict]) -> None:
    def stats_for(rows: list[dict], metric: str) -> tuple[float | None, float | None, int]:
        values = [r["scores"][metric] for r in rows if r.get("scores")]
        if not values:
            return None, None, 0
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        return mean, stdev, len(values)

    print("\n=== Judge Evaluation Summary ===")
    failed = sum(1 for r in results if not r.get("scores"))
    print(f"Total queries: {len(results)}  |  judge failures: {failed}\n")

    header = f"{'Group':<22}{'N':>4}" + "".join(f"{m:>22}" for m in METRICS)
    print(header)
    print("-" * len(header))

    def row_line(label: str, rows: list[dict]):
        cells = [label.ljust(22)]
        n_values = [stats_for(rows, m)[2] for m in METRICS]
        n = max(n_values) if n_values else 0
        cells.append(str(n).rjust(4))
        for m in METRICS:
            mean, stdev, _ = stats_for(rows, m)
            cell = f"{mean:.2f}+/-{stdev:.2f}" if mean is not None else "n/a"
            cells.append(cell.rjust(22))
        print("".join(cells))

    row_line("OVERALL", results)
    for cat in CATEGORIES:
        cat_rows = [r for r in results if r["category"] == cat]
        if cat_rows:
            row_line(cat, cat_rows)


def main():
    parser = argparse.ArgumentParser(description="LLM-as-a-judge eval harness for VitaCoach's RAG chat pipeline.")
    parser.add_argument("--queries", default=str(Path(__file__).parent / "queries.jsonl"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "results.json"))
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of queries processed this run.")
    args = parser.parse_args()

    results = run(Path(args.queries), Path(args.out), args.limit)
    print_summary(results)


if __name__ == "__main__":
    main()
