#!/usr/bin/env python3
"""Test Thymio dongle connection via tdmclient."""
import asyncio
from tdmclient import ClientAsync

async def main():
    print("1. Creating client...")
    try:
        client = ClientAsync()
        print("   Client created (TDM found)")
    except ConnectionRefusedError:
        print("   No TDM server (expected)")
        print("   Cannot continue without TDM server.")
        print("   Options:")
        print("   - Run Thymio Suite on Windows, or")
        print("   - Use: ClientAsync(tdm_addr='WINDOWS_IP', tdm_port=8596)")
        return
    except Exception as e:
        print(f"   Error: {e}")
        return

    print("2. Waiting for node...")
    try:
        node = await asyncio.wait_for(client.wait_for_node(), timeout=10.0)
        print(f"   Found: {node.id_str}")
    except asyncio.TimeoutError:
        print("   No Thymio found in 10 seconds")
        return
    except Exception as e:
        print(f"   Error: {e}")
        return

    print("3. Locking node...")
    await node.lock()
    print("   Locked!")

    print("4. Testing motors (1s)...")
    await node.set_variables({"motor.left.target": [200], "motor.right.target": [200]})
    await asyncio.sleep(1.0)
    await node.set_variables({"motor.left.target": [0], "motor.right.target": [0]})
    print("   Stopped.")

    await node.unlock()
    print("5. Done!")

if __name__ == "__main__":
    asyncio.run(main())
