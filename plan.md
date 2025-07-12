# Piano di Implementazione - Sistema JSON con LLM

## Obiettivo
Sistema che permette a qualsiasi LLM di aggiornare `palio.json` tramite comandi in linguaggio naturale.

**Esempi**: "sottocastello vince 4 a 2 contro villa in calcetto", "salt taglio del tronco maschile, 13.5 secondi"

## Architettura
```
System (coordinator):
├── Agent
│   ├── LLMClient (agnostico)  
│   ├── text_editor_tool
│   └── Sessions management
└── API: send_message(), close_session(), cancel_session()
```

**Gestione Sessioni**:
- **Una sola sessione attiva** alla volta in memoria
- **Persistenza automatica**: salvataggio in `session.json` dopo ogni interazione
- **Recovery**: caricamento da `session.json` all'avvio se presente
- **Nuova sessione**: sovrascrive quella precedente

**Flusso**:
1. Agent riceve messaggio utente
2. Agent → LLMClient: (system_prompt, contesto, conversazione_completa, tool_schema)
3. LLMClient → Agent: Message (TextContent | ToolUseContent)
4. Se ToolUseContent: esegui tool, aggiungi result, torna al punto 2  
5. Se TextContent: fine loop, return

- **Agent**: gestisce loop sincrono + sessioni chat
- **LLMClient**: interfaccia agnostica (Claude, LlamaCPP, etc.)
- **text_editor_tool**: singolo tool per palio.json

## Implementazione

### Core
- [ ] `system.py` - Coordinator principale
  - `System` class con `active_session: Session | None`
  - `send_message(user_msg: str) -> Message` - se c'è sessione attiva usa quella, altrimenti crea nuova
  - `close_session() -> None` - chiude sessione attiva, rimuove `session.json`
  - `cancel_session() -> None` - annulla sessione, rollback a stato precedente + rimuove `session.json`
  - `_create_session() -> Session` - crea nuova sessione con system_prompt, backup stato attuale
  - `_save_session() -> None` - salva sessione corrente in `session.json`
  - `_load_session() -> Session | None` - carica da `session.json` se presente
- [ ] `text_editor_tool.py`
  - `view()` - legge palio.json
  - `str_replace(old, new)` - modifica con validazione JSON
  - `insert(line_number, text)` - inserisce testo a riga specifica
  - `undo()` - rollback ultima modifica
  - Ogni tool restituisce sempre ToolResult (successo o errore), LLM interpreta
- [ ] `agent.py` 
  - `Agent` class - gestisce loop di esecuzione tool
  - `process_messages(messages: list[Message], context: str, tools: list[Tool]) -> list[Message]` - loop tool execution
  - Restituisce uno o più messaggi (uno solo se risposta diretta con testo)
  - System prompt con istruzioni specifiche per palio
- [ ] `main.py` - CLI entry point che usa System
- [ ] Poetry setup + .env

### LLM Support
- [ ] `llm_clients/base_client.py` - Abstract base con `generate_message()`
- [ ] `llm_clients/anthropic_client.py` - Claude API integration
- [ ] `llm_clients/llamacpp_client.py` - Local model support
- [ ] `config.py` - Factory pattern per LLM client da .env

### Models (Pydantic)
- [ ] `models.py` - Message structure agnostica:
  ```python
  class TextContent(BaseModel):
      type: Literal["text"] = "text"
      text: str
      cache_control: CacheControl | None = None

  class ToolUseContent(BaseModel):
      type: Literal["tool_use"] = "tool_use"
      tool_name: str
      tool_parameters: Any
      tool_use_id: str

  class ToolResultContent(BaseModel):
      type: Literal["tool_result"] = "tool_result"
      tool_result: Any
      tool_use_id: str

  Role = Literal["user", "assistant", "event"]

  class Message(BaseModel):
      role: Role
      content: list[TextContent | ToolUseContent | ToolResultContent]
      # + convenience methods: text(), tool_use(), tool_result()

  class Session(BaseModel):
      id: str
      messages: list[Message]
  ```

## Struttura Directory
```
bot_v2/
├── pyproject.toml
├── README.md
├── palio.json
├── session.json (creato automaticamente)
├── palio_bot/
│   ├── __init__.py
│   ├── models.py
│   ├── system.py
│   ├── agent.py
│   ├── text_editor_tool.py
│   ├── config.py
│   └── llm_clients/
│       ├── __init__.py
│       ├── base_client.py
│       ├── anthropic_client.py
│       └── llamacpp_client.py
├── main.py
└── tests/
```

## Stack
- Poetry + Python 3.12+
- Pydantic v2 per validazione
- python-dotenv per .env
- anthropic, requests per LLM clients