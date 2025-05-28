import pytest
import subprocess
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Get script directory and project root
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "../../..").resolve() # Assuming quantfork/ql/currencies/tests -> quantfork

# Define paths for runner source files and compiled executables
CPP_SOURCE_FILE = SCRIPT_DIR / "test_cpp_oceania_runner.cpp"
CPP_RUNNER_PATH = SCRIPT_DIR / "test_cpp_oceania_runner_compiled"
MOJO_RUNNER_SOURCE = SCRIPT_DIR / "oceania_runner.mojo"  # Updated path
MOJO_RUNNER_PATH = SCRIPT_DIR / "oceania_mojo_runner_compiled"
# Define the key dependency for the Mojo runner
OCEANIA_MOJO_DEPENDENCY = (SCRIPT_DIR / "../oceania.mojo").resolve()

# Define currency codes to test
CURRENCY_CODES = [
    "AUD", "NZD"
]

# Create test cases from the currency codes
TEST_CASES = [
    {
        "id": f"oceania_currency_{code}",
        "description": f"Test for Oceania currency {code}",
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
                import sys
                print(f"[DEBUG C++ Oceania] C++ runner {CPP_RUNNER_PATH} is up-to-date. Skipping compilation.", file=sys.stderr)
                return {
                    "success": True,
                    "output": "C++ runner already compiled and up-to-date.",
                    "exit_code": 0
                }
            else:
                import sys
                print(f"[DEBUG C++ Oceania] C++ source {CPP_SOURCE_FILE} is newer. Recompiling.", file=sys.stderr)
        except FileNotFoundError:
            import sys
            print(f"[DEBUG C++ Oceania] FileNotFoundError during mtime check. Will attempt to compile.", file=sys.stderr)
            pass 

    import sys
    print(f"[DEBUG C++ Oceania] Compiling C++ runner: {CPP_RUNNER_PATH}", file=sys.stderr)

    try:
        cmd = [
            "g++", "-std=c++17", 
            f"-I{PROJECT_ROOT}", "-I/usr/local/include",
            str(CPP_SOURCE_FILE), "-o", str(CPP_RUNNER_PATH),
            "-L/usr/local/lib", "-lQuantLib", "-pthread"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
            
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"Error compiling C++ Oceania runner: {e}",
            "exit_code": 1
        }

def compile_mojo_runner():
    """Compile the Mojo runner executable, recompiling if source is newer."""
    if not MOJO_RUNNER_SOURCE.exists():
        return {
            "success": False,
            "output": f"ERROR: Mojo source file {MOJO_RUNNER_SOURCE} not found.",
            "exit_code": 1
        }
    if not OCEANIA_MOJO_DEPENDENCY.exists():
        return {
            "success": False,
            "output": f"ERROR: Mojo dependency file {OCEANIA_MOJO_DEPENDENCY} not found.",
            "exit_code": 1
        }

    recompile_needed = False
    if not MOJO_RUNNER_PATH.exists():
        recompile_needed = True
        import sys
        print(f"[DEBUG MOJO Oceania] Mojo runner {MOJO_RUNNER_PATH} does not exist. Recompiling.", file=sys.stderr)
    else:
        try:
            source_mtime = MOJO_RUNNER_SOURCE.stat().st_mtime
            dependency_mtime = OCEANIA_MOJO_DEPENDENCY.stat().st_mtime
            executable_mtime = MOJO_RUNNER_PATH.stat().st_mtime

            if executable_mtime < source_mtime:
                recompile_needed = True
                import sys
                print(f"[DEBUG MOJO Oceania] Mojo source {MOJO_RUNNER_SOURCE} is newer. Recompiling.", file=sys.stderr)
            elif executable_mtime < dependency_mtime:
                recompile_needed = True
                import sys
                print(f"[DEBUG MOJO Oceania] Mojo dependency {OCEANIA_MOJO_DEPENDENCY} is newer. Recompiling.", file=sys.stderr)
            else:
                import sys
                print(f"[DEBUG MOJO Oceania] Mojo runner {MOJO_RUNNER_PATH} is up-to-date. Skipping compilation.", file=sys.stderr)
                return {
                    "success": True,
                    "output": "Mojo runner already compiled and up-to-date.",
                    "exit_code": 0
                }
        except FileNotFoundError:
            recompile_needed = True
            import sys
            print(f"[DEBUG MOJO Oceania] FileNotFoundError during mtime check. Will attempt to compile.", file=sys.stderr)

    if not recompile_needed:
        return {
            "success": True,
            "output": "Mojo runner already compiled and up-to-date (safeguard).",
            "exit_code": 0
        }

    import sys
    print(f"[DEBUG MOJO Oceania] Compiling Mojo runner: {MOJO_RUNNER_PATH}", file=sys.stderr)
    
    try:
        cmd = ["mojo", "build", str(MOJO_RUNNER_SOURCE), "-o", str(MOJO_RUNNER_PATH)]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            cwd=PROJECT_ROOT # Run from project root, assuming oceania_runner.mojo uses project-relative imports
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"Error compiling Mojo Oceania runner: {e}",
            "exit_code": 1
        }

def run_executable(executable_path, currency_code):
    """Run the given executable with the currency code and return the results."""
    try:
        env_vars = os.environ.copy()
        env_vars["LANG"] = "en_US.UTF-8"
        env_vars["LC_ALL"] = "en_US.UTF-8"

        process = subprocess.run(
            [str(executable_path), currency_code],
            capture_output=True,
            env=env_vars
        )
        stdout_str = process.stdout.decode('utf-8', errors='replace')
        stderr_str = process.stderr.decode('utf-8', errors='replace')
        
        return {
            "success": process.returncode == 0,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "exit_code": process.returncode,
            "raw_stdout": process.stdout,
            "raw_stderr": process.stderr
        }
    except Exception as e:
        return {
            "success": False, "stdout": "", "stderr": f"Error running executable: {e}", "exit_code": 1,
            "raw_stdout": b'', "raw_stderr": b''
        }

@pytest.mark.parametrize(
    "test_data",
    TEST_CASES,
    ids=[t["id"] for t in TEST_CASES]
)
def test_currency(test_data, compiled_runners, request):
    """Test that Mojo and C++ currency implementations match."""
    currency_code = test_data["currency_code"]
    
    if not compiled_runners["cpp"]["success"]:
        pytest.skip(f"C++ runner compilation failed: {compiled_runners['cpp']['output']}")
    
    if not compiled_runners["mojo"]["success"]:
        pytest.skip(f"Mojo runner compilation failed: {compiled_runners['mojo']['output']}")
    
    cpp_result = run_executable(compiled_runners["cpp"]["runner_path"], currency_code)
    mojo_result = run_executable(compiled_runners["mojo"]["runner_path"], currency_code)

    inputs = {"Currency Code": currency_code}
    request.node.inputs = inputs
    request.node.cpp_output = cpp_result["stdout"]
    request.node.mojo_output = mojo_result["stdout"]
    
    assert cpp_result["success"], f"C++ runner failed for '{currency_code}': {cpp_result['stderr']}"
    assert mojo_result["success"], f"Mojo runner failed for '{currency_code}': {mojo_result['stderr']}"
    
    detailed_diffs_data = []
    assertion_passed = True
    error_message_summary = f"Outputs for {currency_code} differ."
    
    if cpp_result["stdout"] != mojo_result["stdout"]:
        assertion_passed = False
        cpp_lines = cpp_result["stdout"].strip().split('\n')
        mojo_lines = mojo_result["stdout"].strip().split('\n')
        
        diff_details_for_error_message = "\n--- Differences ---"
    
        max_lines = max(len(cpp_lines), len(mojo_lines))
        for i in range(max_lines):
            cpp_line = cpp_lines[i] if i < len(cpp_lines) else None
            mojo_line = mojo_lines[i] if i < len(mojo_lines) else None
    
            if cpp_line != mojo_line:
                current_diff = {
                    "type": "line_diff", "line_num": i + 1,
                    "cpp_line": cpp_line if cpp_line is not None else "<missing>",
                    "mojo_line": mojo_line if mojo_line is not None else "<missing>"
                }
                detailed_diffs_data.append(current_diff)
                diff_details_for_error_message += f"\nLine {current_diff['line_num']} differs:"
                diff_details_for_error_message += f"\n  C++ : '{current_diff['cpp_line']}'"
                diff_details_for_error_message += f"\n  Mojo: '{current_diff['mojo_line']}'"
    
        if len(cpp_lines) != len(mojo_lines):
            length_diff_data = {
                "type": "length_diff", "cpp_len": len(cpp_lines), "mojo_len": len(mojo_lines),
                "cpp_lines_preview": cpp_lines[:5], "mojo_lines_preview": mojo_lines[:5]
            }
            detailed_diffs_data.append(length_diff_data)
            diff_details_for_error_message += f"\nOutput length differs: C++ ({length_diff_data['cpp_len']} lines), Mojo ({length_diff_data['mojo_len']} lines)."
        
        request.node.detailed_diffs_data = detailed_diffs_data
        if not assertion_passed:
            error_message_summary += diff_details_for_error_message

    assert assertion_passed, error_message_summary

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__])) 