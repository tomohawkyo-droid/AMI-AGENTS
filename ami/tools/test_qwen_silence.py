#!/usr/bin/env python3

from ami.core.bootloader_agent import BootloaderAgent, RunContext
from ami.types.events import StreamEvent


def main() -> None:
    print("Testing Qwen Silence...")
    agent = BootloaderAgent()

    def stream_handler(x: str | StreamEvent) -> None:
        if isinstance(x, str):
            print(x, end="", flush=True)

    # Run agent
    ctx = RunContext(
        instruction="Hello",
        input_func=lambda _cmd: True,
        stream_callback=stream_handler,
    )
    response, _session_id = agent.run(ctx)

    print("\n\n--- Final Response ---")
    print(f"'{response}'")


if __name__ == "__main__":
    main()
