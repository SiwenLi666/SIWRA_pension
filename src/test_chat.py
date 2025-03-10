"""
Test script for the pension advisor chat functionality.
"""
import asyncio
import os
from dotenv import load_dotenv
from agent import PensionAdvisor
from init_system import init_system

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize the system
    print("Initializing system...")
    await init_system()
    
    # Create advisor instance
    advisor = PensionAdvisor()
    
    # Test conversation
    messages = [
        "Hej! Jag skulle vilja veta mer om min pension. Jag är född 1990 och jobbar i kommunen.",
        "Min månadslön är 35000 kr och jag började jobba här 2015.",
        "Jag är fast anställd. Kan du beräkna min pension?",
        "Vad händer om jag jobbar kvar till 65 års ålder?",
        "Tack för hjälpen!"
    ]
    
    print("\nStarting test conversation...\n")
    
    for message in messages:
        print(f"\nUser: {message}")
        response = await advisor.chat(message)
        print(f"Assistant: {response}\n")
        await asyncio.sleep(1)  # Small delay between messages

if __name__ == "__main__":
    asyncio.run(main()) 