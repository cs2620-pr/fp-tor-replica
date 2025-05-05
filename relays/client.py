import socket
import json
import base64
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from crypto_utils import generate_aes_key, aes_encrypt, aes_decrypt, deserialize_public_key, rsa_encrypt, public_key_fingerprint
sys.path.pop(0)
import hashlib
import argparse

CDS_DEFAULT_IP = '127.0.0.1'
CDS_CLIENT_PORT = 9001

class Client:
    def __init__(self, dest_ip, dest_port, message, cds_ip=CDS_DEFAULT_IP):
        # Ensure message is valid JSON
        import json
        try:
            json.loads(message)
        except Exception as e:
            print(f"[Client] ERROR: Message must be a valid JSON string. Got: {message}\nError: {e}")
            exit(1)
        self.dest_ip = dest_ip
        self.dest_port = dest_port
        self.message = message.encode()
        self.cds_ip = cds_ip

    def get_relays_from_cds(self, n=3):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.cds_ip, CDS_CLIENT_PORT))
            req = f'REQUEST_RELAYS:{n}'.encode()
            s.sendall(req)
            data = s.recv(65536)
            if data == b'NOT_ENOUGH_RELAYS':
                raise Exception('Not enough relays registered!')
            relays = json.loads(data.decode())
            for relay in relays:
                pubkey_obj = deserialize_public_key(relay['public_key'].encode())
                print(f"[Client] Relay {relay['ip']}:{relay['port']} public key fingerprint: {public_key_fingerprint(pubkey_obj)}")
            return relays

    def build_onion(self, relays):
        # Print fingerprints for public keys used in onion layers
        for i, relay in enumerate(relays):
            pubkey_obj = deserialize_public_key(relay['public_key'].encode())
            print(f"[Client] Using relay {relay['ip']}:{relay['port']} public key fingerprint for layer {i+1}: {public_key_fingerprint(pubkey_obj)}")
        N = len(relays)
        session_keys = [generate_aes_key() for _ in range(N)]
        # Prepare innermost payload: always valid JSON, UTF-8 bytes
        try:
            innermost_json = json.loads(self.message.decode('utf-8') if isinstance(self.message, bytes) else self.message)
        except Exception:
            innermost_json = {"msg": self.message.decode('utf-8') if isinstance(self.message, bytes) else self.message}
        payload = json.dumps(innermost_json, ensure_ascii=False).encode('utf-8')
        print(f"[Client] [DEBUG] Innermost payload to destination: {payload!r}")
        # Build onion from innermost to outermost
        for i in reversed(range(N)):
            pubkey_obj = deserialize_public_key(relays[i]['public_key'].encode())
            session_key = session_keys[i]
            session_key_enc = base64.b64encode(rsa_encrypt(pubkey_obj, session_key)).decode('utf-8')
            # Encrypt payload with AES session key
            encrypted_payload = aes_encrypt(session_key, payload)
            payload_b64 = base64.b64encode(encrypted_payload).decode('utf-8')
            # Build envelope for this layer
            next_ip = relays[i]['ip'] if i < N - 1 else self.dest_ip
            next_port = relays[i]['port'] if i < N - 1 else self.dest_port
            layer = {
                'next_ip': next_ip,
                'next_port': next_port,
                'session_key': session_key_enc,
                'payload': payload_b64
            }
            payload = json.dumps(layer).encode('utf-8')
            print(f"[Client] [DEBUG] Layer {i+1} envelope: {payload!r}")
        print(f"[Client] [DEBUG] Final onion payload: {payload!r}, len={len(payload)}")
        print(f"[Client] [DEBUG] Sending to first relay {relays[0]['ip']}:{relays[0]['port']}, len={len(payload)}, type={type(payload)}")
        return payload, relays[0]['ip'], relays[0]['port'], session_keys

    def send_onion(self, onion_bytes, first_ip, first_port, keys):
        import socket
        import base64
        import json
        # Send to first relay (outermost layer)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((first_ip, first_port))
            s.sendall(onion_bytes)
            response = s.recv(65536)
        print(f"[Client] [DEBUG] Received response from first relay: type={type(response)}, len={len(response)}, preview={response[:60]!r}")
        # Unwrap each layer
        response_layer = response
        for i, key in enumerate(keys):
            # Only base64-decode if the response is base64-encoded (i.e., not plaintext JSON error)
            try:
                # Try to decode as utf-8 and parse as JSON
                as_str = response_layer.decode('utf-8')
                if as_str.strip().startswith('{'):
                    # Looks like JSON, stop unwrapping and print result
                    print(f"[Client] [RESULT] {as_str}")
                    return
            except Exception:
                pass
            # If not JSON, assume it is base64-encoded and encrypted
            try:
                response_layer = base64.b64decode(response_layer)
            except Exception as e:
                print(f"[Client] [ERROR] Base64 decode failed at layer {i}: {e}")
                print(f"[Client] [RESULT] Raw response: {repr(response_layer)}")
                return
            print(f"[Client] [DEBUG] Received base64-decoded response: type={type(response_layer)}, len={len(response_layer)}, preview={response_layer[:60]!r}")
            print(f"[Client] [DEBUG] Before aes_decrypt at layer {i}: type={type(response_layer)}, len={len(response_layer)}, preview='{repr(response_layer)[:60]}'")
            response_layer = aes_decrypt(key, response_layer)
            print(f"[Client] [DEBUG] After decrypt at layer {i}: type={type(response_layer)}, len={len(response_layer)}, preview={response_layer[:60]!r}")
            print(f"[Client] [DEBUG] After decrypt at layer {i} (hex): {response_layer.hex()}")
            print(f"[Client] [DEBUG] Passed raw bytes to next decryption at layer {i}, type={type(response_layer)}, len={len(response_layer)}")
        print(f"[Client] [DEBUG] Final decrypted bytes: {repr(response_layer)}, len={len(response_layer)}")
        print(f"[Client] [DEBUG] Final decrypted bytes (hex): {response_layer.hex()}")
        final_payload = response_layer
        # Final layer: print or return the result
        try:
            final_str = final_payload.decode('utf-8')
            print(f"[Client] [DEBUG] Final decoded as UTF-8: {final_str}")
            try:
                resp_json = json.loads(final_str)
                print(f"[Client] [RESULT] {resp_json}")
            except Exception:
                print(f"[Client] [RESULT] {final_str}")
        except Exception as e:
            # Try to base64 decode if encoding is present
            try:
                final_str = final_payload.decode('utf-8', errors='ignore')
                print(f"[Client] [DEBUG] Final decoded as UTF-8 (ignore errors): {final_str}")
                resp_json = json.loads(final_str)
                if resp_json.get('encoding') == 'base64':
                    import base64
                    decoded = base64.b64decode(resp_json['echo'])
                    print(f"[Client] [RESULT] (base64 decoded): {decoded}")
                else:
                    print(f"[Client] [RESULT] {resp_json}")
            except Exception as e2:
                print(f"[Client] [ERROR] Final layer not UTF-8 decodable: {e}")
                print(f"[Client] [DEBUG] Final raw bytes repr: {repr(final_payload)}")
                print(f"[Client] [DEBUG] Final raw bytes (hex): {final_payload.hex()}")

    def run(self, path_length=3):
        relays = self.get_relays_from_cds(path_length)
        onion_bytes, first_ip, first_port, keys = self.build_onion(relays)
        self.send_onion(onion_bytes, first_ip, first_port, keys)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tor-inspired relay client")
    parser.add_argument("dest_ip", help="Destination server IP address")
    parser.add_argument("dest_port", type=int, help="Destination server port")
    parser.add_argument("message", help="Message to send (must be valid JSON string)")
    parser.add_argument("--cds_ip", default=CDS_DEFAULT_IP, help="CDS server IP address (default: 127.0.0.1)")
    parser.add_argument("--path_length", type=int, default=3, help="Number of relays (default: 3)")
    args = parser.parse_args()

    client = Client(args.dest_ip, args.dest_port, args.message, cds_ip=args.cds_ip)
    client.run(args.path_length)
