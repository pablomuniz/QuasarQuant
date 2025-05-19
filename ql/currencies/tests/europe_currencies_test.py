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
    """Compile the C++ runner executable."""
    if not CPP_SOURCE_FILE.exists():
        return {
            "success": False,
            "output": f"ERROR: C++ source file {CPP_SOURCE_FILE} not found.",
            "exit_code": 1
        }
    
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
    """Compile the Mojo runner executable."""
    if not MOJO_RUNNER_SOURCE.exists():
        return {
            "success": False,
            "output": f"ERROR: Mojo source file {MOJO_RUNNER_SOURCE} not found.",
            "exit_code": 1
        }
    
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
        result = subprocess.run(
            [str(executable_path), currency_code],
            capture_output=True,
            text=True
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Error running executable: {e}",
            "exit_code": 1
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
    
    # Prepare test inputs (currency code)
    inputs = {"Currency Code": currency_code}
    
    # Attach data to request.node for the plugin to access
    request.node.inputs = inputs
    request.node.cpp_output = cpp_result["stdout"]
    request.node.mojo_output = mojo_result["stdout"]
    
    # Mark the test with description for better reporting
    pytest.mark.description(test_data["description"])
    
    # Verify both executables ran successfully
    assert cpp_result["success"], f"C++ runner failed with exit code {cpp_result['exit_code']}: {cpp_result['stderr']}"
    assert mojo_result["success"], f"Mojo runner failed with exit code {mojo_result['exit_code']}: {mojo_result['stderr']}"
    
    # --- BEGIN MODIFICATION: Structured diff generation ---
    detailed_diffs_data = []
    assertion_passed = True
    error_message_summary = f"Outputs for {currency_code} differ."

    if cpp_result["stdout"] != mojo_result["stdout"]:
        assertion_passed = False
        cpp_lines = cpp_result["stdout"].strip().split('\n')
        mojo_lines = mojo_result["stdout"].strip().split('\n')
        
        max_lines = max(len(cpp_lines), len(mojo_lines))
        for i in range(max_lines):
            cpp_line = cpp_lines[i] if i < len(cpp_lines) else None
            mojo_line = mojo_lines[i] if i < len(mojo_lines) else None
            
            if cpp_line != mojo_line:
                detailed_diffs_data.append({
                    "type": "line_diff",
                    "line_num": i + 1,
                    "cpp_line": cpp_line if cpp_line is not None else "<missing>",
                    "mojo_line": mojo_line if mojo_line is not None else "<missing>"
                })

        if len(cpp_lines) != len(mojo_lines):
            # Add a specific entry for length difference
            detailed_diffs_data.append({
                "type": "length_diff",
                "cpp_len": len(cpp_lines),
                "mojo_len": len(mojo_lines),
                "cpp_lines_preview": cpp_lines[:5], # Preview first 5 lines
                "mojo_lines_preview": mojo_lines[:5] # Preview first 5 lines
            })
        
        # Attach the structured diff data to the request node
        request.node.detailed_diffs_data = detailed_diffs_data
    # --- END MODIFICATION ---

    # Simplified assertion based on the flag
    assert assertion_passed, error_message_summary

# For standalone execution (outside pytest)
if __name__ == "__main__":
    # Use pytest's main function to run the tests
    import sys
    sys.exit(pytest.main(["-v", __file__])) 