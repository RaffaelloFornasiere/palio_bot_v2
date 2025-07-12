"""Simple dependency container for the palio bot application."""

from typing import Dict, Optional, Literal, Union

from .agent import Agent
from .system import System
from .text_editor_tool import create_text_editor_tools
from .json_editor_tool import create_json_editor_tools
from .llm_clients.llamacpp_client import LlamaCPPClient
from .llm_clients.anthropic_client import AnthropicClient
from .llm_clients.base_client import BaseLLMClient
from .models import Tool


class Container:
    """Simple dependency container for the application."""

    def __init__(
        self, 
        palio_file_path: str = "palio.json", 
        llamacpp_url: str = "http://mac-studio.local:11454",
        llm_provider: Literal["llamacpp", "anthropic"] = "llamacpp",
        anthropic_api_key: Optional[str] = None,
        use_json_editor: bool = True
    ):
        """Initialize the container with configuration.
        
        Args:
            palio_file_path: Path to the palio.json file
            llamacpp_url: URL for LlamaCPP server (used if llm_provider is 'llamacpp')
            llm_provider: Which LLM provider to use ('llamacpp' or 'anthropic')
            anthropic_api_key: API key for Anthropic (used if llm_provider is 'anthropic')
            use_json_editor: Whether to use JSONPath-based editor (True) or text-based editor (False)
        """
        self.palio_file_path = palio_file_path
        self.llamacpp_url = llamacpp_url
        self.llm_provider = llm_provider
        self.anthropic_api_key = anthropic_api_key
        self.use_json_editor = use_json_editor

        # Initialize all services lazily
        self._llm_client: Optional[BaseLLMClient] = None
        self._tools: Optional[Dict[str, Tool]] = None
        self._agent: Optional[Agent] = None
        self._system: Optional[System] = None

    def llm_client(self) -> BaseLLMClient:
        """Get or create LLM client based on configured provider."""
        if self._llm_client is None:
            if self.llm_provider == "llamacpp":
                self._llm_client = LlamaCPPClient(base_url=self.llamacpp_url)
            elif self.llm_provider == "anthropic":
                self._llm_client = AnthropicClient(api_key=self.anthropic_api_key)
            else:
                raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
        return self._llm_client

    def tools(self) -> Dict[str, Tool]:
        """Get or create tools based on configuration."""
        if self._tools is None:
            if self.use_json_editor:
                self._tools = create_json_editor_tools(file_path=self.palio_file_path)
            else:
                self._tools = create_text_editor_tools(file_path=self.palio_file_path)
        return self._tools

    def agent(self) -> Agent:
        """Get or create agent."""
        if self._agent is None:
            self._agent = Agent(
                llm_client=self.llm_client(),
                tools=self.tools()
            )
        return self._agent

    def system(self) -> System:
        """Get or create system."""
        if self._system is None:
            self._system = System(
                agent=self.agent(),
                palio_file_path=self.palio_file_path,
                session_file_path="session.json"
            )
        return self._system

    async def init_container(self) -> None:
        """Initialize the container by creating all services."""
        # Initialize all services to ensure they're created
        self.llm_client()
        self.tools()
        self.agent()
        self.system()
        
        # All initialization is done during service creation
        # No additional setup needed for this simple system