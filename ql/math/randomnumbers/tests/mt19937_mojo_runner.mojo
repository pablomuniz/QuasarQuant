from memory import UnsafePointer
from time import perf_counter_ns
from sys import argv as sys_argv


# Fix import path to use absolute path from project root
from quantfork.ql.math.randomnumbers.mt19937uniformrng import MersenneTwisterUniformRng

fn main() raises:
    var args = sys_argv()
    if len(args) != 2:
        print("Usage: " + args[0] + " <number_of_sequences>")
        return
    
    # Parse number of sequences
    var sequences_arg = args[1]
    var sequences = Int(String(sequences_arg))
    if sequences <= 0:
        print("Error: number of sequences must be positive")
        return
    
    # Initialize MT19937 with same seed as C++ for reproducibility
    var rng = MersenneTwisterUniformRng(42)
    
    # Generate and print sequences
    for i in range(sequences):
        var value = rng.next_real()
        print("Sample " + String(i) + " : " + String(value) + " weight: 1.000000000000000")
    
