import socketserver
import argparse

class EchoRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(4096)
        print(f"[Destination] Received: {data}")
        # Echo back the received data
        self.request.sendall(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Destination Echo Server")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    args = parser.parse_args()
    server_address = ('', args.port)
    with socketserver.TCPServer(server_address, EchoRequestHandler) as server:
        print(f"Destination server listening on port {args.port}")
        server.serve_forever()
