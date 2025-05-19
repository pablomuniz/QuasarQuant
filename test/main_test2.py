import subprocess
import sys
from pathlib import Path
import os

# Determine the project root based on this script's location
# Assuming this script is in quantfork/test/
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "..").resolve()
QL_DIR = PROJECT_ROOT / "ql"

# Environment variable to signal the plugin to use fallback if needed
# (though the plugin should fallback automatically if socket connection fails)
# os.environ["NO_TUI_SOCKET"] = "1" 

def discover_test_files(base_dir: Path) -> list[Path]:
    """Discovers test files (e.g., *_test.py or test_*.py) in the base directory."""
    test_files = []
    if not base_dir.is_dir():
        print(f"Error: Test directory not found: {base_dir}", file=sys.stderr)
        return test_files

    # Look for common pytest file patterns
    patterns = ["*_test.py", "test_*.py"]
    for pattern in patterns:
        for item in base_dir.rglob(pattern):
            if item.is_file() and item not in test_files:
                test_files.append(item)
    
    print(f"Discovered {len(test_files)} test file(s) in {base_dir}:")
    for tf in test_files:
        print(f"  - {tf.relative_to(PROJECT_ROOT)}")
    return test_files

def run_pytest(test_paths: list[Path]) -> bool:
    """Runs pytest on the given test paths and prints output to console."""
    if not test_paths:
        print("No test files found to run.", file=sys.stderr)
        return False

    # We can run pytest on all discovered files at once, or one by one.
    # Running all at once is usually more efficient and gives a consolidated report.
    command = [sys.executable, "-m", "pytest", "-v"] # -v for verbose
    
    # Add paths relative to project root for cleaner pytest output
    # Pytest typically works well if run from the project root,
    # so we'll use absolute paths or paths relative to where pytest is invoked from.
    # For simplicity, let's pass absolute paths to the test files.
    for p in test_paths:
        command.append(str(p.resolve()))

    print(f"\nRunning pytest command: {' '.join(command)}\n")

    try:
        # Run pytest from the project root directory for consistent behavior
        # This helps pytest discover conftest.py files and plugins correctly.
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT 
        )

        # Stream stdout
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
                sys.stdout.flush()
        
        # Stream stderr
        if process.stderr:
            for line in iter(process.stderr.readline, ''):
                print(line, end='', file=sys.stderr)
                sys.stderr.flush()

        process.wait()
        
        if process.returncode == 0:
            print("\nPytest run completed successfully.")
            return True
        else:
            print(f"\nPytest run failed with exit code {process.returncode}.", file=sys.stderr)
            return False

    except FileNotFoundError:
        print(f"Error: Pytest not found. Make sure '{sys.executable} -m pytest' can be run.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An error occurred while running pytest: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    print("Starting Test Execution via main_test2.py...")
    
    # Discover tests within the QL directory
    # You might want to make this more specific if QL_DIR is too broad
    # or if tests are in multiple distinct locations.
    test_files_to_run = discover_test_files(QL_DIR)

    if not test_files_to_run:
        print("No tests found. Exiting.")
        sys.exit(1)
        
    print("\n--- Running All Discovered Tests ---")
    success = run_pytest(test_files_to_run)

    if success:
        print("\nAll tests passed (or completed without pytest error).")
        sys.exit(0)
    else:
        print("\nSome tests failed or an error occurred during the pytest run.")
        sys.exit(1) 