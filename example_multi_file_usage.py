#!/usr/bin/env python
"""Example of using the multi-file JSON editing system."""

import asyncio
from palio_bot.container import Container


async def main():
    """Example usage of multi-file editing."""
    
    # Initialize container (multi-file is now default)
    container = Container(
        llm_provider="llamacpp"  # or "llamacpp"
    )
    
    # Initialize all services
    await container.init_container()
    
    # Get the system
    system = container.system()
    
    # Example 1: View games status
    await system.send_message("mostra lo stato dei giochi")
    
    # Example 2: Update a game result
    await system.send_message("villa vince 2-0 contro salt nel calcetto")
    
    # Example 3: View leaderboard
    await system.send_message("mostra la classifica")
    
    # Example 4: Add manual adjustment to leaderboard
    await system.send_message("penalizza Sottocastello di 5 punti per ritardo")
    
    # Example 5: View a specific game
    await system.send_message("mostra lo stato del gioco G09")
    
    # Close session to save all changes
    system.close_session()
    print("\nAll changes saved!")
    
    # Or cancel session to discard changes
    # system.cancel_session()
    # print("\nAll changes discarded!")


if __name__ == "__main__":
    asyncio.run(main())