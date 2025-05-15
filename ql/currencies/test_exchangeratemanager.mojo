from quantfork.ql.currencies.exchangeratemanager import ExchangeRateManager, ExchangeRate
from quantfork.ql.currencies.europe import *
from quantfork.ql.currencies.america import *
from quantfork.ql.currencies.asia import JPYCurrency
from quantfork.ql.currencies.oceania import AUDCurrency
from quantfork.ql.time.date import Date, January, December
from collections.optional import Optional

fn print_test_header(test_name: String, source: Currency, target: Currency, rate: Optional[Float64] = None):
    print("\n" + test_name)
    print("--------------------------------")
    print("Input:")
    print("  Source Currency:", source.code)
    print("  Target Currency:", target.code)
    if rate is not None:
        print("  Rate to add:", rate.value())

fn print_result(rate: Optional[ExchangeRate], date: Date) raises:
    print("\nResults:")
    print("  Mojo output:", end=" ")
    if rate is None:
        print("No rate available")
    else:
        var rate_val = rate.value()
        # Format with 6 decimal places
        var formatted_rate = String.format("{:.6f}", rate_val.rate)
        print(rate_val.source, "/", rate_val.target, "=", formatted_rate)
    print("--------------------------------")

fn main() raises:
    # Create a manager with some test rates
    var manager = ExchangeRateManager(Date(1, January, 2024), Date(31, December, 2024))
    
    # Test date
    var test_date = Date(1, January, 2024)
    
    # Test 1: Direct lookup (EUR/USD)
    print_test_header("Test 1: Direct lookup", EURCurrency, USDCurrency, 1.0850)
    manager.add_rate(EURCurrency, USDCurrency, 1.0850)
    var rate1 = manager.lookup(EURCurrency, USDCurrency, test_date)
    print_result(rate1, test_date)
    
    # Test 2: Inverse lookup (USD/EUR)
    print_test_header("Test 2: Inverse lookup", USDCurrency, EURCurrency)
    var rate2 = manager.lookup(USDCurrency, EURCurrency, test_date)
    print_result(rate2, test_date)
    
    # Test 3: Triangulation (EUR -> USD -> JPY)
    print_test_header("Test 3: Triangulation", EURCurrency, JPYCurrency, 148.50)
    manager.add_rate(USDCurrency, JPYCurrency, 148.50)
    var rate3 = manager.lookup(EURCurrency, JPYCurrency, test_date)
    print_result(rate3, test_date)
    
    # Test 4: Smart lookup with multiple paths
    print_test_header("Test 4: Smart lookup with multiple paths", EURCurrency, JPYCurrency)
    manager.add_rate(EURCurrency, GBPCurrency, 0.8550)
    manager.add_rate(GBPCurrency, JPYCurrency, 173.50)
    var rate4 = manager.lookup(EURCurrency, JPYCurrency, test_date)
    print_result(rate4, test_date)
    
    # Test 5: Obsoleted currency conversion (EUR -> DEM)
    print_test_header("Test 5: Obsoleted currency conversion", EURCurrency, DEMCurrency)
    var rate5 = manager.lookup(EURCurrency, DEMCurrency, test_date)
    print_result(rate5, test_date)
    
    # Test 6: Clear and reinitialize
    print_test_header("Test 6: Clear and reinitialize", EURCurrency, DEMCurrency)
    manager.clear()
    var rate6 = manager.lookup(EURCurrency, DEMCurrency, test_date)
    print_result(rate6, test_date)
    
    # Test 7: Invalid date
    print_test_header("Test 7: Invalid date", EURCurrency, DEMCurrency)
    var invalid_date = Date(1, January, 1998)  # Before Euro introduction
    var rate7 = manager.lookup(EURCurrency, DEMCurrency, invalid_date)
    print_result(rate7, invalid_date)
    
    # Test 8: Non-existent rate
    print_test_header("Test 8: Non-existent rate", EURCurrency, AUDCurrency)
    var rate8 = manager.lookup(EURCurrency, AUDCurrency, test_date)
    print_result(rate8, test_date) 