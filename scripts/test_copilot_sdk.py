#!/usr/bin/env python3
"""Quick connectivity test for the Copilot SDK.

Run with:
    uv run scripts/test_copilot_sdk.py

Verifies that the bundled Copilot CLI binary works and authentication
is set up correctly.  Prints every event received from the session.
"""

from __future__ import annotations

import asyncio
import sys
import traceback

from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType


async def _run() -> None:
    print("Creating client...", flush=True)
    client = CopilotClient()

    print("Starting client...", flush=True)
    await client.start()
    print(f"Client started. cli_path={client.options.get('cli_path')}", flush=True)

    print("Creating session...", flush=True)
    session = await client.create_session()
    print(f"Session created: {session.session_id}", flush=True)

    collected: list[str] = []

    def handler(event: object) -> None:
        etype = getattr(event, "type", "?")
        data = getattr(event, "data", None)
        msg = getattr(data, "message", None) if data else None
        error_type = getattr(data, "error_type", None) if data else None
        print(f"  Event: {etype} | msg={msg!r:.100s if msg else 'None'} | error={error_type}", flush=True)
        if etype == SessionEventType.ASSISTANT_MESSAGE and msg:
            collected.append(msg)

    session.on(handler)
    print("Sending prompt...", flush=True)
    resp = await session.send_and_wait({"prompt": "Reply with just the word hello"}, timeout=60)
    print(f"Done. Collected {len(collected)} message(s)", flush=True)

    if collected:
        print(f"Answer: {collected[0]}", flush=True)
    else:
        print("No messages collected!", flush=True)
        if resp:
            print(f"Response type: {resp.type}", flush=True)
            print(f"Response data: {resp.data}", flush=True)

    await session.destroy()
    await client.stop()
    print("✓ Copilot SDK is working.", flush=True)


def main() -> None:
    try:
        asyncio.run(_run())
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
