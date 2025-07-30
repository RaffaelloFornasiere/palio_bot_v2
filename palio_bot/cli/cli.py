"""CLI with event system for real-time updates."""

import asyncio
import os
import json
import argparse
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from palio_bot.container import Container
from palio_bot.logging_config import setup_logging, get_logger
from palio_bot.config import Config


console = Console()
logger = get_logger(__name__)


def print_welcome():
    """Print welcome message."""
    console.print(Panel.fit(
        "[bold cyan]🎭 Palio Bot - Sistema di Gestione Dati[/bold cyan]\n\n"
        "Benvenuto! Sono qui per aiutarti a gestire i dati del palio.\n"
        "Posso aggiornare eventi, risultati e classifiche.\n\n"
        "[dim]Comandi speciali:[/dim]\n"
        "[green]/save[/green] - Salva modifiche senza chiudere sessione\n"
        "[green]/close[/green] - Chiudi sessione salvando modifiche\n"
        "[yellow]/cancel[/yellow] - Annulla sessione scartando modifiche\n" 
        "[blue]/status[/blue] - Mostra stato sistema\n"
        "[magenta]/leaderboard[/magenta] - Aggiorna classifica\n"
        "[red]/clear[/red] - Elimina sessione e file temporanei\n"
        "[red]/quit[/red] - Esci dal programma",
        title="Sistema Palio Bot",
        border_style="cyan"
    ))


def print_status(system):
    """Print system status."""
    session = system.get_active_session()
    
    if session:
        console.print(f"\n[green]✓ Sessione attiva:[/green] {session.id}")
        console.print(f"[green]✓ Messaggi:[/green] {len(session.messages)}")
        
        # Check if palio_updated.json exists
        config = Config()
        if config.palio_games_status_temp_path.exists():
            console.print(f"[green]✓ File temporaneo:[/green] {config.palio_games_status_temp_path} presente")
        else:
            console.print(f"[yellow]⚠ File temporaneo:[/yellow] {config.palio_games_status_temp_path} non trovato")
    else:
        console.print("\n[yellow]⚠ Nessuna sessione attiva[/yellow]")
    
    # Check palio.json
    palio_path = Path("palio.json")
    if palio_path.exists():
        console.print(f"[green]✓ File dati:[/green] palio.json presente")
    else:
        console.print(f"[red]✗ File dati:[/red] palio.json non trovato")


async def handle_commands(command: str, system, container) -> bool:
    """Handle special commands. Returns True if should continue, False to exit."""
    command = command.lower().strip()
    cli_consumer = container.cli_consumer()
    
    if command == "/quit":
        if system.get_active_session():
            console.print("\n[yellow]⚠ Sessione attiva presente.[/yellow]")
            console.print("Usa [green]/close[/green] per salvare o [yellow]/cancel[/yellow] per annullare.")
            return True
        return False
    
    elif command == "/save":
        if system.get_active_session():
            system.save_session()
            console.print("\n[green]✓ Modifiche salvate (sessione ancora attiva)[/green]")
        else:
            console.print("\n[yellow]Nessuna sessione attiva da salvare[/yellow]")
        return True
    
    elif command == "/close":
        if system.get_active_session():
            system.close_session()
            cli_consumer.current_session_id = None  # Reset session ID
            console.print("\n[green]✓ Sessione chiusa e modifiche salvate in palio.json[/green]")
        else:
            console.print("\n[yellow]Nessuna sessione da chiudere[/yellow]")
        return True
    
    elif command == "/cancel":
        if system.get_active_session():
            system.cancel_session()
            cli_consumer.current_session_id = None  # Reset session ID
            console.print("\n[yellow]✓ Sessione annullata, modifiche scartate[/yellow]")
        else:
            console.print("\n[yellow]Nessuna sessione da annullare[/yellow]")
        return True
    
    elif command == "/status":
        print_status(system)
        return True
    
    elif command == "/leaderboard":
        console.print("\n[dim]Aggiornamento classifica in corso...[/dim]")
        try:
            from palio_bot.leaderboard_updater import LeaderboardUpdater
            from palio_bot.config import Config
            
            config = Config()
            leaderboard_updater = LeaderboardUpdater(
                config.palio_file_path,
                config.palio_games_status_path,
                config.leader_board_file_path
            )
            
            leaderboard_updater.update_leaderboard()
            console.print("[green]✓ Classifica aggiornata con successo[/green]")
            
        except Exception as e:
            logger.error(f"Error updating leaderboard: {e}", exc_info=True)
            console.print(f"\n[red]Errore nell'aggiornamento della classifica: {e}[/red]")
        
        return True
    
    elif command == "/clear":
        config = Config()
        files_deleted = []
        
        # Cancel active session first
        if system.get_active_session():
            system.cancel_session()
            cli_consumer.current_session_id = None
            console.print("\n[yellow]✓ Sessione attiva annullata[/yellow]")
        
        # Delete session.json
        if config.session_file_path.exists():
            config.session_file_path.unlink()
            files_deleted.append(str(config.session_file_path))
        
        # Delete temp file (palio_games_status_tmp.json)
        if config.palio_games_status_temp_path.exists():
            config.palio_games_status_temp_path.unlink()
            files_deleted.append(str(config.palio_games_status_temp_path))
        
        # Also check for palio_updated.json (legacy temp file)
        palio_updated_path = Path("data/palio_updated.json")
        if palio_updated_path.exists():
            palio_updated_path.unlink()
            files_deleted.append(str(palio_updated_path))
        
        if files_deleted:
            console.print(f"\n[green]✓ File eliminati:[/green] {', '.join(files_deleted)}")
        else:
            console.print("\n[yellow]Nessun file temporaneo da eliminare[/yellow]")
        
        return True
    
    else:
        console.print(f"\n[red]Comando non riconosciuto: {command}[/red]")
        return True


