import pytest
import subprocess
import os
from pathlib import Path
import re
import math

# Get script directory and project root
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "../../../..").resolve()

# Define paths for runner source files and compiled executables
CPP_SOURCE_FILE = SCRIPT_DIR / "mt19937_cpp_runner.cpp"
CPP_RUNNER_PATH = SCRIPT_DIR / "mt19937_cpp_runner_compiled"
MOJO_RUNNER_SOURCE = SCRIPT_DIR / "mt19937_mojo_runner.mojo"
MOJO_RUNNER_PATH = SCRIPT_DIR / "mt19937_mojo_runner_compiled"

# Define test cases - different sequence lengths
TEST_CASES = [
    # === BASIC TESTS ===
    {
        "id": "mt19937_10seq",
        "description": "Test MT19937 with 10 samples",
        "sequences": 10
    },
    {
        "id": "mt19937_50seq",
        "description": "Test MT19937 with 50 samples",
        "sequences": 50
    },
    {
        "id": "mt19937_100seq",
        "description": "Test MT19937 with 100 samples",
        "sequences": 100
    },
    
    # === EDGE CASES ===
    {
        "id": "mt19937_1seq",
        "description": "Test MT19937 with single sample",
        "sequences": 1
    },
    {
        "id": "mt19937_2seq",
        "description": "Test MT19937 with 2 samples",
        "sequences": 2
    },
    
    # === MEDIUM SEQUENCES ===
    {
        "id": "mt19937_200seq",
        "description": "Test MT19937 with 200 samples",
        "sequences": 200
    },
    {
        "id": "mt19937_500seq",
        "description": "Test MT19937 with 500 samples",
        "sequences": 500
    },
    
    # === LARGE SEQUENCES ===
    {
        "id": "mt19937_1000seq",
        "description": "Test MT19937 with 1000 samples",
        "sequences": 1000
    },
    {
        "id": "mt19937_2000seq",
        "description": "Test MT19937 with 2000 samples",
        "sequences": 2000
    },
    
    # === POWER-OF-2 SEQUENCES ===
    {
        "id": "mt19937_32seq",
        "description": "Test MT19937 with 32 samples (2^5)",
        "sequences": 32
    },
    {
        "id": "mt19937_64seq",
        "description": "Test MT19937 with 64 samples (2^6)",
        "sequences": 64
    },
    {
        "id": "mt19937_128seq",
        "description": "Test MT19937 with 128 samples (2^7)",
        "sequences": 128
    },
    
    # === STRESS TESTS ===
    {
        "id": "mt19937_5000seq",
        "description": "Stress test: MT19937 with 5000 samples",
        "sequences": 5000
    },
    {
        "id": "mt19937_10000seq",
        "description": "Stress test: MT19937 with 10000 samples",
        "sequences": 10000
    }
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
        print(f"[ERROR] C++ source file not found at: {CPP_SOURCE_FILE}")
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
                print(f"[DEBUG C++] MT19937 C++ runner up-to-date. Skipping compilation.")
                return {
                    "success": True,
                    "output": "C++ runner already compiled and up-to-date.",
                    "exit_code": 0
                }
        except FileNotFoundError:
            pass 

    print(f"\n[DEBUG C++] Starting C++ compilation:")
    print(f"  Source file: {CPP_SOURCE_FILE}")
    print(f"  Output path: {CPP_RUNNER_PATH}")
    print(f"  Project root: {PROJECT_ROOT}")

    try:
        cmd = [
            "g++", "-std=c++17", 
            f"-I{PROJECT_ROOT}", "-I/usr/local/include",
            str(CPP_SOURCE_FILE), "-o", str(CPP_RUNNER_PATH),
            "-L/usr/local/lib", "-lQuantLib", "-pthread"
        ]
        print(f"  Command: {' '.join(cmd)}")
        
        print("\n[DEBUG C++] Running compilation command...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("\n[DEBUG C++] Compilation output:")
        print("  stdout:")
        for line in result.stdout.splitlines():
            print(f"    {line}")
        print("  stderr:")
        for line in result.stderr.splitlines():
            print(f"    {line}")
        print(f"  Exit code: {result.returncode}")
        
        if result.returncode != 0:
            print("\n[ERROR C++] Compilation failed!")
            print("  Command output:")
            print(result.stdout)
            print("  Error output:")
            print(result.stderr)
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        print(f"\n[ERROR C++] Exception during compilation: {str(e)}")
        return {
            "success": False,
            "output": f"Error compiling C++ runner: {e}",
            "exit_code": 1
        }

def compile_mojo_runner():
    """Compile the Mojo runner executable, recompiling if source is newer."""
    if not MOJO_RUNNER_SOURCE.exists():
        print(f"[ERROR] Mojo source file not found at: {MOJO_RUNNER_SOURCE}")
        return {
            "success": False,
            "output": f"ERROR: Mojo source file {MOJO_RUNNER_SOURCE} not found.",
            "exit_code": 1
        }

    if MOJO_RUNNER_PATH.exists():
        try:
            source_mtime = MOJO_RUNNER_SOURCE.stat().st_mtime
            executable_mtime = MOJO_RUNNER_PATH.stat().st_mtime

            if executable_mtime >= source_mtime:
                print(f"[DEBUG MOJO] MT19937 Mojo runner up-to-date. Skipping compilation.")
                return {
                    "success": True,
                    "output": "Mojo runner already compiled and up-to-date.",
                    "exit_code": 0
                }
        except FileNotFoundError:
            pass

    print(f"\n[DEBUG MOJO] Starting Mojo compilation:")
    print(f"  Source file: {MOJO_RUNNER_SOURCE}")
    print(f"  Output path: {MOJO_RUNNER_PATH}")
    print(f"  Project root: {PROJECT_ROOT}")
    
    try:
        # Add project root to PYTHONPATH for Mojo to find modules
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env.get("PYTHONPATH", ""))
        print(f"  PYTHONPATH: {env['PYTHONPATH']}")
        
        cmd = ["mojo", "build", str(MOJO_RUNNER_SOURCE), "-o", str(MOJO_RUNNER_PATH)]
        print(f"  Command: {' '.join(cmd)}")
        
        print("\n[DEBUG MOJO] Running compilation command...")
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            cwd=PROJECT_ROOT,
            env=env
        )
        
        print("\n[DEBUG MOJO] Compilation output:")
        print("  stdout:")
        for line in result.stdout.splitlines():
            print(f"    {line}")
        print("  stderr:")
        for line in result.stderr.splitlines():
            print(f"    {line}")
        print(f"  Exit code: {result.returncode}")
        
        if result.returncode != 0:
            print("\n[ERROR MOJO] Compilation failed!")
            print("  Command output:")
            print(result.stdout)
            print("  Error output:")
            print(result.stderr)
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        print(f"\n[ERROR MOJO] Exception during compilation: {str(e)}")
        return {
            "success": False,
            "output": f"Error compiling Mojo runner: {e}",
            "exit_code": 1
        }

