import logging

from app.agent.create_agent import build_agent
from app.config.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    log_path = setup_logging()
    agent = build_agent()
    config = {"configurable": {"thread_id": "demo_thread_id"}}

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
            result = agent.invoke({"messages": [{"role": "user", "content": user_input}]}, config=config)
            final_msg = result["messages"][-1]
            logger.info("已生成助手回复。字符数=%s", len(str(final_msg.content)))
            print(f"AI: {final_msg.content}")
        except Exception:
            logger.exception("Agent 调用失败。thread_id=%s", config["configurable"]["thread_id"])
            raise

if __name__ == "__main__":
    main()
