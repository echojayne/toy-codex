import json
from pathlib import Path

from agent import Agent, AgentConfig
from audit_log import SQLiteAuditLog
from context import ContextManager
from event import AgentEvent
from llm import LlmClient, load_llm_config
from workspace_tools import (
    create_read_file_tool, 
    create_list_files_tool,
    create_search_text_tool
)
from editing_tools import create_apply_patch_tool, create_write_file_tool
from command_tools import create_exec_command_tool

from tools import ToolRegistry

AUDIT_DB_PATH = Path(".toy_codex") / "audit" / "events.sqlite3"

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
    with SQLiteAuditLog(AUDIT_DB_PATH) as audit_log:
        print(f"Audit log: {audit_log.path}")
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

            try:
                for event in agent.run_stream(user_input):
                    audit_log.append(event)
                    rendered = render_event(event)
                    if rendered:
                        print(rendered)
            except Exception as error:
                print(f"Error: {type(error).__name__}: {error}")

def render_event(event: AgentEvent) -> str | None:
    if event.type == "turn.started":
        return f"[turn {event.turn_id[:8]}] started"

    if event.type == "llm.started":
        return (
            f"[step {event.payload['step']}] calling model "
            f"with {event.payload['context_items']} context items"
        )

    if event.type == "llm.completed":
        assistant = event.payload["assistant"]
        if not isinstance(assistant, dict):
            return "[model] completed"
        tool_call_count = assistant.get("tool_call_count")
        content = assistant.get("content")
        if tool_call_count:
            return f"[model] requested {tool_call_count} tool call(s)"
        if isinstance(content, str):
            return f"[model] answered: {_preview(content)}"
        return "[model] completed"

    if event.type == "tool.started":
        tool_call = event.payload["tool_call"]
        if not isinstance(tool_call, dict):
            return "[tool] started"
        name = tool_call.get("name")
        arguments = json.dumps(
            tool_call.get("arguments"),
            ensure_ascii=False,
            sort_keys=True,
        )
        return f"[tool:{name}] start {arguments}"

    if event.type == "tool.completed":
        tool_result = event.payload["tool_result"]
        if not isinstance(tool_result, dict):
            return "[tool] completed"
        name = tool_result.get("name")
        is_error = tool_result.get("is_error")
        content = tool_result.get("content")
        status = "error" if is_error else "ok"
        return f"[tool:{name}] {status}: {_preview(str(content))}"

    if event.type == "turn.completed":
        content = event.payload.get("content")
        return f"Assistant: {content}"

    if event.type == "turn.failed":
        return (
            f"[failed] {event.payload.get('error_type')}: "
            f"{event.payload.get('message')}"
        )

    return None

def _preview(value: str, limit: int = 500) -> str:
    compact = value.replace("\n", "\\n")
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."

def main() -> None:
    agent = build_agent()
    run_cli(agent)


if __name__ == "__main__":
    main()
