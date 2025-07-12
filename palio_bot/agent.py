"""Agent implementation for processing messages with tool execution loop."""

import uuid
from typing import Any, Dict, List

from .models import Message, TextContent, ToolUseContent, ToolResultContent, Tool, ToolResult
from .llm_clients.base_client import BaseLLMClient


class Agent:
    """Agent that processes messages through LLM and executes tools in a loop."""
    
    def __init__(self, llm_client: BaseLLMClient, tools: Dict[str, Tool]):
        self.llm_client = llm_client
        self.tools = tools  # Dict[tool_name, Tool]
        self.system_prompt = self._get_system_prompt()
    
    async def process_messages(
        self, 
        messages: List[Message], 
        context: List[TextContent]
    ) -> List[Message]:
        """Process messages through LLM with tool execution loop.
        
        Args:
            messages: List of messages in the conversation
            context: List of TextContent for additional context (e.g., palio.json content)
            
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
            
            # Add LLM response to results and current conversation
            result_messages.append(response_message)
            current_messages.append(response_message)
            
            # Check if response contains tool calls
            has_tool_calls = any(
                isinstance(content, ToolUseContent) 
                for content in response_message.content
            )
            
            if not has_tool_calls:
                # LLM responded with text only, end the loop
                break
            
            # Execute any tool calls in the response
            for content in response_message.content:
                if isinstance(content, ToolUseContent):
                    tool_result = await self._execute_tool(content)
                    
                    # Create tool result message
                    result_message = Message.tool_result(
                        role="user",
                        tool_result=tool_result,
                        tool_use_id=content.tool_use_id
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
        # Check which tools are available
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
