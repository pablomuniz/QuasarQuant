"""
Debug script to check our direction integers.
"""

from quantfork.ql.math.randomnumbers.sobolrsg import SobolRsg, DirectionIntegers

fn main():
    print("=== Debugging Sobol Direction Integers ===")
    
    var sobol = SobolRsg(2, 0, DirectionIntegers.Jaeckel)
    
    print("Direction integers for first 2 dimensions, first 5 positions:")
    for dim in range(2):
        print("Dimension", dim, ":")
        for pos in range(min(5, len(sobol.direction_integers_[dim]))):
            var value = sobol.direction_integers_[dim][pos]
            print("  [", pos, "] =", value)
    
    print("\nFirst integer sequence (precomputed):")
    for dim in range(2):
        var value = sobol.integer_sequence_[dim]
        print("  integer_sequence_[", dim, "] =", value)
        var normalized = Float64(value) * (0.5 / Float64(1 << 31))
        print("  normalized =", normalized) 