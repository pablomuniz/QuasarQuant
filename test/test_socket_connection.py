"""
Test script to verify socket connections between pytest and TUI.

This script will:
1. Try to import the pytest_tui_plugin
2. Try to connect to the TUI socket
3. Send test messages to verify communication

Run this script with: python test_socket_connection.py
"""
import sys
import os
import socket
import time
import json
from pathlib import Path
import importlib.util

# Resolve the script directory
SCRIPT_DIR = Path(__file__).parent.resolve()

def log(message):
    """Log message to stderr."""
    print(f"[SOCKET_TEST] {message}", file=sys.stderr)
    sys.stderr.flush()

def test_import_plugin():
    """Test if the plugin can be imported."""
    log("Testing plugin import...")
    
    plugin_path = SCRIPT_DIR / "pytest_tui_plugin.py"
    if not plugin_path.exists():
        log(f"ERROR: Plugin file not found at {plugin_path}")
        return False
        
    try:
        # Try to import the plugin module
        spec = importlib.util.spec_from_file_location("pytest_tui_plugin", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        log("Plugin imported successfully")
        if hasattr(module, "TUIReportPlugin"):
            log("TUIReportPlugin class found in module")
            return True
        else:
            log("ERROR: TUIReportPlugin class not found in module")
            return False
    except Exception as e:
        log(f"ERROR importing plugin: {type(e).__name__}: {e}")
        return False

def test_socket_connections():
    """Test connecting to various socket addresses."""
    log("Testing socket connections...")
    
    hosts_to_try = [
        "127.0.0.1",
        "localhost",
        "0.0.0.0",
    ]
    
    port = 43567
    results = {}
    
    for host in hosts_to_try:
        log(f"Trying to connect to {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        try:
            start = time.time()
            sock.connect((host, port))
            elapsed = time.time() - start
            
            # Try sending a test message
            test_msg = {
                "type": "test_connection",
                "timestamp": time.time(),
                "data": {"message": "Hello from test_socket_connection.py"}
            }
            
            sock.sendall(json.dumps(test_msg).encode() + b"\n")
            log(f"Successfully connected to {host}:{port} in {elapsed:.3f}s and sent test message")
            results[host] = "SUCCESS"
            
            # Leave connection open briefly to allow for response
            time.sleep(0.5)
            
        except socket.timeout:
            log(f"Connection to {host}:{port} timed out")
            results[host] = "TIMEOUT"
        except ConnectionRefusedError:
            log(f"Connection to {host}:{port} refused")
            results[host] = "REFUSED"
        except Exception as e:
            log(f"Error connecting to {host}:{port}: {type(e).__name__}: {e}")
            results[host] = f"ERROR: {type(e).__name__}"
        finally:
            sock.close()
    
    # Print summary
    log("Socket connection test results:")
    for host, result in results.items():
        log(f"  {host}: {result}")
    
    return any(result == "SUCCESS" for result in results.values())

def check_port_listening():
    """Check if the port is already being listened to."""
    log("Checking if port 43567 is already in use...")
    
    try:
        # Try to create a socket that listens on the port
        # If this succeeds, the port is free
        # If it fails with Address already in use, the port is in use
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_sock.settimeout(1)
        
        # Try binding to localhost
        try:
            test_sock.bind(('127.0.0.1', 43567))
            log("Port 43567 is NOT in use on 127.0.0.1 - this may indicate the TUI server isn't running")
            # Close and try another address
            test_sock.close()
            
            # Try 0.0.0.0 as well
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.settimeout(1)
            try:
                test_sock.bind(('0.0.0.0', 43567))
                log("Port 43567 is NOT in use on 0.0.0.0 - this may indicate the TUI server isn't running")
            except socket.error as e:
                if "Address already in use" in str(e):
                    log("Port 43567 is already in use on 0.0.0.0 - TUI server may be running")
                    return True
                else:
                    log(f"Error checking 0.0.0.0:43567: {e}")
        except socket.error as e:
            if "Address already in use" in str(e):
                log("Port 43567 is already in use on 127.0.0.1 - TUI server may be running")
                return True
            else:
                log(f"Error checking 127.0.0.1:43567: {e}")
    finally:
        try:
            test_sock.close()
        except:
            pass
    
    # Try to use netstat if available
    try:
        log("Checking open ports with netstat...")
        import subprocess
        netstat_output = subprocess.check_output(["netstat", "-tuln"], universal_newlines=True)
        log("Netstat output:")
        for line in netstat_output.splitlines():
            if "43567" in line:
                log(f"  Found port 43567: {line}")
                return True
    except Exception as e:
        log(f"Error running netstat: {e}")
    
    return False

def main():
    """Run all tests."""
    log("Starting socket connection tests")
    
    # First check if port is already listening
    port_listening = check_port_listening()
    
    import_result = test_import_plugin()
    socket_result = test_socket_connections()
    
    log("Test Summary:")
    log(f"  Port 43567 listening: {'YES' if port_listening else 'NO'}")
    log(f"  Plugin import: {'SUCCESS' if import_result else 'FAILED'}")
    log(f"  Socket connection: {'SUCCESS' if socket_result else 'FAILED'}")
    
    if import_result and socket_result:
        log("All tests PASSED")
        return 0
    else:
        log("Some tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 