# Palio Bot - Sistema di Gestione Dati

Sistema completo per la gestione dei dati del palio (festival medievale) tramite linguaggio naturale, con supporto per LLM agnostici, tool execution e event streaming.

## Architettura

```
System (coordinator)
├── Agent (tool execution loop + event producer)
│   ├── LLMClient (agnostico: LlamaCPP/Anthropic)
│   └── Tools (JSON editor per palio.json)
├── Stream (event distribution system)
│   ├── CLI Consumer
│   └── Telegram Consumer
└── Session Management (persistenza automatica)
```

## Componenti Implementati

### 1. Models (`agent/models.py`)
- **Message**: Struttura agnostica compatibile con diversi LLM
  - `TextContent`, `ToolUseContent`, `ToolResultContent`
  - Metodi di convenienza: `text()`, `tool_use()`, `tool_result()`
- **Tool**: Tool con schema JSON e funzione eseguibile
- **ToolResult**: Risultato strutturato (success/error/data/message)
- **Session**: Sessione di conversazione con persistenza
- **AgentContextBlock**: Blocco di contesto strutturato

### 2. LLM Clients (`llm_clients/`)
- **BaseLLMClient**: Interfaccia astratta
  - `generate_message(messages, system_prompt, context, tools)`
- **LlamaCPPClient**: Client per mac-studio.local:11454
  - Conversione bidirezionale Message ↔ OpenAI format
  - Supporto tool calls nativi
- **AnthropicClient**: Client per Anthropic Claude
  - Conversione bidirezionale Message ↔ Anthropic format
  - Supporto tool calls nativi

### 3. JSON Editor Tool (`tools/json_editor_tool.py`)
- **view()**: Visualizza contenuto JSON con JSONPath opzionale
- **set_field()**: Imposta valori a path JSON specifici
- **delete_field()**: Elimina campi a path JSON
- **append()**: Aggiunge elementi ad array JSON
- **insert_at()**: Inserisce elementi in array a indice specifico
- **remove_at()**: Rimuove elementi da array a indice specifico
- **undo()**: Annulla ultima modifica
- Tutti i tool restituiscono `ToolResult` strutturato

### 4. Agent (`agent/agent.py`)
- **Event Producer**: Produce eventi durante esecuzione
- **Loop di esecuzione**: Continua finché LLM non risponde solo con testo
- **Tool execution**: Esegue tool automaticamente e aggiunge risultati
- **System prompt**: Istruzioni in italiano per gestione palio
- **Error handling**: Gestisce errori tool senza eccezioni
- **Event emission**: UserMessageEvent, AgentUpdateEvent, ToolUseEvent, ToolResultEvent, AgentCompleteEvent
- **Cancellation support**: Supporto interruzione via CancellationEvent

### 5. Event Stream (`stream/`)
- **Stream**: Sistema di distribuzione eventi asincrono
- **Events**: UserMessageEvent, AgentUpdateEvent, ToolUseEvent, ToolResultEvent, AgentCompleteEvent, ErrorEvent, CancellationEvent
- **Consumers**: CLIConsumer, TelegramConsumer
- **Interfaces**: Producer, Consumer per event handling

### 6. System (`system.py`)
- **Coordinator principale**: Gestisce sessioni e orchestrazione con event streaming
- **Session management**: Una sola sessione attiva, persistenza automatica
- **File management**: Gestisce palio.json, palio_games_status.json, palio_updated.json
- **Leaderboard update**: Aggiorna classifica con giochi completati
- **API semplice**: `send_message()`, `close_session()`, `cancel_session()`, `cancel_current_operation()`

### 7. Container (`container.py`)
- **Dependency injection**: Gestione dipendenze lazy con event system
- **Factory pattern**: Crea e configura tutti i servizi
- **Multi-provider**: Supporto LlamaCPP e Anthropic
- **Consumer creation**: CLI e Telegram consumers
- **Configuration**: Config-based con override parametri

### 8. CLI (`cli/cli.py`)
- **Interfaccia interattiva**: Chat con assistente
- **Comandi speciali**: `/close`, `/cancel`, `/status`, `/quit`, `/stop`
- **Auto-setup**: Crea palio.json base se mancante
- **Error handling**: Debug dettagliato con traceback
- **Event consumption**: Riceve eventi real-time durante esecuzione
- **Cancellation support**: Supporto interruzione operazioni con `/stop`

### 9. Telegram Bot (`telegram_bot/`)
- **TelegramBot**: Bot Telegram integrato con autenticazione
- **TelegramConsumer**: Consumer per eventi Telegram
- **Audio support**: Trascrizione audio tramite Whisper
- **Multi-chat**: Supporto conversazioni multiple
- **Stop command**: `/stop` per cancellare operazioni in corso
- **Authentication**: Supporto `ALLOWED_USER_ID` per controllo accesso

### 10. API Server (`api/api_server.py`)
- **REST API**: Endpoint per integrazione esterna
- **WebSocket**: Streaming eventi real-time
- **CORS support**: Configurazione cross-origin
- **Multi-year support**: Endpoint per gestire dati di anni precedenti
- **Generated types**: API con tipi TypeScript generati automaticamente

### 11. Services (`services/`)
- **AudioTranscriptionService**: Trascrizione audio tramite Whisper
- **LeaderboardUpdater**: Aggiornamento automatico classifica con divisioni
- **API Logger**: Sistema di logging delle chiamate API per debug

### 12. Models (`models/`)
- **GameStatusModels**: Modelli Pydantic per stato giochi e partite
- **LeaderboardModels**: Modelli per classifica e divisioni
- **PalioModels**: Modelli base del palio
- **Helpers**: Utility per conversioni e validazioni

## Flusso di Esecuzione

