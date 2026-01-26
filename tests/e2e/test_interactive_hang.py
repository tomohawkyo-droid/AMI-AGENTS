import sys

import pytest

from ami.core.bootloader_agent import BootloaderAgent, RunContext


def test_interactive_hang():
    print("\n--> Starting E2E test for interactive session hang...")

    # 1. Setup
    print("--> Initializing BootloaderAgent with REAL Qwen provider...")
    agent = BootloaderAgent()

    print("--> Sending instruction: 'Hi'")

    # DEBUG: Print full prompt construction
    print("--> Full instruction passed to run(): 'Hi'")

    print("--> Watching for stream output (timeout 30s)...")

    # We define a stream callback to see what's actually coming back
    # This mirrors how the CLI updates the TUI
    tokens_received = []

    def debug_callback(token):
        tokens_received.append(token)
        sys.stdout.write(".")
        sys.stdout.flush()

    try:
        # We assume the user won't confirm execution in this test,
        # but 'Hi' shouldn't trigger execution.
        ctx = RunContext(instruction="Hi", stream_callback=debug_callback, timeout=30)
        response, _session = agent.run(ctx)

        print(f"\n\n[FINAL RESPONSE]: {response}")

        if not response and not tokens_received:
            pytest.fail("No response and no tokens received. The agent was silent.")
        elif not response:
            pytest.fail("Tokens received but final response was empty.")
        else:
            print("\nSUCCESS: Agent replied.")
            # Test passes implicitly if we reach here

    except Exception as e:
        print(f"\n[ERROR]: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_interactive_hang()
