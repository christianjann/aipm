#!/usr/bin/env python3
"""List available Copilot models."""
import asyncio
from copilot import CopilotClient

async def main():
    client = CopilotClient()
    await client.start()
    models = await client.list_models()
    for m in models:
        print(f"  {m.id:40s}  {m.name}")
    await client.stop()

asyncio.run(main())
