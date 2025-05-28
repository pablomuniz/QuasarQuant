# Xoshiro random number generator
# This is a daparture from QuantLib cpp.
# Only this type of random number generator will be used in QuasarQuant.

from time import perf_counter_ns
from bit import rotate_bits_left


trait PRNGEngine(Movable):
    fn next_scalar(mut self) -> UInt64:
        """Get only a single value from the generator."""
        pass


@register_passable("trivial")
struct Xoroshiro128Plus(PRNGEngine):
    """Xoroshiro128Plus generator."""

    alias StateType = UInt64
    alias ValueType = UInt64
    alias SeedType = UInt64

    var seed: Self.SeedType
    var s0: Self.StateType
    var s1: Self.StateType

    fn __init__(out self):
        """Seed with current time."""
        self.s0 = 0
        self.s1 = 9
        self.seed = perf_counter_ns()
        self.reset()

    fn __init__(out self, seed: Self.SeedType):
        """Seed with provided value."""
        self.s0 = 0
        self.s1 = 0
        self.seed = seed
        self.reset()

    fn reset(mut self):
        """Start the sequence over using the current seed value.

        The state is seeded by the SplitMix generator after 1000
        warm up iterations."""
        var seedr = SplitMix.with_warmup(self.seed, 1000)
        self.s0 = seedr.next()
        self.s1 = seedr.next()

    fn reseed(mut self, seed: Self.SeedType):
        """Set a new seed and reset the generator."""
        self.seed = seed
        self.reset()

    fn get_seed(self) -> Self.SeedType:
        """Return the current seed value."""
        return self.seed

    @always_inline
    fn step(mut self):
        """Advance the generator by one step."""
        self.s1 ^= self.s0
        self.s0 = rotate_bits_left[24](self.s0) ^ self.s1 ^ (self.s1 << 16)
        self.s1 = rotate_bits_left[37](self.s1)

    @always_inline
    fn next(mut self) -> Self.ValueType:
        """Return the next value in the sequence."""
        var res = self.s0 + self.s1
        self.step()
        return res

    @always_inline
    fn next_scalar(mut self) -> UInt64:
        """Required for generics."""
        return self.next()

    fn jump(mut self):
        """Jump forward in the sequence.

        It is equivalent
        to 2^64 calls to step(); it can be used to generate 2^64
        non-overlapping subsequences for parallel computations."""
        alias coefs0: UInt64 = 0xDF900294D8F554A5
        alias coefs1: UInt64 = 0x170865DF4B3201FC
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        self.s0 = s0
        self.s1 = s1

    fn long_jump(mut self):
        """Jump forward in the sequence.

        It is equivalent to
        2^96 calls to step(); it can be used to generate 2^32 starting points,
        from each of which jump() will generate 2^32 non-overlapping
        subsequences for parallel distributed computations."""
        alias coefs0: UInt64 = 0xD2A98B26625EEE7B
        alias coefs1: UInt64 = 0xDDDF9B1090AA7AC1
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        self.s0 = s0
        self.s1 = s1

    @always_inline
    fn __call__(mut self) -> Self.ValueType:
        """Same as calling next()."""
        return self.next()


