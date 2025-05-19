import asyncio
from pathlib import Path
import os
import sys # Added for sys.stdout.flush()
import traceback # Added for full traceback logging
import subprocess # For pytest execution
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import time

from rich.text import Text
from rich.columns import Columns
# from rich.panel import Panel as RichPanel # Import and alias RichPanel - REVERTED
from rich.table import Table # Import Table
import rich.box as box # Import for box styles

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Static, DataTable, Button, RichLog, ProgressBar # Added ProgressBar
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widget import Widget
from textual.message import Message
from textual.reactive import reactive
from textual.worker import Worker
from textual.screen import Screen # Added Screen

# Import socket-related modules
import socket
import json
import threading

# Helper for simple logging to a file for debugging Textual apps
def debug_log(message: str):
    with open("textual_debug.log", "a") as f:
        f.write(f"{message}\n")

@dataclass
class ParsedTestItem:
    test_item_id: str = ""
    description: str = ""
    overall_status: str = "" # "PASS" or "FAIL"
    fail_reason: str = ""
    shared_inputs: List[str] = field(default_factory=list)
    cpp_stdout: List[str] = field(default_factory=list)
    mojo_stdout: List[str] = field(default_factory=list)
    diffs: List[str] = field(default_factory=list) # Added for DIFF output
    detailed_diffs: List[str] = field(default_factory=list)  # Added for detailed diffs

def parse_test_script_output(raw_output: str) -> tuple[str, List[ParsedTestItem]]:
    preamble_lines: List[str] = []
    items: List[ParsedTestItem] = []
    current_item: ParsedTestItem | None = None
    capturing_shared_input = False
    capturing_cpp_stdout = False
    capturing_mojo_stdout = False
    found_first_test_item = False
    
    debug_log(f"Parsing output length: {len(raw_output)} characters")

    for line in raw_output.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("TEST_ITEM_ID:"):
            found_first_test_item = True
            if current_item:
                items.append(current_item)
            
            # Extract the ID part properly
            full_id = stripped_line.split(":", 1)[1].strip()
            
            # Handle the pytest parametrized format: function[actual-id]
            if "[" in full_id and "]" in full_id:
                # Extract the part in square brackets, which is the actual test ID
                test_id = full_id[full_id.find("[")+1:full_id.find("]")]
            else:
                test_id = full_id
                
            current_item = ParsedTestItem(test_item_id=test_id)
            capturing_shared_input = False
            capturing_cpp_stdout = False
            capturing_mojo_stdout = False
            debug_log(f"Found test item: {test_id}")
        elif not found_first_test_item:
            preamble_lines.append(line) # Collect lines as preamble until the first test item
        elif current_item: # This implies found_first_test_item is True
            if stripped_line.startswith("DESCRIPTION:"):
                current_item.description = stripped_line.split(":", 1)[1].strip()
            elif stripped_line.startswith("OVERALL_STATUS:"):
                current_item.overall_status = stripped_line.split(":", 1)[1].strip().upper()
            elif stripped_line.startswith("FAIL_REASON:"):
                current_item.fail_reason = stripped_line.split(":", 1)[1].strip()
            elif stripped_line.startswith("DIFF:"):
                current_item.diffs.append(stripped_line.split(":", 1)[1].strip()) # Capture DIFF
            elif stripped_line == "SHARED_INPUT_BEGIN":
                capturing_shared_input = True
                debug_log(f"Starting to capture inputs for {current_item.test_item_id}")
            elif stripped_line == "SHARED_INPUT_END":
                capturing_shared_input = False
                debug_log(f"Finished capturing inputs for {current_item.test_item_id}, captured {len(current_item.shared_inputs)} lines")
            elif stripped_line == "CPP_STDOUT_BEGIN":
                capturing_cpp_stdout = True
            elif stripped_line == "CPP_STDOUT_END":
                capturing_cpp_stdout = False
            elif stripped_line == "MOJO_STDOUT_BEGIN":
                capturing_mojo_stdout = True
            elif stripped_line == "MOJO_STDOUT_END":
                capturing_mojo_stdout = False
            elif capturing_shared_input:
                if stripped_line: # Skip empty lines
                    current_item.shared_inputs.append(line)
                    debug_log(f"Added input line for {current_item.test_item_id}: {line}")
            elif capturing_cpp_stdout:
                if line.startswith("OUTPUT: "):
                    current_item.cpp_stdout.append(line.split("OUTPUT: ", 1)[1])
            elif capturing_mojo_stdout:
                if line.startswith("OUTPUT: "):
                    current_item.mojo_stdout.append(line.split("OUTPUT: ", 1)[1])
    
    if current_item: # Append the last item
        items.append(current_item)
    
    debug_log(f"Parsed {len(items)} test items")
    preamble_str = "\n".join(preamble_lines)
    return preamble_str, items

# Determine the project root based on this script's location
# Assuming this script is in quantfork/test/
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "..").resolve()
QL_DIR = PROJECT_ROOT / "ql"

# Check if we're running in Docker (the /app prefix is typically used in Docker)
IS_DOCKER = str(SCRIPT_DIR).startswith("/app/")
debug_log(f"Running in Docker: {IS_DOCKER}")
debug_log(f"Script dir: {SCRIPT_DIR}, Project root: {PROJECT_ROOT}, QL dir: {QL_DIR}")

class TestResult:
    def __init__(self):
        self.test_item_id = ""
        self.description = ""
        self.overall_status = ""
        self.fail_reason = ""
        self.cpp_exit_code = ""
        self.cpp_stdout = ""
        self.cpp_stderr = ""
        self.mojo_exit_code = ""
        self.mojo_stdout = ""
        self.mojo_stderr = ""
        self.diff_output = ""

