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
            current_ai_id = None
            for event in client.stream(user_input, thread_id=thread_id):
                if event.type == "values":
                    continue

                if event.type == "messages-tuple":
                    event_type = event.data.get("type")
                    if event_type == "ai":
                        tool_calls = event.data.get("tool_calls") or []
                        if tool_calls:
                            if current_ai_id is not None:
                                print()
                                current_ai_id = None
                            for tool_call in tool_calls:
                                print(f"[状态] 调用工具 {tool_call.get('name')}")
                            continue

                        content = event.data.get("content", "")
                        if content:
                            message_id = event.data.get("id")
                            if current_ai_id != message_id:
                                if current_ai_id is not None:
                                    print()
                                current_ai_id = message_id
                                answer = ""
                                print("AI: ", end="", flush=True)
                            print(content, end="", flush=True)
                            answer += content
                        continue

                    if event_type == "tool":
                        if current_ai_id is not None:
                            print()
                            current_ai_id = None
                        print(f"[状态] {event.data.get('name')} 已返回结果")
                        continue

                if event.type == "end":
                    if current_ai_id is not None:
                        print()
                        current_ai_id = None
                    usage = event.data.get("usage") or {}
                    total_tokens = usage.get("total_tokens")
                    if total_tokens is not None:
                        print(f"[完成] total_tokens={total_tokens}")

            logger.info("已生成助手回复。字符数=%s", len(answer))
        except Exception:
            logger.exception("Agent 调用失败。thread_id=%s", thread_id)
            raise

if __name__ == "__main__":
    main()
