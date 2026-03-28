from app.agent.create_agent import build_agent


def main() -> None:
    agent = build_agent()
    config = {"configurable": {"thread_id": "demo_thread_id"}}


    print("RAG Cli started, Type 'exit' to quit.")
    while True:
        user_input = input("\n你> ").strip()
        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("再见")
            break

        result = agent.invoke({"messages": [{"role": "user", "content": user_input}]}, config=config)
        final_msg = result["messages"][-1]
        print(f"AI: {final_msg.content}")

if __name__ == "__main__":
    main()