class TestExplorer(Widget):
    class TestSelected(Message):
        def __init__(self, script_path: str) -> None:
            self.script_path = script_path
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Tree("Tests", id="test-tree")

    def on_mount(self) -> None:
        """Populate the tree with test data when the widget is mounted."""
        self.discover_and_populate_tests()
        self.query_one(Tree).focus()
        self.selected_node = None

    def discover_tests(self) -> dict[str, list[Path]]:
        """Discovers test categories and their corresponding test scripts."""
        debug_log("Discovering tests...")
        categories = {}
        if not QL_DIR.is_dir():
            debug_log(f"QL directory not found: {QL_DIR}")
            return categories

        for category_dir in QL_DIR.iterdir():
            if category_dir.is_dir():
                category_name = category_dir.name
                category_tests = []
                
                tests_subdir = category_dir / "tests"
                if tests_subdir.is_dir():
                    for item in tests_subdir.rglob("*"):
                        if item.is_file():
                            # Only include Python files that end with "test.py"
                            if item.name.endswith("test.py"):
                                if item not in category_tests:
                                    category_tests.append(item)
                
                if category_tests:
                    categories[category_name] = sorted(category_tests)
        
        debug_log(f"Test discovery complete. Categories found: {len(categories)}")
        return categories

    def discover_and_populate_tests(self) -> None:
        """Discovers tests and populates the tree widget."""
        tree = self.query_one(Tree)
        tree.clear()
        tree.root.expand()

        test_data = self.discover_tests()

        if not test_data:
            tree.root.add_leaf("No tests found.")
            return

        for category_name, test_scripts in test_data.items():
            category_node = tree.root.add(category_name, data={"type": "category", "name": category_name})
            for script_path in test_scripts:
                # Use script_path.stem to display name without extension
                category_node.add_leaf(script_path.stem, data={"type": "script", "path": str(script_path)})
        
        # debug_log("Tree populated.") # Removed

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle selection of a tree node."""
        node = event.node
        
        # We can't use add_class/remove_class on TreeNode objects
        # Just rely on the built-in selection highlighting
        
        # Add highlighting to the selected node if it's a script
        if node.data and node.data.get("type") == "script":
            self.selected_node = node
            script_path = node.data["path"]
            debug_log(f"TestExplorer: Script selected: {Path(script_path).name}")
            
            # Safely access app and call method directly
            try:
                app = self.app
                if app:
                    # Corrected log message to match the actual call
                    # debug_log(f"TestExplorer: Attempting to call app.test_selected_handler for {script_path}") # Removed
                    app.test_selected_handler(script_path)
                    # debug_log(f"TestExplorer: Successfully called app.test_selected_handler for {script_path}") # Removed
                else:
                    debug_log("TestExplorer: CRITICAL - Could not access app object")
                    # If app is not available here, we can't show a dialog through it.
                    # Fallback to old behavior of printing and raising, but log this specific issue.
                    print("CRITICAL: TestExplorer could not access self.app to show an error dialog.")
                    sys.stdout.flush()
                    # We might still want to raise e here, or a custom error, so the app might still crash hard.
                    # For now, let's log to critical_error.log if possible and then raise.
                    try:
                        with open("critical_error.log", "a") as err_file: # Append mode
                            err_file.write("TestExplorer: Could not access self.app to show dialog. Original error: " + str(e) + "\n")
                    except Exception:
                        pass # Avoid error in error handler
                    raise e # Re-raise the original error that led to this path

            except Exception as e:
                error_message = f"Critical error during test selection or worker initiation: {type(e).__name__}: {str(e)}"
                debug_log(f"TestExplorer: {error_message}")  # Log to main debug log

                # Attempt to write to a separate critical error file (append mode)
                try:
                    with open("critical_error.log", "a") as err_file: # Append mode
                        err_file.write(error_message + "\n")
                        err_file.write("--- End of Critical Error Log Entry ---\n")
                except Exception as ef_write:
                    debug_log(f"TestExplorer: FAILED TO WRITE TO critical_error.log: {type(ef_write).__name__}: {str(ef_write)}")

                # Show the error in a dialog via the app
                if self.app and hasattr(self.app, 'show_critical_error'):
                    self.app.show_critical_error("Error During Test Selection", error_message)
                else:
                    # Fallback if app or method isn't available
                    print(f"--- PYTHON STDOUT START (Fallback) ---")
                    print("CRITICAL: Could not display error dialog. Error was:")
                    print(error_message)
                    print(f"--- PYTHON STDOUT END (Fallback) ---")
                    sys.stdout.flush()
                    # Optionally, re-raise e here if we want the app to crash hard if dialog fails
                    # raise e

class TestOutputPanel(Widget):
    def __init__(self, *, id: str | None = None, classes: str | None = None, name: str | None = None):
        """Initialize the TestOutputPanel widget.
        
        Args:
            id: The ID of the widget.
            classes: The CSS classes of the widget.
            name: The name of the widget.
        """
        super().__init__(id=id, classes=classes, name=name)
        # State tracking for real-time test processing
        self.current_test_id = None
        self.current_test_description = None
        self.collected_data = {}
        self.show_live_output = False  # Flag to control live output display
        self.has_streamed_output = False  # Flag to track if we've already shown output
        self.socket_data_received = False # Flag to track if data came via socket
        
        # Socket-related attributes
        # Changed from Unix socket to TCP
        self.host = '0.0.0.0'  # Listen on all interfaces
        self.port = 43567       # Choose a port that's unlikely to be in use
        self.socket = None
        self.connection = None
        self.socket_thread = None
        self.running = False

    def compose(self) -> ComposeResult:
        """Create the output panel components with a RichLog for all output."""
        yield RichLog(id="output-log", wrap=True, highlight=True, markup=True)
        yield ProgressBar(id="test-progress-bar", total=100)
        
    def on_mount(self) -> None:
        """Initialize the output panel when it's mounted."""
        self.query_one("#test-progress-bar").visible = False
        debug_log("TestOutputPanel mounted with RichLog for output.")
        
        # Start socket listener
        self.start_socket_listener()

    def start_socket_listener(self) -> None:
        """Start the socket listener for pytest messages."""
        try:
            # For TCP sockets, we don't need to create directories or clean up files
            # Create and bind the socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow socket reuse to avoid "address already in use" errors on restart
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            debug_log(f"TestOutputPanel: TCP Socket created. Attempting to bind to {self.host}:{self.port}...")
            self.socket.bind((self.host, self.port))
            debug_log(f"TestOutputPanel: TCP Socket successfully bound to {self.host}:{self.port}.")
            
            # Start listening in a separate thread
            self.running = True
            self.socket.listen(5) # Increased backlog from 1 to 5
            debug_log(f"TestOutputPanel: TCP Socket is now listening on {self.host}:{self.port} with backlog 5.")
            self.socket_thread = threading.Thread(target=self._socket_listener_thread, daemon=True)
            self.socket_thread.start()
            
            debug_log(f"TestOutputPanel: TCP Socket listener thread started for {self.host}:{self.port}.")
        except Exception as e:
            debug_log(f"TestOutputPanel: CRITICAL FAILURE in start_socket_listener for {self.host}:{self.port}: {type(e).__name__}: {e}")
            # Socket setup failed, will rely on stdout parsing

    def _socket_listener_thread(self) -> None:
        """Background thread for listening to socket connections."""
        debug_log("TestOutputPanel: Listener thread started.")
        while self.running:
            try:
                if not self.socket:
                    debug_log("TestOutputPanel: Listener thread: server socket is None, stopping.")
                    break
                
                self.socket.settimeout(1.0) 
                
                # debug_log("TestOutputPanel: Listener thread: waiting for connection...") # Too noisy
                conn, addr = self.socket.accept()
                # debug_log(f"TestOutputPanel: Listener thread: connection accepted from {addr}") # Too noisy

                if not self.running: 
                    debug_log("TestOutputPanel: Listener thread: self.running became false after accept, closing client connection and exiting.")
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except Exception: pass
                    try:
                        conn.close()
                    except Exception: pass
                    break 

                self.connection = conn
                
                # Log socket details if needed for specific debugging, but generally too verbose.
                # try:
                #     local_addr = conn.getsockname()
                #     remote_addr = conn.getpeername()
                #     debug_log(f"TestOutputPanel: Socket details - Local: {local_addr}, Remote: {remote_addr}")
                # except Exception as sock_err:
                #     debug_log(f"TestOutputPanel: Error getting socket details: {sock_err}")
                    
                self._process_socket_messages()

                # After _process_socket_messages, ensure client connection is closed and cleared
                if self.connection:
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except Exception: pass # Ignore errors if already closed
                    try:
                        self.connection.close()
                    except Exception: pass # Ignore errors if already closed
                self.connection = None

            except socket.timeout:
                # Expected timeout from self.socket.accept(), allows loop to check self.running.
                # debug_log("TestOutputPanel: Listener thread: accept timeout.") # Too noisy
                continue 
            except Exception as e:
                if not self.running:
                    debug_log(f"TestOutputPanel: Listener thread: Exception ({type(e).__name__}: {e}) during shutdown. Thread exiting.")
                else:
                    debug_log(f"TestOutputPanel: Listener thread: Unexpected error ({type(e).__name__}: {e}).")
                    time.sleep(0.1) # Small delay for unexpected errors while running
                # Loop continues, will terminate if self.running is false.
        debug_log("TestOutputPanel: Listener thread finished.")
    
    def _process_socket_messages(self) -> None:
        """Process messages from a connected pytest plugin."""
        buffer = ""
        if not self.connection:
            debug_log("TestOutputPanel: _process_socket_messages: called with no active connection.")
            return

        self.connection.settimeout(1.0) # Use a timeout to periodically check self.running

        # debug_log("TestOutputPanel: _process_socket_messages: Starting to process messages.") # Too noisy
        while self.running and self.connection:
            try:
                data_bytes = self.connection.recv(4096)
                if not data_bytes:
                    debug_log("TestOutputPanel: _process_socket_messages: Connection closed by client (recv returned empty).")
                    break 
                
                raw_data_received = data_bytes.decode('utf-8', errors='replace')
                # debug_log(f"TestOutputPanel: Raw data received on socket: {raw_data_received[:200]}...") # Too noisy

                buffer += raw_data_received
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if message: 
                        self._handle_socket_message(message)
            
            except socket.timeout: 
                # debug_log("TestOutputPanel: _process_socket_messages: recv timeout.") # Too noisy
                continue 
            except (ConnectionResetError, BrokenPipeError) as conn_err:
                debug_log(f"TestOutputPanel: _process_socket_messages: Connection error ({type(conn_err).__name__}). Client likely disconnected.")
                break 
            except Exception as e:
                if not self.running: # Check if we are in a shutdown sequence
                    debug_log(f"TestOutputPanel: _process_socket_messages: Exception ({type(e).__name__}) during shutdown.")
                else:
                    debug_log(f"TestOutputPanel: _process_socket_messages: Unexpected error reading from socket ({type(e).__name__}: {e}).")
                break 
        
        # debug_log("TestOutputPanel: _process_socket_messages: Finished processing messages.") # Too noisy
        # Connection cleanup is handled by _socket_listener_thread or stop_socket_listener

    def _handle_socket_message(self, message_json: str) -> None:
        """Handle a JSON message from pytest plugin."""
        debug_log(f"TestOutputPanel: Handling socket message (JSON string): {message_json[:200]}...")
        try:
            message = json.loads(message_json)
            message_type = message.get("type", "")
            data = message.get("data", {})
            debug_log(f"TestOutputPanel: Parsed socket message_type: '{message_type}', data keys: {list(data.keys())}")
            
            # If we process any valid message, assume socket data is flowing
            if message_type:
                self.socket_data_received = True

            # Process different message types
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
            elif message_type == "compilation_status":
                self._handle_compilation_status(data)
                
        except json.JSONDecodeError:
            debug_log(f"Error decoding JSON message: {message_json[:100]}...")
        except Exception as e:
            debug_log(f"Error handling socket message: {e}")
    
    def _handle_session_start(self, data: Dict[str, Any]) -> None:
        """Handle session start message."""
        test_count = data.get("test_count", 0)
        # Prepare for test run
        self.app.call_from_thread(self.prepare_for_live_output)
        
        # Update progress bar
        self.app.call_from_thread(
            self.update_progress, "Starting test session", 0
        )
        
        # Log simulating compilation
        def log_compilation():
            log = self.query_one("#output-log", RichLog)
            log.write("[dim]Compiling C++ code...[/dim]")
            time.sleep(1)
            log.write("[dim]C++ compilation complete[/dim]")
            log.write("[dim]Compiling Mojo code...[/dim]")
            time.sleep(1)
            log.write("[dim]Mojo compilation complete[/dim]")
        
        # Call the function in the main thread
        self.app.call_from_thread(log_compilation)
    
    def _handle_test_start(self, data: Dict[str, Any]) -> None:
        """Handle test start message."""
        test_id = data.get("id", "")
        description = data.get("description", "")
        
        # Store current test info
        self.current_test_id = test_id
        self.current_test_description = description
        
        # Initialize data entry for this test
        if test_id not in self.collected_data:
            self.collected_data[test_id] = {
                "status": "",
                "description": description,
                "inputs": [],
                "cpp_output": [],
                "mojo_output": [],
                "diffs": [],
                "detailed_diffs": []  # Add detailed diffs field
            }
        else:
            # Update description if provided
            if description:
                self.collected_data[test_id]["description"] = description
        
        debug_log(f"Starting test: {test_id} ('{description}')")
        debug_log(f"Current collected_data keys: {list(self.collected_data.keys())}")
        
        def update_ui():
            # Don't show "Processing test" lines to reduce clutter
            pass
            
        self.app.call_from_thread(update_ui)
    
    def _handle_test_inputs(self, data: Dict[str, Any]) -> None:
        """Handle test inputs message."""
        test_id = data.get("id", "")
        inputs = data.get("inputs", {})
        
        debug_log(f"Received inputs for {test_id}: {inputs}")
        
        # Ensure we have an entry for this test
        if test_id not in self.collected_data:
            self.collected_data[test_id] = {
                "status": "",
                "description": "",
                "inputs": [],
                "cpp_output": [],
                "mojo_output": [],
                "diffs": [],
                "detailed_diffs": []  # Add detailed diffs field
            }
        
        # Process inputs into formatted lines for display
        input_lines = []
        
        # Handle dictionary inputs (most common case)
        if isinstance(inputs, dict):
            for name, value in inputs.items():
                input_lines.append(f"{name}: {value}")
        
        # Handle list inputs (pre-formatted lines)
        elif isinstance(inputs, list):
            input_lines = inputs
        
        # Handle string input (single value)
        elif isinstance(inputs, str):
            input_lines = [inputs]
            
        # Handle any other type by converting to string
        else:
            input_lines = [str(inputs)]
        
        # Store the formatted inputs
        self.collected_data[test_id]["inputs"] = input_lines
        debug_log(f"Processed inputs for {test_id}: {input_lines}")
    
    def _handle_test_outputs(self, data: Dict[str, Any]) -> None:
        """Handle test outputs message."""
        test_id = data.get("id", "")
        cpp_output = data.get("cpp_output", "")
        mojo_output = data.get("mojo_output", "")
        
        # Ensure we have an entry for this test
        if test_id not in self.collected_data:
            self.collected_data[test_id] = {
                "status": "",
                "description": "",
                "inputs": [],
                "cpp_output": [],
                "mojo_output": [],
                "diffs": [],
                "detailed_diffs": []  # Add detailed diffs field
            }
        
        # Store outputs as lists
        if cpp_output:
            self.collected_data[test_id]["cpp_output"] = [cpp_output]
        if mojo_output:
            self.collected_data[test_id]["mojo_output"] = [mojo_output]
            
        debug_log(f"Stored outputs for {test_id}: CPP: '{cpp_output}', Mojo: '{mojo_output}'")
    
    def _handle_test_result(self, data: Dict[str, Any]) -> None:
        """Handle test result message."""
        test_id = data.get("id", "")
        status = data.get("status", "")
        reason = data.get("reason", "")
        diff = data.get("diff", "")
        detailed_diffs = data.get("detailed_diffs", [])  # Get detailed diffs if available
        
        # Get additional data that might be included
        cpp_output = data.get("cpp_output", "")
        mojo_output = data.get("mojo_output", "")
        description = data.get("description", "")
        
        # Get inputs explicitly from the message if available
        inputs = data.get("inputs", [])
        
        debug_log(f"Result for {test_id}: Status: {status}, Reason: {reason}")
        debug_log(f"Values: CPP: '{cpp_output}', Mojo: '{mojo_output}', Diff: '{diff}'")
        debug_log(f"Detailed diffs: {detailed_diffs}")  # Log detailed diffs
        debug_log(f"Inputs available: {bool(inputs)} - Inputs count: {len(inputs) if isinstance(inputs, list) else 'not a list'}")
        
        # Ensure we have an entry for this test
        if test_id not in self.collected_data:
            self.collected_data[test_id] = {
                "status": "",
                "description": "",
                "inputs": [],
                "cpp_output": [],
                "mojo_output": [],
                "diffs": [],
                "detailed_diffs": []  # Add detailed diffs field
            }
        
        # Update the entry
        test_data = self.collected_data[test_id]
        test_data["status"] = status
        
        if description:
            test_data["description"] = description
            
        if reason:
            test_data["fail_reason"] = reason
        
        # Store inputs if provided in this message
        if inputs and not test_data["inputs"]:
            if isinstance(inputs, list):
                test_data["inputs"] = inputs
            elif isinstance(inputs, dict):
                # Convert dict to list of strings
                input_lines = []
                for key, value in inputs.items():
                    input_lines.append(f"{key}: {value}")
                test_data["inputs"] = input_lines
            elif isinstance(inputs, str):
                test_data["inputs"] = [inputs]
                
        # Store outputs if provided
        if cpp_output and not test_data["cpp_output"]:
            test_data["cpp_output"] = [cpp_output]
        
        if mojo_output and not test_data["mojo_output"]:
            test_data["mojo_output"] = [mojo_output]
            
        if diff:
            test_data["diffs"] = [diff]
            
        # Store detailed diffs if available
        if detailed_diffs:
            test_data["detailed_diffs"] = detailed_diffs
            
        debug_log(f"Collected inputs for {test_id}: {test_data['inputs']}")
        
        # If test failed but we don't have values, try to extract from failure reason
        if status == "FAIL" and not (cpp_output or mojo_output) and reason:
            try:
                debug_log(f"Checking failure reason for output values: {reason[:100]}")
                # Look for any patterns that might contain output values
                # Look for output values in the reason text
                if "cpp_output" in reason and "mojo_output" in reason:
                    cpp_text = reason.split("cpp_output", 1)[1].split(",", 1)[0]
                    if ":" in cpp_text and "'" in cpp_text:
                        cpp_val = cpp_text.split("'")[1]
                        test_data["cpp_output"] = [cpp_val]
                        
                    mojo_text = reason.split("mojo_output", 1)[1].split(",", 1)[0]
                    if ":" in mojo_text and "'" in mojo_text:
                        mojo_val = mojo_text.split("'")[1]
                        test_data["mojo_output"] = [mojo_val]
                        
                    # Add to diffs too
                    try:
                        cpp_num = float(cpp_val.split(':')[1].strip()) if ':' in cpp_val else 0
                        mojo_num = float(mojo_val.split(':')[1].strip()) if ':' in mojo_val else 0
                        diff_val = abs(cpp_num - mojo_num)
                        test_data["diffs"] = [f"{diff_val:.4f} (C++: {cpp_num}, Mojo: {mojo_num})"]
                    except:
                        # Non-numeric values
                        test_data["diffs"] = ["Values not numeric"]
            except Exception as e:
                debug_log(f"Error extracting NPV from reason: {e}")
                
        # Make sure we have inputs that show in the data table
        if not test_data["inputs"] and (test_data["cpp_output"] or test_data["mojo_output"]):
            # Use a simple, generic placeholder
            test_data["inputs"] = ["Input data"]
            debug_log(f"No inputs found for test with outputs, using generic placeholder for {test_id}")
        elif test_data["inputs"]:
            debug_log(f"Using existing inputs for {test_id}: {test_data['inputs']}")
            
        # Create a ParsedTestItem for display
        item = ParsedTestItem(
            test_item_id=test_id,
            description=test_data.get("description", ""),
            overall_status=status,
            fail_reason=test_data.get("fail_reason", ""),
            shared_inputs=test_data.get("inputs", []),
            cpp_stdout=test_data.get("cpp_output", []),
            mojo_stdout=test_data.get("mojo_output", []),
            diffs=test_data.get("diffs", []),
            detailed_diffs=test_data.get("detailed_diffs", [])  # Include detailed diffs
        )
        
        debug_log(f"Display data for {test_id}: Inputs: {item.shared_inputs}, CPP: {item.cpp_stdout}, Mojo: {item.mojo_stdout}, Diff: {item.diffs}, Detailed diffs: {item.detailed_diffs}")
        
        # Display the test result
        def update_ui():
            self.display_test_results(None, [item], None)
            progress = len(self.collected_data) / max(len(self.collected_data), 1) * 100
            self.update_progress("Running tests", progress)
            
            self.socket_data_received = True # Mark that we got a result via socket
            
        self.app.call_from_thread(update_ui)
    
    def _handle_session_end(self, data: Dict[str, Any]) -> None:
        """Handle session end message."""
        total = data.get("total", 0)
        passed = data.get("passed", 0)
        failed = data.get("failed", 0)
        duration = data.get("duration", 0)
        
        self.socket_data_received = True # Mark that session ended via socket data

        def update_ui():
            # Complete progress bar
            self.update_progress("Tests completed", 100)
            # Hide progress bar
            self.query_one("#test-progress-bar").visible = False
            
            # Show summary
            log = self.query_one("#output-log", RichLog)
            log.write("")
            log.write(f"[bold]Test execution completed. {passed} passed, {failed} failed, total {total} in {duration:.1f}s[/bold]")
            
        self.app.call_from_thread(update_ui)
    
    def on_unmount(self) -> None:
        """Clean up resources when widget is unmounted."""
        self.stop_socket_listener()

    def stop_socket_listener(self) -> None:
        """Stop the socket listener thread and clean up resources."""
        self.running = False # Signal thread to stop
        
        # Close connection if open
        if self.connection:
            try:
                self.connection.shutdown(socket.SHUT_RDWR) # Graceful shutdown
            except Exception: pass # Ignore errors here
            try:
                self.connection.close()
            except Exception: pass
            self.connection = None
        
        # Close server socket if open
        if self.socket:
            try:
                self.socket.close()
            except Exception: pass
            self.socket = None # Set to None so it's not re-closed if stop is called again
        
        # Wait for thread to end AFTER signaling it and trying to close sockets
        if self.socket_thread and self.socket_thread.is_alive():
            self.socket_thread.join(timeout=1.0) # Give it a second to exit
            if self.socket_thread.is_alive():
                debug_log("TestOutputPanel: WARNING - TCP Socket listener thread did not terminate cleanly.")
            
        debug_log(f"TestOutputPanel: TCP Socket listener stopped for {self.host}:{self.port}.")

    def prepare_for_live_output(self) -> None:
        """Prepares the panel for new live output."""
        log = self.query_one("#output-log", RichLog)
        log.clear()
        
        # Reset state tracking
        self.current_test_id = None
        self.current_test_description = None
        self.collected_data = {}
        self.has_streamed_output = False
        self.socket_data_received = False # Reset flag here
        
        # Reset and show progress bar
        progress_bar = self.query_one("#test-progress-bar", ProgressBar)
        progress_bar.update(total=100, progress=0)
        progress_bar.visible = True
        
        # Output a header with brighter colors
        log.write("[bold bright_cyan]🧪 Test Execution Starting 🧪[/bold bright_cyan]")
        log.write("")
        
        debug_log("TestOutputPanel: Prepared for live output (log cleared).")

    def stream_line(self, line: str) -> None:
        """Process an incoming line of text.
        Now only stores line data into the data structure without duplicating display logic."""
        # Track input, output and diffs for DataTable
        
        # Check for test identification lines
        if line.startswith("TEST_ITEM_ID:"):
            # Don't clear previous test output - just start a new test
            full_test_id = line.split(":", 1)[1].strip()
            
            # Extract the actual test ID from parametrized test format
            if "[" in full_test_id and "]" in full_test_id:
                # Get the ID part in square brackets
                self.current_test_id = full_test_id[full_test_id.find("[")+1:full_test_id.find("]")]
            else:
                self.current_test_id = full_test_id
            
            self.collected_data[self.current_test_id] = {
                "status": "", 
                "description": "",
                "inputs": [],
                "cpp_output": [],
                "mojo_output": [],
                "diffs": [],
                "detailed_diffs": []
            }
        elif line.startswith("DESCRIPTION:") and self.current_test_id:
            self.current_test_description = line.split(":", 1)[1].strip()
            if self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["description"] = self.current_test_description
        
        elif line.startswith("SHARED_INPUT_BEGIN"):
            # Start collecting input lines
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["collecting_input"] = True
                debug_log(f"Starting to collect inputs for {self.current_test_id}")
        
        elif line.startswith("SHARED_INPUT_END"):
            # Stop collecting input lines
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["collecting_input"] = False
                debug_log(f"Finished collecting inputs for {self.current_test_id}, count: {len(self.collected_data[self.current_test_id].get('inputs', []))}")
        
        elif line.startswith("CPP_STDOUT_BEGIN"):
            # Start collecting C++ output lines
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["collecting_cpp"] = True
        
        elif line.startswith("CPP_STDOUT_END"):
            # Stop collecting C++ output lines
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["collecting_cpp"] = False
        
        elif line.startswith("MOJO_STDOUT_BEGIN"):
            # Start collecting Mojo output lines
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["collecting_mojo"] = True
        
        elif line.startswith("MOJO_STDOUT_END"):
            # Stop collecting Mojo output lines
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["collecting_mojo"] = False
        
        elif line.startswith("FAIL_REASON:"):
            # Capture fail reason
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["fail_reason"] = line.split(":", 1)[1].strip()
        
        elif line.startswith("DIFF:"):
            # Capture diff
            if self.current_test_id and self.current_test_id in self.collected_data:
                self.collected_data[self.current_test_id]["diffs"].append(line.split(":", 1)[1].strip())
        
        # Handle detailed errors from pytest plugin
        elif line.startswith("DETAILED_DIFF:"):
            # Store detailed diff lines from socket
            if self.current_test_id and self.current_test_id in self.collected_data:
                diff_line = line.split("DETAILED_DIFF:", 1)[1].strip()
                if "detailed_diffs" not in self.collected_data[self.current_test_id]:
                    self.collected_data[self.current_test_id]["detailed_diffs"] = []
                self.collected_data[self.current_test_id]["detailed_diffs"].append(diff_line)
                debug_log(f"Added detailed diff for {self.current_test_id}: {diff_line}")
        
        # Collect input/output/diffs based on collection state
        elif self.current_test_id and self.current_test_id in self.collected_data:
            data = self.collected_data[self.current_test_id]
            
            if data.get("collecting_input", False):
                if not line.strip():  # Skip empty lines
                    pass
                else:
                    data["inputs"].append(line)
                    debug_log(f"Added input line for {self.current_test_id}: {line}")
            elif data.get("collecting_cpp", False) and line.startswith("OUTPUT: "):
                data["cpp_output"].append(line.split("OUTPUT: ", 1)[1])
            elif data.get("collecting_mojo", False) and line.startswith("OUTPUT: "):
                data["mojo_output"].append(line.split("OUTPUT: ", 1)[1])
        
        elif line.startswith("OVERALL_STATUS:"):
            status = line.split(":", 1)[1].strip().upper()
            if self.current_test_id and self.current_test_id in self.collected_data:
                data = self.collected_data[self.current_test_id]
                data["status"] = status
                self.has_streamed_output = True  # Mark that we've displayed output
                
                # Create a ParsedTestItem for display
                item = ParsedTestItem(
                    test_item_id=self.current_test_id,
                    description=data.get("description", ""),
                    overall_status=status,
                    fail_reason=data.get("fail_reason", ""),
                    shared_inputs=data.get("inputs", []),
                    cpp_stdout=data.get("cpp_output", []),
                    mojo_stdout=data.get("mojo_output", []),
                    diffs=data.get("diffs", []),
                    detailed_diffs=data.get("detailed_diffs", [])
                )
                
                # Use the single display method
                self.display_test_results(None, [item], None)
                
                # Reset current test for next test
                self.current_test_id = None
                self.current_test_description = None
                
    def display_test_results(self, preamble_str: str | None, items: List[ParsedTestItem] | None, script_error_content: str | None):
        """Displays formatted test results in the RichLog with Rich Tables."""
        log = self.query_one("#output-log", RichLog)
        self.query_one("#test-progress-bar").visible = False
        
        if script_error_content:
            log.write("[bold red]SCRIPT EXECUTION ERROR:[/bold red]")
            log.write(script_error_content)
            return
        
        if not items:
            log.write("[italic]No test results to display.[/italic]")
            return
            
        debug_log(f"Displaying {len(items)} test results")
        
        # Calculate box width for better appearance
        min_width = 100  # Width for status boxes
        
        for item in items:
            # Extract the test ID properly - get the part in square brackets for parametrized tests
            test_id = item.test_item_id
            if "[" in test_id and "]" in test_id:
                test_id = test_id[test_id.find("[")+1:test_id.find("]")]
            
            # Display test results section - update the PASS/FAIL status box formatting
            if item.overall_status == "PASS":
                # Right-align the status text
                status_width = 6  # Width for "PASS" with some padding
                remaining_width = min_width - status_width
                
                # Just show the test ID without the description for a single-line display
                id_text = f"{test_id}"
                if len(id_text) > remaining_width - 2:
                    id_text = id_text[:remaining_width-5] + "..."
                
                # Pad the left part to ensure the status is right-aligned
                padding = remaining_width - len(id_text)
                if padding > 0:
                    id_text = id_text + " " * padding
                
                status_line = f"{id_text}{item.overall_status}"
                
                # Add padding to ensure minimum width
                if len(status_line) < min_width:
                    status_line = status_line + " " * (min_width - len(status_line))
                
                log.write(f"[bold white on #00dd00]{status_line}[/bold white on #00dd00]")
            elif item.overall_status == "FAIL":
                # Right-align the status text
                status_width = 6  # Width for "FAIL" with some padding
                remaining_width = min_width - status_width
                
                # Just show the test ID without the description for a single-line display
                id_text = f"{test_id}"
                if len(id_text) > remaining_width - 2:
                    id_text = id_text[:remaining_width-5] + "..."
                
                # Pad the left part to ensure the status is right-aligned
                padding = remaining_width - len(id_text)
                if padding > 0:
                    id_text = id_text + " " * padding
                
                status_line = f"{id_text}{item.overall_status}"
                
                # Add padding to ensure minimum width
                if len(status_line) < min_width:
                    status_line = status_line + " " * (min_width - len(status_line))
                
                log.write(f"[bold white on #ff0000]{status_line}[/bold white on #ff0000]")
                
                # Display Table for C++/Mojo/Diff if any of those exist
                if item.cpp_stdout or item.mojo_stdout or item.diffs or item.shared_inputs:
                    table = Table(box=box.SIMPLE, padding=(0,1,0,1))
                    table.add_column("Input", style="bright_cyan")
                    table.add_column("C++", style="bright_blue")
                    table.add_column("QuasarQuant", style="bright_magenta")
                    table.add_column("Diff", style="bright_red")
                    
                    # Clean up any template markers
                    cpp_list = item.cpp_stdout
                    mojo_list = item.mojo_stdout
                    diff_list = item.diffs
                    inputs_list = item.shared_inputs
                    
                    # Use a simple placeholder if we have outputs but no inputs
                    if (cpp_list or mojo_list or diff_list) and not inputs_list:
                        inputs_list = ["Input data"]
                    
                    cpp_len = len(cpp_list)
                    mojo_len = len(mojo_list)
                    diff_len = len(diff_list)
                    num_rows = max(cpp_len, mojo_len, diff_len, 1)  # At least one row
                    
                    # Combine all inputs into a single string for the first row
                    combined_input = ""
                    if inputs_list:
                        table_inputs = []
                        for input_line in inputs_list:
                            if ":" in input_line:
                                # Split into key-value for better formatting
                                key, value = input_line.split(":", 1)
                                table_inputs.append(f"{key.strip()}: {value.strip()}")
                            else:
                                table_inputs.append(input_line)
                        combined_input = "\n".join(table_inputs)

                    # Add rows to the table
                    if num_rows > 0:
                        for i in range(num_rows):
                            # Only show inputs in the first row
                            input_val = combined_input if i == 0 else ""
                            cpp_val = cpp_list[i] if i < cpp_len else ""
                            mojo_val = mojo_list[i] if i < mojo_len else ""
                            diff_val = diff_list[i] if i < diff_len else ""
                            
                            # Clean up template markers in values
                            if isinstance(cpp_val, str) and ("{test_data[" in cpp_val or "test_data[" in cpp_val):
                                cpp_val = "?"
                            if isinstance(mojo_val, str) and ("{test_data[" in mojo_val or "test_data[" in mojo_val):
                                mojo_val = "?"
                                
                            table.add_row(input_val, cpp_val, mojo_val, diff_val)
                    
                    # Add the table to the log
                    log.write(table)
                    
                    # Display detailed diffs if we have them
                    if item.detailed_diffs:
                        log.write("")  # Add spacing
                        log.write("[bold yellow on #222222]---- DETAILED DIFFERENCES ----[/bold yellow on #222222]")
                        log.write("")  # Add spacing after header
                        
                        # --- BEGIN MODIFICATION: Process structured detailed_diffs ---
                        for diff_entry in item.detailed_diffs:
                            if not isinstance(diff_entry, dict): # Handle old string format if it somehow appears
                                log.write(f"  {diff_entry}")
                                continue

                            diff_type = diff_entry.get("type")
                            if diff_type == "line_diff":
                                line_num = diff_entry.get("line_num", "N/A")
                                cpp_line = diff_entry.get("cpp_line", "")
                                mojo_line = diff_entry.get("mojo_line", "")
                                log.write(f"[bold cyan]Line {line_num} differs:[/bold cyan]")
                                log.write(f"  [bold blue]C++: [/bold blue] {cpp_line}")
                                log.write(f"  [bold magenta]Mojo:[/bold magenta] {mojo_line}")
                            elif diff_type == "length_diff":
                                cpp_len = diff_entry.get("cpp_len", "N/A")
                                mojo_len = diff_entry.get("mojo_len", "N/A")
                                log.write(f"[bold yellow]Output length differs: C++ ({cpp_len} lines), Mojo ({mojo_len} lines)[/bold yellow]")
                                # Optionally, display previews if needed, e.g.:
                                # cpp_preview = diff_entry.get("cpp_lines_preview", [])
                                # mojo_preview = diff_entry.get("mojo_lines_preview", [])
                                # if cpp_preview:
                                #     log.write(f"  [bold blue]C++ Preview (first {len(cpp_preview)}):[/bold blue]")
                                #     for line in cpp_preview: log.write(f"    {line}")
                                # if mojo_preview:
                                #     log.write(f"  [bold magenta]Mojo Preview (first {len(mojo_preview)}):[/bold magenta]")
                                #     for line in mojo_preview: log.write(f"    {line}")
                            elif diff_type == "generic_diff": # Fallback from plugin
                                cpp_output_val = diff_entry.get("cpp_output", "N/A")
                                mojo_output_val = diff_entry.get("mojo_output", "N/A")
                                summary = diff_entry.get("summary", "Outputs differ")
                                log.write(f"[bold yellow]{summary}:[/bold yellow]")
                                log.write(f"  [bold blue]C++: [/bold blue] {cpp_output_val}")
                                log.write(f"  [bold magenta]Mojo:[/bold magenta] {mojo_output_val}")
                            else:
                                # Fallback for unknown structured diff or old string format
                                log.write(f"  {str(diff_entry)}")
                        # --- END MODIFICATION ---
                        
                        # Add spacer after detailed differences
                        log.write("")
            else:
                # Handle unknown status
                unknown_status = item.overall_status or 'UNKNOWN'
                status_width = len(unknown_status) + 2
                remaining_width = min_width - status_width
                id_text = f"{test_id}"
                if len(id_text) > remaining_width - 2:
                    id_text = id_text[:remaining_width-5] + "..."
                
                padding = remaining_width - len(id_text)
                if padding > 0:
                    id_text = id_text + " " * padding
                
                status_line = f"{id_text} {unknown_status}"
                
                if len(status_line) < min_width:
                    status_line = status_line + " " * (min_width - len(status_line))
                
                log.write(f"[bold black on yellow]{status_line}[/bold black on yellow]")

    def toggle_live_output(self):
        """Toggles whether to show all output lines in real-time."""
        self.show_live_output = not self.show_live_output
        log = self.query_one("#output-log", RichLog)
        if self.show_live_output:
            log.write("[bold yellow]LIVE OUTPUT ENABLED: Showing all test output[/bold yellow]")
        else:
            log.write("[bold blue]LIVE OUTPUT DISABLED: Showing only summarized results[/bold blue]")
        return self.show_live_output

    def _handle_compilation_status(self, data: Dict[str, Any]) -> None:
        """Handle compilation status message from pytest plugin."""
        phase = data.get("phase", "")
        info = data.get("info", "")
        debug_log(f"Compilation status received: {phase} - {info}")
        
        def update_ui():
            log = self.query_one("#output-log", RichLog)
            progress_bar = self.query_one("#test-progress-bar", ProgressBar)
            progress_bar.visible = True  # Make sure progress bar is visible
            
            # Progress and message based on compilation phase
            if phase == "cpp_start":
                log.write(f"[bold green]⚙️ Compiling C++ ({info})...[/bold green]")
                progress_bar.update(progress=5)
            elif phase == "cpp_end":
                if info == "success":
                    log.write("[bold green]✅ C++ compilation complete[/bold green]")
                    progress_bar.update(progress=25)
                else:
                    log.write("[bold red]❌ C++ compilation failed[/bold red]")
                    progress_bar.update(progress=25)
            elif phase == "mojo_start":
                log.write(f"[bold blue]⚙️ Compiling Mojo ({info})...[/bold blue]")
                progress_bar.update(progress=30)
            elif phase == "mojo_end":
                if info == "success":
                    log.write("[bold blue]✅ Mojo compilation complete[/bold blue]")
                    progress_bar.update(progress=50)
                else:
                    log.write("[bold red]❌ Mojo compilation failed[/bold red]")
                    progress_bar.update(progress=50)
        
        debug_log(f"Calling UI update for compilation status: {phase} - {info}")
        self.app.call_from_thread(update_ui)

    def update_progress(self, stage: str, progress: float) -> None:
        """Updates the progress bar with the current progress."""
        self.query_one("#test-progress-bar").update(progress=progress)
        
    def show_error(self, error_message: str):
        """Shows an error message in the log."""
        log = self.query_one("#output-log", RichLog)
        log.write("[bold red]ERROR:[/bold red] " + error_message)
        self.query_one("#test-progress-bar").visible = False

