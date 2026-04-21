# Palio Bot v2 - Event Stream System

Sistema completo di gestione dati del Palio con supporto per eventi in tempo reale, interfaccia web multi-anno e bot Telegram con audio.

## Features

- **Real-time Event Streaming**: Vedi cosa sta facendo l'agente mentre elabora
- **Tool Transparency**: Ogni uso di tool è visibile immediatamente
- **Progressive Updates**: I messaggi Telegram si aggiornano durante l'elaborazione
- **Rich CLI Output**: Formattazione bella nel terminale con panels e syntax highlighting
- **Cancellation Support**: Interrompi operazioni in corso con `/stop`
- **Multi-year Interface**: Frontend React con supporto per anni multipli
- **Audio Support**: Trascrizione audio tramite Whisper nel bot Telegram
- **API with Generated Types**: REST API con tipi TypeScript auto-generati
- **Authentication**: Controllo accesso per bot Telegram

## Architettura

Il sistema usa un pattern Producer/Consumer con eventi asincroni:

```
User Input → Agent (Producer) → Event Stream → Consumers (CLI/Telegram)
                ↓                     ↓
           Tool Execution        Real-time Updates
```

## File Structure

```
palio_bot/
├── events.py           # Event models (Literal types, no enums)
├── stream.py           # Event distribution system
├── interfaces.py       # Producer/Consumer interfaces
├── agent.py            # Agent che emette eventi
├── system.py           # System coordinator
├── container.py        # Dependency injection
├── models/             # Pydantic models for API
├── utils/              # API logger and utilities
├── cli_consumer.py     # CLI event consumer
├── telegram_consumer.py # Telegram event consumer
├── cli.py              # CLI entry point
├── telegram_bot.py     # Telegram bot entry point
└── api/                # REST API server
```

## Usage

### CLI Mode

```bash
# Normal mode
python -m palio_bot.cli

# Debug mode with verbose logging
python -m palio_bot.cli --debug

# Debug without log file
python -m palio_bot.cli --debug --no-log-file
```

Vedrai:
- 👤 User message in panel blu
- 🔧 Tool usage con parametri
- ✅/❌ Tool results
- 🤖 Assistant response in panel verde

Logs are saved to `logs/palio_bot_YYYYMMDD_HHMMSS.log`

### Telegram Bot

```bash
export TELEGRAM_BOT_TOKEN=your_token_here
export ALLOWED_USER_ID=your_user_id  # optional
export OPENAI_API_KEY=your_openai_key  # per audio transcription
python -m palio_bot.telegram_bot
```

I messaggi si aggiornano progressivamente:
1. "🔄 Processing: [message]"
2. "🔧 Using tool..."
3. Final response

Supporta anche:
- 🎵 Audio messages (trascrizione automatica)
- 🛑 `/stop` per cancellare operazioni
- 🔐 Autenticazione utenti

### Web Interface

```bash
cd website
npm install
npm run dev
```

Features:
- 📅 Calendario eventi multi-anno
- 🎮 Gestione giochi con dettagli partite
- 🏆 Classifica con divisioni
- 🔄 Selezione anno dinamica
- 📊 Tipi TypeScript auto-generati

### palio-core (API + event bus + React)

```bash
python -m palio_bot.core
```

- 🌐 REST API con OpenAPI docs
- 🔌 WebSocket per eventi real-time
- 📋 Multi-year data support
- 🎯 Generated TypeScript types

## Event Types

- `UserMessageEvent` - Utente invia messaggio
- `AgentUpdateEvent` - Agente produce update
- `ToolUseEvent` - Agente usa un tool
- `ToolResultEvent` - Risultato del tool
- `AgentCompleteEvent` - Elaborazione completata
- `ErrorEvent` - Errore durante elaborazione
- `CancellationEvent` - Cancellazione operazione

## Configuration

Environment variables:
- `LLAMACPP_URL` - URL del server LlamaCPP (default: http://mac-studio.local:11454)
- `LLM_PROVIDER` - Provider LLM: "llamacpp" o "anthropic"
- `ANTHROPIC_API_KEY` - API key per Anthropic (se usi anthropic)
- `TELEGRAM_BOT_TOKEN` - Token del bot Telegram
- `ALLOWED_USER_ID` - ID utente autorizzato per Telegram
- `OPENAI_API_KEY` - API key per Whisper (trascrizione audio)

## Comandi

### CLI
- `/close` - Salva modifiche
- `/cancel` - Annulla modifiche
- `/status` - Mostra stato
- `/stop` - Interrompe operazione corrente
- `/quit` - Esci

### Telegram
- `/start` - Avvia bot
- `/status` - Mostra stato
- `/close` - Salva sessione
- `/cancel` - Annulla sessione
- `/stop` - Cancella operazione in corso

## Development

Il sistema è completamente event-driven. Per aggiungere un nuovo consumer:

1. Implementa l'interfaccia `Consumer`
2. Registralo con `stream.add_consumer()`
3. Il consumer riceverà tutti gli eventi

```python
class MyConsumer:
    def filter(self, event: Event) -> bool:
        return True  # Process all events
    
    async def consume(self, event: Event) -> None:
        print(f"Got event: {event.type}")
```