struct Xoroshiro128PlusPlus(PRNGEngine):
    """Xoroshiro128plusplus generator."""

    alias StateType = UInt64
    alias ValueType = UInt64
    alias SeedType = UInt64

    var seed: Self.SeedType
    var s0: Self.StateType
    var s1: Self.StateType

    fn __init__(out self):
        """Seed with current time."""
        self.s0 = 0
        self.s1 = 0
        self.seed = perf_counter_ns()
        self.reset()

    fn __init__(out self, seed: Self.SeedType):
        """Seed with provided value."""
        self.s0 = 0
        self.s1 = 0
        self.seed = seed
        self.reset()

    fn reset(mut self):
        """Start the sequence over using the current seed value.

        The state is seeded by the SplitMix generator after 1000
        warm up iterations."""
        var seedr = SplitMix.with_warmup(self.seed, 1000)
        self.s0 = seedr.next()
        self.s1 = seedr.next()

    fn reseed(mut self, seed: Self.SeedType):
        """Set a new seed and reset the generator."""
        self.seed = seed
        self.reset()

    fn get_seed(self) -> Self.SeedType:
        """Return the current seed value."""
        return self.seed

    @always_inline
    fn step(mut self):
        """Advance the generator by one step."""
        self.s1 ^= self.s0
        self.s0 = rotate_bits_left[49](self.s0) ^ self.s1 ^ (self.s1 << 21)
        self.s1 = rotate_bits_left[28](self.s1)

    @always_inline
    fn next(mut self) -> Self.ValueType:
        """Return the next value in the sequence."""
        var res = rotate_bits_left[17](self.s0 + self.s1) + self.s0
        self.step()
        return res

    @always_inline
    fn next_scalar(mut self) -> UInt64:
        """Required for generics."""
        return self.next()

    fn jump(mut self):
        """Jump forward in the sequence.

        It is equivalent
        to 2^64 calls to step(); it can be used to generate 2^64
        non-overlapping subsequences for parallel computations."""
        alias coefs0: UInt64 = 0x2BD7A6A6E99C2DDC
        alias coefs1: UInt64 = 0x0992CCAF6A6FCA05
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        self.s0 = s0
        self.s1 = s1

    fn long_jump(mut self):
        """Jump forward in the sequence.

        It is equivalent to
        2^96 calls to step(); it can be used to generate 2^32 starting points,
        from each of which jump() will generate 2^32 non-overlapping
        subsequences for parallel distributed computations."""
        alias coefs0: UInt64 = 0x360FD5F2CF8D5D99
        alias coefs1: UInt64 = 0x9C6E6877736C46E3
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        self.s0 = s0
        self.s1 = s1

    @always_inline
    fn __call__(mut self) -> Self.ValueType:
        """Same as calling next()."""
        return self.next()


struct Xoroshiro128StarStar(PRNGEngine):
    """Xoroshiro128starstar generator."""

    alias StateType = UInt64
    alias ValueType = UInt64
    alias SeedType = UInt64

    var seed: Self.SeedType
    var s0: Self.StateType
    var s1: Self.StateType

    fn __init__(out self):
        """Seed with current time."""
        self.s0 = 0
        self.s1 = 0
        self.seed = perf_counter_ns()
        self.reset()

    fn __init__(out self, seed: Self.SeedType):
        """Seed with provided value."""
        self.s0 = 0
        self.s1 = 0
        self.seed = seed
        self.reset()

    fn reset(mut self):
        """Start the sequence over using the current seed value.

        The state is seeded by the SplitMix generator after 1000
        warm up iterations."""
        var seedr = SplitMix.with_warmup(self.seed, 1000)
        self.s0 = seedr.next()
        self.s1 = seedr.next()

    fn reseed(mut self, seed: Self.SeedType):
        """Set a new seed and reset the generator."""
        self.seed = seed
        self.reset()

    fn get_seed(self) -> Self.SeedType:
        """Return the current seed value."""
        return self.seed

    @always_inline
    fn step(mut self):
        """Advance the generator by one step."""
        self.s1 ^= self.s0
        self.s0 = rotate_bits_left[24](self.s0) ^ self.s1 ^ (self.s1 << 16)
        self.s1 = rotate_bits_left[37](self.s1)

    @always_inline
    fn next(mut self) -> Self.ValueType:
        """Return the next value in the sequence."""
        var res = rotate_bits_left[7](self.s0 * 5) * 9
        self.step()
        return res

    @always_inline
    fn next_scalar(mut self) -> UInt64:
        """Required for generics."""
        return self.next()

    fn jump(mut self):
        """Jump forward in the sequence.

        It is equivalent
        to 2^64 calls to step(); it can be used to generate 2^64
        non-overlapping subsequences for parallel computations."""
        alias coefs0: UInt64 = 0xDF900294D8F554A5
        alias coefs1: UInt64 = 0x170865DF4B3201FC
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        self.s0 = s0
        self.s1 = s1

    fn long_jump(mut self):
        """Jump forward in the sequence.

        It is equivalent to
        2^96 calls to step(); it can be used to generate 2^32 starting points,
        from each of which jump() will generate 2^32 non-overlapping
        subsequences for parallel distributed computations."""
        alias coefs0: UInt64 = 0xD2A98B26625EEE7B
        alias coefs1: UInt64 = 0xDDDF9B1090AA7AC1
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
            self.step()
        self.s0 = s0
        self.s1 = s1

    @always_inline
    fn __call__(mut self) -> Self.ValueType:
        """Same as calling next()."""
        return self.next()

