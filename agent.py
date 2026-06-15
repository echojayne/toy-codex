from dataclasses import dataclass

from llm import LlmClient
from context import ContextManager
from tools import ToolRegistry

@dataclass(frozen=True, slots=True)
class AgentConfig:
    system_prompt: str
    max_steps: int = 20

class Agent:
    def __init__(
        self,
        config: AgentConfig,
        llm: LlmClient,
        context: ContextManager,
        tools: ToolRegistry,
    ) -> None:
        self._config = config
        self._llm = llm
        self._context = context
        self._tools = tools

    def run(self, user_input: str) -> str:
        
        current_step = 0
        self._context.record_user(user_input)
        
        while current_step < self._config.max_steps:
            current_step += 1
            assistant_message = self._llm.complete(
                system_prompt=self._config.system_prompt,
                items=self._context.snapshot(),
                tools=self._tools.definitions(),
            )
            self._context.record_assistant(assistant_message)


            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    tool_message = self._tools.execute(tool_call)
                    self._context.record_tool(tool_message)
                continue
            if assistant_message.content is None:
                raise RuntimeError("LLM response has no content or tool calls")

            return assistant_message.content
        raise RuntimeError("Maximum number of steps exceeded without producing a final answer")
        
        