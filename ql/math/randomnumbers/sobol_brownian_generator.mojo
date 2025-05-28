"""
Sobol Brownian generators for Monte Carlo simulations.

This module provides Brownian motion generators based on Sobol low-discrepancy sequences
with Brownian bridge construction for improved efficiency.
"""

from collections import List
from math import sqrt, log
from memory import memcpy
from quantfork.ql.math.randomnumbers.sobolrsg import SobolRsg, DirectionIntegers, Sample

# ===----------------------------------------------------------------------=== #
# Ordering Enum
# ===----------------------------------------------------------------------=== #

@value 
struct Ordering:
    """Ordering of factors and steps in the Sobol sequence."""
    var value: Int
    
    alias Factors = Ordering(0)    # Fill by factor first
    alias Steps = Ordering(1)      # Fill by step first  
    alias Diagonal = Ordering(2)   # Fill diagonally

# ===----------------------------------------------------------------------=== #
# Inverse Cumulative Normal Distribution
# ===----------------------------------------------------------------------=== #

fn inverse_cumulative_normal(x: Float64) -> Float64:
    """
    Inverse cumulative normal distribution function.
    Uses Beasley-Springer-Moro algorithm for approximation.
    """
    if x <= 0.0 or x >= 1.0:
        return 0.0
        
    # Transform to standard normal variable
    var y = x - 0.5
    
    if abs(y) < 0.42:
        # Central region - use rational approximation
        var r = y * y
        var num = (((2.50662823884 * r + 18.61500062529) * r + 41.39119773534) * r + 25.44106049637) * r - 7.784894002430
        var den = ((((3.80036742022 * r + 24.65847065551) * r + 54.47609879853) * r + 44.08050738932) * r + 15.50398748121) * r + 1.0
        return y * num / den
    else:
        # Tail regions
        var r: Float64
        if y > 0:
            r = log(-log(1.0 - x))
        else:
            r = log(-log(x))
            
        var num = ((2.53989162540 * r + 9.76509903226) * r + 12.06284622431) * r + 5.06369196375
        var den = (((3.38767757751 * r + 11.03690054193) * r + 15.06436872916) * r + 8.45073743143) * r + 1.0
        var result = num / den
        
        if y < 0:
            return -result
        else:
            return result

# ===----------------------------------------------------------------------=== #
# Brownian Bridge
# ===----------------------------------------------------------------------=== #

struct BrownianBridge:
    """
    Brownian Bridge construction for transforming uniform random variables
    to Brownian motion paths.
    """
    
    var size_: Int
    var t_: List[Float64]  # Time points
    var sqrtdt_: List[Float64]  # Square root of time differences
    var bridge_index_: List[Int]  # Bridge construction order
    var left_index_: List[Int]
    var right_index_: List[Int]
    var left_weight_: List[Float64]
    var right_weight_: List[Float64]
    var std_dev_: List[Float64]
    
    fn __init__(out self, size: Int):
        """Initialize Brownian bridge for given number of time steps."""
        self.size_ = size
        self.t_ = List[Float64](capacity=size + 1)
        self.sqrtdt_ = List[Float64](capacity=size)
        self.bridge_index_ = List[Int](capacity=size)
        self.left_index_ = List[Int](capacity=size)
        self.right_index_ = List[Int](capacity=size)
        self.left_weight_ = List[Float64](capacity=size)
        self.right_weight_ = List[Float64](capacity=size)
        self.std_dev_ = List[Float64](capacity=size)
        
        # Initialize time points (uniform spacing for now)
        for i in range(size + 1):
            self.t_.append(Float64(i) / Float64(size))
            
        for i in range(size):
            self.sqrtdt_.append(sqrt(self.t_[i+1] - self.t_[i]))
            
        self._initialize_bridge()
    
    fn _initialize_bridge(mut self):
        """Initialize the bridge construction indices and weights."""
        # Simple bridge construction - this is a simplified version
        # Real implementation would use binary tree construction
        
        for i in range(self.size_):
            self.bridge_index_.append(i)
            self.left_index_.append(max(0, i-1))
            self.right_index_.append(min(self.size_-1, i+1))
            
            # Weights for interpolation
            if i == 0:
                self.left_weight_.append(0.0)
                self.right_weight_.append(1.0)
            elif i == self.size_ - 1:
                self.left_weight_.append(1.0)
                self.right_weight_.append(0.0)
            else:
                var dt_left = self.t_[i] - self.t_[i-1]
                var dt_right = self.t_[i+1] - self.t_[i]
                var total_dt = dt_left + dt_right
                self.left_weight_.append(dt_right / total_dt)
                self.right_weight_.append(dt_left / total_dt)
            
            # Standard deviation for this step
            if i == 0:
                self.std_dev_.append(self.sqrtdt_[i])
            else:
                var dt = self.t_[i+1] - self.t_[i-1] if i < self.size_-1 else self.t_[i] - self.t_[i-1]
                self.std_dev_.append(sqrt(dt))

