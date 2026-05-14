"""Telegram Consumer for sending events to Telegram chat.

Two render modes, selected by `TelegramSettings.verbose`:

* Verbose (default): full event stream — thinking blocks, tool calls,
  tool results, token usage. Mirrors the CLI experience.
* Simple: hide tool calls and token usage entirely. Show "Sto
  lavorando…" while the agent works; replace with the agent's final
  reply on completion. `<thinking>…</thinking>` blocks emitted by the
  model are stripped so only the human-facing answer is shown.

The mode is read live on every event, so toggling via /mode takes
effect on the next agent run without restarting.
"""

import logging
import re
from typing import Any, Dict, Set

from telegram import Bot
from telegram.error import TelegramError

from palio_bot.agent.models import TextContent, TokenUsage
from palio_bot.stream.events import (
    AgentCancelledEvent,
    AgentCompleteEvent,
    AgentUpdateEvent,
    ErrorEvent,
    Event,
    ToolResultEvent,
    ToolUseEvent,
    UserMessageEvent,
)
from palio_bot.telegram_bot.settings import TelegramSettings

TELEGRAM_MAX_TEXT = 4000  # safety margin under Telegram's 4096-char hard limit

logger = logging.getLogger(__name__)

# Match <thinking>…</thinking> blocks (possibly multi-line). Used in
# simple mode to hide internal reasoning markup the model emits in the
# regular text channel.
_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)

# Fenced code blocks (```…```), possibly with a language tag. Stripped in
# simple mode — the model often dumps the JSON it just wrote, which is
# debug noise for the humanized view.
_FENCED_CODE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)

# Inline `…` code spans. Also stripped in simple mode to keep the reply
# prose-only.
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# Collapse runs of 3+ blank lines that the strips above can leave behind.
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _strip_thinking(text: str) -> str:
    return _THINKING_RE.sub("", text).strip()


def _humanize(text: str) -> str:
    """Strip thinking, fenced code blocks and inline code from a reply.

    Used for simple-mode rendering so users only see the prose answer.
    """
    text = _THINKING_RE.sub("", text)
    text = _FENCED_CODE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


