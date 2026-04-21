"""Dependency container for adapters (CLI, Telegram, eval).

Adapters talk to palio-core over HTTP for file state; this container
wires up the LLM client, Agent, RemoteFileStore, and System. It does NOT
own file I/O or session staging — those live in `palio_bot.core`.
"""

import logging
from typing import Dict, Literal, Optional

from telegram import Bot

from palio_bot.agent.agent import Agent
from palio_bot.agent.models import Tool
from palio_bot.cli.cli_consumer import CLIConsumer
from palio_bot.config import Config
from palio_bot.core_client.client import CoreClient
from palio_bot.core_client.file_store_remote import RemoteFileStore
from palio_bot.core_client.stream_client import StreamClient
from palio_bot.llm_clients.base_client import BaseLLMClient
from palio_bot.llm_clients.chat_client import ChatClient
from palio_bot.llm_clients.ollama_client import OllamaClient
from palio_bot.models.game_status_models import PalioGamesStatus
from palio_bot.models.leaderboard_models import Leaderboard
from palio_bot.models.palio_models import PalioData
from palio_bot.services.audio_transcription import AudioTranscriptionService
from palio_bot.telegram_bot.telegram_consumer import TelegramConsumer
from palio_bot.tools.file_registry import FileConfig, FileRegistry
from palio_bot.tools.multi_json_editor_tool import create_multi_json_editor_tools

from .system import System

logger = logging.getLogger(__name__)


