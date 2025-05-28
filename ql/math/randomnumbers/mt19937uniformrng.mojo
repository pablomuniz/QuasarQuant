"""
High-performance Mersenne Twister MT19937 uniform random number generator for Mojo.

Optimized version without circular dependencies, Sample types, or Lists.
"""

from memory import memset_zero, UnsafePointer
from sys.intrinsics import likely, unlikely
from time import perf_counter_ns

# ===----------------------------------------------------------------------=== #
# MT19937 Implementation (optimized for performance)
# ===----------------------------------------------------------------------=== #

struct MersenneTwisterUniformRng:
    """
    High-performance Mersenne Twister MT19937 uniform random number generator.
    
    Period: 2^19937-1, passes Diehard statistical tests.
    Uses stack allocation for better cache performance.
    """
    
    # MT19937 constants
    alias N: Int = 624
    alias M: Int = 397
    alias MATRIX_A: UInt32 = 0x9908b0df
    alias UPPER_MASK: UInt32 = 0x80000000
    alias LOWER_MASK: UInt32 = 0x7fffffff
    alias TEMPERING_MASK_B: UInt32 = 0x9d2c5680
    alias TEMPERING_MASK_C: UInt32 = 0xefc60000
    
    # Use InlineArray for stack allocation and better cache performance
    var mt: InlineArray[UInt32, 624]
    var mti: Int
    
    fn __init__(out self, seed: UInt32 = 0):
        """Initialize with a single seed value."""
        self.mt = InlineArray[UInt32, Self.N]()
        self.mti = Self.N
        
        # Break circular dependency - use time-based seed if 0
        var actual_seed = seed
        if seed == 0:
            actual_seed = self._get_time_seed()
        
        self._seed_initialization(actual_seed)
    
    fn __init__(out self, seeds: UnsafePointer[UInt32], seed_count: Int):
        """Initialize with an array of seeds."""
        self.mt = InlineArray[UInt32, Self.N]()
        self.mti = Self.N
        self._seed_initialization_array(seeds, seed_count)
    
    @always_inline
    fn _get_time_seed(self) -> UInt32:
        """Get time-based seed without circular dependency."""
        var ns = perf_counter_ns()
        # Mix the time value for better distribution
        var seed = UInt32(ns & 0xffffffff)
        seed ^= UInt32((ns >> 32) & 0xffffffff)
        seed ^= (seed >> 11)
        seed ^= (seed << 7) & 0x9d2c5680
        return seed if seed != 0 else 1
    
    fn _seed_initialization(mut self, seed: UInt32):
        """Initialize with a single seed."""
        self.mt[0] = seed
        
        for i in range(1, Self.N):
            var prev = self.mt[i - 1]
            self.mt[i] = (1812433253 * (prev ^ (prev >> 30)) + UInt32(i)) & 0xffffffff
        
        self.mti = Self.N
    
    fn _seed_initialization_array(mut self, seeds: UnsafePointer[UInt32], seed_count: Int):
        """Initialize with array of seeds."""
        self._seed_initialization(19650218)
        
        var i = 1
        var j = 0
        var k = Self.N if Self.N > seed_count else seed_count
        
        # First loop
        while k > 0:
            var prev = self.mt[i - 1]
            self.mt[i] = ((self.mt[i] ^ ((prev ^ (prev >> 30)) * 1664525)) + 
                         seeds[j] + UInt32(j)) & 0xffffffff
            i += 1
            j += 1
            
            if i >= Self.N:
                self.mt[0] = self.mt[Self.N - 1]
                i = 1
            if j >= seed_count:
                j = 0
            k -= 1
        
        # Second loop
        k = Self.N - 1
        while k > 0:
            var prev = self.mt[i - 1]
            self.mt[i] = ((self.mt[i] ^ ((prev ^ (prev >> 30)) * 1566083941)) - 
                         UInt32(i)) & 0xffffffff
            i += 1
            
            if i >= Self.N:
                self.mt[0] = self.mt[Self.N - 1]
                i = 1
            k -= 1
        
        self.mt[0] = Self.UPPER_MASK
        self.mti = Self.N
    
    fn _twist(mut self):
        """Generate the next N values in the state array."""
        var kk = 0
        var y: UInt32
        
        # First part: kk=0 to N-M-1
        while kk < Self.N - Self.M:
            y = (self.mt[kk] & Self.UPPER_MASK) | (self.mt[kk + 1] & Self.LOWER_MASK)
            var mag_val = Self.MATRIX_A if (y & 0x1) != 0 else 0
            self.mt[kk] = self.mt[kk + Self.M] ^ (y >> 1) ^ mag_val
            kk += 1
        
        # Second part: kk=N-M to N-2
        while kk < Self.N - 1:
            y = (self.mt[kk] & Self.UPPER_MASK) | (self.mt[kk + 1] & Self.LOWER_MASK)
            var mag_val = Self.MATRIX_A if (y & 0x1) != 0 else 0
            self.mt[kk] = self.mt[(kk + Self.M) - Self.N] ^ (y >> 1) ^ mag_val
            kk += 1
        
        # Final element
        y = (self.mt[Self.N - 1] & Self.UPPER_MASK) | (self.mt[0] & Self.LOWER_MASK)
        var mag_val = Self.MATRIX_A if (y & 0x1) != 0 else 0
        self.mt[Self.N - 1] = self.mt[Self.M - 1] ^ (y >> 1) ^ mag_val
        
        self.mti = 0
    
    @always_inline
    fn next_int32(mut self) -> UInt32:
        """Generate a random 32-bit integer [0, 0xffffffff]."""
        if unlikely(self.mti >= Self.N):
            self._twist()
        
        var y = self.mt[self.mti]
        self.mti += 1
        
        # Tempering
        y ^= (y >> 11)
        y ^= (y << 7) & Self.TEMPERING_MASK_B
        y ^= (y << 15) & Self.TEMPERING_MASK_C
        y ^= (y >> 18)
        
        return y
    
    @always_inline
    fn next_real(mut self) -> Float64:
        """Generate a random number in (0.0, 1.0) interval."""
        return (Float64(self.next_int32()) + 0.5) / 4294967296.0
    
    @always_inline
    fn next_real32(mut self) -> Float32:
        """Generate a random 32-bit float in (0.0, 1.0) interval."""
        return (Float32(self.next_int32()) + 0.5) / 4294967296.0
    
    fn fill_buffer(mut self, mut buffer: UnsafePointer[Float64], count: Int):
        """Fill a pre-allocated buffer with random numbers."""
        for i in range(count):
            buffer[i] = self.next_real()
    
    fn fill_buffer_int32(mut self, mut buffer: UnsafePointer[UInt32], count: Int):
        """Fill a pre-allocated buffer with random integers."""
        for i in range(count):
            buffer[i] = self.next_int32()

