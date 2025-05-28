import pytest
import subprocess
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Get script directory and project root (similar to the bash script)
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "../../..").resolve()

# Define paths for runner source files and compiled executables
CPP_SOURCE_FILE = SCRIPT_DIR / "test_cpp_europe_runner.cpp"
CPP_RUNNER_PATH = SCRIPT_DIR / "test_cpp_europe_runner_compiled"
MOJO_RUNNER_SOURCE = SCRIPT_DIR / "europe_runner.mojo"
MOJO_RUNNER_PATH = SCRIPT_DIR / "europe_mojo_runner_compiled"
# Define the key dependency for the Mojo runner
EUROPE_MOJO_DEPENDENCY = (SCRIPT_DIR / "../europe.mojo").resolve()

# Define currency codes to test (same as in the bash script)
CURRENCY_CODES = [
    "BGL", "BYR", "CHF", "CYP", "CZK", "DKK", "EEK", "EUR", "GBP", "HUF",
    "ISK", "LTL", "LVL", "NOK", "PLN", "ROL", "RON", "RUB", "SEK", "SIT",
    "TRL", "TRY",
    "ATS", "BEF", "DEM", "ESP", "FIM", "FRF", "GRD", "IEP", "ITL", "LUF",
    "MTL", "NLG", "PTE", "SKK",
    "UAH", "RSD", "HRK", "BGN", "GEL"
]

# Create test cases from the currency codes
TEST_CASES = [
    {
        "id": f"europe_currency_{code}",
        "description": f"Test for European currency {code}",
        "currency_code": code
    }
    for code in CURRENCY_CODES
]

# Fixture to compile the C++ and Mojo code once per test session
@pytest.fixture(scope="session")
def compiled_runners():
    """Compile the C++ and Mojo runners once per test session."""
    cpp_result = compile_cpp_runner()
    mojo_result = compile_mojo_runner()
    
    # Return compilation results for use in tests
    return {
        "cpp": {
            "success": cpp_result["success"],
            "output": cpp_result["output"],
            "exit_code": cpp_result["exit_code"],
            "runner_path": CPP_RUNNER_PATH if cpp_result["success"] else None
        },
        "mojo": {
            "success": mojo_result["success"],
            "output": mojo_result["output"],
            "exit_code": mojo_result["exit_code"],
            "runner_path": MOJO_RUNNER_PATH if mojo_result["success"] else None
        }
    }

