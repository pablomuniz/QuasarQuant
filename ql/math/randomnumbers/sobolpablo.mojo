from algorithm import vectorize
from collections import InlineArray
from memory import UnsafePointer
from math import log2
from bit import count_trailing_zeros
from random import random_ui64
from quantfork.ql.math.randomnumbers.sobol_structs import *
from quantfork.ql.math.randomnumbers.mt19937uniformrng import MersenneTwisterUniformRng
from quantfork.ql.math.randomnumbers.primitivepolynomials import PrimitivePolynomials, PPMT_MAX_DIM

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
    """High-performance Sobol sequence generator with vectorized operations.
    
    Parameters:
        dimensions: Number of dimensions for the sequence (compile-time constant).
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
            seed: Random seed for dimensions beyond tabulated values.
            use_gray_code: Use Gray code optimization (recommended for performance).
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
        var max_tabulated = self._load_tabulated_values[dimensions](
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
        var poly_index: Int32 = 0
        
        # Get alternative polynomial limit
        var alt_limit = maxAltDegree if use_alt_polynomials else 0
        
        # Create polynomial structure
        var polynomials = PrimitivePolynomials()
        
        # Process alternative polynomials if needed
        var k = 1
        if use_alt_polynomials and alt_limit > 0:
            while k < min(dimensions, alt_limit):
                # Access alternative polynomials
                var poly_value = alt_primitive_polynomials[Int(current_degree) - 1][poly_index]
                coefficients[k] = poly_value
                
                if coefficients[k] == -1:
                    current_degree += 1
                    poly_index = 0
                    poly_value = alt_primitive_polynomials[Int(current_degree) - 1][poly_index]
                    coefficients[k] = poly_value
                
                degrees[k] = current_degree
                poly_index += 1
                k += 1
        
        # Process standard polynomials for remaining dimensions
        while k < dimensions:
            # Get polynomial based on current degree
            var poly_value: Int64 = 0
            
            # Access the appropriate degree polynomial array
            if current_degree <= 18:
                var poly_ptr = polynomials.pointers[Int(current_degree) - 1]
                var poly_span = polynomials.spans[Int(current_degree) - 1]
                
                if poly_index < poly_span:
                    poly_value = Int64(poly_ptr[poly_index])
                else:
                    # Move to next degree
                    current_degree += 1
                    poly_index = 0
                    if current_degree <= 18:
                        poly_ptr = polynomials.pointers[Int(current_degree) - 1]
                        poly_value = Int64(poly_ptr[poly_index])
            
            coefficients[k] = poly_value
            degrees[k] = current_degree
            poly_index += 1
            k += 1
            
    fn _load_tabulated_values[dimensions: Int](
        mut self,
        direction_method: Int,
        degrees: InlineArray[UInt32, dimensions]
    ) raises -> Int:
        """Load tabulated direction integer values.
        
        Returns:
            Maximum dimension with tabulated values.
        """
        var max_tabulated: Int = 0
        
        if direction_method == DirectionIntegerMethod.UNIT:
            max_tabulated = dimensions
            for k in range(1, max_tabulated):
                for l in range(1, Int(degrees[k]) + 1):
                    self.direction_integers[k][l-1] = 1 << (DIRECTION_INTEGERS_COUNT - l)
        
        elif direction_method == DirectionIntegerMethod.JAECKEL:
            max_tabulated = min(32, dimensions)
            for k in range(1, max_tabulated):
                # k+1 because dimensions start at 2 in jackel_initializers
                var init_ptr = jackel_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
        
        elif direction_method == DirectionIntegerMethod.SOBOL_LEVITAN:
            max_tabulated = min(40, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = sobol_leviatan.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
                    
        elif direction_method == DirectionIntegerMethod.SOBOL_LEVITAN_LEMIEUX:
            max_tabulated = min(360, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = l_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
        
        elif direction_method == DirectionIntegerMethod.JOE_KUO_D5:
            max_tabulated = min(1898, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = joe_kuo_d5_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
                    
        elif direction_method == DirectionIntegerMethod.JOE_KUO_D6:
            max_tabulated = min(1799, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = joe_kuo_d6_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
                    
        elif direction_method == DirectionIntegerMethod.JOE_KUO_D7:
            max_tabulated = min(1898, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = joe_kuo_d7_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
                    
        elif direction_method == DirectionIntegerMethod.KUO:
            max_tabulated = min(4925, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = kuo_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
                    
        elif direction_method == DirectionIntegerMethod.KUO2:
            max_tabulated = min(3946, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = kuo2_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
                    
        elif direction_method == DirectionIntegerMethod.KUO3:
            max_tabulated = min(4585, dimensions)
            for k in range(1, max_tabulated):
                var init_ptr = kuo3_initializers.get_initializer(k+1)
                var j = 0
                while j < Int(degrees[k]) and init_ptr[j] != 0:
                    self.direction_integers[k][j] = init_ptr[j]
                    self.direction_integers[k][j] <<= (32 - j - 1)
                    j += 1
        
        # else:
        #     max_tabulated = min(32, dimensions)
        
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
    fn _xor_direction_vectorized(mut self, j: Int):
        @parameter
        fn xor_op[simd_width: Int](idx: Int):
            @parameter
            if simd_width == 1:
                self.integer_sequence[idx] ^= self.direction_integers[idx][j]
            else:
                for i in range(simd_width):
                    if idx + i < dimensions:
                        self.integer_sequence[idx + i] ^= self.direction_integers[idx + i][j]
        
        vectorize[xor_op, simd_width=16](dimensions)

    
    @always_inline
    fn _normalize_sequence_vectorized(mut self):
        """Normalize integer sequence to (0,1) using vectorize."""
        @parameter
        fn normalize_op[simd_width: Int](idx: Int) -> None:
            """Vectorized normalization."""
            if idx + simd_width <= dimensions:
                # Load integers as SIMD vector
                var int_vals = SIMD[DType.uint32, simd_width]()
                for i in range(simd_width):
                    int_vals[i] = self.integer_sequence[idx + i]
                
                # Convert to float64 and normalize
                var float_vals = int_vals.cast[DType.float64]() * NORMALIZATION_FACTOR
                
                # Store normalized values
                for i in range(simd_width):
                    self.float_sequence[idx + i] = float_vals[i]
        
        vectorize[normalize_op, dimensions]()
    
    @always_inline
    fn next_sequence(mut self) raises -> InlineArray[Float64, dimensions]:
        """Generate next Sobol sequence normalized to (0,1)."""
        if self.use_gray_code:
            self._next_gray_code_sequence()
        else:
            self._next_standard_sequence()
        
        # Normalize using vectorized function
        self._normalize_sequence_vectorized()
        
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
        var n = self.sequence_counter
        var j = 0
        while (n & 1) != 0:
            n >>= 1
            j += 1
        
        # XOR with direction integers using vectorized function
        self._xor_direction_vectorized(j)
    
    @always_inline
    fn _next_standard_sequence(mut self) raises:
        """Generate next sequence without Gray code."""
        self._skip_to_internal(self.sequence_counter)
        
        if self.first_draw:
            self.first_draw = False
        else:
            self.sequence_counter += 1
            if self.sequence_counter == 0:
                raise "Sequence period exceeded"
    
    @always_inline
    fn skip_to(mut self, n: UInt32) raises -> InlineArray[UInt32, dimensions]:
        """Skip to the n-th sample in the low-discrepancy sequence."""
        if self.sequence_counter == 0:
            raise "Sequence period exceeded"
        
        # Find rightmost zero bit
        var n = self.sequence_counter
        var j = 0
        while (n & 1) != 0:
            n >>= 1
            j += 1
        
        # XOR with direction integers using vectorized function
        self._xor_direction_vectorized(j)
    
    @always_inline
    fn _next_standard_sequence(mut self) raises:
        """Generate next sequence without Gray code."""
        self._skip_to_internal(self.sequence_counter)
        
        if self.first_draw:
            self.first_draw = False
        else:
            self.sequence_counter += 1
            if self.sequence_counter == 0:
                raise "Sequence period exceeded"
    
    @always_inline
    fn skip_to(mut self, n: UInt32) raises -> InlineArray[UInt32, dimensions]:
        """Skip to the n-th sample in the low-discrepancy sequence."""
        self.sequence_counter = n
        self._skip_to_internal(n)
        return self.integer_sequence
    
    @always_inline
    fn _skip_to_internal(mut self, n: UInt32) raises:
        """Internal skip implementation."""
        var N = n + 1
        
        # Reset integer sequence using vectorize
        @parameter
        fn reset_op[simd_width: Int](idx: Int) -> None:
            if idx + simd_width <= dimensions:
                var zeros = SIMD[DType.uint32, simd_width](0)
                for i in range(simd_width):
                    self.integer_sequence[idx + i] = 0
        
        vectorize[reset_op, dimensions]()
        
        if self.use_gray_code:
            # Convert to Gray code
            var gray_code = N ^ (N >> 1)
            var num_bits = Int(log2(Float64(N))) + 1
            
            for bit_idx in range(num_bits):
                if (gray_code >> bit_idx) & 1 != 0:
                    self._xor_direction_vectorized(bit_idx)
        else:
            # Standard binary representation
            var mask: UInt32 = 1
            for bit_idx in range(DIRECTION_INTEGERS_COUNT):
                if (N & mask) != 0:
                    self._xor_direction_vectorized(bit_idx)
                mask <<= 1
    
    @always_inline
    fn dimension(self) -> Int:
        """Return the number of dimensions."""
        return dimensions
    
    @always_inline
    fn last_sequence(self) -> InlineArray[Float64, dimensions]:
        """Return the last generated sequence."""
        return self.float_sequence
    
    @always_inline
    fn last_integer_sequence(self) -> InlineArray[UInt32, dimensions]:
        """Return the last generated integer sequence."""
        return self.integer_sequence
    
    fn __del__(owned self):
        """Destructor - nothing to clean up with InlineArrays."""
        pass

        
fn main() raises:
    var rng = SobolGenerator[10]()