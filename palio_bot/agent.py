"""Agent implementation with event production for real-time updates."""

import uuid
from typing import Any, Dict, List, Optional

from .models import Message, TextContent, ToolUseContent, ToolResultContent, Tool, ToolResult
from .llm_clients.base_client import BaseLLMClient
from .interfaces import Producer
from .stream import Stream
from .events import (
    UserMessageEvent, AgentUpdateEvent, ToolUseEvent, 
    ToolResultEvent, AgentCompleteEvent, ErrorEvent
)


class Agent(Producer):
    """Agent that processes messages and emits events during execution."""
    
    def __init__(
        self, 
        llm_client: BaseLLMClient, 
        tools: Dict[str, Tool],
        stream: Stream
    ):
        super().__init__(stream)
        self.llm_client = llm_client
        self.tools = tools  # Dict[tool_name, Tool]
        self.system_prompt = self._get_system_prompt()
    
    async def run(
        self, 
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> Message:
        """Process message and emit events during execution.
        
        Args:
            message: User message to process
            session_id: Session ID for event tracking
            context: Optional context (e.g., current palio.json content)
            
        Returns:
            Final Message from the agent
        """
        try:
            # Emit user message event
            await self.produce(UserMessageEvent(
                session_id=session_id,
                content=message
            ))
            
            # Convert context to TextContent if provided
            context_list = []
            if context:
                context_list.append(TextContent(type="text", text=context))
            
            # Start with user message
            messages = [Message.text(role="user", text=message)]
            
            # Process through tool loop
            result_messages = await self._process_with_events(
                messages, context_list, session_id
            )
            
            # Find the final assistant message with text
            final_message = None
            for msg in reversed(result_messages):
                if msg.role == "assistant":
                    for content in msg.content:
                        if isinstance(content, TextContent):
                            final_message = msg
                            break
                    if final_message:
                        break
            
            if final_message:
                # Emit completion event
                final_text = " ".join(
                    c.text for c in final_message.content 
                    if isinstance(c, TextContent)
                )
                await self.produce(AgentCompleteEvent(
                    session_id=session_id,
                    final_message=final_text
                ))
                return final_message
            else:
                raise ValueError("No final text response from agent")
                
        except Exception as e:
            # Emit error event
            import traceback
            await self.produce(ErrorEvent(
                session_id=session_id,
                error=str(e),
                traceback=traceback.format_exc()
            ))
            raise
    
    async def _process_with_events(
        self, 
        messages: List[Message], 
        context: List[TextContent],
        session_id: str
    ) -> List[Message]:
        """Process messages through LLM with tool execution loop, emitting events.
        
        Args:
            messages: List of messages in the conversation
            context: List of TextContent for additional context
            session_id: Session ID for event tracking
            
        Returns:
            List of messages generated during processing
        """
        result_messages = []
        current_messages = messages.copy()
        
        # Continue loop until LLM responds with text only (no tool calls)
        while True:
            # Get response from LLM
            response_message = await self.llm_client.generate_message(
                messages=current_messages,
                system_prompt=self.system_prompt,
                context=context,
                tools=list(self.tools.values())
            )
            
            # Emit agent update event
            await self.produce(AgentUpdateEvent(
                session_id=session_id,
                message=response_message
            ))
            
            # Add LLM response to results and current conversation
            result_messages.append(response_message)
            current_messages.append(response_message)
            
            # Check if response contains tool calls
            tool_uses = [
                content for content in response_message.content
                if isinstance(content, ToolUseContent)
            ]
            
            if not tool_uses:
                # LLM responded with text only, end the loop
                break
            
            # Process tool uses
            for tool_use in tool_uses:
                # Emit tool use event
                await self.produce(ToolUseEvent(
                    session_id=session_id,
                    tool_name=tool_use.tool_name,
                    parameters=tool_use.tool_parameters
                ))
                
                # Execute tool
                tool_result = await self._execute_tool(tool_use)
                
                # Emit tool result event
                await self.produce(ToolResultEvent(
                    session_id=session_id,
                    tool_name=tool_use.tool_name,
                    result=tool_result
                ))
                
                # Create tool result message
                result_message = Message.tool_result(
                    role="user",
                    tool_result=tool_result,
                    tool_use_id=tool_use.tool_use_id
                )
                
                # Add to results and current conversation
                result_messages.append(result_message)
                current_messages.append(result_message)
        
        return result_messages
    
    async def _execute_tool(self, tool_use: ToolUseContent) -> ToolResult:
        """Execute a tool and return the result.
        
        Args:
            tool_use: ToolUseContent with tool name and parameters
            
        Returns:
            ToolResult (always returns a structured result, never raises)
        """
        tool_name = tool_use.tool_name
        
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                data={"available_tools": list(self.tools.keys())}
            )
        
        try:
            tool = self.tools[tool_name]
            result = tool.call(**tool_use.tool_parameters)
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                data={
                    "tool_name": tool_name,
                    "parameters": tool_use.tool_parameters
                }
            )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for palio data management."""
        return """Sei un assistente per la gestione dei dati del palio (festival medievale) in formato JSON.

Il tuo ruolo è aiutare ad aggiornare e mantenere il file palio.json basandoti su richieste in linguaggio naturale.

Strumenti disponibili (basati su JSONPath):
- json_view: Visualizza contenuto JSON, opzionalmente filtrato per path (es: '$.palio.eventi[0]')
- json_set: Imposta un valore a un path specifico (es: '$.palio.anno' = 2025)
- json_delete: Elimina un campo o elemento
- json_append: Aggiunge un valore a un array
- json_insert: Inserisce in un array a un indice specifico
- json_remove: Rimuove da un array per indice
- json_undo: Annulla l'ultima modifica

TIPI DI GIOCHI:
- "round-robin": Giochi con girone all'italiana dove ogni borgo affronta tutti gli altri. I risultati vengono inseriti partita per partita e il punteggio finale viene calcolato automaticamente (es: calcetto, briscola, morra).
- "score-based": Giochi dove ogni borgo ottiene un punteggio diretto senza confronto uno-contro-uno. Il punteggio viene inserito direttamente per borgo (es: camerieri con quantità d'acqua, cibbè con distanza, scatolone con numero vestiti).

Linee guida:
1. Comprendi sempre lo stato attuale visualizzando il file se necessario 
2. Usa JSONPath per modifiche precise (es: $.palio.eventi[0].nome per il nome del primo evento)
3. Per aggiungere a un array usa json_append, per modificare campi usa json_set
4. Se incontri errori, usa lo strumento json_undo se necessario
5. Fornisci spiegazioni chiare di quello che stai facendo
6. Fai domande se non sei sicuro di come procedere

Esempi di comandi che potresti ricevere:
- "sottocastello vince 4 a 2 contro villa in calcetto" (round-robin)
- "salt nei camerieri fa 850ml" (score-based)
- "aggiungi nuovo evento: corsa dei sacchi"

Rispondi sempre in italiano e sii utile nella gestione dei dati del palio."""