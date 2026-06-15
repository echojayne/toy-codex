from agent import Agent, AgentConfig
from llm import LlmClient, load_llm_config
from context import ContextManager
from pathlib import Path
from workspace_tools import (
    create_read_file_tool, 
    create_list_files_tool,
    create_search_text_tool
)
from editing_tools import create_apply_patch_tool, create_write_file_tool
from command_tools import create_exec_command_tool

from tools import ToolRegistry

def build_agent() -> Agent:
    config_path = Path(__file__).with_name("config.toml")
    llm_config = load_llm_config(config_path)
    agent_config = AgentConfig(
        system_prompt="You are a helpful assistant.",
        max_steps=20,
    )
    llm = LlmClient(llm_config)
    context = ContextManager()
    tools = ToolRegistry()

    tools.register(create_read_file_tool(Path.cwd()))
    tools.register(create_list_files_tool(Path.cwd()))
    tools.register(create_search_text_tool(Path.cwd()))
    tools.register(create_write_file_tool(Path.cwd()))
    tools.register(create_apply_patch_tool(Path.cwd()))
    tools.register(create_exec_command_tool(Path.cwd()))

    return Agent(
        config=agent_config,
        llm=llm,
        context=context,
        tools=tools,
    )

def run_cli(agent: Agent) -> None:
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if user_input.lower() in {"exit", "quit"}:
            return

        if not user_input:
            continue
        
        response = agent.run(user_input)
        print(f"Assistant: {response}")

def main() -> None:
    agent = build_agent()
    run_cli(agent)


if __name__ == "__main__":
    main()
