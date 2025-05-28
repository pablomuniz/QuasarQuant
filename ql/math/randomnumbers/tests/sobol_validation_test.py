import pytest
import subprocess
import os
from pathlib import Path
import re
import math

# Get script directory and project root (similar to the Europe currencies test)
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = (SCRIPT_DIR / "../../../..").resolve()

# Define paths for runner source files and compiled executables
CPP_SOURCE_FILE = SCRIPT_DIR / "sobol_cpp_runner.cpp"
CPP_RUNNER_PATH = SCRIPT_DIR / "sobol_cpp_runner_compiled"
MOJO_RUNNER_SOURCE = SCRIPT_DIR / "sobol_mojo_runner.mojo"
MOJO_RUNNER_PATH = SCRIPT_DIR / "sobol_mojo_runner_compiled"

# Define test cases - different dimensionalities and sequence lengths
TEST_CASES = [
    # === BASIC TESTS (Original) ===
    {
        "id": "sobol_2d_5seq", 
        "description": "Test 2D Sobol sequences with 5 samples",
        "dimensions": 2,
        "sequences": 5
    },
    {
        "id": "sobol_6d_3seq",
        "description": "Test 6D Sobol sequences with 3 samples",
        "dimensions": 6,
        "sequences": 3
    },
    {
        "id": "sobol_3d_10seq",
        "description": "Test 3D Sobol sequences with 10 samples", 
        "dimensions": 3,
        "sequences": 10
    },
    
    # === EDGE CASES ===
    {
        "id": "sobol_1d_1seq",
        "description": "Test 1D single sample (simplest case)",
        "dimensions": 1,
        "sequences": 1
    },
    {
        "id": "sobol_1d_20seq",
        "description": "Test 1D with 20 samples",
        "dimensions": 1,
        "sequences": 20
    },
    
    # === LOW DIMENSIONS, VARIOUS LENGTHS ===
    {
        "id": "sobol_2d_1seq",
        "description": "Test 2D single sample",
        "dimensions": 2,
        "sequences": 1
    },
    {
        "id": "sobol_2d_15seq",
        "description": "Test 2D with 15 samples",
        "dimensions": 2,
        "sequences": 15
    },
    {
        "id": "sobol_3d_25seq",
        "description": "Test 3D with 25 samples",
        "dimensions": 3,
        "sequences": 25
    },
    {
        "id": "sobol_4d_12seq",
        "description": "Test 4D with 12 samples",
        "dimensions": 4,
        "sequences": 12
    },
    {
        "id": "sobol_5d_8seq",
        "description": "Test 5D with 8 samples",
        "dimensions": 5,
        "sequences": 8
    },
    
    # === MEDIUM DIMENSIONS ===
    {
        "id": "sobol_7d_10seq",
        "description": "Test 7D with 10 samples",
        "dimensions": 7,
        "sequences": 10
    },
    {
        "id": "sobol_8d_15seq",
        "description": "Test 8D with 15 samples",
        "dimensions": 8,
        "sequences": 15
    },
    {
        "id": "sobol_9d_7seq",
        "description": "Test 9D with 7 samples",
        "dimensions": 9,
        "sequences": 7
    },
    {
        "id": "sobol_10d_5seq",
        "description": "Test 10D with 5 samples",
        "dimensions": 10,
        "sequences": 5
    },
    
    # === LONGER SEQUENCES ===
    {
        "id": "sobol_2d_50seq",
        "description": "Test 2D with 50 samples",
        "dimensions": 2,
        "sequences": 50
    },
    {
        "id": "sobol_3d_100seq",
        "description": "Test 3D with 100 samples",
        "dimensions": 3,
        "sequences": 100
    },
    {
        "id": "sobol_4d_30seq",
        "description": "Test 4D with 30 samples", 
        "dimensions": 4,
        "sequences": 30
    },
    {
        "id": "sobol_5d_40seq",
        "description": "Test 5D with 40 samples",
        "dimensions": 5,
        "sequences": 40
    },
    
    # === HIGH DIMENSIONS ===
    {
        "id": "sobol_12d_8seq",
        "description": "Test 12D with 8 samples",
        "dimensions": 12,
        "sequences": 8
    },
    {
        "id": "sobol_15d_6seq",
        "description": "Test 15D with 6 samples",
        "dimensions": 15,
        "sequences": 6
    },
    {
        "id": "sobol_20d_5seq",
        "description": "Test 20D with 5 samples",
        "dimensions": 20,
        "sequences": 5
    },
    {
        "id": "sobol_25d_4seq",
        "description": "Test 25D with 4 samples",
        "dimensions": 25,
        "sequences": 4
    },
    
    # === STRESS TESTS ===
    {
        "id": "sobol_6d_200seq",
        "description": "Stress test: 6D with 200 samples",
        "dimensions": 6,
        "sequences": 200
    },
    {
        "id": "sobol_8d_150seq",
        "description": "Stress test: 8D with 150 samples",
        "dimensions": 8,
        "sequences": 150
    },
    {
        "id": "sobol_10d_100seq",
        "description": "Stress test: 10D with 100 samples",
        "dimensions": 10,
        "sequences": 100
    },
    
    # === POWER-OF-2 SEQUENCES (Important for Sobol) ===
    {
        "id": "sobol_3d_32seq",
        "description": "Test 3D with 32 samples (2^5)",
        "dimensions": 3,
        "sequences": 32
    },
    {
        "id": "sobol_4d_64seq",
        "description": "Test 4D with 64 samples (2^6)",
        "dimensions": 4,
        "sequences": 64
    },
    {
        "id": "sobol_5d_128seq",
        "description": "Test 5D with 128 samples (2^7)",
        "dimensions": 5,
        "sequences": 128
    },
    
    # === LARGE STRESS TESTS ===
    {
        "id": "sobol_2d_1000seq",
        "description": "Large stress test: 2D with 1000 samples",
        "dimensions": 2,
        "sequences": 1000
    },
    {
        "id": "sobol_3d_500seq",
        "description": "Large stress test: 3D with 500 samples",
        "dimensions": 3,
        "sequences": 500
    },
    {
        "id": "sobol_6d_250seq",
        "description": "Large stress test: 6D with 250 samples",
        "dimensions": 6,
        "sequences": 250
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
                print(f"[DEBUG C++] Sobol C++ runner up-to-date. Skipping compilation.", file=sys.stderr)
                return {
                    "success": True,
                    "output": "C++ runner already compiled and up-to-date.",
                    "exit_code": 0
                }
        except FileNotFoundError:
            pass 

    import sys
    print(f"[DEBUG C++] Compiling Sobol C++ runner: {CPP_RUNNER_PATH}", file=sys.stderr)

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
            "output": f"Error compiling C++ runner: {e}",
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

    if MOJO_RUNNER_PATH.exists():
        try:
            source_mtime = MOJO_RUNNER_SOURCE.stat().st_mtime
            executable_mtime = MOJO_RUNNER_PATH.stat().st_mtime

            if executable_mtime >= source_mtime:
                import sys
                print(f"[DEBUG MOJO] Sobol Mojo runner up-to-date. Skipping compilation.", file=sys.stderr)
                return {
                    "success": True,
                    "output": "Mojo runner already compiled and up-to-date.",
                    "exit_code": 0
                }
        except FileNotFoundError:
            pass

    import sys
    print(f"[DEBUG MOJO] Compiling Sobol Mojo runner: {MOJO_RUNNER_PATH}", file=sys.stderr)
    
    try:
        cmd = ["mojo", "build", str(MOJO_RUNNER_SOURCE), "-o", str(MOJO_RUNNER_PATH)]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            cwd=PROJECT_ROOT
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"Error compiling Mojo runner: {e}",
            "exit_code": 1
        }

def run_executable(executable_path, dimensions, sequences):
    """Run the given executable with dimensions and sequences args."""
    try:
        env_vars = os.environ.copy()
        env_vars["LANG"] = "en_US.UTF-8"
        env_vars["LC_ALL"] = "en_US.UTF-8"

        process = subprocess.run(
            [str(executable_path), str(dimensions), str(sequences)],
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
    # Sample format: "Sample 0 : 0.500000000000000 0.500000000000000 weight: 1.000000000000000"
    pattern = r'Sample\s+(\d+)\s*:\s*([\d\.\-e\+\s]+)\s*weight:\s*([\d\.\-e\+]+)'
    match = re.match(pattern, line.strip())
    if not match:
        return None
    
    sample_num = int(match.group(1))
    values_str = match.group(2).strip()
    weight = float(match.group(3))
    
    # Parse the space-separated values
    values = [float(x) for x in values_str.split()]
    
    return {
        "sample_num": sample_num,
        "values": values, 
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
        
        if len(cpp_sample["values"]) != len(mojo_sample["values"]):
            return False, f"Different number of values at line {i+1}: C++ {len(cpp_sample['values'])}, Mojo {len(mojo_sample['values'])}"
        
        # Compare each value with tolerance
        for j, (cpp_val, mojo_val) in enumerate(zip(cpp_sample["values"], mojo_sample["values"])):
            if abs(cpp_val - mojo_val) > tolerance:
                return False, f"Value mismatch at line {i+1}, position {j}: C++ {cpp_val}, Mojo {mojo_val}, diff {abs(cpp_val - mojo_val)}"
        
        # Compare weight
        if abs(cpp_sample["weight"] - mojo_sample["weight"]) > tolerance:
            return False, f"Weight mismatch at line {i+1}: C++ {cpp_sample['weight']}, Mojo {mojo_sample['weight']}"
    
    return True, "All values match within tolerance"

@pytest.mark.parametrize(
    "test_data",
    TEST_CASES,
    ids=[t["id"] for t in TEST_CASES]
)
def test_sobol_sequences(test_data, compiled_runners, request):
    """Test that Mojo and C++ Sobol implementations match exactly."""
    dimensions = test_data["dimensions"]
    sequences = test_data["sequences"]
    
    # Skip test if compilation failed
    if not compiled_runners["cpp"]["success"]:
        pytest.skip(f"C++ runner compilation failed: {compiled_runners['cpp']['output']}")
    
    if not compiled_runners["mojo"]["success"]:
        pytest.skip(f"Mojo runner compilation failed: {compiled_runners['mojo']['output']}")
    
    # Run the C++ and Mojo executables
    cpp_result = run_executable(compiled_runners["cpp"]["runner_path"], dimensions, sequences)
    mojo_result = run_executable(compiled_runners["mojo"]["runner_path"], dimensions, sequences)

    # Prepare test inputs
    inputs = {"Dimensions": dimensions, "Sequences": sequences}
    
    # Attach data to request.node for the plugin to access
    request.node.inputs = inputs
    request.node.cpp_output = cpp_result["stdout"]
    request.node.mojo_output = mojo_result["stdout"]
    
    # Verify both executables ran successfully
    assert cpp_result["success"], f"C++ runner failed for {dimensions}D x {sequences} sequences with exit code {cpp_result['exit_code']}: {cpp_result['stderr']}"
    assert mojo_result["success"], f"Mojo runner failed for {dimensions}D x {sequences} sequences with exit code {mojo_result['exit_code']}: {mojo_result['stderr']}"
    
    # Compare numerical values instead of exact string matching
    numerical_match, comparison_message = compare_numerical_output(cpp_result["stdout"], mojo_result["stdout"])
    
    if numerical_match:
        # Values match - test passes
        return
    
    # Values don't match - provide detailed error information
    detailed_diffs_data = []
    assertion_passed = False
    error_message_summary = f"Sobol sequences for {dimensions}D x {sequences} differ numerically: {comparison_message}"
    
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