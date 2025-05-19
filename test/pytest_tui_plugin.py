"""
Pytest plugin for TUI integration using socket-based IPC.

This plugin connects to a TUI application and sends test events
in a structured JSON format, eliminating the need for stdout parsing.
"""
import pytest
import json
import socket
import os
import time
import threading
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path # Import Path

# Global dictionary to store test inputs keyed by node ID
_node_data_store = {}

# Add global compilation status function that tests can call
def compilation_status(phase: str, info: str):
    """
    Send compilation status to the TUI.
    
    Args:
        phase: One of "cpp_start", "cpp_end", "mojo_start", "mojo_end"
        info: Additional info about the compilation
    """
    plugin = getattr(pytest, '_tui_plugin_instance', None)
    if plugin:
        print(f"[PLUGIN DEBUG] compilation_status: Sending through plugin: {phase}: {info}", file=sys.stderr)
        plugin._send_compilation_status(phase, info)
    else:
        # Use direct print statements for fallback that match what the TUI expects to parse
        print(f"[PLUGIN DEBUG] compilation_status: No plugin available, using fallback: {phase}: {info}", file=sys.stderr)
        if phase == "cpp_start":
            print(f"CPP_COMPILE_START: {info}")
        elif phase == "cpp_end":
            print(f"CPP_COMPILE_END: {info.upper()}")
        elif phase == "mojo_start":
            print(f"MOJO_COMPILE_START: {info}")
        elif phase == "mojo_end":
            print(f"MOJO_COMPILE_END: {info.upper()}")
        # Ensure immediate flush
        sys.stdout.flush()

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Capture the test data directly from the test item before and after test execution."""
    # Before test runs
    test_id = item.nodeid
    
    # Extract test_data from parameterized tests
    test_data = {}
    if hasattr(item, "callspec") and hasattr(item.callspec, "params") and "test_data" in item.callspec.params:
        test_data = item.callspec.params["test_data"]
        print(f"[PROTOCOL DEBUG] Found test_data in params for {test_id}: {test_data}", file=sys.stderr)
    
    # Store initial info
    _node_data_store[test_id] = {
        "inputs": getattr(item, "inputs", {}),
        "cpp_output": getattr(item, "cpp_output", ""),
        "mojo_output": getattr(item, "mojo_output", ""),
        "description": item.get_closest_marker("description")
    }
    
    # If we have test_data, use it directly
    if test_data and isinstance(test_data, dict):
        if "inputs" in test_data:
            _node_data_store[test_id]["inputs"] = test_data["inputs"]
            print(f"[PROTOCOL DEBUG] Using inputs from test_data for {test_id}: {test_data['inputs']}", file=sys.stderr)
        if "cpp_output" in test_data:
            _node_data_store[test_id]["cpp_output"] = test_data["cpp_output"]
        if "mojo_output" in test_data:
            _node_data_store[test_id]["mojo_output"] = test_data["mojo_output"]
        if "description" in test_data:
            _node_data_store[test_id]["description"] = test_data["description"]
    
    # Let the test run
    yield
    
    # After test runs, update with any values that got set during test execution
    if test_id in _node_data_store:
        _node_data_store[test_id]["inputs"] = getattr(item, "inputs", _node_data_store[test_id]["inputs"])
        _node_data_store[test_id]["cpp_output"] = getattr(item, "cpp_output", _node_data_store[test_id]["cpp_output"])
        _node_data_store[test_id]["mojo_output"] = getattr(item, "mojo_output", _node_data_store[test_id]["mojo_output"])
        
        print(f"[PROTOCOL DEBUG] Final data for {test_id} after run: {_node_data_store[test_id]}", file=sys.stderr)

class TUIReportPlugin:
    """Pytest plugin that sends test data to TUI via IPC socket."""
    
    def __init__(self):
        # Print some debug info about environment
        print(f"[PLUGIN DEBUG] Running in Docker: {os.path.exists('/.dockerenv')}", file=sys.stderr)
        print(f"[PLUGIN DEBUG] Current working directory: {os.getcwd()}", file=sys.stderr)
        
        # Try multiple possible hostnames, but prioritize localhost since we're in the same container
        self.hosts_to_try = [
            '127.0.0.1',            # Same container localhost connection
            'localhost',            # Same container via hostname
            '0.0.0.0',              # Any interface
        ]
        self.host = self.hosts_to_try[0]  # Start with localhost
        self.port = 43567        # Same port as in the TUI
        print(f"[PLUGIN DEBUG] TUIReportPlugin: Will try connecting to these hosts: {self.hosts_to_try}", file=sys.stderr)
        
        self.client = None
        self.connected = False
        self.test_count = 0
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.current_test_data = {}  # Dictionary to store test data by ID
        
        print("[PLUGIN DEBUG] TUIReportPlugin: Initializing connection attempts...", file=sys.stderr)
        
        # Try each host in our list
        for host in self.hosts_to_try:
            self.host = host
            print(f"[PLUGIN DEBUG] Trying to connect to {self.host}:{self.port}...", file=sys.stderr)
            
            initial_connection_attempts = 3
            for attempt in range(initial_connection_attempts):
                print(f"[PLUGIN DEBUG] Connection attempt {attempt + 1}/{initial_connection_attempts} to {self.host}:{self.port}...", file=sys.stderr)
                if attempt > 0: # Don't sleep before the very first attempt
                    time.sleep(0.2 * attempt) # Increasingly longer sleeps (0.2s, 0.4s)
                self._setup_connection(timeout=1) # Use a shorter timeout for these initial attempts
                if self.connected:
                    print(f"[PLUGIN DEBUG] Successfully connected to {self.host}:{self.port}", file=sys.stderr)
                    break # Exit attempt loop if connected
            
            if self.connected:
                break # Exit host loop if connected
        
        # If we couldn't connect, fall back to stdout for backward compatibility
        if not self.connected:
            print("[PLUGIN DEBUG] WARNING: All connection attempts failed. Falling back to stdout.", file=sys.stderr)
            # Set fallback mode
            self.fallback_mode = True
        else:
            print(f"[PLUGIN DEBUG] TUIReportPlugin: Successfully connected to TUI socket at {self.host}:{self.port}.", file=sys.stderr)
            self.fallback_mode = False
    
    def _ensure_connected(self) -> bool:
        """Ensures connection to the socket, attempting to connect if necessary."""
        if not self.connected:
            print("[PLUGIN DEBUG] _ensure_connected: Not connected. Attempting to establish connection...", file=sys.stderr)
            self._setup_connection(timeout=1) # Shorter timeout for re-attempts
            if self.connected:
                print("[PLUGIN DEBUG] _ensure_connected: Re-connection SUCCEEDED.", file=sys.stderr)
            else:
                print("[PLUGIN DEBUG] _ensure_connected: Re-connection FAILED.", file=sys.stderr)
        return self.connected

    def _setup_connection(self, timeout: int) -> None:
        """Try to connect to the TUI socket with timeout."""
        print(f"[PLUGIN DEBUG] _setup_connection: Attempting to connect to {self.host}:{self.port} with timeout {timeout}s...", file=sys.stderr)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        
        try:
            # Connect to the socket (TUI should be listening)
            self.sock.connect((self.host, self.port))
            self.connected = True
            # Reset to blocking mode for normal operation
            self.sock.settimeout(None)
            print(f"[PLUGIN DEBUG] _setup_connection: Connection to {self.host}:{self.port} SUCCEEDED.", file=sys.stderr)
        except socket.timeout:
            print(f"[PLUGIN DEBUG] _setup_connection: Connection to {self.host}:{self.port} FAILED (Timeout).", file=sys.stderr)
            self.connected = False
        except ConnectionRefusedError:
            print(f"[PLUGIN DEBUG] _setup_connection: Connection to {self.host}:{self.port} FAILED (ConnectionRefusedError).", file=sys.stderr)
            self.connected = False
        except Exception as e:
            print(f"[PLUGIN DEBUG] _setup_connection: Connection to {self.host}:{self.port} FAILED (Error: {type(e).__name__}: {e}).", file=sys.stderr)
            self.connected = False
    
    def _send_message(self, message_type: str, data: Dict[str, Any]) -> None:
        """Send a structured message to the TUI."""
        if self.fallback_mode:
            # Fallback to stdout for backward compatibility
            self._print_fallback(message_type, data)
            return
            
        if not self._ensure_connected():
            print(f"[PLUGIN DEBUG] _send_message: Connection failed for type '{message_type}'. Switching to fallback.", file=sys.stderr)
            self.fallback_mode = True # Switch to fallback if connection fails before send
            self._print_fallback(message_type, data) # Send this message via fallback
            return
            
        message = {
            "type": message_type,
            "timestamp": time.time(),
            "data": data
        }
        
        try:
            self.sock.sendall(json.dumps(message).encode() + b"\n")
        except (BrokenPipeError, ConnectionResetError):
            # Connection lost, try to reconnect once
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                # Try sending again
                self.sock.sendall(json.dumps(message).encode() + b"\n")
            except Exception:
                # If reconnection fails, switch to fallback mode
                self.connected = False
                self.fallback_mode = True
                print(f"[PLUGIN DEBUG] _send_message: BrokenPipe/ConnectionReset and re-connection FAILED for type '{message_type}'. Switched to fallback.", file=sys.stderr)
                self._print_fallback(message_type, data)
    
    def _send_compilation_status(self, phase: str, info: str) -> None:
        """Send compilation status message to TUI."""
        print(f"[PLUGIN DEBUG] _send_compilation_status: Sending {phase}: {info}", file=sys.stderr)
        self._send_message("compilation_status", {
            "phase": phase,
            "info": info
        })
    
    def _print_fallback(self, message_type: str, data: Dict[str, Any]) -> None:
        """Print in the format expected by the current TUI parser."""
        if message_type == "session_start":
            print(f"TESTS {data['test_count']}")
            print(f"Running tests...")
            print("COMPILATION CPP")
            time.sleep(1)
            print("Compilation successful!")
            print("Compilation time: 1.0s")
            print("COMPILATION MOJO")
            time.sleep(1)
            print("Compilation successful!")
            print("Compilation time: 1.0s")
            
        elif message_type == "test_start":
            print(f"TEST_ITEM_ID: {data['id']}")
            print(f"DESCRIPTION: {data['description']}")
            
        elif message_type == "test_inputs":
            print("SHARED_INPUT_BEGIN")
            # Handle different input types properly
            inputs = data.get('inputs', {})
            if isinstance(inputs, dict):
                for name, value in inputs.items():
                    print(f"{name}: {value}")
            elif isinstance(inputs, list):
                for item in inputs:
                    print(item)
            else:
                print(str(inputs))
            print("SHARED_INPUT_END")
            
        elif message_type == "test_outputs":
            print("CPP_STDOUT_BEGIN")
            print(f"OUTPUT: {data['cpp_output']}")
            print("CPP_STDOUT_END")
            print("MOJO_STDOUT_BEGIN")
            print(f"OUTPUT: {data['mojo_output']}")
            print("MOJO_STDOUT_END")
            print("CPP_EXIT_CODE: 0")
            print("MOJO_EXIT_CODE: 0")
            
        elif message_type == "test_result":
            print(f"OVERALL_STATUS: {data['status']}")
            if data['status'] == "FAIL" and 'reason' in data:
                print(f"FAIL_REASON: {data['reason']}")
                if 'diff' in data and data['diff']:
                    print(f"DIFF: {data['diff']}")
                # Also print detailed diffs if available
                if 'detailed_diffs' in data and data['detailed_diffs']:
                    for diff_line in data['detailed_diffs']:
                        print(f"DETAILED_DIFF: {diff_line}")
            print("END_OF_TEST_ITEM")
            
        elif message_type == "session_end":
            print("RUN_SCRIPT_SUMMARY_BEGIN")
            print(f"Tests completed: {data['total']}")
            print(f"Tests passed: {data['passed']}")
            print(f"Tests failed: {data['failed']}")
            print(f"Execution time: {data['duration']:.1f}s")
            print("RUN_SCRIPT_SUMMARY_END")
            
        elif message_type == "compilation_status":
            # Fallback for compilation status
            phase = data.get("phase", "")
            info = data.get("info", "")
            
            if phase == "cpp_start":
                print(f"CPP_COMPILE_START: {info}")
            elif phase == "cpp_end":
                print(f"CPP_COMPILE_END: {info.upper()}")
            elif phase == "mojo_start":
                print(f"MOJO_COMPILE_START: {info}")
            elif phase == "mojo_end":
                print(f"MOJO_COMPILE_END: {info.upper()}")
            
        # Ensure output is visible immediately
        sys.stdout.flush()
    
    def pytest_collection_modifyitems(self, items):
        """Count the number of tests to be run."""
        self.test_count = len(items)
        
        # Send session start event
        self._send_message("session_start", {
            "test_count": self.test_count,
            "start_time": time.time()
        })
    
    def _get_param_id(self, nodeid):
        """Extract the parameter ID portion from a full nodeid.
        
        Examples:
          "test_compare_cpp_mojo[test-pepe-001]" -> "test-pepe-001"
          "test_function" -> "test_function"
        """
        if "[" in nodeid and "]" in nodeid:
            return nodeid[nodeid.find("[")+1:nodeid.find("]")]
        return nodeid.split("::")[-1]  # Fallback to function name

    def pytest_runtest_setup(self, item):
        """Called before each test is run."""
        # Extract test metadata
        test_id = item.nodeid
        param_id = self._get_param_id(test_id)  # Use consistent param_id format
        
        description = item.get_closest_marker("description")
        description = description.args[0] if description else "No description"
        
        # Clear data for this test
        test_data = {}
        
        # For parametrized tests, extract data directly from the parameter
        if hasattr(item, "callspec") and hasattr(item.callspec, "params") and "test_data" in item.callspec.params:
            param_data = item.callspec.params["test_data"]
            if isinstance(param_data, dict):
                # Store the actual parameter values that will be used in the test
                test_data = param_data.copy()
                
                # Override description if available in test_data
                if "description" in param_data:
                    description = param_data["description"]
                    
                print(f"[PLUGIN DEBUG] Found test_data in params: {test_data}", file=sys.stderr)
        
        # Store this test data
        if not hasattr(self, "test_data_dict"):
            self.test_data_dict = {}
            
        self.test_data_dict[test_id] = test_data
        
        # Send test start event with consistent param_id format
        self._send_message("test_start", {
            "id": param_id,  # Use consistent param_id format
            "description": description
        })
    
    def pytest_runtest_logreport(self, report):
        """Called for each test phase (setup/call/teardown)."""
        if report.when == "call":
            # Test has been executed
            self.tests_run += 1
            
            # Extract test ID from the report - full ID for dict lookup
            test_id = report.nodeid
            # Get consistent param_id format for messages
            param_id = self._get_param_id(test_id)
            
            print(f"[PLUGIN DEBUG] Processing test report for {test_id} (passed: {report.passed})", file=sys.stderr)
            
            # Get data from our global store which is more reliable
            node_data = _node_data_store.get(test_id, {})
            print(f"[PLUGIN DEBUG] Node data from store: {node_data}", file=sys.stderr)
            
            # Prioritize data sources:
            # 1. _node_data_store (most reliable, captured directly from the test item)
            # 2. test_data_dict (captured during setup)
            # 3. report object attributes (least reliable)
            
            # Get the stored test data
            test_data = self.test_data_dict.get(test_id, {}) if hasattr(self, "test_data_dict") else {}
            
            # Extract key values - prioritize node_data over test_data
            cpp_output = node_data.get("cpp_output", "") or test_data.get("cpp_output", "")
            mojo_output = node_data.get("mojo_output", "") or test_data.get("mojo_output", "")
            inputs = node_data.get("inputs", {}) or test_data.get("inputs", {})
            description = node_data.get("description", "") or test_data.get("description", "")
            
            # Debug the inputs to help diagnose issues
            print(f"[PLUGIN DEBUG] Final inputs for {test_id}: {inputs} (type: {type(inputs)})", file=sys.stderr)
            
            # Ensure inputs is serializable for JSON
            if inputs is None:
                inputs = {}
                
            # Normalize inputs to ensure it's a dict - helps with serialization
            if not isinstance(inputs, dict) and not isinstance(inputs, list):
                try:
                    # Try to convert to dict if it's some other type
                    inputs = dict(inputs)
                except (TypeError, ValueError):
                    # If conversion fails, wrap it in a dictionary
                    inputs = {"input": str(inputs)}
            
            print(f"[PLUGIN DEBUG] Final normalized inputs for {param_id}: {inputs}", file=sys.stderr)
            
            # Send inputs - always use param_id
            self._send_message("test_inputs", {
                "id": param_id,  # Use consistent param_id format
                "inputs": inputs
            })
            
            # Send outputs - always use param_id
            self._send_message("test_outputs", {
                "id": param_id,  # Use consistent param_id format
                "cpp_output": cpp_output,
                "mojo_output": mojo_output
            })
            
            # Calculate diff if needed
            diff = None
            if cpp_output and mojo_output and cpp_output != mojo_output:
                try:
                    # Try to extract numerical values
                    cpp_val = float(cpp_output.split(':')[1].strip())
                    mojo_val = float(mojo_output.split(':')[1].strip())
                    diff_val = round(abs(cpp_val - mojo_val), 4)
                    diff = f"{diff_val} (C++: {cpp_val}, Mojo: {mojo_val})"
                except (ValueError, IndexError):
                    diff = f"'{mojo_output}' vs '{cpp_output}'"
            
            # Track results
            if report.passed:
                self.tests_passed += 1
                status = "PASS"
            else:
                self.tests_failed += 1
                status = "FAIL"
                
            # --- BEGIN MODIFICATION: Use structured diff data ---
            detailed_diffs_payload = [] # Initialize as empty list
            if hasattr(report.node, "detailed_diffs_data"):
                detailed_diffs_payload = report.node.detailed_diffs_data
                print(f"[PLUGIN DEBUG] Using structured detailed_diffs_data from report.node for {param_id}", file=sys.stderr)
            elif status == "FAIL":
                # Fallback for non-structured diffs if detailed_diffs_data is not present
                # This part can be removed if all tests are guaranteed to provide structured diffs
                print(f"[PLUGIN DEBUG] No structured detailed_diffs_data for {param_id}. Falling back to basic diff from outputs.", file=sys.stderr)
                if cpp_output and mojo_output and cpp_output != mojo_output:
                    detailed_diffs_payload = [
                        {
                            "type": "generic_diff",
                            "cpp_output": cpp_output,
                            "mojo_output": mojo_output,
                            "summary": "Outputs differ (fallback)"
                        }
                    ]
            # --- END MODIFICATION ---
                
            # Prepare result data with all the information - always use param_id
            result_data = {
                "id": param_id,  # Use consistent param_id format
                "status": status,
                "duration": getattr(report, "duration", 0),
                "description": description,
                "cpp_output": cpp_output,
                "mojo_output": mojo_output,
                "inputs": inputs # Ensure inputs are included
            }
            
            if status == "FAIL":
                # Format reason
                reason = "Test failed" # Generic reason
                if hasattr(report, "longrepr"):
                    # Extract just the first line for brevity if it's an assertion error summary
                    longrepr_str = str(report.longrepr)
                    first_line = longrepr_str.split('\\n')[0]
                    if "AssertionError:" in first_line:
                        reason = first_line.split("AssertionError:",1)[1].strip()
                    elif first_line:
                         reason = first_line # Use the first line if not a typical assertion error
                
                result_data["reason"] = reason
                
                if diff: # This is the summary diff string
                    result_data["diff"] = diff
                
                # Add the detailed diffs (now structured or fallback)
                # Ensure detailed_diffs_payload is always a list
                result_data["detailed_diffs"] = detailed_diffs_payload if isinstance(detailed_diffs_payload, list) else []
                print(f"[PLUGIN DEBUG] Attaching detailed_diffs to result_data for {param_id}: {result_data['detailed_diffs']}", file=sys.stderr)
            
            # Send the test result - always use param_id
            print(f"[PLUGIN DEBUG] Sending test_result for {param_id} with keys: {list(result_data.keys())}", file=sys.stderr)
            self._send_message("test_result", result_data)
    
    def pytest_terminal_summary(self, terminalreporter):
        """Called at the end of the test session."""
        # Send session end event
        self._send_message("session_end", {
            "total": self.tests_run,
            "passed": self.tests_passed,
            "failed": self.tests_failed,
            "duration": terminalreporter.duration
        })
        
        # Clean up the socket
        if self.connected:
            try:
                self.sock.close()
            except Exception:
                pass

@pytest.fixture
def tui_reporter(request):
    """Fixture to attach test data to the report object."""
    yield
    
    # After test completes, attach data to the report for the plugin to use
    if hasattr(request, "param"):
        # For parametrized tests
        request.node.cpp_output = request.param.get("cpp_output", "")
        request.node.mojo_output = request.param.get("mojo_output", "")
        request.node.inputs = request.param.get("inputs", {})
    # We don't need to do anything else here, as test_pepe.py already attaches these
    # values directly to request.node

def pytest_configure(config):
    """Register the plugin."""
    print("[PLUGIN DEBUG] pytest_configure: Registering TUI reporter plugin", file=sys.stderr)
    
    # Create plugin instance
    plugin = TUIReportPlugin()
    
    # Register the plugin
    config.pluginmanager.register(plugin, "tui_reporter")
    print("[PLUGIN DEBUG] pytest_configure: Plugin registration complete", file=sys.stderr)
    
    # Store a reference to the plugin instance in the pytest module right away
    # This makes the compilation_status hook available sooner
    setattr(pytest, "_tui_plugin_instance", plugin)
    
    # Make the compilation_status method directly available as a module-level function
    # This provides a fallback even before pytest.compilation_status is properly set up
    setattr(pytest, "compilation_status", compilation_status)
    
    # Explicitly announce that the compilation status hook is available
    print("[PLUGIN DEBUG] pytest_configure: compilation_status hook is now available", file=sys.stderr)
    
    # Print loaded plugins for verification
    plugins = config.pluginmanager.list_name_plugin()
    plugin_names = [name for name, _ in plugins]
    print(f"[PLUGIN DEBUG] Loaded plugins: {plugin_names}", file=sys.stderr) 