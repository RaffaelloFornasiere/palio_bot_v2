"""CLI for the palio bot system."""

import asyncio
import sys
from pathlib import Path

from palio_bot.container import Container
from palio_bot.models import TextContent


async def main():
    """Main CLI function."""
    print("🎭 Palio Bot - Sistema di gestione dati palio")
    print("=" * 50)
    
    # Initialize container
    container = Container()
    await container.init_container()
    system = container.system()
    
    # Check if palio.json exists, create basic one if not
    palio_path = Path("palio.json")
    if not palio_path.exists():
        print("📄 Creando palio.json di base...")
        basic_palio = {
            "palio": {
                "anno": 2024,
                "eventi": [],
                "contrade": []
            }
        }
        import json
        with open(palio_path, 'w', encoding='utf-8') as f:
            json.dump(basic_palio, f, ensure_ascii=False, indent=2)
        print(f"✅ Creato {palio_path}")
    
    # Show current session status
    active_session = system.get_active_session()
    if active_session:
        print(f"📝 Sessione attiva: {active_session.id}")
        print(f"   Messaggi: {len(active_session.messages)}")
    else:
        print("📝 Nessuna sessione attiva")
    
    print("\nComandi disponibili:")
    print("  - Scrivi un messaggio per interagire con l'assistente")
    print("  - '/close' per chiudere la sessione")
    print("  - '/cancel' per annullare la sessione e ripristinare backup")
    print("  - '/status' per vedere lo stato del sistema")
    print("  - '/quit' per uscire")
    print()
    
    while True:
        try:
            # Get user input
            user_input = input("👤 Tu: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input == "/quit":
                print("👋 Arrivederci!")
                break
            elif user_input == "/close":
                system.close_session()
                print("✅ Sessione chiusa")
                continue
            elif user_input == "/cancel":
                system.cancel_session()
                print("↩️  Sessione annullata e backup ripristinato")
                continue
            elif user_input == "/status":
                await show_status(system)
                continue
            
            # Send message to system
            print("🤖 Assistente: ", end="", flush=True)
            
            try:
                response = await system.send_message(user_input)
                
                # Print assistant response
                for content in response.content:
                    if isinstance(content, TextContent):
                        print(content.text)
                        break
                else:
                    print("Nessuna risposta testuale disponibile.")
                    
            except Exception as e:
                print(f"❌ Errore: {str(e)}")
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrotto dall'utente. Arrivederci!")
            break
        except EOFError:
            print("\n\n👋 Arrivederci!")
            break


async def show_status(system):
    """Show system status."""
    print("\n📊 Stato del sistema:")
    print("-" * 30)
    
    # Session info
    active_session = system.get_active_session()
    if active_session:
        print(f"📝 Sessione attiva: {active_session.id}")
        print(f"   Creata: {active_session.creation_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Messaggi: {len(active_session.messages)}")
        
        # Count message types
        user_msgs = sum(1 for msg in active_session.messages if msg.role == "user")
        assistant_msgs = sum(1 for msg in active_session.messages if msg.role == "assistant")
        print(f"   - Utente: {user_msgs}")
        print(f"   - Assistente: {assistant_msgs}")
    else:
        print("📝 Nessuna sessione attiva")
    
    # File info
    palio_path = Path("palio.json")
    if palio_path.exists():
        size = palio_path.stat().st_size
        print(f"📄 palio.json: {size} bytes")
    else:
        print("📄 palio.json: Non trovato")
    
    session_path = Path("session.json")
    if session_path.exists():
        size = session_path.stat().st_size
        print(f"💾 session.json: {size} bytes")
    else:
        print("💾 session.json: Non trovato")
    
    # Backup info
    backup_files = list(Path(".").glob("palio_backup_*.json"))
    if backup_files:
        print(f"🔄 Backup files: {len(backup_files)}")
    else:
        print("🔄 Nessun backup trovato")
    
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Arrivederci!")
        sys.exit(0)