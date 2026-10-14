"""Measure retrieval quality, answer accuracy, refusals and data leaks.

Usage:
  python -m app.evaluate --retrieval-only   # embeddings only, almost free
  python -m app.evaluate                    # also calls the LLM

Question types in eval/questions.jsonl:
  answerable   -> expected_source set: must retrieve it and mention expected_keywords
  restricted   -> forbidden set: confidential values must NEVER appear (retrieval or answer)
  unanswerable -> neither: the bot must refuse
"""

import json
import sys

from app.config import ROOT, get_settings
from app.rag import NO_ANSWER, answer_question, retrieve
from app.vectorstore import get_vectorstore

EVAL_FILE = ROOT / "eval" / "questions.jsonl"


def _kind(item: dict) -> str:
    if item.get("expected_source"):
        return "answerable"
    if item.get("forbidden"):
        return "restricted"
    return "unanswerable"


def main() -> None:
    retrieval_only = "--retrieval-only" in sys.argv
    settings = get_settings()
    store = get_vectorstore(settings)
    items = [json.loads(line) for line in EVAL_FILE.read_text(encoding="utf-8").splitlines()
             if line.strip()]

    hits, reciprocal_ranks, accuracy, leak_free, refusals, tokens = [], [], [], [], [], 0
    print(f"Evaluating {len(items)} questions (top_k={settings.top_k}, "
          f"min_relevance={settings.min_relevance})\n")

    for item in items:
        question, kind = item["question"], _kind(item)
        results = retrieve(question, settings, store)
        sources = [doc.metadata["source"] for doc, _ in results]
        retrieved_text = " ".join(doc.page_content for doc, _ in results).lower()
        line = f"{kind[:5].upper():<6}"

        if kind == "answerable":
            expected = item["expected_source"]
            rank = sources.index(expected) + 1 if expected in sources else None
            hits.append(rank is not None)
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            line += f"{'HIT ' if rank else 'MISS'} rank={rank or '-'}"
        elif kind == "restricted":
            leaked = [f for f in item["forbidden"] if f.lower() in retrieved_text]
            line += f"retrieval-leak={'YES ' + str(leaked) if leaked else 'no'}"
            if retrieval_only:
                leak_free.append(not leaked)
        else:
            line += f"retrieved={len(results)}"

        if not retrieval_only:
            result = answer_question(question, None, settings, store)
            answer = result["answer"].lower()
            tokens += result["usage"]["total_tokens"]

            if kind == "answerable":
                keywords = item.get("expected_keywords", [])
                score = sum(k.lower() in answer for k in keywords) / len(keywords) if keywords else 1.0
                accuracy.append(score)
                line += f" answer={score:.0%}"
            elif kind == "restricted":
                leaked = [f for f in item["forbidden"]
                          if f.lower() in answer or f.lower() in retrieved_text]
                leak_free.append(not leaked)
                line += f" answer-leak={'YES ' + str(leaked) if leaked else 'no'}"
            else:
                refused = NO_ANSWER.lower() in answer or "don't know" in answer
                refusals.append(refused)
                line += f" refused={'yes' if refused else 'NO'}"

        print(f"{line:<48} {question}")

    print("\n=== SUMMARY ===")
    if hits:
        print(f"Retrieval hit rate:  {sum(hits) / len(hits):.0%}")
        print(f"MRR:                 {sum(reciprocal_ranks) / len(reciprocal_ranks):.2f}")
    if accuracy:
        print(f"Answer accuracy:     {sum(accuracy) / len(accuracy):.0%}")
    if leak_free:
        print(f"Leak tests passed:   {sum(leak_free)}/{len(leak_free)}")
    if refusals:
        print(f"Correct refusals:    {sum(refusals)}/{len(refusals)}")
    if not retrieval_only:
        print(f"Total tokens:        {tokens}")


if __name__ == "__main__":
    main()
