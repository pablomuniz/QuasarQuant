# File: quantfork/ql/math/randomnumbers/test_xoshiro.mojo

from testing import assert_equal, assert_true, assert_false
from quantfork.ql.math.randomnumbers.xoshiro import (
    Xoroshiro128Plus, Xoroshiro128PlusPlus, Xoroshiro128StarStar,
    Xoshiro256StarStar, Xoshiro256Plus, Xoshiro256PlusPlus, # n=1 aliases
    Xoshiro256Vect, # The generic Xoshiro256Vect
    xoshiro256_star_star, xoshiro256_plus, xoshiro256_plus_plus, # mixers
    SplitMix
)

# SIMD and DType.uint64 are built-in, no specific top-level import needed for them directly here.

fn test_splitmix() raises:
    print("\nTesting SplitMix...")
    var sm_time = SplitMix() 
    var sm_seed = SplitMix.with_warmup(12345, 0)
    var sm_seed_warmup = SplitMix.with_warmup(12345, 10)

    assert_equal(sm_seed.get_seed(), 12345)
    assert_equal(sm_seed_warmup.get_seed(), 12345)

    var val_time_a = sm_time.next()
    var val_time_b = sm_time.next()
    assert_true(val_time_a != val_time_b)
    print(" SplitMix time-seeded values:", val_time_a, val_time_b)

    var val_seed_a = sm_seed.next()
    sm_seed.reset() # reset with original seed and warmup (0 in this case)
    var val_seed_b = sm_seed.next()
    assert_equal(val_seed_a, val_seed_b)

    var val_warmup_a = sm_seed_warmup.next() # After 10 internal warmup + 1 next
    
    var sm_seed_no_warmup_compare = SplitMix.with_warmup(12345, 0) # Original seed, no explicit warmup
    var val_no_warmup_compare = sm_seed_no_warmup_compare.next()
    
    assert_true(val_warmup_a != val_no_warmup_compare)
    print(" SplitMix warmup test: Output with warmup differs from no warmup, as expected.")

    sm_seed.reseed(54321, 5) # New seed, new warmup
    assert_equal(sm_seed.get_seed(), 54321)
    var val_reseed = sm_seed.next()
    print(" SplitMix reseed val:", val_reseed)
    assert_true(val_reseed != val_seed_a)
    
    var scalar_val = sm_seed.next_scalar()
    assert_true(scalar_val != val_reseed)

    print("SplitMix tests passed (basic checks).")

fn test_xoroshiro128plus() raises:
    print("\nTesting Xoroshiro128Plus...")
    var rng_time = Xoroshiro128Plus()
    var seed_time = rng_time.get_seed()
    print(" Initialized Xoroshiro128Plus with seed (time-based):", seed_time)
    var val_time_a = rng_time.next()
    var val_time_b = rng_time.next()
    print(" val_time_a:", val_time_a, "val_time_b:", val_time_b)
    assert_true(val_time_a != val_time_b)

    var rng_seeded = Xoroshiro128Plus(12345)
    assert_equal(rng_seeded.get_seed(), 12345)
    var val_seeded_a = rng_seeded.next()
    var val_seeded_b = rng_seeded.next()
    assert_true(val_seeded_a != val_seeded_b)

    rng_seeded.reset()
    assert_equal(rng_seeded.get_seed(), 12345)
    var val_seeded_c = rng_seeded.next()
    assert_equal(val_seeded_c, val_seeded_a)

    rng_seeded.reseed(54321)
    assert_equal(rng_seeded.get_seed(), 54321)
    var val_reseed_d = rng_seeded.next()
    assert_true(val_reseed_d != val_seeded_a)

    var val_call = rng_seeded() # Test __call__
    var val_scalar = rng_seeded.next_scalar()
    print(" val_reseed_d:", val_reseed_d, "val_call:", val_call, "val_scalar", val_scalar)
    assert_true(val_call != val_reseed_d)
    assert_true(val_scalar != val_call)

    # Test jump
    var rng_jump = Xoroshiro128Plus(789)
    for _ in range(5): _ = rng_jump.next() # Advance a bit
    var s0_before_jump = rng_jump.s0 # inspect internal state (for simple check only)
    rng_jump.jump()
    var s0_after_jump = rng_jump.s0
    assert_true(s0_before_jump != s0_after_jump)
    _ = rng_jump.next()  # Just verify it still works after jump
    print(" Jump test: Value after jump obtained.")

    # Test long_jump
    var rng_long_jump = Xoroshiro128Plus(101112)
    for _ in range(5): _ = rng_long_jump.next()
    var s0_before_long_jump = rng_long_jump.s0
    rng_long_jump.long_jump()
    var s0_after_long_jump = rng_long_jump.s0
    assert_true(s0_before_long_jump != s0_after_long_jump)
    _ = rng_long_jump.next()  # Just verify it still works after long_jump
    print(" Long jump test: Value after long jump obtained.")

    print("Xoroshiro128Plus tests passed (basic checks).")

fn test_xoroshiro128plusplus() raises:
    print("\nTesting Xoroshiro128PlusPlus...")
    var rng = Xoroshiro128PlusPlus(5678)
    assert_equal(rng.get_seed(), 5678)
    var v1 = rng.next()
    var v2 = rng.next()
    assert_true(v1 != v2)
    rng.reset()
    assert_equal(v1, rng.next())
    print(" Xoroshiro128PlusPlus basic values:", v1, v2)
    # Users can expand with jump/long_jump tests similar to Xoroshiro128Plus
    print("Xoroshiro128PlusPlus tests passed (basic checks).")