class Container:
    """Dependency container with core-client wiring."""

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_provider: Optional[Literal["openrouter", "llamacpp", "ollama"]] = None,
        ollama_model: Optional[str] = None,
        adapter_label: str = "adapter",
    ):
        if config is None:
            config = Config()

        self.config = config
        self.llamacpp_url = config.llama_cpp_url
        self.llm_provider = llm_provider or config.llm_provider
        self.ollama_model = ollama_model or config.ollama_model
        self.adapter_label = adapter_label

        self._llm_client: Optional[BaseLLMClient] = None
        self._file_registry: Optional[FileRegistry] = None
        self._core_client: Optional[CoreClient] = None
        self._remote_file_store: Optional[RemoteFileStore] = None
        self._tools: Optional[Dict[str, Tool]] = None
        self._stream: Optional[StreamClient] = None
        self._agent: Optional[Agent] = None
        self._system: Optional[System] = None
        self._cli_consumer: Optional[CLIConsumer] = None
        self._audio_transcription_service: Optional[AudioTranscriptionService] = None

        logger.info(
            "Container initialized (label=%s, provider=%s, core_url=%s)",
            adapter_label,
            self.llm_provider,
            config.palio_core_url,
        )

    # ---------- LLM ----------

    def llm_client(self) -> BaseLLMClient:
        if self._llm_client is None:
            logger.info(f"Creating LLM client: {self.llm_provider}")
            if self.llm_provider == "openrouter":
                if not self.config.openrouter_api_key:
                    raise ValueError(
                        "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter"
                    )
                self._llm_client = ChatClient(
                    base_url=self.config.openrouter_base_url,
                    api_key=self.config.openrouter_api_key,
                    model=self.config.openrouter_model,
                    provider_label="openrouter",
                )
            elif self.llm_provider == "llamacpp":
                self._llm_client = ChatClient(base_url=self.llamacpp_url)
            elif self.llm_provider == "ollama":
                ollama_url = self.llamacpp_url.replace(":11454", ":11434")
                self._llm_client = OllamaClient(
                    base_url=ollama_url, model=self.ollama_model
                )
            else:
                raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
            logger.info("LLM client created successfully")
        return self._llm_client

    # ---------- core-facing clients ----------

    def core_client(self) -> CoreClient:
        if self._core_client is None:
            self._core_client = CoreClient(
                base_url=self.config.palio_core_url,
                token=self.config.palio_core_token,
            )
            logger.info("CoreClient ready at %s", self.config.palio_core_url)
        return self._core_client

    def remote_file_store(self) -> RemoteFileStore:
        if self._remote_file_store is None:
            self._remote_file_store = RemoteFileStore(self.core_client())
        return self._remote_file_store

    # ---------- registry, tools, stream ----------

    def file_registry(self) -> FileRegistry:
        """Local-only registry — used for config metadata (allow_edit,
        validators) and as the authoritative view of which files exist.
        The canonical paths stored here mirror core's config for the rare
        cases where adapters need to know where a file lives.
        """
        if self._file_registry is None:
            registry = FileRegistry()
            registry.register(
                "palio",
                FileConfig(
                    path=self.config.palio_file_path,
                    validator=PalioData,
                    allow_edit=False,
                    use_safety_copy=False,
                ),
            )
            registry.register(
                "palio_games_status",
                FileConfig(
                    path=self.config.palio_games_status_path,
                    validator=PalioGamesStatus,
                    allow_edit=True,
                    use_safety_copy=False,
                ),
            )
            registry.register(
                "leaderboard",
                FileConfig(
                    path=self.config.leaderboard_file_path,
                    validator=Leaderboard,
                    allow_edit=True,
                    use_safety_copy=False,
                ),
            )
            self._file_registry = registry
            logger.info("Registry created with %d files", len(registry.files))
        return self._file_registry

    def tools(self) -> Dict[str, Tool]:
        if self._tools is None:
            self._tools = create_multi_json_editor_tools(
                self.file_registry(),
                file_store=self.remote_file_store(),
            )
            logger.info(f"Created tools: {list(self._tools.keys())}")
        return self._tools

    def stream(self) -> StreamClient:
        if self._stream is None:
            self._stream = StreamClient(
                core_url=self.config.palio_core_url,
                token=self.config.palio_core_token,
                on_fatal=self._on_stream_fatal,
            )
        return self._stream

    def _on_stream_fatal(self, exc: BaseException) -> None:
        """Called by StreamClient when the reconnect budget is exhausted."""
        logger.fatal(
            "StreamClient lost connection to palio-core (%s); adapter must exit",
            exc,
        )

    def agent(self) -> Agent:
        if self._agent is None:
            self._agent = Agent(llm_client=self.llm_client(), tools=self.tools())
        return self._agent

    def system(self) -> System:
        if self._system is None:
            self._system = System(
                agent=self.agent(),
                stream=self.stream(),
                file_registry=self.file_registry(),
                core_client=self.core_client(),
                remote_file_store=self.remote_file_store(),
                label=self.adapter_label,
                config=self.config,
            )
        return self._system

    # ---------- consumers ----------

    def cli_consumer(self) -> CLIConsumer:
        if self._cli_consumer is None:
            self._cli_consumer = CLIConsumer()
            self.stream().add_consumer(self._cli_consumer)
        return self._cli_consumer

    def create_telegram_consumer(self, bot: Bot, chat_id: int) -> TelegramConsumer:
        consumer = TelegramConsumer(bot, chat_id)
        self.stream().add_consumer(consumer)
        return consumer

    def audio_transcription_service(self) -> AudioTranscriptionService:
        if self._audio_transcription_service is None:
            self._audio_transcription_service = AudioTranscriptionService(self.config)
        return self._audio_transcription_service

    async def init_container(self) -> None:
        logger.info("\n" + "=" * 60)
        logger.info("Initializing container")
        logger.info("=" * 60)

        try:
            self.llm_client()
            self.file_registry()
            self.core_client()
            self.remote_file_store()
            self.tools()
            self.stream()
            self.agent()
            self.system()

            await self.stream().start_processing()
            logger.info("Container initialization complete")
            logger.info("=" * 60 + "\n")

        except Exception as e:
            logger.error(f"Failed to initialize container: {e}", exc_info=True)
            raise
