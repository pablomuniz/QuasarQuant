#!/usr/bin/env python3

import re

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
    
    print(f"DEBUG: cpp_lines = {len(cpp_lines)}, mojo_lines = {len(mojo_lines)}")
    
    if len(cpp_lines) != len(mojo_lines):
        return False, f"Different number of lines: C++ {len(cpp_lines)}, Mojo {len(mojo_lines)}"
    
    for i, (cpp_line, mojo_line) in enumerate(zip(cpp_lines, mojo_lines)):
        print(f"DEBUG: Line {i+1}:")
        print(f"  C++:  '{cpp_line}'")
        print(f"  Mojo: '{mojo_line}'")
        
        cpp_sample = parse_sample_line(cpp_line)
        mojo_sample = parse_sample_line(mojo_line)
        
        print(f"  C++ parsed: {cpp_sample}")
        print(f"  Mojo parsed: {mojo_sample}")
        
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
            diff = abs(cpp_val - mojo_val)
            print(f"    Value {j}: C++ {cpp_val}, Mojo {mojo_val}, diff {diff}, tolerance {tolerance}")
            if diff > tolerance:
                return False, f"Value mismatch at line {i+1}, position {j}: C++ {cpp_val}, Mojo {mojo_val}, diff {diff}"
        
        # Compare weight
        weight_diff = abs(cpp_sample["weight"] - mojo_sample["weight"])
        print(f"    Weight: C++ {cpp_sample['weight']}, Mojo {mojo_sample['weight']}, diff {weight_diff}")
        if weight_diff > tolerance:
            return False, f"Weight mismatch at line {i+1}: C++ {cpp_sample['weight']}, Mojo {mojo_sample['weight']}"
    
    return True, "All values match within tolerance"

# Test with simulated outputs from the failing test
cpp_output = """Sample 0 : 0.500000000000000 0.500000000000000 weight: 1.000000000000000
Sample 1 : 0.750000000000000 0.250000000000000 weight: 1.000000000000000"""

mojo_output = """Sample 0 : 0.5 0.5 weight: 1.0
Sample 1 : 0.75 0.25 weight: 1.0"""

print("Testing compare_numerical_output function:")
result, message = compare_numerical_output(cpp_output, mojo_output)
print(f"\nResult: {result}")
print(f"Message: {message}") 