class TelegramConsumer:
    """Consumer that sends events to a Telegram chat with progressive updates."""

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        settings: TelegramSettings,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.settings = settings
        self.message_stack: Dict[str, int] = {}  # session_id -> message_id
        self.current_text: Dict[str, str] = {}  # session_id -> accumulated text (verbose mode)
        self.simple_reply: Dict[str, str] = {}  # session_id -> latest non-thinking text (simple mode)
        # Session IDs owned by this chat. Populated on the first UserMessageEvent
        # we render (the one that came from our own chat flow); subsequent
        # events for other sessions — including those from other chats on the
        # unified bus — are ignored.
        self._known_sessions: Set[str] = set()

    def claim_session(self, session_id: str) -> None:
        """Register a session as belonging to this chat.

        Called by the bot wrapper when it kicks off a send_message flow, so
        the very first UserMessageEvent is not dropped by the filter.
        """
        self._known_sessions.add(session_id)

    def filter(self, event: Event) -> bool:
        """Only handle events for sessions owned by this chat."""
        if isinstance(event, UserMessageEvent):
            self._known_sessions.add(event.session_id)
            return True
        return event.session_id in self._known_sessions

    async def consume(self, event: Event) -> None:
        try:
            if isinstance(event, UserMessageEvent):
                await self._handle_user_message(event)
            elif isinstance(event, ToolUseEvent):
                if self.settings.verbose:
                    await self._handle_tool_use(event)
            elif isinstance(event, ToolResultEvent):
                if self.settings.verbose:
                    await self._handle_tool_result(event)
            elif isinstance(event, AgentUpdateEvent):
                await self._handle_agent_update(event)
            elif isinstance(event, AgentCompleteEvent):
                await self._handle_agent_complete(event)
            elif isinstance(event, AgentCancelledEvent):
                await self._handle_agent_cancelled(event)
            elif isinstance(event, ErrorEvent):
                await self._handle_error(event)
        except TelegramError as e:
            logger.error(f"Telegram error in consumer: {e}")

    # ---------- handlers ----------

    async def _handle_user_message(self, event: UserMessageEvent) -> None:
        preview = self._escape_html(event.content)
        if len(preview) > 500:
            preview = preview[:500] + "…"
        if self.settings.verbose:
            text = f"🔄 Processing: {preview}\n\n⏳ Thinking..."
        else:
            text = "⏳ Sto lavorando…"
        msg = await self.bot.send_message(self.chat_id, text, parse_mode='HTML')
        self.message_stack[event.session_id] = msg.message_id
        self.current_text[event.session_id] = ""
        self.simple_reply[event.session_id] = ""

    async def _handle_tool_use(self, event: ToolUseEvent) -> None:
        if event.session_id not in self.message_stack:
            return
        current = self.current_text.get(event.session_id, "")
        tool_text = f"\n\n🔧 Using tool: <code>{self._escape_html(event.tool_name)}</code>"
        if event.parameters:
            params_preview = self._format_parameters(event.parameters)
            if params_preview:
                tool_text += f"\n📝 {params_preview}"
        updated_text = current + tool_text
        self.current_text[event.session_id] = updated_text
        await self._update_message(event.session_id, updated_text + "\n\n⏳ Processing...")

    async def _handle_tool_result(self, event: ToolResultEvent) -> None:
        if event.session_id not in self.message_stack:
            return
        current = self.current_text.get(event.session_id, "")
        if event.result.success:
            result_text = "\n\n✅ Tool executed successfully!"
        else:
            result_text = f"\n❌ Error: {event.result.error}"
        updated_text = current + result_text
        self.current_text[event.session_id] = updated_text
        await self._update_message(event.session_id, updated_text + "\n\n⏳ Thinking...")

    async def _handle_agent_update(self, event: AgentUpdateEvent) -> None:
        if event.session_id not in self.message_stack:
            return
        text_parts = [
            c.text for c in event.message.content if isinstance(c, TextContent)
        ]
        if not text_parts:
            return

        if self.settings.verbose:
            current = self.current_text.get(event.session_id, "")
            agent_text = "\n\n🤖 " + "\n".join(text_parts)
            if event.message.token_usage:
                agent_text += f"\n{self._format_token_usage(event.message.token_usage)}"
            updated_text = current + agent_text
            self.current_text[event.session_id] = updated_text
            await self._update_message(event.session_id, updated_text + "\n\n⏳ Thinking...")
        else:
            # Simple mode: replace the placeholder with the latest reply
            # AFTER stripping <thinking>…</thinking>, fenced code blocks
            # and inline code spans. The agent typically emits a
            # thinking-heavy update before tool calls and a clean summary
            # at the end; we want the user to see the latter as prose
            # only — no raw JSON dumps.
            stripped = _humanize("\n".join(text_parts))
            if not stripped:
                return  # keep "Sto lavorando…" — nothing user-facing yet
            self.simple_reply[event.session_id] = stripped
            await self._update_message(event.session_id, f"🤖 {self._escape_html(stripped)}")

    async def _handle_agent_complete(self, event: AgentCompleteEvent) -> None:
        if event.session_id not in self.message_stack:
            return

        if self.settings.verbose:
            final_text = self.current_text.get(event.session_id, "")
            final_text = f"{final_text}\n\n✅ Processing complete!" if final_text else "✅ Processing complete!"
            if event.total_token_usage:
                final_text += f"\n\n{self._format_token_usage(event.total_token_usage)}"
        else:
            reply = self.simple_reply.get(event.session_id, "").strip()
            final_text = f"🤖 {self._escape_html(reply)}" if reply else "✅ Fatto."

        await self._update_message(event.session_id, final_text)
        self._cleanup_session(event.session_id)

    async def _handle_agent_cancelled(self, event: AgentCancelledEvent) -> None:
        if event.session_id not in self.message_stack:
            return
        if self.settings.verbose:
            final_text = self.current_text.get(event.session_id, "")
            final_text = (
                f"{final_text}\n\n🛑 Processing cancelled: {event.reason}"
                if final_text
                else f"🛑 Processing cancelled: {event.reason}"
            )
        else:
            final_text = "🛑 Annullato."
        await self._update_message(event.session_id, final_text)
        self._cleanup_session(event.session_id)

    async def _handle_error(self, event: ErrorEvent) -> None:
        safe_error = self._escape_html(event.error)
        if len(safe_error) > TELEGRAM_MAX_TEXT - 20:
            safe_error = safe_error[: TELEGRAM_MAX_TEXT - 20] + "…"
        error_text = f"❌ Error: {safe_error}"
        await self.bot.send_message(self.chat_id, error_text, parse_mode='HTML')
        self._cleanup_session(event.session_id)

    # ---------- helpers ----------

    def _cleanup_session(self, session_id: str) -> None:
        self.message_stack.pop(session_id, None)
        self.current_text.pop(session_id, None)
        self.simple_reply.pop(session_id, None)
        self._known_sessions.discard(session_id)

    async def _update_message(self, session_id: str, text: str) -> None:
        if session_id not in self.message_stack:
            return
        try:
            if len(text) > TELEGRAM_MAX_TEXT:
                text = text[: TELEGRAM_MAX_TEXT - 3] + "..."
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_stack[session_id],
                text=text,
                parse_mode='HTML',
            )
        except TelegramError as e:
            if "can't parse entities" in str(e).lower():
                try:
                    logger.warning(f"HTML parsing failed, retrying without parse mode: {e}")
                    await self.bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=self.message_stack[session_id],
                        text=text,
                        parse_mode=None,
                    )
                except TelegramError as fallback_e:
                    logger.error(f"Failed to update message even without parse mode: {fallback_e}")
            elif "message is not modified" not in str(e).lower():
                logger.error(f"Failed to update message: {e}")

    def _format_parameters(self, parameters: Dict[str, Any]) -> str:
        if not parameters:
            return ""
        parts = []
        if "path" in parameters:
            parts.append(f"Path: <code>{self._escape_html(parameters['path'])}</code>")
        elif "json_path" in parameters:
            parts.append(f"Path: <code>{self._escape_html(parameters['json_path'])}</code>")
        if "value" in parameters:
            value = parameters["value"]
            if isinstance(value, (dict, list)):
                parts.append("Value: [complex object]")
            else:
                parts.append(f"Value: <code>{self._escape_html(str(value))}</code>")
        if "old_string" in parameters and "new_string" in parameters:
            parts.append(f"Replace: <code>{self._escape_html(parameters['old_string'][:20])}...</code>")
        return " | ".join(parts[:2])

    def _escape_html(self, text: str) -> str:
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

    def _format_token_usage(self, token_usage: TokenUsage) -> str:
        parts = [f"Tokens: {token_usage.input_tokens}→{token_usage.output_tokens} ({token_usage.total_tokens})"]
        timing_parts = []
        if token_usage.get_prompt_eval_duration_ms() is not None:
            timing_parts.append(f"Prompt: {token_usage.get_prompt_eval_duration_ms():.0f}ms")
        if token_usage.get_eval_duration_ms() is not None:
            timing_parts.append(f"Gen: {token_usage.get_eval_duration_ms():.0f}ms")
        if timing_parts:
            parts.append(" | ".join(timing_parts))
        return f"📊 <i>{' | '.join(parts)}</i>"
