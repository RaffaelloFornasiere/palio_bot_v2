# Palio Bot - Sistema di Gestione Dati

Sistema completo per la gestione dei dati del palio (festival medievale) tramite linguaggio naturale, con supporto per LLM agnostici e tool execution.

## Architettura

```
System (coordinator)
├── Agent (tool execution loop)
│   ├── LLMClient (agnostico)
│   └── Tools (text editor per palio.json)
└── Session Management (persistenza automatica)
```

## Componenti Implementati

### 1. Models (`models.py`)
- **Message**: Struttura agnostica compatibile con diversi LLM
  - `TextContent`, `ToolUseContent`, `ToolResultContent`
  - Metodi di convenienza: `text()`, `tool_use()`, `tool_result()`
- **Tool**: Tool con schema JSON e funzione eseguibile
- **ToolResult**: Risultato strutturato (success/error/data/message)
- **Session**: Sessione di conversazione con persistenza

### 2. LLM Clients (`llm_clients/`)
- **BaseLLMClient**: Interfaccia astratta
  - `generate_message(messages, system_prompt, context, tools)`
- **LlamaCPPClient**: Client per mac-studio.local:11454
  - Conversione bidirezionale Message ↔ OpenAI format
  - Supporto tool calls nativi

### 3. Text Editor Tool (`text_editor_tool.py`)
- **view()**: Visualizza contenuto palio.json con validazione
- **str_replace()**: Sostituisce stringhe con validazione JSON
- **insert()**: Inserisce testo a riga specifica
- **undo()**: Annulla ultima modifica
- Tutti i tool restituiscono `ToolResult` strutturato

### 4. Agent (`agent.py`)
- **Loop di esecuzione**: Continua finché LLM non risponde solo con testo
- **Tool execution**: Esegue tool automaticamente e aggiunge risultati
- **System prompt**: Istruzioni in italiano per gestione palio
- **Error handling**: Gestisce errori tool senza eccezioni

### 5. System (`system.py`)
- **Coordinator principale**: Gestisce sessioni e orchestrazione
- **Session management**: Una sola sessione attiva, persistenza automatica
- **Backup automatico**: Salva stato palio.json all'inizio sessione
- **API semplice**: `send_message()`, `close_session()`, `cancel_session()`

### 6. Container (`container.py`)
- **Dependency injection**: Gestione dipendenze lazy
- **Factory pattern**: Crea e configura tutti i servizi
- **Configurazione semplice**: palio_file_path + llamacpp_url

### 7. CLI (`main.py`)
- **Interfaccia interattiva**: Chat con assistente
- **Comandi speciali**: `/close`, `/cancel`, `/status`, `/quit`
- **Auto-setup**: Crea palio.json base se mancante
- **Error handling**: Debug dettagliato con traceback

## Flusso di Esecuzione

1. **Avvio**: Container inizializza tutti i servizi
2. **Messaggio utente**: System crea/riprende sessione
3. **Context**: Carica contenuto attuale palio.json
4. **Agent loop**:
   - Invia messaggi + context + tools a LLM
   - Se LLM chiama tool → esegue e aggiunge risultato
   - Se LLM risponde con testo → termina loop
5. **Persistenza**: Salva sessione automaticamente
6. **Backup**: Su `cancel_session()` ripristina stato precedente

## Gestione Sessioni

- **Una sessione attiva**: Singleton pattern
- **Persistenza**: `session.json` salvato dopo ogni interazione
- **Recovery**: Caricamento automatico all'avvio
- **Backup**: `palio_backup_{session_id}.json` per rollback
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

- **LlamaCPP**: `http://mac-studio.local:11454` (configurabile)
- **Files**: `palio.json`, `session.json` (paths configurabili)
- **Tools**: Supporto nativo con server LlamaCPP aggiornato

## Comandi CLI

- `python main.py` - Avvia interfaccia
- Messaggi naturali: "sottocastello vince 4 a 2 contro villa in calcetto"
- `/close` - Chiude sessione mantenendo modifiche
- `/cancel` - Annulla e ripristina backup
- `/status` - Info sistema dettagliate
- `/quit` - Esce

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
├── palio.json                    # Database JSON
├── session.json                  # Sessione attiva
├── palio_backup_*.json          # Backup automatici
├── main.py                      # CLI entry point
├── palio_bot/
│   ├── models.py               # Pydantic models
│   ├── system.py              # System coordinator
│   ├── agent.py               # Agent con tool loop
│   ├── container.py           # Dependency injection
│   ├── text_editor_tool.py    # Tool per JSON editing
│   └── llm_clients/
│       ├── base_client.py     # Interface astratta
│       └── llamacpp_client.py # LlamaCPP implementation
└── CLAUDE.md                   # Questa documentazione
```

Il sistema è pronto per l'uso e completamente funzionale per la gestione dei dati del palio tramite linguaggio naturale.