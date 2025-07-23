#!/usr/bin/env python
"""Test script for multi-file JSON editing functionality."""

import asyncio
import logging
from pathlib import Path

from palio_bot.container import Container

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_multi_file():
    """Test the multi-file editing capability."""
    print("\n" + "="*60)
    print("Testing Multi-File JSON Editing")
    print("="*60 + "\n")
    
    # Initialize container (multi-file is now default)
    container = Container()
    await container.init_container()
    
    system = container.system()
    
    # Test 1: View games file
    print("\n1. Testing view of games file:")
    print("-" * 40)
    await system.send_message("mostra lo stato dei giochi")
    
    # Test 2: View leaderboard file
    print("\n2. Testing view of leaderboard file:")
    print("-" * 40)
    await system.send_message("mostra la classifica")
    
    # Test 3: Modify games file
    print("\n3. Testing modification of games file:")
    print("-" * 40)
    await system.send_message("sottocastello vince 3-1 contro villa nel calcetto")
    
    # Test 4: Modify leaderboard file
    print("\n4. Testing modification of leaderboard file:")
    print("-" * 40)
    await system.send_message("aggiungi 5 punti bonus a Villa nella classifica per fair play")
    
    # Test 5: View both files to confirm changes
    print("\n5. Verifying changes in both files:")
    print("-" * 40)
    await system.send_message("mostra sia lo stato dei giochi che la classifica")
    
    # Close session to save changes
    print("\n6. Closing session to save changes:")
    print("-" * 40)
    system.close_session()
    print("Session closed - changes should be saved to both files")
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_multi_file())