@always_inline
fn xoshiro256_plus[n: Int, T: DType](s0: SIMD[T, n], s1: SIMD[T, n], s2: SIMD[T, n], s3: SIMD[T, n]) -> SIMD[T, n]:
    """Mixer for xoshiro plus generator with 256-bits of state."""
    return s0 + s3


@always_inline
fn xoshiro256_plus_plus[n: Int, T: DType](s0: SIMD[T, n], s1: SIMD[T, n], s2: SIMD[T, n], s3: SIMD[T, n]) -> SIMD[T, n]:
    """Mixer for xoshiro plus-plus generator with 256-bits of state."""
    return rotate_bits_left[23](s0 + s3) + s0


@always_inline
fn xoshiro256_star_star[n: Int, T: DType](s0: SIMD[T, n], s1: SIMD[T, n], s2: SIMD[T, n], s3: SIMD[T, n]) -> SIMD[T, n]:
     """Mixer for xoshiro star-star generator with 256-bits of state."""
    return rotate_bits_left[7](s1 * 5) * 9

alias MixerType = fn[n: Int, T: DType](SIMD[T, n], SIMD[T, n], SIMD[T, n], SIMD[T, n]) -> SIMD[T, n]

@register_passable("trivial")
struct Xoshiro256Vect[n: Int, mixer: MixerType](PRNGEngine):
    """Compute n parallel streams."""

    alias StateType = SIMD[DType.uint64, n]
    alias ValueType = Self.StateType
    alias SeedType = UInt64

    var seed: Self.SeedType
    
    var s0: Self.StateType
    var s1: Self.StateType
    var s2: Self.StateType
    var s3: Self.StateType

    @staticmethod
    fn ndim() -> Int:
        return n

    fn __init__(out self):
        """Seed with current time."""
        self.s0 = 0
        self.s1 = 0
        self.s2 = 0
        self.s3 = 0
        self.seed = perf_counter_ns()
        self.reset()

    fn __init__(out self, seed: Self.SeedType):
        """Seed with provided value."""
        self.s0 = 0
        self.s1 = 0
        self.s2 = 0
        self.s3 = 0
        self.seed = seed
        self.reset()

    fn reset(mut self):
         """Start the sequence over using the current seed value.
         
        The scalar engine is seeded by SplitMix. If there are more
        dimentions, other n-1 streams are seeded by taking a jump
        and assigning the jumped state to the next generator.
        This will result in independent streams, which will be
        returned as n-values in a SIMD."""
        @parameter
        if n == 1:
            var seedr = SplitMix.with_warmup(self.seed, 1000)
            self.s0 = seedr.next()
            self.s1 = seedr.next()
            self.s2 = seedr.next()
            self.s3 = seedr.next()
        else:
            var seedr = Xoshiro256Vect[1, mixer](self.seed)
            for i in range(n):
                self.s0[i] = seedr.s0
                self.s1[i] = seedr.s1
                self.s2[i] = seedr.s2
                self.s3[i] = seedr.s3
                seedr.jump()

    fn reseed(mut self, seed: Self.SeedType):
        """Set a new seed and reset the generator."""
        self.seed = seed
        self.reset()

    fn get_seed(self) -> Self.SeedType:
        """Return the current seed value."""
        return self.seed

    @always_inline
    fn step(mut self):
        """Advance the generator by one step.
        
        The streams are advanced in parallel
        using SIMD operations."""
        var t = self.s1 << 17
        self.s2 ^= self.s0
        self.s3 ^= self.s1
        self.s1 ^= self.s2
        self.s0 ^= self.s3
        self.s2 ^= t
        self.s3 = rotate_bits_left[45](self.s3)

    @always_inline
    fn next(mut self) -> Self.ValueType:
        """Return the next value in the sequence.
        
        The nth stream value will be in result[n - 1]."""
        var res = mixer(self.s0, self.s1, self.s2, self.s3)
        self.step()
        return res

    @always_inline
    fn next_scalar(mut self) -> UInt64:
        """Required for generics."""
        return self.next()[0]

    @always_inline
    fn __call__(mut self) -> Self.ValueType:
        """Same as calling next()."""
        return self.next()

    fn jump(mut self):
        """Jump forward in the sequence.
        
        It is equivalent to 2^128 calls to step(); it can be used to generate 2^128
        non-overlapping subsequences for parallel computations."""
        alias coefs0: UInt64 = 0x180EC6D33CFD0ABA
        alias coefs1: UInt64 = 0xD5A61266F0C9392C
        alias coefs2: UInt64 = 0xA9582618E03FC9AA
        alias coefs3: UInt64 = 0x39ABDC4529B1661C
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        var s2: Self.StateType = 0
        var s3: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        for j in range(64):
            if coefs2 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        for j in range(64):
            if coefs3 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        self.s0 = s0
        self.s1 = s1
        self.s2 = s2
        self.s3 = s3

    fn long_jump(mut self):
        """Jump forward in the sequence.
        
        It is equivalent to 2^192 calls to step();
        it can be used to generate 2^64 starting points,
        from each of which jump() will generate 2^64 non-overlapping
        subsequences for parallel distributed computations."""
        alias coefs0: UInt64 = 0x76E15D3EFEFDCBBF
        alias coefs1: UInt64 = 0xC5004E441C522FB3
        alias coefs2: UInt64 = 0x77710069854EE241
        alias coefs3: UInt64 = 0x39109BB02ACBE635
        var s0: Self.StateType = 0
        var s1: Self.StateType = 0
        var s2: Self.StateType = 0
        var s3: Self.StateType = 0
        for j in range(64):
            if coefs0 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        for j in range(64):
            if coefs1 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        for j in range(64):
            if coefs2 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        for j in range(64):
            if coefs3 & (1 << j):
                s0 ^= self.s0
                s1 ^= self.s1
                s2 ^= self.s2
                s3 ^= self.s3
            self.step()
        self.s0 = s0
        self.s1 = s1
        self.s2 = s2
        self.s3 = s3

