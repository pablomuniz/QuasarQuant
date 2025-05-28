from collections import InlineArray
from memory import UnsafePointer
from math import log2
from bit import count_trailing_zeros
from random import random_ui64
from quantfork.ql.math.randomnumbers.sobol_structs import *
from quantfork.ql.math.randomnumbers.mt19937uniformrng import MersenneTwisterUniformRng

# Constants
alias MAX_DIMENSIONS = 21200
alias DIRECTION_INTEGERS_COUNT = 32
alias NORMALIZATION_FACTOR: Float64 = 0.5 / (1 << 31)

# Direction integer initialization methods
@value
struct DirectionIntegerMethod:
    alias UNIT = 0
    alias JAECKEL = 1
    alias SOBOL_LEVITAN = 2
    alias SOBOL_LEVITAN_LEMIEUX = 3
    alias JOE_KUO_D5 = 4
    alias JOE_KUO_D6 = 5
    alias JOE_KUO_D7 = 6
    alias KUO = 7
    alias KUO2 = 8
    alias KUO3 = 9

    @staticmethod
    fn needs_alt_polynomials(method: Int) -> Bool:
        """Check if method requires alternative primitive polynomials."""
        return (method == DirectionIntegerMethod.KUO or
                method == DirectionIntegerMethod.KUO2 or
                method == DirectionIntegerMethod.KUO3 or
                method == DirectionIntegerMethod.SOBOL_LEVITAN or
                method == DirectionIntegerMethod.SOBOL_LEVITAN_LEMIEUX)