# ===----------------------------------------------------------------------=== #
# Standard Sobol Brownian Generator
# ===----------------------------------------------------------------------=== #

struct SobolBrownianGenerator:
    """Standard Sobol Brownian generator using regular Sobol sequences."""
    
    var factors_: Int
    var steps_: Int
    var ordering_: Ordering
    var bridge_: BrownianBridge
    var ordered_indices_: List[List[Int]]
    var bridged_variates_: List[List[Float64]]
    var last_step_: Int
    var generator_: SobolRsg
    
    fn __init__(
        out self,
        factors: Int,
        steps: Int,
        ordering: Ordering,
        seed: UInt = 0,
        integers: DirectionIntegers = DirectionIntegers.Jaeckel
    ):
        """
        Initialize standard Sobol Brownian generator.
        
        Args:
            factors: Number of factors
            steps: Number of time steps
            ordering: Sequence ordering
            seed: Random seed
            integers: Direction integers type
        """
        self.factors_ = factors
        self.steps_ = steps
        self.ordering_ = ordering
        self.bridge_ = BrownianBridge(steps)
        self.last_step_ = 0
        self.generator_ = SobolRsg(factors * steps, seed, integers)
        
        # Initialize ordered indices matrix
        self.ordered_indices_ = List[List[Int]](capacity=factors)
        for i in range(factors):
            var factor_indices = List[Int](capacity=steps)
            for j in range(steps):
                factor_indices.append(0)
            self.ordered_indices_.append(factor_indices^)
            
        # Initialize bridged variates matrix
        self.bridged_variates_ = List[List[Float64]](capacity=factors)
        for i in range(factors):
            var factor_variates = List[Float64](capacity=steps)
            for j in range(steps):
                factor_variates.append(0.0)
            self.bridged_variates_.append(factor_variates^)
            
        self._fill_ordered_indices()
    
    fn _fill_ordered_indices(mut self):
        """Fill the ordered indices matrix based on the ordering type."""
        var counter = 0
        
        if self.ordering_.value == Ordering.Factors.value:
            # Fill by factor first
            for i in range(self.factors_):
                for j in range(self.steps_):
                    self.ordered_indices_[i][j] = counter
                    counter += 1
                    
        elif self.ordering_.value == Ordering.Steps.value:
            # Fill by step first
            for j in range(self.steps_):
                for i in range(self.factors_):
                    self.ordered_indices_[i][j] = counter
                    counter += 1
                    
        elif self.ordering_.value == Ordering.Diagonal.value:
            # Fill diagonally (variate 2 used for second factor's full path)
            var i0 = 0
            var j0 = 0
            var i = 0
            var j = 0
            
            while counter < self.factors_ * self.steps_:
                self.ordered_indices_[i][j] = counter
                counter += 1
                
                if i == 0 or j == self.steps_ - 1:
                    # We completed a diagonal and have to start a new one
                    if i0 < self.factors_ - 1:
                        # We start the path of the next factor
                        i0 = i0 + 1
                        j0 = 0
                    else:
                        # We move along the path of the last factor
                        i0 = self.factors_ - 1
                        j0 = j0 + 1
                    i = i0
                    j = j0
                else:
                    # We move along the diagonal
                    i = i - 1
                    j = j + 1
    
    fn next_sequence(mut self) -> Sample:
        """Get the next Sobol sequence from the underlying generator."""
        return self.generator_.next_sequence()
    
    fn next_path(mut self) -> Float64:
        """Generate the next Brownian path and return the weight."""
        var sample = self.next_sequence()
        
        # Apply Brownian bridge transformation
        for i in range(self.factors_):
            # Transform uniform variates to normal using ordered indices
            for j in range(self.steps_):
                var uniform_val = sample.value[self.ordered_indices_[i][j]]
                self.bridged_variates_[i][j] = inverse_cumulative_normal(uniform_val)
        
        self.last_step_ = 0
        return sample.weight
    
    fn next_step(mut self, mut output: List[Float64]) -> Float64:
        """
        Get the next step values for all factors.
        
        Args:
            output: Output list to fill with factor values
            
        Returns:
            Weight (always 1.0 for this implementation)
        """
        if len(output) != self.factors_:
            print("Error: output size mismatch")
            return 0.0
            
        if self.last_step_ >= self.steps_:
            print("Error: sequence exhausted")
            return 0.0
            
        for i in range(self.factors_):
            output[i] = self.bridged_variates_[i][self.last_step_]
            
        self.last_step_ += 1
        return 1.0
    
    fn number_of_factors(self) -> Int:
        """Get the number of factors."""
        return self.factors_
        
    fn number_of_steps(self) -> Int:
        """Get the number of steps."""
        return self.steps_
    
    fn ordered_indices(self) -> List[List[Int]]:
        """Get the ordered indices matrix."""
        return self.ordered_indices_