def ensure_palio_json_exists():
    """Ensure palio.json and palio_games_status.json exist with basic structures."""
    config = Config()
    
    # Ensure data directory exists
    config.palio_file_path.parent.mkdir(exist_ok=True)
    
    # Check palio.json
    if not config.palio_file_path.exists():
        console.print(f"\n[yellow]File {config.palio_file_path} non trovato. Creazione file base...[/yellow]")
        
        basic_structure = {
            "palio": {
                "anno": 2024,
                "borghi": ["villa", "salt", "badia", "sottocastello"],
                "eventi": []
            }
        }
        
        with open(config.palio_file_path, 'w', encoding='utf-8') as f:
            json.dump(basic_structure, f, ensure_ascii=False, indent=2)
        
        console.print(f"[green]✓ File {config.palio_file_path} creato con struttura base[/green]")
    
    # Check palio_games_status.json
    if not config.palio_games_status_path.exists():
        console.print(f"\n[yellow]File {config.palio_games_status_path} non trovato. Creazione file base...[/yellow]")
        
        basic_status = {
            "game_scores": {},
            "last_updated": None
        }
        
        with open(config.palio_games_status_path, 'w', encoding='utf-8') as f:
            json.dump(basic_status, f, ensure_ascii=False, indent=2)
        
        console.print(f"[green]✓ File {config.palio_games_status_path} creato con struttura base[/green]")


async def main():
    """Main CLI entry point with event system."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Palio Bot CLI")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-log-file", action="store_true", help="Disable logging to file")
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug, log_file=not args.no_log_file)
    
    logger.info("Starting Palio Bot CLI")
    logger.debug(f"Debug mode: {args.debug}")
    
    print_welcome()
    ensure_palio_json_exists()
    
    # Get configuration from environment or use defaults
    llamacpp_url = os.getenv("LLAMACPP_URL", "http://mac-studio.local:11454")
    llm_provider = os.getenv("LLM_PROVIDER", "llamacpp")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    
    # Create container and initialize
    console.print("\n[dim]Inizializzazione sistema...[/dim]")
    
    # Create config (will use env variables and defaults)
    config = Config()
    
    container = Container(
        config=config,
        llm_provider=llm_provider,  # Can override config
        anthropic_api_key=anthropic_api_key  # Can override config
    )
    
    try:
        await container.init_container()
    except Exception as e:
        logger.error(f"Failed to initialize container: {e}", exc_info=True)
        console.print(f"\n[red]Errore durante l'inizializzazione: {e}[/red]")
        if args.debug:
            console.print("[dim]Controlla i log per maggiori dettagli[/dim]")
        return
    
    # Get services
    system = container.system()
    cli_consumer = container.cli_consumer()
    
    console.print("[green]✓ Sistema inizializzato[/green]")
    
    # Main interaction loop
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]>[/bold cyan]")
            
            if not user_input.strip():
                continue
            
            # Handle special commands
            if user_input.startswith("/"):
                should_continue = await handle_commands(user_input, system, container)
                if not should_continue:
                    break
                continue
            
            # Process message - events will be displayed in real-time
            try:
                # The CLI consumer will automatically adopt the session ID from the first event
                await system.send_message(user_input)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                console.print(f"\n[red]Errore: {e}[/red]")
                if args.debug:
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt")
            console.print("\n\n[yellow]Interruzione da tastiera[/yellow]")
            if system.get_active_session():
                system.cancel_session()
                console.print("\n[yellow]✓ Sessione annullata, modifiche scartate[/yellow]")
            else:
                break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            console.print(f"\n[red]Errore inaspettato: {e}[/red]")
            if args.debug:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
    
    # Cleanup
    logger.info("Shutting down...")
    await container.stream().stop_processing()
    console.print("\n[cyan]Arrivederci! 👋[/cyan]")
    logger.info("Palio Bot CLI stopped")


if __name__ == "__main__":
    asyncio.run(main())