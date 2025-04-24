import grpc
from concurrent import futures
import tor_pb2
import tor_pb2_grpc
import threading
import time
import random

class DirectoryServerServicer(tor_pb2_grpc.DirectoryServerServicer):
    
    def __init__(self):
        super().__init__()
        self.nodes = []
        
        # periodically ping relay nodes to check if they are still alive
        threading.Thread(target=self.RelayPing, daemon=True).start()
        
        
    def GetRelayNodes(self, request, context):
        
        if len(self.nodes) < 3:
            print("Warning: less than 3 relays registered; returning all nodes.")
            selected = list(self.nodes)
        else:
            selected = random.sample(self.nodes, 3)
        print(f"Selected relays: {[node.address for node in selected]}")
        return tor_pb2.GetRelayNodesResponse(relay_nodes=selected)
    
    def RelayRegister(self, request, context):
        new_node = tor_pb2.RelayNode(address=request.address, node_type=request.node_type)
        self.nodes.append(new_node)
        print(f"Registered relay: {new_node.address}, type: {new_node.node_type}")
        return tor_pb2.Empty()

    def RelayPing(self):

        # Periodically ping all nodes in the list
        while True:
            time.sleep(10)  # Sleep for a bit (10 seconds)
            alive_nodes = []
            for node in self.nodes:
                # Create a channel and stub to communicate with the relay node
                channel = grpc.insecure_channel(node.address)
                stub = tor_pb2_grpc.RelayStub(channel)

                # Send a Ping message to the relay node
                try:
                    stub.Ping(tor_pb2.Empty())
                    alive_nodes.append(node)
                except grpc.RpcError as e:
                    print(f"Node {node.address} is not responding: {e}")

            self.nodes = alive_nodes  # Update the list of alive nodes

            
        
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    tor_pb2_grpc.add_DirectoryServerServicer_to_server(
        DirectoryServerServicer(), server)
    server.add_insecure_port("localhost:50051")
    # get address at port 50051
    import socket
    
    print("Starting directory server on localhost:50051")
    server.start()
    server.wait_for_termination()



if __name__ == "__main__":
    serve()