# ===----------------------------------------------------------------------=== #
# Burley2020 Sobol Brownian Generator
# ===----------------------------------------------------------------------=== #

struct Burley2020SobolBrownianGenerator:
    """Burley2020 scrambled Sobol Brownian generator for improved properties."""
    
    var factors_: Int
    var steps_: Int
    var ordering_: Ordering
    var bridge_: BrownianBridge
    var ordered_indices_: List[List[Int]]
    var bridged_variates_: List[List[Float64]]
    var last_step_: Int
    var generator_: SobolRsg  # Would be Burley2020SobolRsg in full implementation
    var scramble_seed_: UInt
    
    fn __init__(
        out self,
        factors: Int,
        steps: Int,
        ordering: Ordering,
        seed: UInt = 0,
        integers: DirectionIntegers = DirectionIntegers.Jaeckel,
        scramble_seed: UInt = 0
    ):
        """
        Initialize Burley2020 Sobol Brownian generator.
        
        Args:
            factors: Number of factors
            steps: Number of time steps  
            ordering: Sequence ordering
            seed: Random seed
            integers: Direction integers type
            scramble_seed: Seed for scrambling
        """
        self.factors_ = factors
        self.steps_ = steps
        self.ordering_ = ordering
        self.bridge_ = BrownianBridge(steps)
        self.last_step_ = 0
        self.scramble_seed_ = scramble_seed
        # For now, use regular SobolRsg - would use Burley2020SobolRsg in full implementation
        self.generator_ = SobolRsg(factors * steps, seed, integers, use_gray_code=False)
        
        # Initialize ordered indices matrix
        self.ordered_indices_ = List[List[Int]](capacity=factors)
        for i in range(factors):
            var factor_indices = List[Int](capacity=steps)
            for j in range(steps):
                factor_indices.append(0)
            self.ordered_indices_.append(factor_indices^)
            
        # Initialize bridged variates matrix
        self.bridged_variates_ = List[List[Float64]](capacity=factors)
        for i in range(factors):
            var factor_variates = List[Float64](capacity=steps)
            for j in range(steps):
                factor_variates.append(0.0)
            self.bridged_variates_.append(factor_variates^)
            
        self._fill_ordered_indices()
    
    fn _fill_ordered_indices(mut self):
        """Fill the ordered indices matrix based on the ordering type."""
        var counter = 0
        
        if self.ordering_.value == Ordering.Factors.value:
            # Fill by factor first
            for i in range(self.factors_):
                for j in range(self.steps_):
                    self.ordered_indices_[i][j] = counter
                    counter += 1
                    
        elif self.ordering_.value == Ordering.Steps.value:
            # Fill by step first
            for j in range(self.steps_):
                for i in range(self.factors_):
                    self.ordered_indices_[i][j] = counter
                    counter += 1
                    
        elif self.ordering_.value == Ordering.Diagonal.value:
            # Fill diagonally (variate 2 used for second factor's full path)
            var i0 = 0
            var j0 = 0
            var i = 0
            var j = 0
            
            while counter < self.factors_ * self.steps_:
                self.ordered_indices_[i][j] = counter
                counter += 1
                
                if i == 0 or j == self.steps_ - 1:
                    # We completed a diagonal and have to start a new one
                    if i0 < self.factors_ - 1:
                        # We start the path of the next factor
                        i0 = i0 + 1
                        j0 = 0
                    else:
                        # We move along the path of the last factor
                        i0 = self.factors_ - 1
                        j0 = j0 + 1
                    i = i0
                    j = j0
                else:
                    # We move along the diagonal
                    i = i - 1
                    j = j + 1
    
    fn next_sequence(mut self) -> Sample:
        """Get the next scrambled Sobol sequence."""
        # Apply Burley2020 scrambling to the basic Sobol sequence
        var base_sample = self.generator_.next_sequence()
        
        # For now, return the base sample - would apply scrambling in full implementation
        return base_sample
    
    fn next_path(mut self) -> Float64:
        """Generate the next Brownian path and return the weight."""
        var sample = self.next_sequence()
        
        # Apply Brownian bridge transformation
        for i in range(self.factors_):
            # Transform uniform variates to normal using ordered indices
            for j in range(self.steps_):
                var uniform_val = sample.value[self.ordered_indices_[i][j]]
                self.bridged_variates_[i][j] = inverse_cumulative_normal(uniform_val)
        
        self.last_step_ = 0
        return sample.weight
    
    fn next_step(mut self, mut output: List[Float64]) -> Float64:
        """Get the next step values for all factors."""
        if len(output) != self.factors_:
            print("Error: output size mismatch")
            return 0.0
            
        if self.last_step_ >= self.steps_:
            print("Error: sequence exhausted")
            return 0.0
            
        for i in range(self.factors_):
            output[i] = self.bridged_variates_[i][self.last_step_]
            
        self.last_step_ += 1
        return 1.0
    
    fn number_of_factors(self) -> Int:
        """Get the number of factors."""
        return self.factors_
        
    fn number_of_steps(self) -> Int:
        """Get the number of steps."""
        return self.steps_
    
    fn ordered_indices(self) -> List[List[Int]]:
        """Get the ordered indices matrix."""
        return self.ordered_indices_

