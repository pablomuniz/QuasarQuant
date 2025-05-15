#!/usr/bin/env python
import time
import sys

if __name__ == "__main__":
    print("Running test pepe (Python version)...")
    print("Compiling test code (Python version)...")
    time.sleep(1)
    print("Compilation successful (Python version)!")

    # First test item
    print("TEST_ITEM_ID: test-pepe-py-001")
    print("DESCRIPTION: Simple Python test for cash flow calculations")
    print("OVERALL_STATUS: PASS")
    print("CPP_EXIT_CODE: 0")
    print("MOJO_EXIT_CODE: 0")

    print("CPP_STDOUT_BEGIN")
    print("Python Cash flow value: 100.00")
    print("Python Interest rate: 0.05")
    print("Python NPV: 95.24")
    print("CPP_STDOUT_END")

    print("MOJO_STDOUT_BEGIN")
    print("Python Cash flow value: 100.00")
    print("Python Interest rate: 0.05")
    print("Python NPV: 95.24")
    print("MOJO_STDOUT_END")

    print("END_OF_TEST_ITEM")

    # Second test item
    print("TEST_ITEM_ID: test-pepe-py-002")
    print("DESCRIPTION: Complex Python test with multiple flows")
    print("OVERALL_STATUS: FAIL")
    print("FAIL_REASON: Python Numerical discrepancy between C++ and Mojo")
    print("CPP_EXIT_CODE: 0")
    print("MOJO_EXIT_CODE: 0")

    print("CPP_STDOUT_BEGIN")
    print("Python Cash flow sequence: [100, 150, 200]")
    print("Python Interest rate: 0.06")
    print("Python NPV: 398.67")
    print("CPP_STDOUT_END")

    print("MOJO_STDOUT_BEGIN")
    print("Python Cash flow sequence: [100, 150, 200]")
    print("Python Interest rate: 0.06")
    print("Python NPV: 398.68") # Simulate discrepancy
    print("MOJO_STDOUT_END")

    print("END_OF_TEST_ITEM")

    print("RUN_SCRIPT_SUMMARY_BEGIN")
    print("Python Tests completed: 2")
    print("Python Tests passed: 1")
    print("Python Tests failed: 1")
    print("Python Execution time: 0.2s") # Faster as no shell overhead
    print("RUN_SCRIPT_SUMMARY_END")

    sys.exit(0) 