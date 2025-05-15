import asyncio
from pathlib import Path
import os
import sys # Added for sys.stdout.flush()
import traceback # Added for full traceback logging
from dataclasses import dataclass, field
from typing import List

from rich.text import Text
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table # Import Table
import rich.box as box # Import for box styles

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Static, DataTable, Button # Removed LoadingIndicator
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widget import Widget
from textual.message import Message
from textual.reactive import reactive
from textual.worker import Worker
from textual.screen import Screen # Added Screen

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

def parse_test_script_output(raw_output: str) -> List[ParsedTestItem]:
    items = []
    current_item = None
    capturing_shared_input = False
    capturing_cpp_stdout = False
    capturing_mojo_stdout = False

    for line in raw_output.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("TEST_ITEM_ID:"):
            if current_item:
                items.append(current_item)
            current_item = ParsedTestItem(test_item_id=stripped_line.split(":", 1)[1].strip())
            capturing_shared_input = False
            capturing_cpp_stdout = False
            capturing_mojo_stdout = False
        elif current_item:
            if stripped_line.startswith("DESCRIPTION:"):
                current_item.description = stripped_line.split(":", 1)[1].strip()
            elif stripped_line.startswith("OVERALL_STATUS:"):
                current_item.overall_status = stripped_line.split(":", 1)[1].strip().upper()
            elif stripped_line.startswith("FAIL_REASON:"):
                current_item.fail_reason = stripped_line.split(":", 1)[1].strip()
            elif stripped_line == "SHARED_INPUT_BEGIN":
                capturing_shared_input = True
            elif stripped_line == "SHARED_INPUT_END":
                capturing_shared_input = False
            elif stripped_line == "CPP_STDOUT_BEGIN":
                capturing_cpp_stdout = True
            elif stripped_line == "CPP_STDOUT_END":
                capturing_cpp_stdout = False
            elif stripped_line == "MOJO_STDOUT_BEGIN":
                capturing_mojo_stdout = True
            elif stripped_line == "MOJO_STDOUT_END":
                capturing_mojo_stdout = False
            elif capturing_shared_input:
                current_item.shared_inputs.append(line)
            elif capturing_cpp_stdout:
                if line.startswith("OUTPUT: "):
                    current_item.cpp_stdout.append(line.split("OUTPUT: ", 1)[1])
            elif capturing_mojo_stdout:
                if line.startswith("OUTPUT: "):
                    current_item.mojo_stdout.append(line.split("OUTPUT: ", 1)[1])
    
    if current_item: # Append the last item
        items.append(current_item)
    return items

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
                # debug_log(f"Checking category: {category_name}") # Removed
                category_tests = []
                
                tests_subdir = category_dir / "tests"
                if tests_subdir.is_dir():
                    for item in tests_subdir.rglob("*"):
                        if item.is_file():
                            is_sh_script = (
                                item.name.endswith("_tests.sh") or
                                item.name.startswith("test_") or # Covers test_*.sh
                                item.name.startswith("run_")    # Covers run_*.sh
                            ) and item.name.endswith(".sh")

                            is_py_script = (
                                item.name.endswith("_tests.py") or
                                item.name.startswith("test_") or # Covers test_*.py
                                item.name.startswith("run_")    # Covers run_*.py
                            ) and item.name.endswith(".py")

                            if (is_sh_script or is_py_script) and os.access(item, os.X_OK):
                                if item not in category_tests:
                                    category_tests.append(item)
                                    # debug_log(f"  Found executable script: {item}") # Removed
                
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
                category_node.add_leaf(script_path.name, data={"type": "script", "path": str(script_path)})
        
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

    def compose(self) -> ComposeResult:
        """Create the output panel components based on simplified structure."""
        # yield Static("Debug Text in TestOutputPanel (RED area)", id="panel-debug-text") # REMOVED
        yield ScrollableContainer(id="output-details") # This is our main scrollable area
        
    def on_mount(self) -> None:
        """Initialize the output panel when it's mounted."""
        # self.query_one("#output-details").styles.background = "blue" # DEBUG COLOR REMOVED
        # self.query_one("#panel-debug-text").styles.background = "magenta" # DEBUG COLOR REMOVED
        debug_log("TestOutputPanel mounted for structured test output.")

    def _display_content_in_details(self, content: str, is_script_error: bool):
        debug_log(f"Updating display. Is script error: {is_script_error}, Content length: {len(content)}.")
        
        details_container = self.query_one("#output-details", ScrollableContainer)
        details_container.visible = True
        details_container.remove_children()

        if is_script_error:
            error_text = Text(f"SCRIPT EXECUTION ERROR:\n{content}", style="bold red")
            details_container.mount(Static(error_text))
        else:
            parsed_items = parse_test_script_output(content)
            if not parsed_items:
                details_container.mount(Static("[i]No parsable test items found in output.[/i]"))
                return

            for item in parsed_items:
                # details_container.mount(Static(Text(f"Test ID: {item.test_item_id}", style="bold"))) # Test ID moved to status bar
                details_container.mount(Static(Text(item.description, style="dim")))

                status_style = ""
                status_text_centered = ""
                text_color_on_status_bg = "black" # Default for yellow/green

                if item.overall_status == "PASS":
                    status_style = "green"
                    status_text_centered = "PASS"
                elif item.overall_status == "FAIL":
                    status_style = "red"
                    status_text_centered = "FAIL"
                    text_color_on_status_bg = "white"
                else: # Other statuses (WARN, SKIP, etc.)
                    status_style = "yellow"
                    status_text_centered = item.overall_status
                
                # Status Bar Line (using Horizontal layout)
                status_bar_line = Horizontal()
                status_bar_line.styles.width = "100%"
                status_bar_line.styles.background = status_style
                status_bar_line.styles.padding = (0, 1)
                status_bar_line.styles.height = "auto" # Let content define height

                # Mount the Horizontal status_bar_line first
                details_container.mount(status_bar_line)

                id_static = Static(f"Test ID: {item.test_item_id}")
                id_static.styles.width = "auto"
                id_static.styles.color = text_color_on_status_bg
                id_static.styles.text_style = "bold"
                id_static.styles.margin = (0,1,0,0) # Right margin for spacing

                status_text_static = Static(status_text_centered)
                status_text_static.styles.width = "1fr" # Take remaining space
                status_text_static.styles.text_align = "center"
                status_text_static.styles.color = text_color_on_status_bg
                status_text_static.styles.text_style = "bold"
                
                # Then mount children into the now-mounted status_bar_line
                status_bar_line.mount(id_static)
                status_bar_line.mount(status_text_static)

                if item.overall_status == "FAIL":
                    # Line 2 for FAIL: Reason
                    reason_text_str = f"Reason: {item.fail_reason}" if item.fail_reason else "Reason: Not specified"
                    reason_bar = Static(Text(reason_text_str, style=f"{text_color_on_status_bg} on {status_style}"))
                    reason_bar.styles.width = "100%"
                    reason_bar.styles.background = status_style # Match first FAIL line background
                    reason_bar.styles.padding = (0,1)
                    reason_bar.styles.height = "auto"
                    details_container.mount(reason_bar)
                    
                    # --- Inputs Display Line (New 3rd line for FAIL) ---
                    inputs_summary = "[No inputs found]"
                    if item.shared_inputs:
                        inputs_summary = ", ".join(item.shared_inputs)
                    
                    inputs_display_bar = Static(Text(f"Inputs: {inputs_summary}", style=f"{text_color_on_status_bg} on {status_style}"))
                    inputs_display_bar.styles.width = "100%"
                    inputs_display_bar.styles.background = status_style 
                    inputs_display_bar.styles.padding = (0, 1)
                    inputs_display_bar.styles.height = "auto"
                    # inputs_display_bar.styles.text_align = "center" # Inputs are usually better left-aligned
                    details_container.mount(inputs_display_bar)
                    # --- End Inputs Display Line ---
                    
                    # C++/Mojo OUTPUT comparison (as tables)
                    cpp_output_lines = item.cpp_stdout
                    mojo_output_lines = item.mojo_stdout

                    cpp_table = Table(title="C++ STDOUT", box=box.ROUNDED, show_header=False, expand=True, padding=(0,1))
                    cpp_table.add_column("Output")
                    if cpp_output_lines:
                        for line in cpp_output_lines:
                            cpp_table.add_row(line)
                    else:
                        cpp_table.add_row("[No C++ Output]")

                    mojo_table = Table(title="Mojo STDOUT", box=box.ROUNDED, show_header=False, expand=True, padding=(0,1))
                    mojo_table.add_column("Output")
                    if mojo_output_lines:
                        for line in mojo_output_lines:
                            mojo_table.add_row(line)
                    else:
                        mojo_table.add_row("[No Mojo Output]")

                    # Use Textual Horizontal layout for side-by-side tables
                    output_layout = Horizontal()
                    output_layout.styles.width = "100%"
                    output_layout.styles.align_horizontal = "center" # Center the whole block
                    output_layout.styles.height = "auto" # Let content determine height

                    # Mount the Horizontal output_layout first
                    details_container.mount(output_layout)

                    cpp_static = Static(cpp_table)
                    cpp_static.styles.width = "auto"  # Option 2: Let table content suggest width
                    cpp_static.styles.margin = (0, 1) # Some margin between tables

                    mojo_static = Static(mojo_table)
                    mojo_static.styles.width = "auto"
                    mojo_static.styles.margin = (0, 1)

                    output_layout.mount(cpp_static)
                    output_layout.mount(mojo_static)
                    
                    # --- C++/Mojo INPUTS comparison (as tables) --- REMOVED
                    # cpp_input_lines = item.cpp_inputs
                    # mojo_input_lines = item.mojo_inputs
                    # ... (rest of the input table creation and mounting code removed)
                    # --- End C++/Mojo INPUTS comparison ---

                details_container.mount(Static("")) # Spacer line

        self.refresh()
        async def do_scroll():
            details_container.scroll_home(animate=False)
        self.set_timer(0.1, do_scroll)

    def show_raw_output(self, raw_stdout: str):
        self._display_content_in_details(raw_stdout, is_script_error=False)

    def show_error(self, error_message: str):
        self._display_content_in_details(error_message, is_script_error=True)

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

