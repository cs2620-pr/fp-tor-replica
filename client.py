import socket
import json
import base64
from crypto_utils import generate_aes_key, aes_encrypt, aes_decrypt, deserialize_public_key, rsa_encrypt, public_key_fingerprint
import hashlib

CDS_IP = '127.0.0.1'
CDS_CLIENT_PORT = 9001

class Client:
    def __init__(self, dest_ip, dest_port, message):
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

    def get_relays_from_cds(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((CDS_IP, CDS_CLIENT_PORT))
            s.sendall(b'REQUEST_RELAYS')
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
        # Generate 3 AES keys
        K1 = generate_aes_key()
        K2 = generate_aes_key()
        K3 = generate_aes_key()

        # Use relays in the order returned by CDS
        relay_outer_pubkey = deserialize_public_key(relays[0]['public_key'].encode())
        relay_middle_pubkey = deserialize_public_key(relays[1]['public_key'].encode())
        relay_inner_pubkey = deserialize_public_key(relays[2]['public_key'].encode())
        session_key_outer_enc = base64.b64encode(rsa_encrypt(relay_outer_pubkey, K1)).decode('utf-8')
        session_key_middle_enc = base64.b64encode(rsa_encrypt(relay_middle_pubkey, K2)).decode('utf-8')
        session_key_inner_enc = base64.b64encode(rsa_encrypt(relay_inner_pubkey, K3)).decode('utf-8')

        # Innermost layer (destination)
        # self.message must be bytes
        if isinstance(self.message, str):
            message_bytes = self.message.encode('utf-8')
        else:
            message_bytes = self.message
        layer3_payload = aes_encrypt(K3, message_bytes)  # always bytes now

        # Middle layer (relay 3)
        layer2_dict = {
            'next_ip': relays[2]['ip'],
            'next_port': relays[2]['port'],
            'session_key': session_key_inner_enc,
            'payload': base64.b64encode(layer3_payload).decode('utf-8')  # string for JSON
        }
        layer2_json = json.dumps(layer2_dict)
        layer2_payload = aes_encrypt(K2, layer2_json.encode('utf-8'))

        # Outermost layer (relay 2)
        layer1_dict = {
            'next_ip': relays[1]['ip'],
            'next_port': relays[1]['port'],
            'session_key': session_key_middle_enc,
            'payload': base64.b64encode(layer2_payload).decode('utf-8')
        }
        layer1_json = json.dumps(layer1_dict)
        layer1_payload = aes_encrypt(K1, layer1_json.encode('utf-8'))

        # Top layer (relay 1)
        onion_msg = {
            'next_ip': relays[0]['ip'],
            'next_port': relays[0]['port'],
            'session_key': session_key_outer_enc,
            'payload': base64.b64encode(layer1_payload).decode('utf-8')
        }

        # Logging - show actual relay order and fingerprints
        for i, relay in enumerate(relays):
            pubkey_obj = deserialize_public_key(relay['public_key'].encode())
            print(f"[Client] [DEBUG] Layer {i+1} relay: {relay['ip']}:{relay['port']} fingerprint: {hashlib.sha256(relay['public_key'].encode()).hexdigest()}")
        print(f"[Client] [DEBUG] Session keys (hex): {[k.hex() for k in [K1, K2, K3]]}")
        print(f"[Client] [DEBUG] Onion message session_key field (base64): {onion_msg['session_key']}")
        return onion_msg, [K1, K2, K3], relays

    def send_onion(self, onion_msg, relays, keys):
        import socket
        import base64
        import json
        print(f"[Client] [DEBUG] Onion message: {onion_msg}")
        # Send to first relay
        first_ip = onion_msg['next_ip']
        first_port = onion_msg['next_port']
        session_key = onion_msg['session_key']
        payload = onion_msg['payload']
        # Compose top-level JSON, send as bytes
        top_json = json.dumps(onion_msg).encode('utf-8')
        print(f"[Client] [DEBUG] Sending to first relay {first_ip}:{first_port}, len={len(top_json)}, type={type(top_json)}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((first_ip, first_port))
            s.sendall(top_json)
            data = s.recv(65536)
        print(f"[Client] [DEBUG] Received response from first relay: type={type(data)}, len={len(data)}, preview={repr(data)[:60]}")
        # Always base64-decode the response before decryption
        try:
            data = base64.b64decode(data)
        except Exception as e:
            print(f"[Client] [ERROR] Could not base64-decode response: {e}")
            print(f"[Client] Raw response: {repr(data)[:120]}")
            return
        print(f"[Client] [DEBUG] Received base64-decoded response: type={type(data)}, len={len(data)}, preview={repr(data)[:60]}")
        # Decrypt response through all layers (do NOT reverse session_keys)
        response_layer = data
        for i, session_key in enumerate(keys):
            print(f"[Client] [DEBUG] Before aes_decrypt at layer {i}: type={type(response_layer)}, len={len(response_layer)}, preview='{repr(response_layer)[:60]}'")
            response_layer = aes_decrypt(session_key, response_layer)
            print(f"[Client] [DEBUG] After decrypt at layer {i}: type={type(response_layer)}, len={len(response_layer)}, preview={repr(response_layer)[:60]}")
            print(f"[Client] [DEBUG] After decrypt at layer {i} (hex): {response_layer.hex()[:60]}")
            print(f"[Client] [DEBUG] Passed raw bytes to next decryption at layer {i}, type={type(response_layer)}, len={len(response_layer)}")
        print(f"[Client] [DEBUG] Final decrypted bytes: {repr(response_layer)}, len={len(response_layer)}")
        print(f"[Client] [DEBUG] Final decrypted bytes (hex): {response_layer.hex()}")
        try:
            decoded = response_layer.decode('utf-8')
            print(f"[Client] [DEBUG] Final decoded response: {decoded}")
            print(f"[Client] [DEBUG] Final JSON: {json.loads(decoded)}")
        except Exception as e:
            print(f"[Client] [ERROR] Final layer not UTF-8 decodable: {e}")
            print(f"[Client] [DEBUG] Final raw bytes repr: {repr(response_layer)}")
            print(f"[Client] [DEBUG] Final raw bytes (hex): {response_layer.hex()}")

    def run(self):
        relays = self.get_relays_from_cds()
        onion_msg, keys, relays = self.build_onion(relays)
        self.send_onion(onion_msg, relays, keys)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python client.py <dest_ip> <dest_port> <message>")
        sys.exit(1)
    dest_ip = sys.argv[1]
    dest_port = int(sys.argv[2])
    message = sys.argv[3]
    client = Client(dest_ip, dest_port, message)
    client.run()
