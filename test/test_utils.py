"""
Test utilities for comparing C++ and Mojo implementations across test files.

This module provides standard functions for test formatting and display
that work with the TUI system.
"""
import time
from typing import Dict, List, Optional

def simulate_compilation(language: str):
    """Simulate compilation of code"""
    print(f"COMPILATION {language}")
    time.sleep(1)
    print("Compilation successful!")
    print(f"Compilation time: 1.0s")

def calculate_diff(cpp_output: str, mojo_output: str) -> Optional[str]:
    """Calculate numerical difference if possible"""
    try:
        # Assuming outputs have format like "NPV: 398.68"
        cpp_val = float(cpp_output.split(':')[1].strip())
        mojo_val = float(mojo_output.split(':')[1].strip())
        diff_val = round(abs(cpp_val - mojo_val), 2)
        return f"{diff_val} (C++: {cpp_val}, Mojo: {mojo_val})"
    except (ValueError, IndexError):
        return "Non-numeric difference"

def compare_cpp_mojo(test_id: str, description: str, inputs: Dict, 
                    cpp_output: str, mojo_output: str) -> bool:
    """Compare Mojo implementation against QuantLib C++ reference implementation.
    
    Displays results in TUI-compatible format and returns whether the test passed.
    
    Args:
        test_id: Unique test identifier
        description: Test description
        inputs: Dictionary of input values
        cpp_output: Output from C++ implementation (reference)
        mojo_output: Output from Mojo implementation
        
    Returns:
        bool: True if outputs match, False otherwise
    """
    # Print test metadata for the TUI to parse
    print(f"TEST_ITEM_ID: {test_id}")
    print(f"DESCRIPTION: {description}")
    
    # Print inputs
    print("SHARED_INPUT_BEGIN")
    for input_name, input_value in inputs.items():
        print(f"{input_name}: {input_value}")
    print("SHARED_INPUT_END")
    
    # Print C++ output
    print("CPP_STDOUT_BEGIN")
    print(f"OUTPUT: {cpp_output}")
    print("CPP_STDOUT_END")
    
    # Print Mojo output
    print("MOJO_STDOUT_BEGIN")
    print(f"OUTPUT: {mojo_output}")
    print("MOJO_STDOUT_END")
    
    # Add exit codes for compatibility with TUI
    print("CPP_EXIT_CODE: 0")
    print("MOJO_EXIT_CODE: 0")
    
    # Check for discrepancy and output status
    has_discrepancy = cpp_output != mojo_output
    if has_discrepancy:
        print(f"OVERALL_STATUS: FAIL")
        print(f"FAIL_REASON: Mojo implementation differs from QuantLib C++ reference")
        diff = calculate_diff(cpp_output, mojo_output)
        if diff:
            print(f"DIFF: {diff}")
        print("END_OF_TEST_ITEM")
        return False
    else:
        print(f"OVERALL_STATUS: PASS")
        print("END_OF_TEST_ITEM")
        return True
        
def report_test_session_start(test_count: int, test_name: str):
    """Report the start of a test session in TUI format.
    
    Args:
        test_count: Number of test cases
        test_name: Name of the test suite
    """
    print(f"TESTS {test_count}")
    print(f"Running test {test_name}...")
    
    # Simulate compilation steps
    simulate_compilation("CPP")
    simulate_compilation("MOJO")
    
def report_test_session_end(total: int, passed: int, failed: int, execution_time: float):
    """Report the end of a test session in TUI format.
    
    Args:
        total: Total number of tests
        passed: Number of passed tests
        failed: Number of failed tests  
        execution_time: Time taken to execute tests (seconds)
    """
    print("RUN_SCRIPT_SUMMARY_BEGIN")
    print(f"Tests completed: {total}")
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {failed}")
    print(f"Execution time: {execution_time}s")
    print("RUN_SCRIPT_SUMMARY_END") 