class MainTest(App):
    """The main application for the QuantFork Test Suite TUI."""

    CSS_PATH = "main_test.css"

    TITLE = "QuasarQuant Test Suite"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
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
        # debug_log(f"MainTest.execute_test_script_via_handler: self is {type(self)}") # Removed
        
        try:
            # debug_log(f"MainTest.execute_test_script_via_handler: Preparing to call self.run_worker (assuming even older signature with positional name AND group).") # Removed
            worker_name = f"test_runner_{Path(script_path).name}"
            # We need to create a simple async function that captures script_path
            # since any args we pass to run_worker aren't being forwarded to the callable
            
            # Define an async function inside our method to capture script_path
            async def run_script():
                await self._run_test_and_post_message(script_path)
                
            # Use the async function as our worker
            self.run_worker(
                run_script,
                worker_name, 
                "test_execution_group", 
                exclusive=False
            )
            # debug_log(f"MainTest.execute_test_script_via_handler: self.run_worker called for '{script_path}' with worker name '{worker_name}'.") # Removed
        except Exception as e:
            debug_log(f"MainTest: EXCEPTION during worker call for {Path(script_path).name}: {type(e).__name__}: {str(e)}")
            # Re-raise so TestExplorer can catch it and log, and potentially try its fallback.
            raise
        # debug_log(f"MainTest.execute_test_script_via_handler: Exiting for {script_path}") # Removed

    async def _run_test_and_post_message(self, script_path: str) -> None:
        """Runs the test script in a worker and posts a message with the result."""
        script_name = Path(script_path).name
        debug_log(f"Worker ({script_name}): Starting execution.")
        # debug_log(f"Worker _run_test_and_post_message: type(self) is {type(self)}") # Removed
        full_raw_output = ""
        try:
            full_raw_output = await self._execute_test_script_raw(script_path) # Uses self.
            debug_log(f"Worker ({script_name}): Test completed. Raw output length: {len(full_raw_output)}.")
            
            if not isinstance(self, App):
                debug_log(f"Worker ({script_name}): CRITICAL WARNING - self is NOT an App instance! type(self)={type(self)}. Cannot post message.")
                return

            self.post_message( # Uses self.
                TestExecutionResult(
                    script_path,
                    raw_stdout=full_raw_output
                )
            )
        except Exception as e_worker:
            tb_str = traceback.format_exc()
            debug_log(f"Worker ({script_name}): Error: {type(e_worker).__name__}: {str(e_worker)}.")
            debug_log(f"Worker ({script_name}) Traceback:\n{tb_str}")
            
            if not isinstance(self, App):
                debug_log(f"Worker ({script_name}): CRITICAL WARNING - self is NOT an App instance (exception block)! type(self)={type(self)}. Cannot post error message.")
                return

            self.post_message( # Uses self.
                TestExecutionResult(script_path, error_message=str(e_worker))
            )
        debug_log(f"Worker ({script_name}): Finished and posted message.")

    async def on_test_execution_result(self, message: TestExecutionResult) -> None:
        """Handles the result of a test execution from a worker."""
        script_name = Path(message.script_path).name
        debug_log(f"MainTest: Received execution result for {script_name}.")
        output_panel = self.query_one(TestOutputPanel)
        if message.error_message:
            debug_log(f"MainTest: Displaying error from test {script_name}: {message.error_message[:100]}...")
            output_panel.show_error(f"Test execution error: {message.error_message}")
        elif message.raw_stdout is not None: # Check if raw_stdout is present
            debug_log(f"MainTest: Displaying raw_stdout from test {script_name}...")
            output_panel.show_raw_output(message.raw_stdout)
        else:
            debug_log(f"MainTest: No raw_stdout or error in result for {script_name}. Showing generic error.")
            output_panel.show_error("Test ran but produced no output or error information (and no raw_stdout).")

    async def _execute_test_script_raw(self, script_path: str) -> str:
        """Executes a test script (SH or PY) and returns its raw stdout, or raises an exception."""
        actual_script_path = Path(script_path) # Ensure it's a Path object
        script_name = actual_script_path.name
        debug_log(f"_execute_test_script_raw ({script_name}): Preparing to execute...")

        if not actual_script_path.exists():
            msg = f"Script does not exist: {actual_script_path}"
            debug_log(f"_execute_test_script_raw ({script_name}): ERROR - {msg}")
            raise FileNotFoundError(msg)
            
        if not os.access(actual_script_path, os.X_OK):
            msg = f"Script is not executable: {actual_script_path}"
            debug_log(f"_execute_test_script_raw ({script_name}): ERROR - {msg}")
            # For Python scripts, os.X_OK might not be strictly necessary if we prepend the interpreter,
            # but it's a good check for shell scripts.
            if actual_script_path.suffix != '.py': # Only raise if not a .py we can run with interpreter
                raise PermissionError(msg)
        
        command_to_run = []
        if actual_script_path.suffix == ".py":
            # Prepend python interpreter. This assumes 'python' is in PATH within Docker.
            # Or use sys.executable if more robustness is needed and it points to the correct one.
            command_to_run = ["python", str(actual_script_path)]
            # debug_log(f"Identified Python script. Command: {command_to_run}") # Removed
        else: # For .sh scripts or others, execute directly
            command_to_run = [str(actual_script_path)]
            # debug_log(f"Identified non-Python script. Command: {command_to_run}") # Removed

        proc = await asyncio.create_subprocess_exec(
            *command_to_run, # Unpack the command list
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        output_bytes = await proc.stdout.read()
        await proc.wait()
        
        full_output = output_bytes.decode(errors="replace")
        debug_log(f"_execute_test_script_raw ({script_name}): Completed. Exit: {proc.returncode}, Output len: {len(full_output)}.")
        
        if proc.returncode != 0 and not full_output:
            raise ValueError(f"Script {actual_script_path} failed with code {proc.returncode} and produced no output.")
        # No change needed for the case where script produces no output but exits cleanly, 
        # as the Python script is designed to produce output.
            
        return full_output

    def show_critical_error(self, title: str, message: str) -> None:
        """Pushes an error screen to display a critical error message."""
        debug_log(f"MainTest: Showing critical error dialog. Title: '{title}', Message: '{message[:100]}...'")
        self.push_screen(ErrorScreen(title=title, error_message=message))

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