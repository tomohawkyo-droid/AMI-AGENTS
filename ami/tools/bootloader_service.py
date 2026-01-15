#!/usr/bin/env python3
"""
Minimal Agent Service - Refactored to use unified AmiMatrixBot.
"""
import asyncio
import sys
import json
import threading
import signal
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from base.backend.matrix.client import AmiMatrixBot
from base.backend.matrix.streaming import StreamBuffer
from base.backend.agents.session_store import SessionStore
from agents.ami.core.bootloader_agent import BootloaderAgent
from nio import RoomMessageText

class AgentBot(AmiMatrixBot):
    """
    Agent-Specific Bot Logic.
    Inherits core Matrix capabilities from AmiMatrixBot.
    Adds MinimalAgent execution and Streaming.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure store_path is a Path object (nio might convert it to str)
        store_path = Path(self.store_path)
        self.session_db_path = store_path.parent / "agent_sessions.sqlite"
        self.session_store = SessionStore(self.session_db_path)
        
        self.active_tasks = {} # room_id -> (task, stop_event)
        self.pending_confirmations = {} # room_id -> Future

    async def message_callback(self, room: RoomMessageText, event: RoomMessageText):
        # Override the base empty callback
        sender = event.sender
        if sender == self.user_id:
            return
            
        print(f"DEBUG: Processing message from {sender}")
        content = event.body.strip()
        if not content:
            return

        # Handle confirmations
        if room.room_id in self.pending_confirmations and not self.pending_confirmations[room.room_id].done():
            if content.lower() in ["y", "yes"]:
                self.pending_confirmations[room.room_id].set_result(True)
                return
            elif content.lower() in ["n", "no"]:
                self.pending_confirmations[room.room_id].set_result(False)
                return
            else:
                return 

        # Handle STOP
        if content.lower() == "stop":
            if room.room_id in self.active_tasks:
                task, stop_event = self.active_tasks[room.room_id]
                stop_event.set()
                await self.room_send(
                    room.room_id,
                    "m.room.message",
                    {"msgtype": "m.text", "body": "🛑 Stopping agent..."},
                    ignore_unverified_devices=True
                )
            return

        # Handle E2E Test Ping (Legacy/Direct handling)
        if "E2E_TEST_PING" in content:
            print(f"[{self.user_id}] E2E Ping from {sender}. Ponging...")
            await self.room_send(
                room.room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": "E2E_TEST_PONG"},
                ignore_unverified_devices=True
            )
            return

        # Handle Diagnostics Test (Connectivity Verification)
        if "Diagnostics Test" in content:
            print(f"[{self.user_id}] Diagnostics Test from {sender}. Acking...")
            await self.room_send(
                room.room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": f"ACK: {content}"},
                ignore_unverified_devices=True
            )
            return

        # Execute Agent
        full_prompt = content
        session_id = self.session_store.get_session(room.room_id)
        
        if room.room_id in self.active_tasks:
            old_task, old_stop_event = self.active_tasks[room.room_id]
            old_stop_event.set()
        
        stop_event = threading.Event()
        task = asyncio.create_task(
            self._run_agent_task(room.room_id, full_prompt, session_id, stop_event)
        )
        self.active_tasks[room.room_id] = (task, stop_event)

    async def _run_agent_task(self, room_id, full_prompt, session_id, stop_event):
        try:
            loop = asyncio.get_running_loop()
            streamer = StreamBuffer(self, room_id, loop)
            
            def wait_for_input():
                fut = loop.create_future()
                self.pending_confirmations[room_id] = fut
                try:
                    import concurrent.futures
                    cfut = concurrent.futures.Future()
                    def bridge_future(f):
                        try:
                            res = f.result()
                            cfut.set_result(res)
                        except Exception as e:
                            cfut.set_exception(e)
                    loop.call_soon_threadsafe(lambda: fut.add_done_callback(bridge_future))
                    return cfut.result(timeout=600)
                finally:
                    loop.call_soon_threadsafe(lambda: self.pending_confirmations.pop(room_id, None))

            agent = BootloaderAgent()
            allowed_tools = ["save_memory"]
            
            print(f"DEBUG: Calling agent.run with session_id={session_id}")
            response, actual_session_id = await loop.run_in_executor(
                None, agent.run, full_prompt, session_id, streamer.on_token, stop_event, wait_for_input, allowed_tools
            )
            print(f"DEBUG: agent.run completed. Response length: {len(response) if response else 0}")
            
            print("DEBUG: Finalizing streamer...")
            await streamer.finalize()
            print("DEBUG: Streamer finalized.")
            
            # Send response
            if response:
                print(f"DEBUG: Calling self.send_text for room {room_id}...")
                await self.send_text(room_id, response)
                print("DEBUG: self.send_text completed.")

            if actual_session_id != session_id:
                self.session_store.save_session(room_id, actual_session_id)

        except Exception as e:
            error_msg = f"Agent Error: {str(e)}"
            print(error_msg)
            await self.room_send(
                room_id,
                "m.room.message",
                {"msgtype": "m.text", "body": error_msg},
                ignore_unverified_devices=True
            )
        finally:
            if room_id in self.active_tasks:
                if self.active_tasks[room_id][1] == stop_event:
                    del self.active_tasks[room_id]

async def main():
    credentials_file = PROJECT_ROOT / "credentials.json"
    store_path = PROJECT_ROOT / "logs" / "matrix_store"
    
    if not credentials_file.exists():
        print(f"Error: credentials.json not found.")
        sys.exit(1)

    with open(credentials_file, 'r') as f:
        creds = json.load(f)

    bot = AgentBot(
        homeserver=creds["homeserver"],
        user_id=creds["user_id"],
        device_id=creds["device_id"],
        access_token=creds["access_token"],
        store_path=store_path,
        admin_user="@moderator:mx1.p9q3fjcwcla0.uk" 
    )
    
    bot.add_event_callback(bot.message_callback, RoomMessageText)
    
    # Graceful Shutdown Handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        print("\n[Signal] Received exit signal. Stopping bot...")
        stop_event.set()

    loop.add_signal_handler(signal.SIGINT, handle_signal)
    loop.add_signal_handler(signal.SIGTERM, handle_signal)

    # Run bot in a task so we can wait for stop_event
    bot_task = asyncio.create_task(bot.start())
    
    try:
        await stop_event.wait()
    finally:
        print("[Shutdown] Closing bot client...")
        await bot.client.close()
        # Ensure bot task is cancelled/awaited if it hasn't finished
        if not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        print("[Shutdown] Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(main())