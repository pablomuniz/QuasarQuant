"""
Test and demonstration of Sobol sequence generators for Monte Carlo simulations.
"""

from collections import List
from quantfork.ql.math.randomnumbers.sobolrsg import SobolRsg, DirectionIntegers, Sample
from quantfork.ql.math.randomnumbers.sobol_brownian_generator import (
    SobolBrownianGenerator,
    Ordering, 
    inverse_cumulative_normal
)

fn test_basic_sobol():
    """Test basic Sobol sequence generation."""
    print("=== Testing Basic Sobol Sequence Generation ===")
    
    var rsg = SobolRsg(2, 0, DirectionIntegers.Jaeckel)
    
    print("Generating first 5 Sobol sequences (2D):")
    for i in range(5):
        var sample = rsg.next_sequence()
        print("Sample", i, ": [", sample.value[0], ",", sample.value[1], "], weight:", sample.weight)
    
    # Test higher dimensions
    print("\nTesting 6D Sobol sequences:")
    var rsg6d = SobolRsg(6, 0, DirectionIntegers.Jaeckel)
    for i in range(3):
        var sample = rsg6d.next_sequence()
        print("6D Sample", i, ":", end="")
        for j in range(6):
            print(" ", sample.value[j], end="")
        print()

fn test_brownian_generator():
    """Test Sobol Brownian generator."""
    print("\n=== Testing Sobol Brownian Generator ===")
    
    var factors = 2
    var steps = 3
    var generator = SobolBrownianGenerator(factors, steps, Ordering.Factors)
    
    print("Generating Brownian paths:")
    print("Factors:", generator.number_of_factors(), "Steps:", generator.number_of_steps())
    
    # Debug: Show the ordering indices
    print("Ordering indices:")
    var indices = generator.ordered_indices()
    for i in range(factors):
        print("  Factor", i, "indices:", end="")
        for j in range(steps):
            print(" ", indices[i][j], end="")
        print()
    
    # Generate a few paths with detailed debugging
    for path in range(3):
        print("\n--- Path", path, "---")
        
        # Debug: Check the underlying Sobol sequence
        var sample = generator.next_sequence()
        print("Raw Sobol values:", end="")
        for k in range(len(sample.value)):
            print(" ", sample.value[k], end="")
        print()
        
        var weight = generator.next_path()
        print("Path weight:", weight)
        
        var output = List[Float64](capacity=factors)
        for i in range(factors):
            output.append(0.0)
            
        for step in range(steps):
            var step_weight = generator.next_step(output)
            print("  Step", step, ": [", output[0], ",", output[1], "]")

fn test_inverse_normal():
    """Test inverse cumulative normal function."""
    print("\n=== Testing Inverse Cumulative Normal ===")
    
    var test_values = List[Float64]()
    test_values.append(0.1)
    test_values.append(0.25)
    test_values.append(0.5)
    test_values.append(0.75)
    test_values.append(0.9)
    
    for i in range(len(test_values)):
        var u = test_values[i]
        var z = inverse_cumulative_normal(u)
        print("U =", u, "-> Z =", z)

fn test_ordering_comparison():
    """Test different ordering methods."""
    print("\n=== Testing Different Ordering Methods ===")
    
    var factors = 2
    var steps = 3
    
    # Test Factors ordering
    print("Factors ordering:")
    var gen_factors = SobolBrownianGenerator(factors, steps, Ordering.Factors)
    var indices_factors = gen_factors.ordered_indices()
    for i in range(factors):
        print("Factor", i, "indices:", end="")
        for j in range(steps):
            print(" ", indices_factors[i][j], end="")
        print()
    
    # Test Steps ordering  
    print("\nSteps ordering:")
    var gen_steps = SobolBrownianGenerator(factors, steps, Ordering.Steps)
    var indices_steps = gen_steps.ordered_indices()
    for i in range(factors):
        print("Factor", i, "indices:", end="")
        for j in range(steps):
            print(" ", indices_steps[i][j], end="")
        print()
    
    # Test Diagonal ordering
    print("\nDiagonal ordering:")
    var gen_diagonal = SobolBrownianGenerator(factors, steps, Ordering.Diagonal)
    var indices_diagonal = gen_diagonal.ordered_indices()
    for i in range(factors):
        print("Factor", i, "indices:", end="")
        for j in range(steps):
            print(" ", indices_diagonal[i][j], end="")
        print()

fn main():
    """Run all tests."""
    test_basic_sobol()
    test_brownian_generator()
    test_inverse_normal()
    test_ordering_comparison()
    print("\n=== All Tests Completed ===")
