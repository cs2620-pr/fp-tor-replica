import socket
import threading
import json
import random
import hashlib

RELAY_REG_PORT = 9000  # Port for relays to register
CLIENT_REQ_PORT = 9001  # Port for clients to request relays

class CentralDirectoryServer:
    def __init__(self):
        self.relays = []  # List of dicts: {"ip": str, "port": int, "public_key": str}
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self.relay_registration_server, daemon=True).start()
        threading.Thread(target=self.client_request_server, daemon=True).start()
        print(f"[CDS] Central Directory Server running on ports {RELAY_REG_PORT} (relay reg), {CLIENT_REQ_PORT} (client req)")
        while True:
            pass  # Keep main thread alive

    def relay_registration_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", RELAY_REG_PORT))
            s.listen()
            print(f"[CDS] Listening for relay registrations on port {RELAY_REG_PORT}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_relay_registration, args=(conn, addr), daemon=True).start()

    def handle_relay_registration(self, conn, addr):
        try:
            data = conn.recv(8192)
            relay_info = json.loads(data.decode())
            with self.lock:
                # Check for duplicate (by ip/port)
                found = False
                for r in self.relays:
                    if r["ip"] == relay_info["ip"] and r["port"] == relay_info["port"]:
                        if r["public_key"] != relay_info["public_key"]:
                            print(f"[CDS] Relay {relay_info['ip']}:{relay_info['port']} public key updated.")
                            r["public_key"] = relay_info["public_key"]
                        else:
                            print(f"[CDS] Relay already registered: {relay_info}")
                        found = True
                        break
                if not found:
                    self.relays.append(relay_info)
                    print(f"[CDS] Registered relay: {relay_info}")
            conn.sendall(b'OK')
        except Exception as e:
            print(f"[CDS] Relay registration error from {addr}: {e}")
            conn.sendall(b'ERROR')
        finally:
            conn.close()

    def client_request_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", CLIENT_REQ_PORT))
            s.listen()
            print(f"[CDS] Listening for client relay requests on port {CLIENT_REQ_PORT}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client_request, args=(conn, addr), daemon=True).start()

    def handle_client_request(self, conn, addr):
        try:
            with self.lock:
                if len(self.relays) < 3:
                    conn.sendall(b'NOT_ENOUGH_RELAYS')
                    return
                selected = random.sample(self.relays, 3)
            conn.sendall(json.dumps(selected).encode())
            import hashlib
            for relay in selected:
                fingerprint = hashlib.sha256(relay['public_key'].encode()).hexdigest()
                print(f"[CDS] [KEY] Sending relay public key fingerprint: {fingerprint} for {relay['ip']}:{relay['port']}")
            print(f"[CDS] Provided relays to client {addr}: {selected}")
        except Exception as e:
            print(f"[CDS] Client request error from {addr}: {e}")
            conn.sendall(b'ERROR')
        finally:
            conn.close()

if __name__ == "__main__":
    cds = CentralDirectoryServer()
    cds.start()
