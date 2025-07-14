"""Dependency container with event system integration."""

import logging
from typing import Dict, Optional, Literal

from .agent import Agent
from .system import System
from .stream import Stream
from .cli_consumer import CLIConsumer
from .telegram_consumer import TelegramConsumer
from .text_editor_tool import create_text_editor_tools
from .json_editor_tool import create_json_editor_tools
from .llm_clients.llamacpp_client import LlamaCPPClient
from .llm_clients.anthropic_client import AnthropicClient
from .llm_clients.base_client import BaseLLMClient
from .models import Tool
from telegram import Bot

logger = logging.getLogger(__name__)


class Container:
    """Dependency container with event streaming support."""

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
        self._stream: Optional[Stream] = None
        self._agent: Optional[Agent] = None
        self._system: Optional[System] = None
        self._cli_consumer: Optional[CLIConsumer] = None
        
        logger.info(f"Container initialized with provider={llm_provider}, json_editor={use_json_editor}")

    def llm_client(self) -> BaseLLMClient:
        """Get or create LLM client based on configured provider."""
        if self._llm_client is None:
            logger.info(f"Creating LLM client: {self.llm_provider}")
            if self.llm_provider == "llamacpp":
                logger.debug(f"LlamaCPP URL: {self.llamacpp_url}")
                self._llm_client = LlamaCPPClient(base_url=self.llamacpp_url)
            elif self.llm_provider == "anthropic":
                logger.debug("Using Anthropic API")
                self._llm_client = AnthropicClient(api_key=self.anthropic_api_key)
            else:
                raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
            logger.info("LLM client created successfully")
        return self._llm_client

    def tools(self) -> Dict[str, Tool]:
        """Get or create tools based on configuration."""
        if self._tools is None:
            logger.info(f"Creating tools: json_editor={self.use_json_editor}")
            if self.use_json_editor:
                self._tools = create_json_editor_tools(file_path="palio_updated.json")
            else:
                self._tools = create_text_editor_tools(file_path="palio_updated.json")
            logger.info(f"Created {len(self._tools)} tools: {list(self._tools.keys())}")
        return self._tools

    def stream(self) -> Stream:
        """Get or create event stream."""
        if self._stream is None:
            logger.info("Creating event stream")
            self._stream = Stream()
        return self._stream

    def agent(self) -> Agent:
        """Get or create agent with event support."""
        if self._agent is None:
            logger.info("Creating agent")
            self._agent = Agent(
                llm_client=self.llm_client(),
                tools=self.tools(),
                stream=self.stream()
            )
            logger.info("Agent created successfully")
        return self._agent

    def system(self) -> System:
        """Get or create system with event support."""
        if self._system is None:
            logger.info("Creating system")
            self._system = System(
                agent=self.agent(),
                stream=self.stream(),
                palio_file_path=self.palio_file_path,
                session_file_path="session.json"
            )
            logger.info("System created successfully")
        return self._system
    
    def cli_consumer(self) -> CLIConsumer:
        """Get or create CLI consumer."""
        if self._cli_consumer is None:
            logger.info("Creating CLI consumer")
            self._cli_consumer = CLIConsumer()
            # Auto-register with stream
            self.stream().add_consumer(self._cli_consumer)
            logger.info("CLI consumer registered with stream")
        return self._cli_consumer
    
    def create_telegram_consumer(self, bot: Bot, chat_id: int) -> TelegramConsumer:
        """Create a new Telegram consumer for a specific chat.
        
        Note: Telegram consumers are created per-chat, not singleton.
        """
        consumer = TelegramConsumer(bot, chat_id)
        self.stream().add_consumer(consumer)
        return consumer

    async def init_container(self) -> None:
        """Initialize the container by creating all services and starting event processing."""
        logger.info("\n" + "="*60)
        logger.info("Initializing container")
        logger.info("="*60)
        
        try:
            # Initialize core services
            logger.info("Creating core services...")
            self.llm_client()
            self.tools()
            self.stream()
            self.agent()
            self.system()
            
            # Start event processing
            logger.info("Starting event processing...")
            await self.stream().start_processing()
            
            logger.info("Container initialization complete")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"Failed to initialize container: {e}", exc_info=True)
            raise