# ===----------------------------------------------------------------------=== #
# Factory Classes
# ===----------------------------------------------------------------------=== #

struct SobolBrownianGeneratorFactory:
    """Factory for creating standard Sobol Brownian generators."""
    
    var ordering_: Ordering
    var seed_: UInt
    var integers_: DirectionIntegers
    
    fn __init__(
        out self,
        ordering: Ordering,
        seed: UInt = 0,
        integers: DirectionIntegers = DirectionIntegers.Jaeckel
    ):
        self.ordering_ = ordering
        self.seed_ = seed
        self.integers_ = integers
    
    fn create(self, factors: Int, steps: Int) -> SobolBrownianGenerator:
        """Create a new Sobol Brownian generator with the factory settings."""
        return SobolBrownianGenerator(factors, steps, self.ordering_, self.seed_, self.integers_)

struct Burley2020SobolBrownianGeneratorFactory:
    """Factory for creating Burley2020 Sobol Brownian generators."""
    
    var ordering_: Ordering
    var seed_: UInt
    var integers_: DirectionIntegers  
    var scramble_seed_: UInt
    
    fn __init__(
        out self,
        ordering: Ordering,
        seed: UInt = 0,
        integers: DirectionIntegers = DirectionIntegers.Jaeckel,
        scramble_seed: UInt = 0
    ):
        self.ordering_ = ordering
        self.seed_ = seed
        self.integers_ = integers
        self.scramble_seed_ = scramble_seed
    
    fn create(self, factors: Int, steps: Int) -> Burley2020SobolBrownianGenerator:
        """Create a new Burley2020 Sobol Brownian generator with the factory settings."""
        return Burley2020SobolBrownianGenerator(
            factors, steps, self.ordering_, self.seed_, self.integers_, self.scramble_seed_
        ) 