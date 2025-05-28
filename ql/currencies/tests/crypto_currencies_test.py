import pytest
import subprocess
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Get script directory and project root
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "../../..").resolve()

# Define paths for runner source files and compiled executables
CPP_SOURCE_FILE = SCRIPT_DIR / "test_cpp_crypto_runner.cpp"
CPP_RUNNER_PATH = SCRIPT_DIR / "test_cpp_crypto_runner_compiled"
MOJO_RUNNER_SOURCE = SCRIPT_DIR / "crypto_runner.mojo"
MOJO_RUNNER_PATH = SCRIPT_DIR / "crypto_mojo_runner_compiled"
CRYPTO_MOJO_DEPENDENCY = (SCRIPT_DIR / "../crypto.mojo").resolve()

# Define currency codes to test
CURRENCY_CODES = [
    "BTC", "ETH", "ETC", "BCH", "XRP", "LTC", "DASH", "ZEC"
]

TEST_CASES = [
    {
        "id": f"crypto_currency_{code}",
        "description": f"Test for Crypto currency {code}",
        "currency_code": code
    }
    for code in CURRENCY_CODES
]

@pytest.fixture(scope="session")
def compiled_runners():
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
    if not CPP_SOURCE_FILE.exists():
        return {"success": False, "output": f"ERROR: C++ source {CPP_SOURCE_FILE} not found.", "exit_code": 1}
    if CPP_RUNNER_PATH.exists():
        try:
            if CPP_RUNNER_PATH.stat().st_mtime >= CPP_SOURCE_FILE.stat().st_mtime:
                return {"success": True, "output": "C++ runner up-to-date.", "exit_code": 0}
        except FileNotFoundError:
            pass 
    try:
        cmd = [
            "g++", "-std=c++17", f"-I{PROJECT_ROOT}", "-I/usr/local/include",
            str(CPP_SOURCE_FILE), "-o", str(CPP_RUNNER_PATH),
            "-L/usr/local/lib", "-lQuantLib", "-pthread"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
    except Exception as e:
        return {"success": False, "output": f"Error compiling C++ Crypto runner: {e}", "exit_code": 1}

def compile_mojo_runner():
    if not MOJO_RUNNER_SOURCE.exists():
        return {"success": False, "output": f"ERROR: Mojo source {MOJO_RUNNER_SOURCE} not found.", "exit_code": 1}
    if not CRYPTO_MOJO_DEPENDENCY.exists():
        return {"success": False, "output": f"ERROR: Mojo dependency {CRYPTO_MOJO_DEPENDENCY} not found.", "exit_code": 1}
    
    recompile = False
    if not MOJO_RUNNER_PATH.exists():
        recompile = True
    else:
        try:
            if MOJO_RUNNER_PATH.stat().st_mtime < MOJO_RUNNER_SOURCE.stat().st_mtime or \
               MOJO_RUNNER_PATH.stat().st_mtime < CRYPTO_MOJO_DEPENDENCY.stat().st_mtime:
                recompile = True
        except FileNotFoundError:
            recompile = True

    if not recompile:
        return {"success": True, "output": "Mojo runner up-to-date.", "exit_code": 0}

    try:
        cmd = ["mojo", "build", str(MOJO_RUNNER_SOURCE), "-o", str(MOJO_RUNNER_PATH)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        return {"success": result.returncode == 0, "output": result.stdout + result.stderr, "exit_code": result.returncode}
    except Exception as e:
        return {"success": False, "output": f"Error compiling Mojo Crypto runner: {e}", "exit_code": 1}

def run_executable(executable_path, currency_code):
    try:
        env_vars = os.environ.copy()
        env_vars["LANG"] = "en_US.UTF-8"
        env_vars["LC_ALL"] = "en_US.UTF-8"
        process = subprocess.run([str(executable_path), currency_code], capture_output=True, env=env_vars)
        return {
            "success": process.returncode == 0,
            "stdout": process.stdout.decode('utf-8', errors='replace'),
            "stderr": process.stderr.decode('utf-8', errors='replace'),
            "exit_code": process.returncode
        }
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": f"Error running executable: {e}", "exit_code": 1}

@pytest.mark.parametrize("test_data", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_currency(test_data, compiled_runners, request):
    currency_code = test_data["currency_code"]
    if not compiled_runners["cpp"]["success"]:
        pytest.skip(f"C++ runner compilation failed: {compiled_runners['cpp']['output']}")
    if not compiled_runners["mojo"]["success"]:
        pytest.skip(f"Mojo runner compilation failed: {compiled_runners['mojo']['output']}")
    
    cpp_result = run_executable(compiled_runners["cpp"]["runner_path"], currency_code)
    mojo_result = run_executable(compiled_runners["mojo"]["runner_path"], currency_code)
    
    assert cpp_result["success"], f"C++ runner failed for '{currency_code}': {cpp_result['stderr']}"
    assert mojo_result["success"], f"Mojo runner failed for '{currency_code}': {mojo_result['stderr']}"
    
    if cpp_result["stdout"] != mojo_result["stdout"]:
        cpp_lines = cpp_result["stdout"].strip().split('\n')
        mojo_lines = mojo_result["stdout"].strip().split('\n')
        diff_details = "\n--- Differences ---"
        max_lines = max(len(cpp_lines), len(mojo_lines))
        for i in range(max_lines):
            cl = cpp_lines[i] if i < len(cpp_lines) else "<missing>"
            ml = mojo_lines[i] if i < len(mojo_lines) else "<missing>"
            if cl != ml:
                diff_details += f"\nLine {i+1} differs:\n  C++ : '{cl}'\n  Mojo: '{ml}'"
        if len(cpp_lines) != len(mojo_lines):
            diff_details += f"\nOutput length differs: C++ ({len(cpp_lines)} lines), Mojo ({len(mojo_lines)} lines)."
        assert False, f"Outputs for {currency_code} differ.{diff_details}"

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__])) 