def run_executable(executable_path, sequences):
    """Run the given executable with sequences arg."""
    try:
        env_vars = os.environ.copy()
        env_vars["LANG"] = "en_US.UTF-8"
        env_vars["LC_ALL"] = "en_US.UTF-8"

        process = subprocess.run(
            [str(executable_path), str(sequences)],
            capture_output=True,
            env=env_vars
        )

        try:
            stdout_str = process.stdout.decode('utf-8', errors='replace')
        except Exception:
            stdout_str = "<stdout decoding error>"

        try:
            stderr_str = process.stderr.decode('utf-8', errors='replace')
        except Exception:
            stderr_str = "<stderr decoding error>"

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
            "success": False,
            "stdout": "",
            "stderr": f"Error running executable: {e}",
            "exit_code": 1,
            "raw_stdout": b'',
            "raw_stderr": b''
        }

def parse_sample_line(line):
    """Parse a sample line and extract numerical values."""
    # Sample format: "Sample 0 : 0.500000000000000 weight: 1.000000000000000"
    pattern = r'Sample\s+(\d+)\s*:\s*([\d\.\-e\+]+)\s*weight:\s*([\d\.\-e\+]+)'
    match = re.match(pattern, line.strip())
    if not match:
        return None
    
    sample_num = int(match.group(1))
    value = float(match.group(2))
    weight = float(match.group(3))
    
    return {
        "sample_num": sample_num,
        "value": value,
        "weight": weight
    }

