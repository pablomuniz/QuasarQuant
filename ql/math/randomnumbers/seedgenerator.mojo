"""
Random seed generator for Mojo.

Based on QuantLib's SeedGenerator which uses a sophisticated initialization
process with multiple MT19937 generators to produce high-quality random seeds.
Implements proper singleton pattern matching C++ behavior.
"""

from collections import List
import time
from .mt19937uniformrng import MersenneTwisterUniformRng

# ===----------------------------------------------------------------------=== #
# Proper Singleton Implementation
# ===----------------------------------------------------------------------=== #

# Global singleton state - this ensures ONE instance for entire program
var _global_seed_generator_rng: Optional[MersenneTwisterUniformRng] = None
var _global_seed_generator_initialized: Bool = False

fn _initialize_global_seed_generator():
    """
    Initialize the global seed generator using the same algorithm as QuantLib C++.
    This is called only once, just like the C++ singleton constructor.
    """
    global _global_seed_generator_rng, _global_seed_generator_initialized
    
    if _global_seed_generator_initialized:
        return
    
    # Same initialization as C++ SeedGenerator constructor
    # firstSeed is chosen based on current time (like std::time(nullptr))
    var current_time = time.time_ns()
    var first_seed = UInt32(current_time % (1 << 32))
    
    # First RNG seeded with time
    var first = MersenneTwisterUniformRng(first_seed)
    
    # secondSeed is as random as it could be
    var second_seed = first.next_int32()
    var second = MersenneTwisterUniformRng(second_seed)
    
    # Use the second rng to initialize the final one
    var skip = second.next_int32() % 1000
    
    # Create initialization array with 4 seeds (exactly as in C++)
    var init = List[UInt32]()
    init.append(second.next_int32())
    init.append(second.next_int32())
    init.append(second.next_int32())
    init.append(second.next_int32())
    
    # Initialize final RNG with seed array
    var final_rng = MersenneTwisterUniformRng(init)
    
    # Skip some values as in C++ version
    for i in range(int(skip)):
        _ = final_rng.next_int32()
    
    # Store the initialized RNG globally
    _global_seed_generator_rng = final_rng
    _global_seed_generator_initialized = True

fn seed_generator_get() -> UInt32:
    """
    Get a random seed value from the global singleton SeedGenerator.
    
    This function matches the C++ SeedGenerator::instance().get() behavior:
    - Same global state for entire program
    - Sequential seeds from the same internal RNG
    - Thread-safe initialization (simplified)
    """
    global _global_seed_generator_rng, _global_seed_generator_initialized
    
    # Initialize if not done yet (like C++ singleton lazy initialization)
    if not _global_seed_generator_initialized:
        _initialize_global_seed_generator()
    
    # Get next value from the global RNG (like C++ instance().get())
    return _global_seed_generator_rng.value().next_int32()

# ===----------------------------------------------------------------------=== #
# SeedGenerator Struct (for compatibility)
# ===----------------------------------------------------------------------=== #

struct SeedGenerator:
    """
    SeedGenerator struct that provides access to the global singleton.
    This is for API compatibility but all instances share the same global state.
    """
    
    fn __init__(out self):
        """Constructor - but all instances share global state."""
        pass
    
    @staticmethod
    fn instance_get() -> UInt32:
        """Static method matching C++ SeedGenerator::instance().get()"""
        return seed_generator_get()
    
    fn get(self) -> UInt32:
        """Instance method that delegates to global singleton."""
        return seed_generator_get()

# ===----------------------------------------------------------------------=== #
# Convenience Functions
# ===----------------------------------------------------------------------=== #

fn generate_seed() -> UInt32:
    """Generate a random seed using the global SeedGenerator singleton."""
    return seed_generator_get() 