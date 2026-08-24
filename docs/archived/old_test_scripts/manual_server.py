import sys
from tdmclient.server import Server
from tdmclient.tcp import TDMServerTCP
from tdmclient.nodes_local import NodesLocal

def run_server():
    print("Attempting manual startup of TDM server...")
    try:
        # 1. Force initialization of local node discovery (scan serial ports directly)
        nodes_local = NodesLocal()
        
        # 2. Create TDM core server logic
        server = Server(nodes_local=nodes_local)
        
        # 3. Bind TCP port 8596
        # This is to interface with thymio_bridge.py
        tcp_server = TDMServerTCP(server, 8596)
        
        print("Server ready, listening on port: 8596")
        print("Searching for robots, please verify usbipd is attached and permissions are set...")
        
        # 4. Enter main loop
        tcp_server.run()
    except Exception as e:
        print(f"Startup failed: {e}")

if __name__ == "__main__":
    run_server()
