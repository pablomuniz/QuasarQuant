#!/usr/bin/env python3
"""
TUI Socket Listener for the pytest plugin.

This is a simple demonstration of how the TUI can listen for test events
from our pytest plugin via a Unix domain socket.

In a real implementation, this would be integrated into the Textual TUI app.
"""
import socket
import os
import json
import threading
import sys
import time

SOCKET_PATH = "/tmp/pytest_tui.sock"

class TUISocketListener:
    """Socket listener for receiving test events from pytest."""
    
    def __init__(self):
        self.socket_path = SOCKET_PATH
        self.running = False
        self.connection = None
        self.test_data = {}
        self.session_data = {
            "test_count": 0,
            "tests_completed": 0,
            "tests_passed": 0,
            "tests_failed": 0
        }
        
        # Set up the socket
        self._setup_socket()
    
    def _setup_socket(self):
        """Set up the Unix domain socket."""
        # Make sure the socket doesn't already exist
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Create the socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.socket_path)
        print(f"Socket created at {self.socket_path}")
        
        # Set socket permissions so pytest can connect
        os.chmod(self.socket_path, 0o777)
        print("Socket permissions set")
    
    def start(self):
        """Start listening for connections."""
        self.running = True
        self.sock.listen(1)
        print("Listening for connections...")
        
        # Start listening in a separate thread
        self.listener_thread = threading.Thread(target=self._listen_for_connections)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def _listen_for_connections(self):
        """Listen for connections from pytest."""
        while self.running:
            try:
                # Wait for a connection with a timeout
                self.sock.settimeout(1.0)
                try:
                    conn, _ = self.sock.accept()
                    print("Connection established!")
                    self.connection = conn
                    
                    # Start processing messages
                    self._process_messages()
                except socket.timeout:
                    # Just a timeout, continue polling
                    continue
            except Exception as e:
                print(f"Error accepting connection: {e}")
                time.sleep(1)
    
    def _process_messages(self):
        """Process messages from the connection."""
        buffer = ""
        self.connection.settimeout(None)  # No timeout for receiving
        
        while self.running and self.connection:
            try:
                # Receive data
                data = self.connection.recv(4096)
                if not data:
                    # Connection closed
                    print("Connection closed by pytest")
                    self.connection = None
                    break
                
                # Add to buffer and process complete messages
                buffer += data.decode('utf-8')
                
                # Process any complete messages (delimited by newlines)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self._handle_message(message)
            
            except Exception as e:
                print(f"Error processing messages: {e}")
                self.connection = None
                break
    
    def _handle_message(self, message_json):
        """Handle a message from pytest."""
        try:
            message = json.loads(message_json)
            message_type = message.get("type", "")
            data = message.get("data", {})
            
            # Handle different message types
            if message_type == "session_start":
                self._handle_session_start(data)
            elif message_type == "test_start":
                self._handle_test_start(data)
            elif message_type == "test_inputs":
                self._handle_test_inputs(data)
            elif message_type == "test_outputs":
                self._handle_test_outputs(data)
            elif message_type == "test_result":
                self._handle_test_result(data)
            elif message_type == "session_end":
                self._handle_session_end(data)
            
        except json.JSONDecodeError:
            print(f"Error decoding message: {message_json}")
        except Exception as e:
            print(f"Error handling message: {e}")
    
    def _handle_session_start(self, data):
        """Handle session start message."""
        self.session_data["test_count"] = data.get("test_count", 0)
        print(f"Test session started. Total tests: {self.session_data['test_count']}")
        print("Simulating compilation...")
        time.sleep(2)  # Just for demonstration
        print("Compilation complete.")
    
    def _handle_test_start(self, data):
        """Handle test start message."""
        test_id = data.get("id", "")
        description = data.get("description", "")
        
        # Store test data
        self.test_data[test_id] = {
            "id": test_id,
            "description": description,
            "inputs": {},
            "cpp_output": "",
            "mojo_output": "",
            "status": "running"
        }
        
        print(f"\nTest started: {test_id} - {description}")
    
    def _handle_test_inputs(self, data):
        """Handle test inputs message."""
        test_id = data.get("id", "")
        inputs = data.get("inputs", {})
        
        if test_id in self.test_data:
            self.test_data[test_id]["inputs"] = inputs
            
            # Print inputs
            print("Inputs:")
            for name, value in inputs.items():
                print(f"  {name}: {value}")
    
    def _handle_test_outputs(self, data):
        """Handle test outputs message."""
        test_id = data.get("id", "")
        cpp_output = data.get("cpp_output", "")
        mojo_output = data.get("mojo_output", "")
        
        if test_id in self.test_data:
            self.test_data[test_id]["cpp_output"] = cpp_output
            self.test_data[test_id]["mojo_output"] = mojo_output
            
            # Print outputs
            print("Outputs:")
            print(f"  C++: {cpp_output}")
            print(f"  Mojo: {mojo_output}")
    
    def _handle_test_result(self, data):
        """Handle test result message."""
        test_id = data.get("id", "")
        status = data.get("status", "")
        
        if test_id in self.test_data:
            self.test_data[test_id]["status"] = status
            
            # Update session data
            self.session_data["tests_completed"] += 1
            if status == "PASS":
                self.session_data["tests_passed"] += 1
                print(f"✅ Test PASSED: {test_id}")
            else:
                self.session_data["tests_failed"] += 1
                reason = data.get("reason", "")
                diff = data.get("diff", "")
                print(f"❌ Test FAILED: {test_id}")
                print(f"  Reason: {reason}")
                if diff:
                    print(f"  Diff: {diff}")
    
    def _handle_session_end(self, data):
        """Handle session end message."""
        total = data.get("total", 0)
        passed = data.get("passed", 0)
        failed = data.get("failed", 0)
        duration = data.get("duration", 0)
        
        print("\n--- Test Session Summary ---")
        print(f"Total tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Duration: {duration:.1f}s")
        print("---------------------------")
    
    def stop(self):
        """Stop the listener."""
        self.running = False
        
        # Close the socket
        if hasattr(self, "sock"):
            self.sock.close()
        
        # Remove the socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        print("Listener stopped.")

def main():
    """Main function."""
    print("Starting TUI Socket Listener...")
    listener = TUISocketListener()
    listener.start()
    
    try:
        # Keep running until Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping listener...")
    finally:
        listener.stop()

if __name__ == "__main__":
    main() 