# Mojo Runner to print currency properties for comparison with C++
from sys import argv as sys_argv

# Import the necessary structs from the main africa definitions file
from quantfork.ql.currencies.africa import (
    CurrencyData, Rounding, # Base types needed
    AOACurrency, BWPCurrency, EGPCurrency, ETBCurrency, GHSCurrency, KESCurrency,
    MADCurrency, MURCurrency, NGNCurrency, TNDCurrency, UGXCurrency, XOFCurrency,
    ZARCurrency, ZMWCurrency
)

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    # We need to instantiate the correct struct based on the code
    # This mimics the C++ runner's logic
    var currency_data: CurrencyData

    if code == "AOA":
        var currency = AOACurrency()
        currency_data = currency.data
    elif code == "BWP":
        var currency = BWPCurrency()
        currency_data = currency.data
    elif code == "EGP":
        var currency = EGPCurrency()
        currency_data = currency.data
    elif code == "ETB":
        var currency = ETBCurrency()
        currency_data = currency.data
    elif code == "GHS":
        var currency = GHSCurrency()
        currency_data = currency.data
    elif code == "KES":
        var currency = KESCurrency()
        currency_data = currency.data
    elif code == "MAD":
        var currency = MADCurrency()
        currency_data = currency.data
    elif code == "MUR":
        var currency = MURCurrency()
        currency_data = currency.data
    elif code == "NGN":
        var currency = NGNCurrency()
        currency_data = currency.data
    elif code == "TND":
        var currency = TNDCurrency()
        currency_data = currency.data
    elif code == "UGX":
        var currency = UGXCurrency()
        currency_data = currency.data
    elif code == "XOF":
        var currency = XOFCurrency()
        currency_data = currency.data
    elif code == "ZAR":
        var currency = ZARCurrency()
        currency_data = currency.data
    elif code == "ZMW":
        var currency = ZMWCurrency()
        currency_data = currency.data
    else:
        print("Error: Unknown currency code '", code, "' in Mojo runner.")
        # Mojo doesn't have exit() built-in yet? We might need sys or os for exit codes.
        # For now, just print error and continue/return if possible.
        # If this is main, returning is sufficient.
        # Consider raising an error if used as a library.
        return
        
    # Print properties in the exact same format as the C++ runner
    print("Name:", currency_data.name)
    print("Code:", currency_data.code)
    print("NumericCode:", currency_data.numeric_code)
    print("Symbol:", currency_data.symbol)
    print("FractionSymbol:", currency_data.fraction_symbol)
    print("FractionsPerUnit:", currency_data.fractions_per_unit)
    
    # Print rounding details
    print("RoundingType:", currency_data.rounding.type.__str__())
    print("RoundingPrecision:", currency_data.rounding.precision)
    print("RoundingDigit:", currency_data.rounding.digit)

fn main() raises: # Raises needed for potential conversion errors
    var args = sys_argv()
    if len(args) != 2:
        print("Usage: mojo africa_runner.mojo <CurrencyCode>")
        return

    # Command-line arg is likely StringLiteral, convert to String
    var currency_code_arg = args[1]
    var currency_code = String(currency_code_arg)
    
    print_currency_properties(currency_code) 