1. **Avvio**: Container inizializza tutti i servizi e avvia event processing
2. **Messaggio utente**: System crea/riprende sessione
3. **Context**: Carica contenuto attuale palio.json e leaderboard
4. **Agent loop con eventi**:
   - Produce `UserMessageEvent`
   - Invia messaggi + context + tools a LLM
   - Se LLM chiama tool → produce `ToolUseEvent` e `ToolResultEvent`
   - Se LLM risponde con testo → produce `AgentCompleteEvent`
   - Consumers ricevono eventi real-time
5. **Persistenza**: Salva sessione automaticamente
6. **File sync**: Su `close_session()` copia palio_updated.json → palio_games_status.json

## Gestione Sessioni

- **Una sessione attiva**: Singleton pattern
- **Persistenza**: `session.json` salvato dopo ogni interazione
- **Recovery**: Caricamento automatico all'avvio
- **Cleanup**: Rimozione file su close/cancel

## Tool Schema

Tutti i tool seguono schema JSON standard:
```json
{
  "type": "function",
  "function": {
    "name": "view",
    "description": "Visualizza il contenuto completo del file palio.json",
    "parameters": {
      "type": "object",
      "properties": {},
      "required": []
    }
  }
}
```

## Error Handling

- **Tool errors**: Sempre `ToolResult`, mai eccezioni
- **LLM errors**: Propagati con dettagli per debug
- **System errors**: Traceback completo in CLI
- **File errors**: Gestiti gracefully con messaggi utili

## Configurazione

- **LLM Providers**: LlamaCPP (`http://mac-studio.local:11454`) e Anthropic (configurabili)
- **Files**: `data/palio.json`, `data/session.json`, `data/leaderboard.json` (paths configurabili)
- **Tools**: JSONPath-based editor per editing strutturato
- **Event System**: Stream asincrono per real-time updates

## Comandi CLI

- `python -m palio_bot` - Avvia interfaccia CLI
- Messaggi naturali: "sottocastello vince 4 a 2 contro villa in calcetto"
- `/close` - Chiude sessione mantenendo modifiche
- `/cancel` - Annulla e ripristina backup
- `/status` - Info sistema dettagliate
- `/stop` - Interrompe operazione corrente
- `/quit` - Esce

## Altre Interfacce

- **Telegram Bot**: `python -m palio_bot.telegram_bot`
- **API Server**: `python -m palio_bot.api.api_server`

## Esempi di Utilizzo

```python
# Programmatitico
container = Container()
await container.init_container()
system = container.system()

response = await system.send_message("aggiungi nuovo evento: corsa dei sacchi")
print(response.content[0].text)
```

## File Structure

```
bot_v2/
├── data/                         # Dati del sistema
│   ├── palio.json               # Specifica del palio
│   ├── palio_games_status.json  # Stato attuale dei giochi
│   ├── palio_updated.json       # Modifiche in corso (sessione attiva)
│   ├── leaderboard.json         # Classifica aggiornata
│   └── session.json             # Sessione attiva
├── palio_bot/
│   ├── __main__.py             # Entry point principale
│   ├── config.py               # Configurazione
│   ├── container.py            # Dependency injection
│   ├── system.py               # System coordinator
│   ├── leaderboard_updater.py  # Aggiornatore classifica
│   ├── models/                 # Modelli Pydantic
│   │   ├── game_status_models.py # Modelli per giochi e partite
│   │   ├── leaderboard_models.py # Modelli per classifica
│   │   ├── palio_models.py     # Modelli base palio
│   │   └── helpers.py          # Utility per conversioni
│   ├── utils/                  # Utilities
│   │   └── api_logger.py       # Logger per API calls
│   ├── agent/
│   │   ├── agent.py            # Agent con tool loop
│   │   ├── models.py           # Pydantic models
│   │   └── system_prompt.py    # System prompt
│   ├── llm_clients/
│   │   ├── base_client.py      # Interface astratta
│   │   ├── llamacpp_client.py  # LlamaCPP implementation
│   │   └── anthropic_client.py # Anthropic implementation
│   ├── tools/
│   │   ├── json_editor_tool.py # JSONPath editor
│   │   └── text_editor_tool.py # Text editor (legacy)
│   ├── stream/
│   │   ├── stream.py           # Event stream
│   │   ├── events.py           # Event types
│   │   └── interfaces.py       # Producer/Consumer interfaces
│   ├── cli/
│   │   ├── cli.py              # CLI interface
│   │   └── cli_consumer.py     # CLI event consumer
│   ├── telegram_bot/
│   │   ├── telegram_bot.py     # Telegram bot
│   │   └── telegram_consumer.py # Telegram event consumer
│   ├── api/
│   │   └── api_server.py       # REST API server
│   └── services/
│       ├── audio_transcription.py # Audio transcription service
│       └── __init__.py
├── website/                     # React frontend
│   ├── src/
│   │   ├── features/
│   │   │   ├── calendar/       # Calendario eventi
│   │   │   ├── games/          # Gestione giochi con dettagli
│   │   │   └── leaderboard/    # Classifica con divisioni
│   │   ├── generated/          # Tipi TypeScript auto-generati
│   │   ├── components/         # Componenti condivisi con YearSelector
│   │   ├── contexts/           # YearContext per multi-anno
│   │   └── utils/              # API utilities e yearApi
│   └── ...
├── docker/                      # Docker configuration
│   ├── Dockerfile.api
│   ├── Dockerfile.telegram
│   └── docker-compose.yml
├── scripts/                     # Utility scripts
│   ├── restore.sh
│   └── restore_games_status.py
└── CLAUDE.md                   # Questa documentazione
```

Il sistema è pronto per l'uso e completamente funzionale per la gestione dei dati del palio tramite linguaggio naturale.