import pytest
import time
from typing import Dict, List, Optional

# Define test cases for standard pytest parametrize
TEST_CASES = [
    # Each test case is a dictionary with metadata and test values
    {
        "id": "test-pepe-001",
        "description": "Simple test for cash flow calculations",
        "inputs": {
            "Cash flow value": "100.00",
            "Interest rate": "0.05"
        },
        "cpp_output": "NPV: 95.24",
        "mojo_output": "NPV: 95.24"
    },
    {
        "id": "test-pepe-002",
        "description": "Complex test with multiple flows",
        "inputs": {
            "Cash flow sequence": "[100, 150, 200]",
            "Interest rate": "0.06"
        },
        "cpp_output": "NPV: 398.67",
        "mojo_output": "NPV: 398.68"
    },
    {
        "id": "test-pepe-003",
        "description": "Test with IRR calculation",
        "inputs": {
            "Cash flow sequence": "[-1000, 300, 400, 500]",
            "Time period": "Annual"
        },
        "cpp_output": "IRR: 0.1016",
        "mojo_output": "IRR: 0.1016"
    }
]

# Standard pytest parametrize format with clean separation of test data
@pytest.mark.parametrize(
    "test_data",
    TEST_CASES,
    ids=[t["id"] for t in TEST_CASES]
)
def test_compare_cpp_mojo(test_data, request):
    """Compare Mojo implementation against QuantLib C++ reference implementation.
    
    Test passes when Mojo output exactly matches C++ output (QuantLib reference implementation).
    """
    # Attach test data to the request.node for the plugin to access
    request.node.cpp_output = test_data["cpp_output"]
    request.node.mojo_output = test_data["mojo_output"]
    request.node.inputs = test_data["inputs"]
    
    # Mark the test with description for better reporting
    pytest.mark.description(test_data["description"])
    
    # The actual test is very simple now - just compare outputs
    assert test_data["mojo_output"] == test_data["cpp_output"], \
        f"Mojo output '{test_data['mojo_output']}' differs from QuantLib C++ reference '{test_data['cpp_output']}'"
    
    # Add a small delay to simulate processing time
    time.sleep(1)

# For standalone execution (outside pytest)
if __name__ == "__main__":
    # Use pytest's main function to run the tests
    import sys
    sys.exit(pytest.main(["-v", __file__])) 