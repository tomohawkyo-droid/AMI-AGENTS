#!/usr/bin/env python3
import sys
from pathlib import Path

from ami.core.bootloader_agent import BootloaderAgent

def main():
    print("Testing Qwen Silence...")
    agent = BootloaderAgent()
    
    # Run agent
    response, session_id = agent.run(
        instruction="Hello",
        input_func=lambda: True, 
        stream_callback=lambda x: print(x, end="", flush=True)
    )
    
    print("\n\n--- Final Response ---")
    print(f"'{response}'")

if __name__ == "__main__":
    main()

