#!/usr/bin/env python3
"""Test Thymio dongle connection via tdmclient local discovery."""
import asyncio
from tdmclient import ClientAsync

async def main():
    print("1. Creating client...")
    try:
        client = ClientAsync()
    except ConnectionRefusedError:
        print("   TDM server not found (expected, continuing...)")

    print("2. Starting local discovery...")
    try:
        client.start_local_discovery()
    except Exception as e:
        print(f"   Discovery error: {e}")

    print("3. Waiting for node (10s timeout)...")
    try:
        node = await asyncio.wait_for(client.wait_for_node(), timeout=10.0)
        print(f"   Found node: {node.id_str}")

        print("4. Locking node...")
        await node.lock()
        print("   Locked!")

        print("5. Testing motors (1 second)...")
        await node.set_variables({"motor.left.target": [200], "motor.right.target": [200]})
        await asyncio.sleep(1.0)
        await node.set_variables({"motor.left.target": [0], "motor.right.target": [0]})
        print("   Motors stopped.")

        await node.unlock()
        print("6. Done! Dongle works.")
    except asyncio.TimeoutError:
        print("   ERROR: No Thymio found within 10 seconds.")
        print("   Make sure dongle is attached to WSL and Thymio is ON.")
    except Exception as e:
        print(f"   ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