def compile_cpp_runner():
    """Compile the C++ runner executable, recompiling if source is newer."""
    # Ensure the source file itself exists before any other checks
    if not CPP_SOURCE_FILE.exists():
        return {
            "success": False,
            "output": f"ERROR: C++ source file {CPP_SOURCE_FILE} not found.",
            "exit_code": 1
        }

    if CPP_RUNNER_PATH.exists():
        try:
            source_mtime = CPP_SOURCE_FILE.stat().st_mtime
            executable_mtime = CPP_RUNNER_PATH.stat().st_mtime
            
            if executable_mtime >= source_mtime:
                # Executable is up-to-date or newer, skip compilation
                import sys # Required for print to stderr for debugging
                print(f"[DEBUG C++] C++ runner {CPP_RUNNER_PATH} (mtime: {executable_mtime}) is up-to-date or newer than source {CPP_SOURCE_FILE} (mtime: {source_mtime}). Skipping compilation.", file=sys.stderr)
                return {
                    "success": True,
                    "output": "C++ runner already compiled and up-to-date.",
                    "exit_code": 0
                }
            else:
                import sys # Required for print to stderr for debugging
                print(f"[DEBUG C++] C++ source {CPP_SOURCE_FILE} (mtime: {source_mtime}) is newer than {CPP_RUNNER_PATH} (mtime: {executable_mtime}). Recompiling.", file=sys.stderr)
        except FileNotFoundError:
            # Fall through to compilation if stat fails (e.g., a file was deleted unexpectedly)
            import sys # Required for print to stderr for debugging
            print(f"[DEBUG C++] FileNotFoundError during mtime check for {CPP_RUNNER_PATH} or {CPP_SOURCE_FILE}. Will attempt to compile.", file=sys.stderr)
            pass 

    # If we reach here, either the runner doesn't exist, or it's outdated, or stat failed.
    import sys # Required for print to stderr for debugging
    print(f"[DEBUG C++] Compiling C++ runner: {CPP_RUNNER_PATH}", file=sys.stderr) # Requires import sys

    try:
        # Send compilation status via pytest plugin hook if available
        try:
            # Use pytest hooks if they're loaded by this point
            import pytest
            if hasattr(pytest, "compilation_status"):
                pytest.compilation_status("cpp_start", "Europe Currency Tests")
        except (ImportError, AttributeError):
            pass  # Hook not available, we're not running inside pytest
        
        # Similar to g++ command in the bash script
        cmd = [
            "g++", "-std=c++17", 
            f"-I{PROJECT_ROOT}", "-I/usr/local/include",
            str(CPP_SOURCE_FILE), "-o", str(CPP_RUNNER_PATH),
            "-L/usr/local/lib", "-lQuantLib", "-pthread"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Send compilation end status via hook if available
        try:
            import pytest
            if hasattr(pytest, "compilation_status"):
                status = "success" if result.returncode == 0 else "failed"
                pytest.compilation_status("cpp_end", status)
        except (ImportError, AttributeError):
            pass  # Hook not available
            
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        # Signal error via hook if available
        try:
            import pytest
            if hasattr(pytest, "compilation_status"):
                pytest.compilation_status("cpp_end", "error")
        except (ImportError, AttributeError):
            pass  # Hook not available
            
        return {
            "success": False,
            "output": f"Error compiling C++ runner: {e}",
            "exit_code": 1
        }

def compile_mojo_runner():
    """Compile the Mojo runner executable, recompiling if source is newer."""
    # Ensure the source file itself exists
    if not MOJO_RUNNER_SOURCE.exists():
        return {
            "success": False,
            "output": f"ERROR: Mojo source file {MOJO_RUNNER_SOURCE} not found.",
            "exit_code": 1
        }
    # Ensure the main dependency also exists
    if not EUROPE_MOJO_DEPENDENCY.exists():
        return {
            "success": False,
            "output": f"ERROR: Mojo dependency file {EUROPE_MOJO_DEPENDENCY} not found.",
            "exit_code": 1
        }

    recompile_needed = False
    if not MOJO_RUNNER_PATH.exists():
        recompile_needed = True
        import sys
        print(f"[DEBUG MOJO] Mojo runner {MOJO_RUNNER_PATH} does not exist. Recompiling.", file=sys.stderr)
    else:
        try:
            source_mtime = MOJO_RUNNER_SOURCE.stat().st_mtime
            dependency_mtime = EUROPE_MOJO_DEPENDENCY.stat().st_mtime
            executable_mtime = MOJO_RUNNER_PATH.stat().st_mtime

            if executable_mtime < source_mtime:
                recompile_needed = True
                import sys # Required for print to stderr for debugging
                print(f"[DEBUG MOJO] Mojo source {MOJO_RUNNER_SOURCE} (mtime: {source_mtime}) is newer than {MOJO_RUNNER_PATH} (mtime: {executable_mtime}). Recompiling.", file=sys.stderr)
            elif executable_mtime < dependency_mtime:
                recompile_needed = True
                import sys # Required for print to stderr for debugging
                print(f"[DEBUG MOJO] Mojo dependency {EUROPE_MOJO_DEPENDENCY} (mtime: {dependency_mtime}) is newer than {MOJO_RUNNER_PATH} (mtime: {executable_mtime}). Recompiling.", file=sys.stderr)
            else:
                # Executable is up-to-date or newer than both source and its key dependency
                import sys # Required for print to stderr for debugging
                print(f"[DEBUG MOJO] Mojo runner {MOJO_RUNNER_PATH} (mtime: {executable_mtime}) is up-to-date or newer than source {MOJO_RUNNER_SOURCE} (mtime: {source_mtime}) and dependency {EUROPE_MOJO_DEPENDENCY} (mtime: {dependency_mtime}). Skipping compilation.", file=sys.stderr)
                return {
                    "success": True,
                    "output": "Mojo runner already compiled and up-to-date.",
                    "exit_code": 0
                }
        except FileNotFoundError:
            recompile_needed = True
            # Fall through to compilation if stat fails
            import sys # Required for print to stderr for debugging
            print(f"[DEBUG MOJO] FileNotFoundError during mtime check for {MOJO_RUNNER_PATH}, {MOJO_RUNNER_SOURCE}, or {EUROPE_MOJO_DEPENDENCY}. Will attempt to compile.", file=sys.stderr)
            # pass # No longer just pass, ensure recompile_needed is true

    if not recompile_needed:
        # This case should ideally not be reached if logic above is correct
        # but as a safeguard if it was already compiled and up to date.
        return {
            "success": True,
            "output": "Mojo runner already compiled and up-to-date (safeguard).",
            "exit_code": 0
        }

    # If we reach here, either the runner doesn't exist, or it's outdated, or stat failed.
    import sys # Required for print to stderr for debugging
    print(f"[DEBUG MOJO] Compiling Mojo runner: {MOJO_RUNNER_PATH}", file=sys.stderr)
    
    try:
        # Send compilation status via pytest plugin hook if available
        try:
            import pytest
            if hasattr(pytest, "compilation_status"):
                pytest.compilation_status("mojo_start", "Europe Currency Tests")
        except (ImportError, AttributeError):
            pass  # Hook not available
        
        # Change to project root for Mojo build command, like in the bash script
        cmd = ["mojo", "build", str(MOJO_RUNNER_SOURCE), "-o", str(MOJO_RUNNER_PATH)]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            cwd=PROJECT_ROOT  # Run from project root
        )
        
        # Send compilation end status via hook if available
        try:
            import pytest
            if hasattr(pytest, "compilation_status"):
                status = "success" if result.returncode == 0 else "failed"
                pytest.compilation_status("mojo_end", status)
        except (ImportError, AttributeError):
            pass  # Hook not available
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        # Signal error via hook if available
        try:
            import pytest
            if hasattr(pytest, "compilation_status"):
                pytest.compilation_status("mojo_end", "error")
        except (ImportError, AttributeError):
            pass  # Hook not available
            
        return {
            "success": False,
            "output": f"Error compiling Mojo runner: {e}",
            "exit_code": 1
        }

