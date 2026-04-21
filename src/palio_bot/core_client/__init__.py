"""HTTP client for `palio_bot.core`.

Adapters (CLI, Telegram, eval) use `CoreClient` for session lifecycle and
`RemoteFileStore` as the tool-facing FileStore backed by HTTP.
"""

from palio_bot.core_client.client import CoreClient, CoreClientError
from palio_bot.core_client.file_store_remote import RemoteFileStore

__all__ = ["CoreClient", "CoreClientError", "RemoteFileStore"]