fn test_xoroshiro128starstar() raises:
    print("\nTesting Xoroshiro128StarStar...")
    var rng = Xoroshiro128StarStar(91011)
    assert_equal(rng.get_seed(), 91011)
    var v1 = rng.next()
    var v2 = rng.next()
    assert_true(v1 != v2)
    rng.reset()
    assert_equal(v1, rng.next())
    print(" Xoroshiro128StarStar basic values:", v1, v2)
    # Users can expand with jump/long_jump tests similar to Xoroshiro128Plus
    print("Xoroshiro128StarStar tests passed (basic checks).")

fn test_xoshiro256_n1_variants() raises:
    print("\nTesting Xoshiro256 (n=1) variants (aliases)...")
    var rng_s = Xoshiro256StarStar(11122) # n=1 alias for Xoshiro256VectStarStar[1]
    var rng_p = Xoshiro256Plus(33344)     
    var rng_pp = Xoshiro256PlusPlus(55566)

    var vs1 = rng_s.next()[0] # next() returns SIMD[_,1], so access [0]
    var vs2 = rng_s.next_scalar() # next_scalar() directly returns UInt64
    assert_true(vs1 != vs2)
    print(" Xoshiro256StarStar (n=1) values:", vs1, vs2)
    rng_s.reset()
    assert_equal(vs1, rng_s.next()[0])

    # Similar brief checks for Plus and PlusPlus
    var vp1 = rng_p.next_scalar()
    var vp2 = rng_p.next_scalar()
    assert_true(vp1 != vp2)
    print(" Xoshiro256Plus (n=1) values:", vp1, vp2)

    var vpp1 = rng_pp.next_scalar()
    var vpp2 = rng_pp.next_scalar()
    assert_true(vpp1 != vpp2)
    print(" Xoshiro256PlusPlus (n=1) values:", vpp1, vpp2)
    
    print("Xoshiro256 (n=1) variants tests passed (basic checks).")

fn test_xoshiro256vect_variants() raises:
    print("\nTesting Xoshiro256Vect (n=2) variants...")
    alias N: Int = 2 # Test with SIMD width 2. Ensure your Mojo setup supports this.
    alias SIMD_UI64_N = SIMD[DType.uint64, N]

    alias MyVectStarStar = Xoshiro256Vect[N, xoshiro256_star_star]
    var rng_vs = MyVectStarStar(77777)
    assert_equal(rng_vs.get_seed(), 77777)

    var val_vs_a: SIMD_UI64_N = rng_vs.next()
    var val_vs_b: SIMD_UI64_N = rng_vs.next()
    print(" MyVectStarStar (n=", N, ") val_a:", val_vs_a[0], val_vs_a[1])
    print(" MyVectStarStar (n=", N, ") val_b:", val_vs_b[0], val_vs_b[1])
    
    # Check streams are different and advance
    assert_true(val_vs_a[0] != val_vs_a[1])
    assert_true(val_vs_a[0] != val_vs_b[0])
    assert_true(val_vs_a[1] != val_vs_b[1])

    rng_vs.reset()
    var val_vs_c: SIMD_UI64_N = rng_vs.next()
    assert_true(val_vs_c[0] == val_vs_a[0] and val_vs_c[1] == val_vs_a[1])

    var val_before_scalar_call_s0 = rng_vs.s0[0] # Capture s0[0] before next_scalar
    var scalar_val = rng_vs.next_scalar() # next_scalar calls next(), then returns res[0]. It advances the state.
    
    # The state s0[0] should have changed due to the internal step() in next()
    assert_true(val_before_scalar_call_s0 != rng_vs.s0[0])
    # And scalar_val should be different from the s0[0] of the *previous* full SIMD output's stream 0
    assert_true(scalar_val != val_vs_c[0])


    # Test jump for one of the n=N variants
    var s0_val_before_jump = rng_vs.s0[0]
    rng_vs.jump()
    var s0_val_after_jump = rng_vs.s0[0]
    assert_true(s0_val_before_jump != s0_val_after_jump)
    print(" SIMD jump test passed for MyVectStarStar.")

    # Placeholder for other Xoshiro256Vect variants (Plus, PlusPlus) with N > 1
    alias MyVectPlus = Xoshiro256Vect[N, xoshiro256_plus]
    var rng_vp = MyVectPlus(88888)
    var val_vp_a: SIMD_UI64_N = rng_vp.next()
    print(" MyVectPlus (n=", N, ") val_a:", val_vp_a[0], val_vp_a[1])
    assert_true(val_vp_a[0] != val_vp_a[1])

    print("Xoshiro256Vect (n=", N, ") variants tests passed (basic checks).")

fn main() raises:
    print("Starting Xoshiro PRNG tests...")
    test_splitmix()
    test_xoroshiro128plus()
    test_xoroshiro128plusplus()
    test_xoroshiro128starstar()
    test_xoshiro256_n1_variants()
    test_xoshiro256vect_variants()

    print("\nAll basic tests completed.")
    print("Important: These are functional checks, not statistical quality tests.")
    print("Jump/LongJump tests confirm state changes, not cryptographic correctness of the jump.")
    print("Review output for any test failures or unexpected values.") 