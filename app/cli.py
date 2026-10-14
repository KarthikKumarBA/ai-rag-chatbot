"""Terminal chat.

Usage:
  python -m app.cli
"""

from app.config import get_settings
from app.rag import answer_question
from app.vectorstore import get_vectorstore


def main() -> None:
    settings = get_settings()
    store = get_vectorstore(settings)
    history: list[dict] = []

    print(f"Northwind assistant | source: {settings.docs_source} | LLM: {settings.llm_provider} | "
          f"embeddings: {settings.embedding_provider}")
    print("Ask a question, or type 'exit' to quit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            break

        result = answer_question(question, history, settings, store)

        print(f"\nBot: {result['answer']}")
        if result["standalone_question"] != question:
            print(f"  (understood as: {result['standalone_question']})")
        for s in result["sources"]:
            section = f" - {s['section']}" if s["section"] else ""
            link = f"  {s['url']}" if s["url"] else ""
            print(f"  [{s['id']}] {s['title'] or s['source']}{section} (score {s['score']}){link}")
        print(f"  tokens: {result['usage']['total_tokens']}\n")

        history = (history + [{"question": question, "answer": result["answer"]}])[
            -settings.history_turns:]


if __name__ == "__main__":
    main()
