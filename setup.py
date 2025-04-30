#!/usr/bin/env python3
"""
Setup script for the onion network project.
Installs dependencies and generates protocol buffer files.
"""

import os
import sys
import subprocess
import argparse
import platform


def check_python_version():
    """
    Check if the Python version is compatible.
    
    Returns:
        bool: True if compatible, False otherwise.
    """
    min_version = (3, 7)
    current_version = sys.version_info[:2]
    
    if current_version < min_version:
        print(f"Error: Python {min_version[0]}.{min_version[1]} or higher is required.")
        print(f"Current version: {current_version[0]}.{current_version[1]}")
        return False
    
    return True


def install_dependencies(binary_only=False, force=False):
    """
    Install dependencies using pip.
    
    Args:
        binary_only (bool, optional): Whether to use binary-only packages.
        force (bool, optional): Whether to force reinstallation.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    # Check if pip is available
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"])
    except subprocess.CalledProcessError:
        print("Error: pip is not available.")
        return False
    
    print("Installing dependencies...")
    
    # Base command
    cmd = [sys.executable, "-m", "pip", "install"]
    
    if force:
        cmd.append("--force-reinstall")
    
    if binary_only:
        # Use binary-only packages
        cmd.extend([
            "--only-binary=:all:", "grpcio",
            "--only-binary=:all:", "grpcio-tools",
            "protobuf",
            "requests",
            "cryptography",
            "psutil"
        ])
    else:
        # Use requirements.txt
        cmd.extend(["-r", "requirements.txt"])
    
    try:
        subprocess.check_call(cmd)
        print("Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False


def generate_proto_files():
    """
    Generate Python files from the Protocol Buffer definition.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    print("Generating protocol buffer files...")
    
    # Check if the proto file exists
    proto_file = os.path.join("network", "protos", "onion_network.proto")
    if not os.path.exists(proto_file):
        print(f"Error: Protocol buffer file not found at {proto_file}")
        return False
    
    # Output directory
    output_dir = os.path.join("network", "protos")
    
    # Make sure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate the Python code
    try:
        # Run the protoc compiler to generate both _pb2.py and _pb2_grpc.py files
        subprocess.check_call([
            sys.executable, "-m", "grpc_tools.protoc",
            "-I", os.path.dirname(proto_file),
            f"--python_out={output_dir}",
            f"--grpc_python_out={output_dir}",
            proto_file
        ])
        
        # Fix the import paths in the generated files
        pb2_grpc_file = os.path.join(output_dir, "onion_network_pb2_grpc.py")
        
        # Read the content of the file
        with open(pb2_grpc_file, "r") as f:
            content = f.read()
        
        # Replace the incorrect import
        content = content.replace(
            "import onion_network_pb2 as onion__network__pb2", 
            "from . import onion_network_pb2 as onion__network__pb2"
        )
        
        # Write the modified content back to the file
        with open(pb2_grpc_file, "w") as f:
            f.write(content)
        
        print("Protocol buffer files generated successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating protocol buffer files: {e}")
        return False
    except FileNotFoundError:
        print("Error: grpc_tools.protoc module not found. Make sure grpcio-tools is installed.")
        return False


def create_directories():
    """
    Create necessary directories for the project.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    print("Creating necessary directories...")
    
    # List of directories to create
    directories = [
        "core",
        "network",
        "network/protos",
        "cli",
        "monitoring",
        "scripts",
        "logs",
        "docs"
    ]
    
    try:
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        print("Directories created successfully.")
        return True
    except OSError as e:
        print(f"Error creating directories: {e}")
        return False


def create_init_files():
    """
    Create __init__.py files in each directory.
    
    Returns:
        bool: True if successful, False otherwise.
    """
    print("Creating __init__.py files...")
    
    # List of directories for init files
    directories = [
        "core",
        "network",
        "network/protos",
        "cli",
        "monitoring",
        "scripts"
    ]
    
    try:
        for directory in directories:
            init_file = os.path.join(directory, "__init__.py")
            
            # Create the file if it doesn't exist
            if not os.path.exists(init_file):
                with open(init_file, "w") as f:
                    f.write(f"# {directory} package\n")
        
        print("__init__.py files created successfully.")
        return True
    except OSError as e:
        print(f"Error creating __init__.py files: {e}")
        return False


def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Setup the onion network project.")
    parser.add_argument("--binary-only", action="store_true", help="Use binary-only packages")
    parser.add_argument("--force", action="store_true", help="Force reinstallation of dependencies")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--skip-proto", action="store_true", help="Skip protocol buffer generation")
    
    args = parser.parse_args()
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Create necessary directories
    if not create_directories():
        return 1
    
    # Create __init__.py files
    if not create_init_files():
        return 1
    
    # Install dependencies
    if not args.skip_deps:
        if not install_dependencies(args.binary_only, args.force):
            print("Tip: If you're having issues with the grpcio installation, try using the --binary-only option.")
            return 1
    
    # Generate protocol buffer files
    if not args.skip_proto:
        if not generate_proto_files():
            return 1
    
    print("\nSetup completed successfully!")
    print("\nTo test the onion network:")
    print("1. Run the test script:")
    print("   python scripts/test_onion_network.py")
    print("\nOr to run components individually:")
    print("1. Start the registry service:")
    print("   python scripts/run_registry.py")
    print("2. Start router nodes:")
    print("   python scripts/run_router.py --port 5051 --type 1  # Entry node")
    print("   python scripts/run_router.py --port 5052 --type 2  # Middle node")
    print("   python scripts/run_router.py --port 5053 --type 3  # Exit node")
    print("3. Start the terminus client:")
    print("   python scripts/run_terminus.py")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())