def run_executable(executable_path, currency_code):
    """Run the given executable with the currency code and return the results."""
    try:
        # Define environment variables for the subprocess
        env_vars = os.environ.copy() # Start with a copy of the current environment
        env_vars["LANG"] = "en_US.UTF-8"
        env_vars["LC_ALL"] = "en_US.UTF-8"
        # You could also try "C.UTF-8" if "en_US.UTF-8" doesn't show a change

        process = subprocess.run(
            [str(executable_path), currency_code],
            capture_output=True,
            env=env_vars # Pass the modified environment
        )

        # Attempt to decode stdout and stderr as UTF-8, replacing errors for general use
        # but keeping raw bytes available if needed for debugging specific cases.
        try:
            stdout_str = process.stdout.decode('utf-8', errors='replace')
        except Exception:
            # Fallback if even replace fails or if stdout is None (though capture_output=True should prevent None)
            stdout_str = "<stdout decoding error or empty>"

        try:
            stderr_str = process.stderr.decode('utf-8', errors='replace')
        except Exception:
            stderr_str = "<stderr decoding error or empty>"
        
        # For debugging the raw bytes of EUR, you might add a temporary print here
        # if currency_code == "EUR" and executable_path == CPP_RUNNER_PATH:
        #     import sys
        #     print(f"DEBUG EUR CPP STDOUT BYTES: {repr(process.stdout)}", file=sys.stderr)
        #     print(f"DEBUG EUR CPP STDERR BYTES: {repr(process.stderr)}", file=sys.stderr)

        return {
            "success": process.returncode == 0,
            "stdout": stdout_str, # Decoded string
            "stderr": stderr_str, # Decoded string
            "exit_code": process.returncode,
            "raw_stdout": process.stdout, # Keep raw bytes for potential targeted debugging
            "raw_stderr": process.stderr  # Keep raw bytes
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Error running executable (outer try): {e}",
            "exit_code": 1,
            "raw_stdout": b'',
            "raw_stderr": b''
        }