# New Message class for worker results
class TestExecutionResult(Message):
    def __init__(self,
                 script_path: str,
                 raw_stdout: str | None = None, # Changed from results/summary/compilation
                 error_message: str | None = None
                 ) -> None:
        super().__init__()
        self.script_path = script_path
        self.raw_stdout = raw_stdout # Changed
        self.error_message = error_message

class TestScriptOutputLine(Message):
    """A message to stream a single line of script output."""
    def __init__(self, line: str) -> None:
        super().__init__()
        self.line = line

class TestProgressUpdate(Message):
    """A message to update the test execution progress."""
    def __init__(self, stage: str, progress: float) -> None:
        super().__init__()
        self.stage = stage
        self.progress = progress

class MainTest(App):
    """The main application for the QuantFork Test Suite TUI."""

    CSS_PATH = "main_test.css"

    TITLE = "QuasarQuant Test Suite"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("l", "toggle_live_output", "Toggle Live Output"),
        # ("t", "show_debug_tools", "Debug Tools") # Example for later if needed
    ]
                                                                                                                                                                           
    def compose(self) -> ComposeResult:
        """Compose the application's layout."""
        yield Header()
        yield Horizontal(
            TestExplorer(id="test-explorer-panel"),
            Vertical(
                TestOutputPanel(id="main-content-panel"),
                id="main-area"
            )
        )
        yield Footer()

    async def on_test_selected(self, message: TestExplorer.TestSelected):
        debug_log(f"MainTest: Test selection event for: {Path(message.script_path).name}")
        self.execute_test_script_via_handler(message.script_path)

    def test_selected_handler(self, script_path: str):
        """Handler for when a test script is selected in the explorer."""
        self.execute_test_script_via_handler(script_path)

    def execute_test_script_via_handler(self, script_path: str):
        debug_log(f"MainTest: Executing script: {Path(script_path).name}")
        
        output_panel = self.query_one(TestOutputPanel)
        output_panel.prepare_for_live_output() # Prepare for new output

        try:
            # Define an async function inside our method to capture script_path
            async def run_script():
                await self._run_test_and_post_message(script_path)
                
            # Use the async function as our worker
            self.run_worker(
                run_script,
                f"test_runner_{Path(script_path).name}", 
                "test_execution_group", 
                exclusive=False
            )
        except Exception as e:
            debug_log(f"MainTest: EXCEPTION during worker call for {Path(script_path).name}: {type(e).__name__}: {str(e)}")
            # Re-raise so TestExplorer can catch it and log, and potentially try its fallback.
            raise

    async def _run_test_and_post_message(self, script_path: str) -> None:
        """Runs the test script in a worker and posts a message with the result."""
        script_name = Path(script_path).name
        debug_log(f"Worker ({script_name}): Starting execution.")
        full_raw_output_accumulator = [] # Accumulate lines here
        try:
            # _execute_test_script_raw will now post TestScriptOutputLine messages
            # and also return the full output for final parsing.
            full_raw_output = await self._execute_test_script_raw(script_path, self.post_message)
            debug_log(f"Worker ({script_name}): Test completed. Full output length: {len(full_raw_output)}.")
            
            if not isinstance(self, App):
                debug_log(f"Worker ({script_name}): CRITICAL WARNING - self is NOT an App instance! type(self)={type(self)}. Cannot post message.")
                return

            self.post_message(
                TestExecutionResult(
                    script_path,
                    raw_stdout=full_raw_output # Send accumulated full output
                )
            )
        except Exception as e_worker:
            tb_str = traceback.format_exc()
            debug_log(f"Worker ({script_name}): Error: {type(e_worker).__name__}: {str(e_worker)}.")
            debug_log(f"Worker ({script_name}) Traceback:\n{tb_str}")
            
            if not isinstance(self, App):
                debug_log(f"Worker ({script_name}): CRITICAL WARNING - self is NOT an App instance (exception block)! type(self)={type(self)}. Cannot post error message.")
                return

            self.post_message(
                TestExecutionResult(script_path, error_message=str(e_worker))
            )
        debug_log(f"Worker ({script_name}): Finished and posted message.")

    async def on_test_execution_result(self, message: TestExecutionResult) -> None:
        """Handles the result of a test execution from a worker."""
        script_name = Path(message.script_path).name
        debug_log(f"MainTest: Received execution result for {script_name}.")
        output_panel = self.query_one(TestOutputPanel)

        debug_log(f"MainTest ({script_name}): In on_test_execution_result. output_panel.socket_data_received = {output_panel.socket_data_received}, output_panel.has_streamed_output = {output_panel.has_streamed_output}")

        if message.error_message:
            debug_log(f"MainTest ({script_name}): Displaying error: {message.error_message[:100]}...")
            output_panel.show_error(f"Test execution error: {message.error_message}")
        elif output_panel.socket_data_received:
            debug_log(f"MainTest ({script_name}): Socket data was received. Display presumed handled by socket methods.")
            # Ensure progress bar is hidden, as socket_handle_session_end should do this.
            output_panel.query_one("#test-progress-bar").update(progress=100)
            output_panel.query_one("#test-progress-bar").visible = False
            # Socket handlers (_handle_session_end) are responsible for the final summary message.
        elif message.raw_stdout is not None:
            # Socket data not received, fallback to stdout processing
            if output_panel.has_streamed_output:
                debug_log(f"MainTest ({script_name}): No socket data. Streamed output was shown. Finalizing.")
                output_panel.query_one("#test-progress-bar").update(progress=100)
                output_panel.query_one("#test-progress-bar").visible = False
            else:
                debug_log(f"MainTest ({script_name}): No socket data and no streamed output. Will parse full raw_stdout.")
                if message.raw_stdout is not None:
                    debug_log(f"MainTest ({script_name}): --- BEGIN RAW STDOUT ---")
                    for line_num, line_content in enumerate(message.raw_stdout.splitlines()): # Log line by line for readability
                        debug_log(f"MainTest ({script_name}) STDOUT Line {line_num + 1}: {line_content}")
                    debug_log(f"MainTest ({script_name}): --- END RAW STDOUT ---")
                else:
                    debug_log(f"MainTest ({script_name}): raw_stdout is None.")
                
                preamble, parsed_items = parse_test_script_output(message.raw_stdout or "") # Ensure string if None
                debug_log(f"MainTest ({script_name}): Parsed {len(parsed_items)} items from raw_stdout.")
                output_panel.display_test_results(preamble_str=preamble, items=parsed_items, script_error_content=None)
        else:
            debug_log(f"MainTest: ({script_name}) No socket data, no raw_stdout, no error. Showing generic message.")
            output_panel.show_error("Test ran but produced no definitive results via socket or stdout.")

    async def on_test_script_output_line(self, message: TestScriptOutputLine) -> None:
        output_panel = self.query_one(TestOutputPanel)
        output_panel.stream_line(message.line)

    async def on_test_progress_update(self, message: TestProgressUpdate) -> None:
        """Handle test progress update messages."""
        output_panel = self.query_one(TestOutputPanel)
        output_panel.update_progress(message.stage, message.progress)

    async def _execute_test_script_raw(self, script_path: str, post_message_callback: callable) -> str:
        """Executes a test script, posts lines via callback, and returns its full raw stdout."""
        actual_script_path = Path(script_path)
        script_name = actual_script_path.name
        debug_log(f"_execute_test_script_raw ({script_name}): Preparing to execute for streaming...")

        if not actual_script_path.exists():
            msg = f"Script does not exist: {actual_script_path}"
            debug_log(f"_execute_test_script_raw ({script_name}): ERROR - {msg}")
            raise FileNotFoundError(msg)
            
        # Initialize progress tracking variables
        num_tests = 0
        cpp_compilation_started = False
        cpp_compilation_done = False
        mojo_compilation_started = False
        mojo_compilation_done = False
        test_items_detected = []
        current_progress = 0.0

        # Determine how to run the script based on file type
        if actual_script_path.suffix == ".py":
            # For Python files, check if it's a pytest file
            if self._is_pytest_file(actual_script_path):
                # For pytest files, explicitly load our plugin
                plugin_path = SCRIPT_DIR / "pytest_tui_plugin.py"
                
                # Ensure the plugin is loaded by explicitly including it via pythonpath and plugins
                debug_log(f"_execute_test_script_raw ({script_name}): Running as pytest with plugin: {plugin_path}")
                
                # For debug purposes, print environment variables
                for key, value in os.environ.items():
                    if "PYTHON" in key:
                        debug_log(f"ENV: {key}={value}")
                
                command_to_run = [
                    "python", "-m", "pytest", 
                    str(actual_script_path),
                    "--verbose",
                    "-p", "pytest_tui_plugin"
                ]
            else:
                # For other Python files, run directly
                command_to_run = ["python", str(actual_script_path)]
        else:
            # For shell scripts, execute directly
            command_to_run = [str(actual_script_path)]
            
            # Check if it's executable for shell scripts
            if not os.access(actual_script_path, os.X_OK):
                msg = f"Script is not executable: {actual_script_path}"
                debug_log(f"_execute_test_script_raw ({script_name}): ERROR - {msg}")
                raise PermissionError(msg)

        proc = await asyncio.create_subprocess_exec(
            *command_to_run, 
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, # Capture stderr separately
        )
        
        full_output_lines = []
        full_error_lines = [] # For stderr

        async def log_stream(stream, stream_name, line_list, post_callback):
            nonlocal cpp_compilation_started, cpp_compilation_done, mojo_compilation_started, mojo_compilation_done
            nonlocal test_items_detected, num_tests, current_progress

            while not stream.at_eof():
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line_str = line_bytes.decode(errors="replace").rstrip()
                line_list.append(line_str)
                log_msg = f"_execute_test_script_raw ({script_name}) [{stream_name}]: {line_str}"
                debug_log(log_msg) # Log to main debug log
                if post_callback and stream_name == "STDOUT": # Only post STDOUT lines for live TUI updates
                    post_callback(TestScriptOutputLine(line_str))
                
                # --- Begin progress tracking logic with our new indicators ---
                if stream_name == "STDOUT": # Apply progress logic only to STDOUT
                    if "TEST_ITEM_ID:" in line_str:
                        test_id = line_str.split(":", 1)[1].strip()
                        test_items_detected.append(test_id)
                        if num_tests > 0:
                            test_progress_increment = 50.0 / num_tests
                            current_progress = 50.0 + (len(test_items_detected) * test_progress_increment)
                        else:
                            current_progress = 50.0 + (len(test_items_detected) * 10.0)
                        if post_callback:
                            post_callback(TestProgressUpdate(f"Test {test_id}", min(current_progress, 100.0)))
                    # Add recognition for our new compile indicators
                    elif "CPP_COMPILE_START:" in line_str:
                        cpp_compilation_started = True
                        compile_info = line_str.split(":", 1)[1].strip()
                        if post_callback: 
                            post_callback(TestProgressUpdate(f"Compiling C++ ({compile_info})", 5.0))
                    
                    elif "CPP_COMPILE_END:" in line_str:
                        cpp_compilation_done = True
                        result = line_str.split(":", 1)[1].strip()
                        if post_callback: 
                            post_callback(TestProgressUpdate(f"C++ Compilation {result}", 25.0))
                    
                    elif "MOJO_COMPILE_START:" in line_str:
                        mojo_compilation_started = True
                        compile_info = line_str.split(":", 1)[1].strip()
                        if post_callback: 
                            post_callback(TestProgressUpdate(f"Compiling Mojo ({compile_info})", 30.0))
                    
                    elif "MOJO_COMPILE_END:" in line_str:
                        mojo_compilation_done = True
                        result = line_str.split(":", 1)[1].strip()
                        if post_callback: 
                            post_callback(TestProgressUpdate(f"Mojo Compilation {result}", 50.0))
                    
                    # Keep existing fallback progress indicators
                    elif "COMPILATION CPP" in line_str:
                        if not cpp_compilation_started:
                            cpp_compilation_started = True
                            if post_callback: post_callback(TestProgressUpdate("CPP Compilation Started", 5.0))
                    elif "COMPILATION MOJO" in line_str:
                        if not mojo_compilation_started:
                            mojo_compilation_started = True
                            if not cpp_compilation_done:
                                cpp_compilation_done = True 
                            if post_callback: post_callback(TestProgressUpdate("MOJO Compilation Started", 30.0))
                    elif cpp_compilation_started and "Compilation successful" in line_str and not cpp_compilation_done:
                        cpp_compilation_done = True
                        if post_callback: post_callback(TestProgressUpdate("CPP Compilation Complete", 25.0))
                    elif mojo_compilation_started and "Compilation successful" in line_str and not mojo_compilation_done:
                        mojo_compilation_done = True
                        if post_callback: post_callback(TestProgressUpdate("MOJO Compilation Complete", 50.0))
                    elif "TESTS" in line_str and line_str.split("TESTS", 1)[1].strip().isdigit():
                        num_tests = int(line_str.split("TESTS", 1)[1].strip())
                        debug_log(f"Detected {num_tests} tests in total")
                # --- End progress tracking logic ---

        # Run tasks to log stdout and stderr concurrently
        await asyncio.gather(
            log_stream(proc.stdout, "STDOUT", full_output_lines, post_message_callback),
            log_stream(proc.stderr, "STDERR", full_error_lines, None) # No post_callback for stderr to TUI lines
        )
        
        await proc.wait()
        
        # Ensure progress reaches 100% when script is done
        if post_message_callback:
            post_message_callback(TestProgressUpdate("Complete", 100.0))
        
        # Join with minimal newlines to reduce vertical spacing
        full_output = "\n".join(full_output_lines)
        # full_error_output = "\n".join(full_error_lines) # We log stderr lines directly, but can join if needed elsewhere
        
        debug_log(f"_execute_test_script_raw ({script_name}): Completed. Exit: {proc.returncode}, Full STDOUT len: {len(full_output)}, Full STDERR len: {len(full_error_lines)}")
        
        if proc.returncode != 0 and not full_output and not full_error_lines: # Check both streams
            raise ValueError(f"Script {actual_script_path} failed with code {proc.returncode} and produced no output on stdout or stderr.")
            
        return full_output # Return stdout for existing parsing logic, stderr is logged

    def _is_pytest_file(self, script_path: Path) -> bool:
        """Determine if a Python file is a pytest file.
        
        Checks for:
        1. Filename ends with 'test.py'
        2. Contains pytest import
        3. Contains test_ functions
        """
        if not script_path.name.endswith("test.py"):
            # Fast check: name doesn't match our convention
            return False
            
        # Check content for pytest import or test functions
        try:
            with open(script_path, "r") as f:
                content = f.read()
                if "import pytest" in content or "from pytest" in content:
                    return True
                if "def test_" in content:
                    return True
        except Exception as e:
            debug_log(f"Error checking if {script_path} is a pytest file: {e}")
            
        return False

    def show_critical_error(self, title: str, message: str) -> None:
        """Pushes an error screen to display a critical error message."""
        debug_log(f"MainTest: Showing critical error dialog. Title: '{title}', Message: '{message[:100]}...'")
        self.push_screen(ErrorScreen(title=title, error_message=message))

    def action_toggle_live_output(self) -> None:
        """Toggle between showing all output or just filtered results."""
        output_panel = self.query_one(TestOutputPanel)
        is_enabled = output_panel.toggle_live_output()
        if is_enabled:
            self.notify("Live output enabled: showing all test details", title="Output Mode")
        else:
            self.notify("Live output disabled: showing filtered results", title="Output Mode")

    # Remove or comment out the old _execute_test_script and parse_test_output for now
    # async def _execute_test_script(self, script_path: str) -> tuple:
    #     ...
    # def parse_test_output(self, output):
    #     ...

class ErrorScreen(Screen):
    """A modal screen to display an error message."""

    BINDINGS = [("escape", "dismiss_screen", "Dismiss")]

    def __init__(self, title: str, error_message: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.error_title = title
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.error_title, classes="dialog_title"),
            Static("⚠️", classes="dialog_icon"), # Added icon
            Static(self.error_message, classes="dialog_message"),
            Button("OK (Exit App)", variant="error", id="dialog_ok_button"), # Changed label and variant
            classes="dialog_container"
        )

    def on_mount(self) -> None:
        container = self.query_one(".dialog_container")
        container.styles.border = ("heavy", "red")
        self.query_one("#dialog_ok_button").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dialog_ok_button":
            self.app.exit() # Changed to exit app
    
    def action_dismiss_screen(self) -> None:
        self.app.exit() # Changed to exit app

if __name__ == "__main__":
    app = MainTest()
    app.run() 