alias Xoshiro256VectStarStar = Xoshiro256Vect[mixer = xoshiro256_star_star]
alias Xoshiro256VectPlusPlus = Xoshiro256Vect[mixer = xoshiro256_plus_plus]
alias Xoshiro256VectPlus = Xoshiro256Vect[mixer = xoshiro256_plus]
alias Xoshiro256StarStar = Xoshiro256VectStarStar[n = 1]
alias Xoshiro256PlusPlus = Xoshiro256VectPlusPlus[n = 1]
alias Xoshiro256Plus = Xoshiro256VectPlus[n = 1]

#@register_passable("trivial")
struct SplitMix(PRNGEngine):
    """SplitMix 64-bit pseudo-random generator."""

    alias SeedType = UInt64
    alias StateType = UInt64
    alias ValueType = UInt64

    var seed: Self.SeedType
    var state: Self.StateType

    @staticmethod
    fn ndim() -> Int:
        return 1

    fn __init__(out self):
        """Default constructor."""
        self.state = 0
        self.seed = perf_counter_ns()
        self.reset(0)
    
    fn __copyinit__(out self, other: Self):
        """Copy constructor."""
        self.seed = other.seed
        self.state = other.state
    
    @staticmethod
    fn with_warmup(seed: UInt64, warmup: Int) -> Self:
        """Create SplitMix with specific warmup."""
        var result = Self()
        result.seed = seed
        result.reset(warmup)
        return result

    fn reset(mut self, warmup: Int = 0):
        """Start the sequence over using the current seed value.
        
        Arguments:
            warmup -- advance the state this many times."""
        self.state = self.seed
        self.step(warmup)

    fn reseed(mut self, seed: Self.SeedType, warmup: Int = 0):
        """Set a new seed and reset the generator.
        
        Arguments:
            warmup -- advance the state this many times."""
        self.seed = seed
        self.reset(warmup)

    fn get_seed(self) -> Self.SeedType:
        """Return the current seed value."""
        return self.seed

    @always_inline
    fn step(mut self):
        """Advance the generator by one step."""
            self.state += 0x9E3779B97F4A7C15

    @always_inline
    fn step(mut self, times: Int):
        """Advance the generator by times steps."""
        for _ in range(times):
            self.step()

    @always_inline
    fn next(mut self) -> Self.ValueType:
        """Return the next value in the sequence."""
        self.step()
        var z = self.state
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) * 0x94D049BB133111EB
        return z ^ (z >> 31)

    @always_inline
    fn next_scalar(mut self) -> UInt64:
        return self.next()

    @always_inline
    fn __call__(mut self) -> Self.ValueType:
        """Same as calling next()."""
        return self.next()