# from collections import List
# import time

# # ===----------------------------------------------------------------------=== #
# # Sample Type (matching QuantLib's Sample<Real>)
# # ===----------------------------------------------------------------------=== #

# @value
# struct Sample[T: AnyType]:
#     """Weighted sample containing a value and weight."""
#     var value: T
#     var weight: Float64
    
#     fn __init__(out self, value: T, weight: Float64 = 1.0):
#         self.value = value
#         self.weight = weight

# # Type alias for Real sample (Float64 in Mojo)
# alias RealSample = Sample[Float64]

# # ===----------------------------------------------------------------------=== #
# # MT19937 Implementation (exactly matching C++ interface)
# # ===----------------------------------------------------------------------=== #

# struct MersenneTwisterUniformRng:
#     """
#     Mersenne Twister MT19937 uniform random number generator.
    
#     This exactly matches the QuantLib C++ implementation interface and behavior.
#     Period: 2^19937-1, passes Diehard statistical tests.
#     """
    
#     # MT19937 constants (exactly as in C++)
#     alias N: Int = 624      # state size
#     alias M: Int = 397      # shift size
#     alias MATRIX_A: UInt32 = 0x9908b0df   # constant vector a
#     alias UPPER_MASK: UInt32 = 0x80000000  # most significant w-r bits  
#     alias LOWER_MASK: UInt32 = 0x7fffffff  # least significant r bits
    
#     # Internal state (matching C++ exactly)
#     var mt: List[UInt32]    # state array
#     var mti: Int            # index into state array
    
#     fn __init__(out self, seed: UInt32 = 0):
#         """Initialize with a single seed value (matches C++ constructor)."""
#         self.mt = List[UInt32](capacity=Self.N)
#         self.mti = Self.N + 1  # Mark as uninitialized
        
#         # Initialize array to proper size
#         for _ in range(Self.N):
#             self.mt.append(0)
        
#         self._seed_initialization(seed)
    
#     fn __init__(out self, seeds: List[UInt32]):
#         """Initialize with an array of seeds (matches C++ constructor)."""
#         self.mt = List[UInt32](capacity=Self.N)
#         self.mti = Self.N + 1
        
#         # Initialize array to proper size
#         for _ in range(Self.N):
#             self.mt.append(0)
        
#         self._seed_initialization_array(seeds)
    
#     fn _seed_initialization(mut self, seed: UInt32):
#         """
#         Initialize with a single seed (matches C++ seedInitialization exactly).
#         """
#         # Use system time if seed is 0 (like C++ version with SeedGenerator)
#         var s: UInt32
#         if seed != 0:
#             s = seed
#         else:
#             # Simple time-based seed (in real C++ it uses SeedGenerator::instance().get())
#             var current_time = time.time_ns()
#             s = UInt32(current_time % (1 << 32))
        
#         self.mt[0] = s & 0xffffffff
#         self.mti = 1
        
