#!/bin/bash

echo "TESTS 2"
echo "Running test pepe..."
echo "COMPILATION CPP"
sleep 1
echo "Compilation successful!"
echo "Compilation time: 1.0s"

echo "COMPILATION MOJO"
sleep 1
echo "Compilation successful!"
echo "Compilation time: 1.0s"
# First test item

echo "TEST_ITEM_ID: test-pepe-001"
echo "DESCRIPTION: Simple test for cash flow calculations"
echo "OVERALL_STATUS: PASS"
echo "CPP_EXIT_CODE: 0"
echo "MOJO_EXIT_CODE: 0"

echo "SHARED_INPUT_BEGIN"
echo "Cash flow value: 100.00"
echo "Interest rate: 0.05"
echo "SHARED_INPUT_END"

echo "CPP_STDOUT_BEGIN"
echo "OUTPUT: NPV: 95.24"
echo "CPP_STDOUT_END"

echo "MOJO_STDOUT_BEGIN"
echo "OUTPUT: NPV: 95.24"
echo "MOJO_STDOUT_END"

echo "END_OF_TEST_ITEM"
sleep 2
# Second test item
echo "TEST_ITEM_ID: test-pepe-002"
echo "DESCRIPTION: Complex test with multiple flows"
echo "OVERALL_STATUS: FAIL"
echo "FAIL_REASON: Numerical discrepancy between C++ and Mojo"
echo "CPP_EXIT_CODE: 0"
echo "MOJO_EXIT_CODE: 0"

echo "SHARED_INPUT_BEGIN"
echo "Cash flow sequence: [100, 150, 200]"
echo "Interest rate: 0.06"
echo "SHARED_INPUT_END"

echo "CPP_STDOUT_BEGIN"
echo "OUTPUT: NPV: 398.67"
echo "CPP_STDOUT_END"

echo "MOJO_STDOUT_BEGIN"
echo "OUTPUT: NPV: 398.68"
echo "MOJO_STDOUT_END"

echo "DIFF: 0.01"
sleep 2

echo "END_OF_TEST_ITEM"

echo "RUN_SCRIPT_SUMMARY_BEGIN"
echo "Tests completed: 2"
echo "Tests passed: 1"
echo "Tests failed: 1"
echo "Execution time: 1.0s"
echo "RUN_SCRIPT_SUMMARY_END"

exit 0
