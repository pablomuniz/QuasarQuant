"""
Mojo runner for Sobol sequence validation against QuantLib C++ implementation.
Takes dimensions and sequence count as command line arguments.
"""

import sys
from collections import List
from quantfork.ql.math.randomnumbers.sobolrsg import SobolRsg, DirectionIntegers

fn main() raises:
    # Check command line arguments
    var args = sys.argv()
    if len(args) != 3:
        print("Usage:", args[0], "<dimensions> <sequences>", file=sys.stderr)
        sys.exit(1)
    
    # Convert string arguments to integers
    var dimensions: Int = 0
    var sequences: Int = 0
    
    try:
        dimensions = Int(args[1])
    except:
        print("Error: dimensions must be a valid integer", file=sys.stderr)
        sys.exit(1)
        
    try:
        sequences = Int(args[2])
    except:
        print("Error: sequences must be a valid integer", file=sys.stderr)
        sys.exit(1)
    
    if dimensions <= 0 or sequences <= 0:
        print("Dimensions and sequences must be positive integers", file=sys.stderr)
        sys.exit(1)
    
    # Create Sobol generator with Jaeckel direction integers (same as C++)
    var sobol = SobolRsg(dimensions, 0, DirectionIntegers.Jaeckel)
    
    for i in range(sequences):
        var sample = sobol.next_sequence()
        print("Sample", i, ":", end="")
        for j in range(dimensions):
            # Use simple string conversion - the values are correct
            var value = sample.value[j]
            print(" " + String(value), end="")
        print(" weight: " + String(sample.weight)) 