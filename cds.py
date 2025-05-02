import socket
import threading
import json
import random
import hashlib

def find_available_port(start_port, max_attempts=10):
    """Try to find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find available port after {max_attempts} attempts")

class CentralDirectoryServer:
    def __init__(self):
        self.relays = []  # List of dicts: {"ip": str, "port": int, "public_key": str}
        self.lock = threading.Lock()
        self.relay_port = find_available_port(9000)
        self.client_port = find_available_port(9001)

    def start(self):
        threading.Thread(target=self.relay_registration_server, daemon=True).start()
        threading.Thread(target=self.client_request_server, daemon=True).start()
        print(f"[CDS] Central Directory Server running on ports {self.relay_port} (relay reg), {self.client_port} (client req)")
        
        # Write ports to a file so client can find them
        with open("cds_ports.txt", "w") as f:
            f.write(f"{self.relay_port}\n{self.client_port}\n")
        
        while True:
            pass  # Keep main thread alive

    def relay_registration_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", self.relay_port))
            s.listen()
            print(f"[CDS] Listening for relay registrations on port {self.relay_port}")
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
            s.bind(("0.0.0.0", self.client_port))
            s.listen()
            print(f"[CDS] Listening for client relay requests on port {self.client_port}")
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
