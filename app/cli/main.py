import logging

from app.config.logging_setup import setup_logging
from app.retrieval.retriever import format_citation_label
from app.services.rag_service import get_rag_service, new_thread_id

logger = logging.getLogger(__name__)


def main() -> None:
    log_path = setup_logging()
    rag_service = get_rag_service()
    thread_id = new_thread_id("cli")

    logger.info("CLI 已启动。日志文件=%s", log_path)

    print("RAG Cli started, Type 'exit' to quit.")
    while True:
        user_input = input("\n你> ").strip()
        if not user_input:
            continue
        if user_input.lower() == "exit":
            logger.info("用户主动退出 CLI。")
            print("再见")
            break

        logger.info("收到用户输入。thread_id=%s 字符数=%s", thread_id, len(user_input))
        try:
            answer_started = False
            final_result = None
            for event in rag_service.stream(user_input, thread_id=thread_id):
                if event.type == "tool_call":
                    if answer_started:
                        print()
                        answer_started = False
                    print(f"[状态] {event.status_line}")
                    continue

                if event.type == "tool_result":
                    if answer_started:
                        print()
                        answer_started = False
                    print(f"[状态] {event.status_line}")
                    for citation in event.citations:
                        print(f"[引用] {format_citation_label(citation)}")
                    continue

                if event.type == "answer":
                    if not answer_started:
                        print("AI: ", end="", flush=True)
                        answer_started = True
                    print(event.content, end="", flush=True)
                    continue

                if event.type == "complete":
                    final_result = event.result

            if answer_started:
                print()

            usage = (final_result.usage if final_result else None) or {}
            total_tokens = usage.get("total_tokens")
            if total_tokens is not None:
                print(f"[完成] total_tokens={total_tokens}")

            logger.info("已生成助手回复。字符数=%s", len(final_result.answer if final_result else ""))
        except Exception:
            logger.exception("Agent 调用失败。thread_id=%s", thread_id)
            raise

if __name__ == "__main__":
    main()
