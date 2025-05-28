"""
Monte Carlo simulation example using Sobol sequences.

This example demonstrates using Sobol Brownian generators for option pricing
and other financial simulations.
"""

from collections import List
from math import exp, sqrt, log
from builtin.math import max as math_max
from quantfork.ql.math.randomnumbers.sobolrsg import SobolRsg, DirectionIntegers
from quantfork.ql.math.randomnumbers.sobol_brownian_generator import SobolBrownianGenerator, Ordering

# ===----------------------------------------------------------------------=== #
# Monte Carlo Option Pricing Example
# ===----------------------------------------------------------------------=== #

fn monte_carlo_european_call(
    spot: Float64,           # Current stock price
    strike: Float64,         # Strike price
    risk_free_rate: Float64, # Risk-free interest rate
    volatility: Float64,     # Volatility
    time_to_expiry: Float64, # Time to expiration
    num_paths: Int           # Number of Monte Carlo paths
) -> Float64:
    """
    Price a European call option using Monte Carlo with Sobol sequences.
    
    Args:
        spot: Current stock price
        strike: Strike price
        risk_free_rate: Risk-free interest rate
        volatility: Volatility (sigma)
        time_to_expiry: Time to expiration (T)
        num_paths: Number of Monte Carlo paths
        
    Returns:
        Option price
    """
    print("Pricing European Call Option using Sobol Monte Carlo:")
    print("  Spot:", spot)
    print("  Strike:", strike)
    print("  Rate:", risk_free_rate)
    print("  Volatility:", volatility)
    print("  Time to expiry:", time_to_expiry)
    print("  Number of paths:", num_paths)
    
    # Single factor (1D), single time step
    var generator = SobolBrownianGenerator(1, 1, Ordering.Factors)
    
    var payoff_sum = 0.0
    var drift = risk_free_rate - 0.5 * volatility * volatility
    var vol_sqrt_t = volatility * sqrt(time_to_expiry)
    
    var random_output = List[Float64](capacity=1)
    random_output.append(0.0)
    
    for path in range(num_paths):
        # Generate next path
        var weight = generator.next_path()
        var step_weight = generator.next_step(random_output)
        
        # Get the random normal variable
        var z = random_output[0]
        
        # Calculate final stock price using geometric Brownian motion
        var final_price = spot * exp(drift * time_to_expiry + vol_sqrt_t * z)
        
        # Calculate payoff
        var payoff = math_max(final_price - strike, 0.0)
        payoff_sum += payoff
        
        if path < 5:  # Print first few paths for debugging
            print("  Path", path, ": Z =", z, ", Final price =", final_price, ", Payoff =", payoff)
    
    # Discount back to present value
    var option_price = exp(-risk_free_rate * time_to_expiry) * payoff_sum / Float64(num_paths)
    
    print("  Option price:", option_price)
    return option_price

fn monte_carlo_geometric_asian_option(
    spot: Float64,
    strike: Float64,
    risk_free_rate: Float64,
    volatility: Float64,
    time_to_expiry: Float64,
    num_steps: Int,
    num_paths: Int
) -> Float64:
    """
    Price a geometric Asian option using multi-step Monte Carlo with Sobol sequences.
    
    Args:
        spot: Current stock price
        strike: Strike price
        risk_free_rate: Risk-free interest rate
        volatility: Volatility
        time_to_expiry: Time to expiration
        num_steps: Number of time steps for path discretization
        num_paths: Number of Monte Carlo paths
        
    Returns:
        Option price
    """
    print("\nPricing Geometric Asian Option using Multi-Step Sobol Monte Carlo:")
    print("  Spot:", spot)
    print("  Strike:", strike)
    print("  Time steps:", num_steps)
    print("  Number of paths:", num_paths)
    
    var generator = SobolBrownianGenerator(1, num_steps, Ordering.Steps)
    
    var dt = time_to_expiry / Float64(num_steps)
    var drift = risk_free_rate - 0.5 * volatility * volatility
    var vol_sqrt_dt = volatility * sqrt(dt)
    
    var payoff_sum = 0.0
    var random_output = List[Float64](capacity=1)
    random_output.append(0.0)
    
    for path in range(num_paths):
        var weight = generator.next_path()
        
        var log_price_sum = 0.0
        var current_log_price = log(spot)
        
        # Simulate the path
        for step in range(num_steps):
            var step_weight = generator.next_step(random_output)
            var z = random_output[0]
            
            # Update log price
            current_log_price += drift * dt + vol_sqrt_dt * z
            log_price_sum += current_log_price
        
        # Calculate geometric average
        var avg_log_price = log_price_sum / Float64(num_steps)
        var geometric_average = exp(avg_log_price)
        
        # Calculate payoff
        var payoff = math_max(geometric_average - strike, 0.0)
        payoff_sum += payoff
        
        if path < 3:  # Print first few paths
            print("  Path", path, ": Geometric avg =", geometric_average, ", Payoff =", payoff)
    
    # Discount back to present value
    var option_price = exp(-risk_free_rate * time_to_expiry) * payoff_sum / Float64(num_paths)
    
    print("  Asian option price:", option_price)
    return option_price

fn compare_sobol_vs_pseudorandom():
    """
    Compare convergence of Sobol vs pseudo-random sequences.
    (Note: For demo purposes, we'll just show Sobol convergence)
    """
    print("\n=== Convergence Analysis ===")
    
    var spot = 100.0
    var strike = 100.0
    var rate = 0.05
    var vol = 0.2
    var time_to_expiry = 1.0
    
    var path_counts = List[Int]()
    path_counts.append(100)
    path_counts.append(500)
    path_counts.append(1000)
    path_counts.append(5000)
    
    print("European Call Option convergence with Sobol sequences:")
    
    for i in range(len(path_counts)):
        var num_paths = path_counts[i]
        var price = monte_carlo_european_call(spot, strike, rate, vol, time_to_expiry, num_paths)
        print("  Paths:", num_paths, "-> Price:", price)

fn main():
    """Run Monte Carlo examples."""
    try:
        print("=== Sobol Monte Carlo Examples ===")
        
        # Basic European option
        var euro_price = monte_carlo_european_call(
            spot=100.0,
            strike=105.0, 
            risk_free_rate=0.05,
            volatility=0.2,
            time_to_expiry=1.0,
            num_paths=1000
        )
        
        # Multi-step Asian option
        var asian_price = monte_carlo_geometric_asian_option(
            spot=100.0,
            strike=100.0,
            risk_free_rate=0.05,
            volatility=0.2,
            time_to_expiry=1.0,
            num_steps=50,
            num_paths=1000
        )
        
        # Convergence analysis
        compare_sobol_vs_pseudorandom()
        
        print("\n=== Monte Carlo Examples Completed ===")
        
    except e:
        print("Error during Monte Carlo examples:", e) 