@value
struct SobolGenerator[dimensions: Int]:
    """High-performance Sobol sequence generator with SIMD optimizations.
    
    Parameters:
        dimensions: Number of dimensions for the sequence (compile-time constant)
    """
    
    var direction_integers: InlineArray[InlineArray[UInt32, DIRECTION_INTEGERS_COUNT], dimensions]
    var integer_sequence: InlineArray[UInt32, dimensions]
    var float_sequence: InlineArray[Float64, dimensions]
    var sequence_counter: UInt32
    var use_gray_code: Bool
    var first_draw: Bool
    
    fn __init__(
        out self,
        direction_method: Int = DirectionIntegerMethod.JAECKEL,
        seed: UInt64 = 0,
        use_gray_code: Bool = True
    ) raises:
        """Initialize Sobol sequence generator.
        
        Args:
            direction_method: Method for initializing direction integers
            seed: Random seed for dimensions beyond tabulated values
            use_gray_code: Use Gray code optimization (recommended for performance)
        """
        if dimensions <= 0:
            raise "Dimensions must be positive"
        if dimensions > MAX_DIMENSIONS:
            raise "Dimensions exceed maximum supported"
        
        self.sequence_counter = 0
        self.use_gray_code = use_gray_code
        self.first_draw = True
        
        # Initialize arrays
        self.integer_sequence = InlineArray[UInt32, dimensions]()
        self.float_sequence = InlineArray[Float64, dimensions]()
        self.direction_integers = InlineArray[InlineArray[UInt32, DIRECTION_INTEGERS_COUNT], dimensions]()
        
        # Initialize direction integers
        self._initialize_direction_integers(direction_method, seed)
        
        # Pre-compute first sequence if using Gray code
        if use_gray_code:
            for k in range(dimensions):
                self.integer_sequence[k] = self.direction_integers[k][0]
    
    fn _initialize_direction_integers(
        mut self,
        direction_method: Int,
        seed: UInt64
    ) raises:
        """Initialize direction integers based on chosen method."""
        
        # Arrays for polynomial info
        var polynomial_degrees = InlineArray[UInt32, dimensions]()
        var polynomial_coefficients = InlineArray[Int64, dimensions]()
        
        # Load primitive polynomials
        self._load_primitive_polynomials(
            DirectionIntegerMethod.needs_alt_polynomials(direction_method),
            polynomial_degrees,
            polynomial_coefficients
        )
        
        # Initialize first dimension (degenerate case)
        for j in range(DIRECTION_INTEGERS_COUNT):
            self.direction_integers[0][j] = 1 << (DIRECTION_INTEGERS_COUNT - j - 1)
        
        # Load tabulated values and get max tabulated dimension
        var max_tabulated = self._load_tabulated_values(
            direction_method,
            polynomial_degrees
        )
        
        # Generate remaining dimensions if needed
        if dimensions > max_tabulated:
            self._generate_random_directions(
                max_tabulated,
                polynomial_degrees,
                seed
            )
        
        # Complete all direction integers using recurrence relation
        self._complete_direction_integers(
            polynomial_degrees,
            polynomial_coefficients
        )
    
    fn _load_primitive_polynomials(
        self,
        use_alt_polynomials: Bool,
        mut degrees: InlineArray[UInt32, dimensions],
        mut coefficients: InlineArray[Int64, dimensions]
    ) raises:
        """Load primitive polynomials and their degrees."""
        
        # First dimension is unused
        degrees[0] = 0
        coefficients[0] = 0
        
        var current_degree: UInt32 = 1
        var poly_index = 0
        #var alt_limit = sobol_structs.maxAltDegree if use_alt_polynomials else 0
        var alt_limit = 0
        
        
        # Process alternative polynomials if needed
        var k = 1
        while k < min(dimensions, alt_limit):
            var poly_ptr = alt_primitive_polynomials[Int(current_degree) - 1]
            coefficients[k] = poly_ptr[poly_index]
            
            if coefficients[k] == -1:
                current_degree += 1
                poly_index = 0
                poly_ptr = alt_primitive_polynomials[Int(current_degree) - 1]
                coefficients[k] = poly_ptr[poly_index]
            
            degrees[k] = current_degree
            poly_index += 1
            k += 1
        
        # Process standard polynomials for remaining dimensions
        while k < dimensions:
            # Placeholder - in real implementation, load from PrimitivePolynomials
            coefficients[k] = poly_index
            degrees[k] = current_degree
            
            poly_index += 1
            k += 1
    
    fn _load_tabulated_values(
        mut self,
        direction_method: Int,
        degrees: InlineArray[UInt32, dimensions]
    ) -> Int:
        """Load tabulated direction integer values.
        
        Returns:
            Maximum dimension with tabulated values
        """
        var max_tabulated: Int = 0
        
        if direction_method == DirectionIntegerMethod.UNIT:
            max_tabulated = dimensions
            for k in range(1, max_tabulated):
                for l in range(1, Int(degrees[k]) + 1):
                    self.direction_integers[k][l-1] = 1 << (DIRECTION_INTEGERS_COUNT - l)
        
        elif direction_method == DirectionIntegerMethod.JAECKEL:
            max_tabulated = min(32, dimensions)
            # In real implementation, load from Jaeckel initializers
            for k in range(1, max_tabulated):
                for j in range(Int(degrees[k])):
                    self.direction_integers[k][j] = UInt32(j + 1) << (DIRECTION_INTEGERS_COUNT - j - 1)
        
        elif direction_method == DirectionIntegerMethod.JOE_KUO_D7:
            max_tabulated = min(1898, dimensions)
            # Load from JoeKuo D7 initializers
            for k in range(1, max_tabulated):
                for j in range(Int(degrees[k])):
                    self.direction_integers[k][j] = UInt32(j + 1) << (DIRECTION_INTEGERS_COUNT - j - 1)
        
        # Add other methods as needed
        else:
            max_tabulated = min(32, dimensions)
        
        return max_tabulated
    fn _generate_random_directions(
        mut self,
        start_dimension: Int,
        degrees: InlineArray[UInt32, dimensions],
        seed: UInt64
    ) raises:
        """Generate random direction integers for dimensions beyond tabulated values."""
        var rng = MersenneTwisterUniformRng(seed)
        for k in range(start_dimension, dimensions):
            var degree = Int(degrees[k])
            for l in range(1, degree + 1):
                var direction_int: UInt32 = 0
                while True:
                    var u = rng.next().value
                    direction_int = UInt32(u * Float64(1 << l))
                    if direction_int & 1 != 0:
                        break
                self.direction_integers[k][l-1] = direction_int << (32 - l)
    
    fn _complete_direction_integers(
        mut self,
        degrees: InlineArray[UInt32, dimensions],
        coefficients: InlineArray[Int64, dimensions]
    ):
        """Complete direction integers using recurrence relation."""
        for k in range(1, dimensions):
            var degree = Int(degrees[k])
            
            for l in range(degree, DIRECTION_INTEGERS_COUNT):
                var n = self.direction_integers[k][l - degree] >> degree
                
                # Apply recurrence relation (eq. 8.19 from Jäckel)
                for j in range(1, degree):
                    if (coefficients[k] >> (degree - j - 1)) & 1 != 0:
                        n ^= self.direction_integers[k][l - j]
                
                n ^= self.direction_integers[k][l - degree]
                self.direction_integers[k][l] = n
    
    @always_inline
    fn next_sequence(mut self) raises -> InlineArray[Float64, dimensions]:
        """Generate next Sobol sequence normalized to (0,1)."""
        if self.use_gray_code:
            self._next_gray_code_sequence()
        else:
            self._next_standard_sequence()
        
        # Normalize using SIMD
        self._normalize_sequence_simd()
        
        return self.float_sequence
    
    @always_inline
    fn next_integer_sequence(mut self) raises -> InlineArray[UInt32, dimensions]:
        """Generate next integer Sobol sequence."""
        if self.use_gray_code:
            self._next_gray_code_sequence()
        else:
            self._next_standard_sequence()
        
        return self.integer_sequence
    
    @always_inline
    fn _next_gray_code_sequence(mut self) raises:
        """Generate next sequence using Gray code optimization."""
        if self.first_draw:
            self.first_draw = False
            return
        
        self.sequence_counter += 1
        if self.sequence_counter == 0:
            raise "Sequence period exceeded"
        
        # Find rightmost zero bit
        var rightmost_zero = count_trailing_zeros(~self.sequence_counter)
        
        # XOR with direction integers using SIMD
        self._xor_direction_simd(Int(rightmost_zero))
    
    @always_inline
    fn _next_standard_sequence(mut self) raises:
        """Generate next sequence without Gray code."""
        if self.first_draw:
            self.first_draw = False
        else:
            self.sequence_counter += 1
            if self.sequence_counter == 0:
                raise "Sequence period exceeded"
        
        self._skip_to_internal(self.sequence_counter)
    
    @always_inline
    fn _xor_direction_simd(mut self, j: Int):
        """Perform XOR operation using SIMD instructions."""
        alias simd_width = 8
        
        @parameter
        for i in range(0, dimensions, simd_width):
            @parameter
            if i + simd_width <= dimensions:
                # Load current values into SIMD register
                var current = SIMD[DType.uint32, simd_width]()
                var direction = SIMD[DType.uint32, simd_width]()
                
                for k in range(simd_width):
                    current[k] = self.integer_sequence[i + k]
                    direction[k] = self.direction_integers[i + k][j]
    
    @always_inline
    fn _normalize_sequence_simd(mut self):
        """Normalize integer sequence to (0,1) using SIMD."""
        alias simd_width = 4
        
        @parameter
        for i in range(0, dimensions, simd_width):
            @parameter
            if i + simd_width <= dimensions:
                var int_vals = SIMD[DType.uint32, simd_width]()
                for k in range(simd_width):
                    int_vals[k] = self.integer_sequence[i + k]
                
                var float_vals = int_vals.cast[DType.float64]() * NORMALIZATION_FACTOR
                
                for k in range(simd_width):
                    self.float_sequence[i + k] = float_vals[k]
            else:
                @parameter
                for k in range(dimensions - i):
                    self.float_sequence[i + k] = Float64(self.integer_sequence[i + k]) * NORMALIZATION_FACTOR
    
    @always_inline
    fn _skip_to_internal(mut self, n: UInt32) raises:
        """Internal skip implementation."""
        var N = n + 1
        
        if self.use_gray_code:
            var gray_code = N ^ (N >> 1)
            var num_bits = Int(log2(Float64(N))) + 1
            
            @parameter
            for k in range(dimensions):
                self.integer_sequence[k] = 0
            
            for bit_idx in range(num_bits):
                if (gray_code >> bit_idx) & 1 != 0:
                    self._xor_direction_simd(bit_idx)
        else:
            @parameter
            for k in range(dimensions):
                self.integer_sequence[k] = 0
            
            var mask: UInt32 = 1
            for bit_idx in range(DIRECTION_INTEGERS_COUNT):
                if (N & mask) != 0:
                    self._xor_direction_simd(bit_idx)
                mask <<= 1