@pytest.mark.parametrize(
    "test_data",
    TEST_CASES,
    ids=[t["id"] for t in TEST_CASES]
)
def test_currency(test_data, compiled_runners, request):
    """Test that Mojo and C++ currency implementations match."""
    currency_code = test_data["currency_code"]
    
    # Skip test if compilation failed
    if not compiled_runners["cpp"]["success"]:
        pytest.skip(f"C++ runner compilation failed: {compiled_runners['cpp']['output']}")
    
    if not compiled_runners["mojo"]["success"]:
        pytest.skip(f"Mojo runner compilation failed: {compiled_runners['mojo']['output']}")
    
    # Run the C++ and Mojo executables
    cpp_result = run_executable(compiled_runners["cpp"]["runner_path"], currency_code)
    mojo_result = run_executable(compiled_runners["mojo"]["runner_path"], currency_code)

    # Temporary debug for EUR C++ raw output if needed
    # if currency_code == "EUR":
    #    import sys
    #    print(f"EUR CPP RAW STDOUT in test_currency: {cpp_result.get('raw_stdout')}", file=sys.stderr)
    #    print(f"EUR MOJO RAW STDOUT in test_currency: {mojo_result.get('raw_stdout')}", file=sys.stderr) # Also print Mojo for comparison

    # Prepare test inputs (currency code)
    inputs = {"Currency Code": currency_code}
    
    # Attach data to request.node for the plugin to access
    request.node.inputs = inputs
    request.node.cpp_output = cpp_result["stdout"]
    request.node.mojo_output = mojo_result["stdout"]
    
    # Verify both executables ran successfully
    assert cpp_result["success"], f"C++ runner failed for currency_code '{currency_code}' with exit code {cpp_result['exit_code']}: {cpp_result['stderr']}"
    assert mojo_result["success"], f"Mojo runner failed for currency_code '{currency_code}' with exit code {mojo_result['exit_code']}: {mojo_result['stderr']}"
    
    # --- BEGIN MODIFICATION: Structured diff generation ---
    detailed_diffs_data = []
    assertion_passed = True
    error_message_summary = f"Outputs for {currency_code} differ."
    
    if cpp_result["stdout"] != mojo_result["stdout"]:
        assertion_passed = False
        cpp_lines = cpp_result["stdout"].strip().split('\n')
        mojo_lines = mojo_result["stdout"].strip().split('\n')
        
        # Prepare a more detailed error message string
        diff_details_for_error_message = "\n--- Differences ---"
    
        max_lines = max(len(cpp_lines), len(mojo_lines))
        for i in range(max_lines):
            cpp_line = cpp_lines[i] if i < len(cpp_lines) else None
            mojo_line = mojo_lines[i] if i < len(mojo_lines) else None
    
            if cpp_line != mojo_line:
                current_diff = {
                    "type": "line_diff",
                    "line_num": i + 1,
                    "cpp_line": cpp_line if cpp_line is not None else "<missing>",
                    "mojo_line": mojo_line if mojo_line is not None else "<missing>"
                }
                detailed_diffs_data.append(current_diff)
                diff_details_for_error_message += f"\nLine {current_diff['line_num']} differs:"
                diff_details_for_error_message += f"\n  C++ : '{current_diff['cpp_line']}'"
                diff_details_for_error_message += f"\n  Mojo: '{current_diff['mojo_line']}'"
    
        if len(cpp_lines) != len(mojo_lines):
            length_diff_data = {
                "type": "length_diff",
                "cpp_len": len(cpp_lines),
                "mojo_len": len(mojo_lines),
                "cpp_lines_preview": cpp_lines[:5], # Preview first 5 lines
                "mojo_lines_preview": mojo_lines[:5] # Preview first 5 lines
            }
            detailed_diffs_data.append(length_diff_data)
            diff_details_for_error_message += f"\nOutput length differs: C++ ({length_diff_data['cpp_len']} lines), Mojo ({length_diff_data['mojo_len']} lines)."
            # Optionally add preview to error message if desired, for example:
            # diff_details_for_error_message += f"\n  C++ Preview (first {len(length_diff_data['cpp_lines_preview'])}): {length_diff_data['cpp_lines_preview']}"
            # diff_details_for_error_message += f"\n  Mojo Preview (first {len(length_diff_data['mojo_lines_preview'])}): {length_diff_data['mojo_lines_preview']}"
        
        # Attach the structured diff data to the request node (might be useful for other plugins or future use)
        request.node.detailed_diffs_data = detailed_diffs_data
        
        # Append the collected diff details to the main error message for pytest output
        if not assertion_passed:
            error_message_summary += diff_details_for_error_message
    # --- END MODIFICATION ---

    # Simplified assertion based on the flag
    assert assertion_passed, error_message_summary

# For standalone execution (outside pytest)
if __name__ == "__main__":
    # Use pytest's main function to run the tests
    import sys
    sys.exit(pytest.main(["-v", __file__])) 