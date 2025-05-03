#!/usr/bin/env python3
import os
import subprocess
import sys

def main():
    """Generate the gRPC Python code from the proto file."""
    # Get the project root directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the proto file
    proto_file = os.path.join(current_dir, 'network', 'protos', 'onion_network.proto')
    
    # Output directory
    output_dir = os.path.join(current_dir, 'network', 'protos')
    
    # Make sure the proto file exists
    if not os.path.exists(proto_file):
        print(f"Error: Proto file not found at {proto_file}")
        return 1
    
    # Make sure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate the Python code
    print(f"Generating Python code from {proto_file}...")
    try:
        # Run the protoc compiler to generate both _pb2.py and _pb2_grpc.py files
        subprocess.check_call([
            'python', '-m', 'grpc_tools.protoc',
            '-I', os.path.dirname(proto_file),
            f'--python_out={output_dir}',
            f'--grpc_python_out={output_dir}',
            proto_file
        ])
        
        # Fix the import paths in the generated files
        pb2_grpc_file = os.path.join(output_dir, 'onion_network_pb2_grpc.py')
        
        # Read the content of the file
        with open(pb2_grpc_file, 'r') as f:
            content = f.read()
        
        # Replace the incorrect import
        content = content.replace(
            "import onion_network_pb2 as onion__network__pb2", 
            "from . import onion_network_pb2 as onion__network__pb2"
        )
        
        # Write the modified content back to the file
        with open(pb2_grpc_file, 'w') as f:
            f.write(content)
        
        print("Python code generated successfully and import paths fixed.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error generating Python code: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
