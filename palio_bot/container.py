"""Dependency container with file registry and event system integration."""

import logging
from typing import Dict, Optional, Literal

from palio_bot.agent.agent import Agent
from .system import System
from palio_bot.stream.stream import Stream
from palio_bot.cli.cli_consumer import CLIConsumer
from palio_bot.telegram_bot.telegram_consumer import TelegramConsumer
from palio_bot.tools.multi_json_editor_tool import create_multi_json_editor_tools
from palio_bot.tools.file_registry import FileRegistry, FileConfig
from .llm_clients.llamacpp_client import LlamaCPPClient
from .llm_clients.anthropic_client import AnthropicClient
from .llm_clients.ollama_client import OllamaClient
from .llm_clients.base_client import BaseLLMClient
from palio_bot.agent.models import Tool
from palio_bot.config import Config
from palio_bot.services.audio_transcription import AudioTranscriptionService
from palio_bot.models.palio_models import PalioData
from palio_bot.models.game_status_models import PalioGamesStatus
from palio_bot.models.leaderboard_models import Leaderboard
from telegram import Bot

logger = logging.getLogger(__name__)


class Container:
    """Dependency container with file registry and event streaming support."""

    def __init__(
        self, 
        config: Config = None,
        llm_provider: Literal["llamacpp", "anthropic", "ollama"] = None,
        anthropic_api_key: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ):
        """Initialize the container with configuration.
        
        Args:
            config: Configuration object (will create default if not provided)
            llm_provider: Which LLM provider to use (overrides config if provided)
            anthropic_api_key: API key for Anthropic (overrides config if provided)
            ollama_model: Model name for Ollama (defaults to "llama3.2")
        """
        if config is None:
            config = Config()
            
        self.config = config
        self.llamacpp_url = config.llama_cpp_url
        self.llm_provider = llm_provider or config.llm_provider
        self.anthropic_api_key = anthropic_api_key or config.anthropic_api_key
        self.ollama_model = ollama_model or config.ollama_model

        # Initialize all services lazily
        self._llm_client: Optional[BaseLLMClient] = None
        self._file_registry: Optional[FileRegistry] = None
        self._tools: Optional[Dict[str, Tool]] = None
        self._stream: Optional[Stream] = None
        self._agent: Optional[Agent] = None
        self._system: Optional[System] = None
        self._cli_consumer: Optional[CLIConsumer] = None
        self._audio_transcription_service: Optional[AudioTranscriptionService] = None
        
        logger.info(f"Container initialized with provider={llm_provider}")

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
            elif self.llm_provider == "ollama":
                logger.debug(f"Using Ollama with model: {self.ollama_model}")
                # Use same URL as llamacpp but with port 11434
                ollama_url = self.llamacpp_url.replace(":11454", ":11434")
                self._llm_client = OllamaClient(base_url=ollama_url, model=self.ollama_model)
            else:
                raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
            logger.info("LLM client created successfully")
        return self._llm_client

    def file_registry(self) -> FileRegistry:
        """Get or create file registry."""
        if self._file_registry is None:
            logger.info("Creating file registry")
            registry = FileRegistry()
            
            # Register palio.json (read-only reference)
            registry.register("palio", FileConfig(
                path=self.config.palio_file_path,
                validator=PalioData,
                allow_edit=False,  # Read-only
                use_safety_copy=False  # No safety copy needed
            ))
            
            # Register palio_games_status.json (editable)
            registry.register("games", FileConfig(
                path=self.config.palio_games_status_path,
                validator=PalioGamesStatus,
                allow_edit=True,
                use_safety_copy=True
            ))
            
            # Register leaderboard.json (editable)
            registry.register("leaderboard", FileConfig(
                path=self.config.leaderboard_file_path,
                validator=Leaderboard,
                allow_edit=True,
                use_safety_copy=True
            ))
            
            self._file_registry = registry
            logger.info(f"File registry created with {len(registry.files)} files")
        return self._file_registry

    def tools(self) -> Dict[str, Tool]:
        """Get or create tools based on configuration."""
        if self._tools is None:
            logger.info("Creating multi-file JSON editor tools")
            # Pass system if it's already created, otherwise None (will be set later)
            system = self._system if hasattr(self, '_system') and self._system else None
            self._tools = create_multi_json_editor_tools(self.file_registry(), system)
            logger.info(f"Created {len(self._tools)} tools: {list(self._tools.keys())}")
        return self._tools

    def stream(self) -> Stream:
        """Get or create event stream."""
        if self._stream is None:
            logger.info("Creating event stream")
            self._stream = Stream()
        return self._stream

    def agent(self) -> Agent:
        """Get or create agent."""
        if self._agent is None:
            logger.info("Creating agent")
            self._agent = Agent(
                llm_client=self.llm_client(),
                tools=self.tools()
            )
            logger.info("Agent created successfully")
        return self._agent

    def system(self) -> System:
        """Get or create system with event and file registry support."""
        if self._system is None:
            logger.info("Creating system")
            self._system = System(
                agent=self.agent(),
                stream=self.stream(),
                file_registry=self.file_registry(),
                config=self.config
            )
            
            # Now update tools with system reference if they don't have it
            if self._tools:
                for tool_name, tool in self._tools.items():
                    if hasattr(tool.function, '__self__') and hasattr(tool.function.__self__, 'system'):
                        if not tool.function.__self__.system:
                            tool.function.__self__.system = self._system
                            logger.debug(f"Updated tool {tool_name} with system reference")
            
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
    
    def audio_transcription_service(self) -> AudioTranscriptionService:
        """Get or create audio transcription service."""
        if self._audio_transcription_service is None:
            logger.info("Creating audio transcription service")
            self._audio_transcription_service = AudioTranscriptionService(self.config)
            logger.info("Audio transcription service created")
        return self._audio_transcription_service

    async def init_container(self) -> None:
        """Initialize the container by creating all services and starting event processing."""
        logger.info("\n" + "="*60)
        logger.info("Initializing container")
        logger.info("="*60)
        
        try:
            # Initialize core services
            logger.info("Creating core services...")
            self.llm_client()
            self.file_registry()
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