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
            s.bind(("0.0.0.0", RELAY_REG_PORT))  # Accept connections from any interface
            s.listen()
            print(f"[CDS] Listening for relay registrations on 0.0.0.0:{RELAY_REG_PORT}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_relay_registration, args=(conn, addr), daemon=True).start()

    def handle_relay_registration(self, conn, addr):
        try:
            data = conn.recv(8192)
            relay_info = json.loads(data.decode())
            # Support deregistration
            if relay_info.get('deregister'):
                with self.lock:
                    self.relays = [r for r in self.relays if not (r['ip'] == relay_info['ip'] and r['port'] == relay_info['port'])]
                    print(f"[CDS] Deregistered relay: {relay_info['ip']}:{relay_info['port']}")
                conn.sendall(b'OK')
                return
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
            s.bind(("0.0.0.0", CLIENT_REQ_PORT))  # Accept connections from any interface
            s.listen()
            print(f"[CDS] Listening for client requests on 0.0.0.0:{CLIENT_REQ_PORT}")
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client_request, args=(conn, addr), daemon=True).start()

    def handle_client_request(self, conn, addr):
        try:
            data = conn.recv(1024)
            req = data.decode().strip()
            n = 3
            if req == 'LIST_RELAYS':
                with self.lock:
                    conn.sendall(json.dumps(self.relays).encode())
                print(f"[CDS] Provided LIST_RELAYS to {addr}: {self.relays}")
                return
            if req.startswith('REQUEST_RELAYS:'):
                try:
                    n = int(req.split(':')[1])
                except Exception:
                    n = 3
            if req.startswith('REQUEST_RELAYS'):
                with self.lock:
                    if len(self.relays) < n:
                        conn.sendall(b'NOT_ENOUGH_RELAYS')
                        return
                    selected = random.sample(self.relays, n)
                conn.sendall(json.dumps(selected).encode())
                import hashlib
                for relay in selected:
                    fingerprint = hashlib.sha256(relay['public_key'].encode()).hexdigest()
                    print(f"[CDS] [KEY] Sending relay public key fingerprint: {fingerprint} for {relay['ip']}:{relay['port']}")
                print(f"[CDS] Provided relays to client {addr}: {selected}")
                return
            conn.sendall(b'ERROR')
        except Exception as e:
            print(f"[CDS] Client request error from {addr}: {e}")
            conn.sendall(b'ERROR')
        finally:
            conn.close()

if __name__ == "__main__":
    cds = CentralDirectoryServer()
    cds.start()
