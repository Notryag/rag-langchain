import logging

from app.config.logging_setup import setup_logging
from app.services.chat_client import get_chat_client, new_thread_id

logger = logging.getLogger(__name__)


def main() -> None:
    log_path = setup_logging()
    client = get_chat_client()
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
            answer = ""
            response_started = False
            for event in client.stream(user_input, thread_id):
                if event.kind == "status":
                    if response_started:
                        print()
                        response_started = False
                    print(f"[状态] {event.text}")
                    continue

                if event.kind == "token":
                    if not response_started:
                        print("AI: ", end="", flush=True)
                        response_started = True
                    print(event.text, end="", flush=True)
                    answer += event.text
                    continue

                if response_started:
                    print()

                usage = event.metadata.get("usage") or {}
                elapsed_ms = event.metadata.get("elapsed_ms")
                if elapsed_ms is not None:
                    summary = f"[完成] {elapsed_ms} ms"
                    total_tokens = usage.get("total_tokens")
                    if total_tokens is not None:
                        summary += f" | total_tokens={total_tokens}"
                    print(summary)

            logger.info("已生成助手回复。字符数=%s", len(answer))
        except Exception:
            logger.exception("Agent 调用失败。thread_id=%s", thread_id)
            raise

if __name__ == "__main__":
    main()