#         while self.mti < Self.N:
#             # Exactly as in C++: Knuth TAOCP Vol2. 3rd Ed. P.106 multiplier
#             var prev = self.mt[self.mti - 1]
#             self.mt[self.mti] = (1812433253 * (prev ^ (prev >> 30)) + UInt32(self.mti))
#             self.mt[self.mti] &= 0xffffffff  # for >32 bit machines
#             self.mti += 1
    
#     fn _seed_initialization_array(mut self, seeds: List[UInt32]):
#         """
#         Initialize with array of seeds (matches C++ constructor exactly).
#         """
#         # First initialize with default seed (exactly as in C++)
#         self._seed_initialization(19650218)
        
#         var i = 1
#         var j = 0
#         var k = max(Self.N, len(seeds))
        
#         # First loop (exactly as in C++)
#         while k != 0:
#             var prev = self.mt[i - 1]
#             self.mt[i] = ((self.mt[i] ^ ((prev ^ (prev >> 30)) * 1664525)) + 
#                          seeds[j] + UInt32(j))  # non linear
#             self.mt[i] &= 0xffffffff  # for WORDSIZE > 32 machines
#             i += 1
#             j += 1
            
#             if i >= Self.N:
#                 self.mt[0] = self.mt[Self.N - 1]
#                 i = 1
#             if j >= len(seeds):
#                 j = 0
#             k -= 1
        
#         # Second loop (exactly as in C++)
#         k = Self.N - 1
#         while k != 0:
#             var prev = self.mt[i - 1]
#             self.mt[i] = ((self.mt[i] ^ ((prev ^ (prev >> 30)) * 1566083941)) - 
#                          UInt32(i))  # non linear
#             self.mt[i] &= 0xffffffff  # for WORDSIZE > 32 machines
#             i += 1
            
#             if i >= Self.N:
#                 self.mt[0] = self.mt[Self.N - 1]
#                 i = 1
#             k -= 1
        
#         # MSB is 1; assuring non-zero initial array (exactly as in C++)
#         self.mt[0] = Self.UPPER_MASK
    
#     fn _twist(mut self):
#         """
#         Generate the next N values in the sequence (matches C++ twist exactly).
#         """
#         # Static array as in C++ (mag01[x] = x * MATRIX_A for x=0,1)
#         var mag01_0: UInt32 = 0x0
#         var mag01_1: UInt32 = Self.MATRIX_A
        
#         var kk = 0
#         var y: UInt32
        
#         # First part: kk=0 to N-M-1 (exactly as in C++)
#         while kk < Self.N - Self.M:
#             y = (self.mt[kk] & Self.UPPER_MASK) | (self.mt[kk + 1] & Self.LOWER_MASK)
#             var mag_val = mag01_1 if (y & 0x1) != 0 else mag01_0
#             self.mt[kk] = self.mt[kk + Self.M] ^ (y >> 1) ^ mag_val
#             kk += 1
        
#         # Second part: kk=N-M to N-2 (exactly as in C++)
#         while kk < Self.N - 1:
#             y = (self.mt[kk] & Self.UPPER_MASK) | (self.mt[kk + 1] & Self.LOWER_MASK)
#             var mag_val = mag01_1 if (y & 0x1) != 0 else mag01_0
#             self.mt[kk] = self.mt[(kk + Self.M) - Self.N] ^ (y >> 1) ^ mag_val
#             kk += 1
        
#         # Final element (exactly as in C++)
#         y = (self.mt[Self.N - 1] & Self.UPPER_MASK) | (self.mt[0] & Self.LOWER_MASK)
#         var mag_val = mag01_1 if (y & 0x1) != 0 else mag01_0
#         self.mt[Self.N - 1] = self.mt[Self.M - 1] ^ (y >> 1) ^ mag_val
        
#         self.mti = 0
    
#     fn next_int32(mut self) -> UInt32:
#         """
#         Generate a random 32-bit integer (matches C++ nextInt32 exactly).
#         Returns: random integer in [0, 0xffffffff]
#         """
#         if self.mti >= Self.N:
#             self._twist()  # generate N words at a time
        
#         var y = self.mt[self.mti]
#         self.mti += 1
        
#         # Tempering (exactly as in C++)
#         y ^= (y >> 11)
#         y ^= (y << 7) & 0x9d2c5680
#         y ^= (y << 15) & 0xefc60000
#         y ^= (y >> 18)
        
#         return y
    
#     fn next_real(mut self) -> Float64:
#         """
#         Generate a random number in (0.0, 1.0) interval (matches C++ nextReal exactly).
#         """
#         return (Float64(self.next_int32()) + 0.5) / 4294967296.0
    
#     fn next(mut self) -> RealSample:
#         """
#         Generate a weighted sample with weight 1.0 (matches C++ next exactly).
#         """
#         return RealSample(self.next_real(), 1.0) 