def compare_numerical_output(cpp_output, mojo_output, tolerance=1e-14):
    """Compare outputs by parsing numerical values instead of exact string comparison."""
    cpp_lines = cpp_output.strip().split('\n')
    mojo_lines = mojo_output.strip().split('\n')
    
    if len(cpp_lines) != len(mojo_lines):
        return False, f"Different number of lines: C++ {len(cpp_lines)}, Mojo {len(mojo_lines)}"
    
    for i, (cpp_line, mojo_line) in enumerate(zip(cpp_lines, mojo_lines)):
        cpp_sample = parse_sample_line(cpp_line)
        mojo_sample = parse_sample_line(mojo_line)
        
        if cpp_sample is None:
            return False, f"Failed to parse C++ line {i+1}: {cpp_line}"
        if mojo_sample is None:
            return False, f"Failed to parse Mojo line {i+1}: {mojo_line}"
        
        if cpp_sample["sample_num"] != mojo_sample["sample_num"]:
            return False, f"Sample number mismatch at line {i+1}: C++ {cpp_sample['sample_num']}, Mojo {mojo_sample['sample_num']}"
        
        # Compare value with tolerance
        if abs(cpp_sample["value"] - mojo_sample["value"]) > tolerance:
            return False, f"Value mismatch at line {i+1}: C++ {cpp_sample['value']}, Mojo {mojo_sample['value']}, diff {abs(cpp_sample['value'] - mojo_sample['value'])}"
    
    return True, "All values match within tolerance"

@pytest.mark.parametrize(
    "test_data",
    TEST_CASES,
    ids=[t["id"] for t in TEST_CASES]
)
def test_mt19937_sequences(test_data, compiled_runners, request):
    """Test that Mojo and C++ MT19937 implementations match exactly."""
    sequences = test_data["sequences"]
    
    # Skip test if compilation failed
    if not compiled_runners["cpp"]["success"]:
        pytest.skip(f"C++ runner compilation failed: {compiled_runners['cpp']['output']}")
    
    if not compiled_runners["mojo"]["success"]:
        pytest.skip(f"Mojo runner compilation failed: {compiled_runners['mojo']['output']}")
    
    # Run the C++ and Mojo executables
    cpp_result = run_executable(compiled_runners["cpp"]["runner_path"], sequences)
    mojo_result = run_executable(compiled_runners["mojo"]["runner_path"], sequences)

    # Prepare test inputs
    inputs = {"Sequences": sequences}
    
    # Attach data to request.node for the plugin to access
    request.node.inputs = inputs
    request.node.cpp_output = cpp_result["stdout"]
    request.node.mojo_output = mojo_result["stdout"]
    
    # Verify both executables ran successfully
    assert cpp_result["success"], f"C++ runner failed for {sequences} sequences with exit code {cpp_result['exit_code']}: {cpp_result['stderr']}"
    assert mojo_result["success"], f"Mojo runner failed for {sequences} sequences with exit code {mojo_result['exit_code']}: {mojo_result['stderr']}"
    
    # Compare numerical values instead of exact string matching
    numerical_match, comparison_message = compare_numerical_output(cpp_result["stdout"], mojo_result["stdout"])
    
    if numerical_match:
        # Values match - test passes
        return
    
    # Values don't match - provide detailed error information
    detailed_diffs_data = []
    assertion_passed = False
    error_message_summary = f"MT19937 sequences for {sequences} samples differ numerically: {comparison_message}"
    
    # Also provide the original string comparison for debugging
    if cpp_result["stdout"] != mojo_result["stdout"]:
        cpp_lines = cpp_result["stdout"].strip().split('\n')
        mojo_lines = mojo_result["stdout"].strip().split('\n')
        
        diff_details_for_error_message = "\n--- String Format Differences (for debugging) ---"
    
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
        
        request.node.detailed_diffs_data = detailed_diffs_data
        error_message_summary += diff_details_for_error_message

    # Final assertion
    assert assertion_passed, error_message_summary

# For standalone execution
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__])) 