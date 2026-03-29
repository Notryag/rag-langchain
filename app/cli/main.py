import logging

from app.config.logging_setup import setup_logging
from app.services.chat_service import ask, build_thread_config, get_agent

logger = logging.getLogger(__name__)


def main() -> None:
    log_path = setup_logging()
    get_agent()
    config = build_thread_config("demo_thread_id")

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

        logger.info("收到用户输入。thread_id=%s 字符数=%s", config["configurable"]["thread_id"], len(user_input))
        try:
            answer = ask(user_input, config["configurable"]["thread_id"])
            logger.info("已生成助手回复。字符数=%s", len(answer))
            print(f"AI: {answer}")
        except Exception:
            logger.exception("Agent 调用失败。thread_id=%s", config["configurable"]["thread_id"])
            raise

if __name__ == "__main__":
    main()
