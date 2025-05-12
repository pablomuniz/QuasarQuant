# Mojo Runner to print crypto currency properties for comparison with C++
from sys import argv as sys_argv

# Import the necessary structs from the main crypto definitions file
from quantfork.ql.currencies.crypto import (
    CurrencyData, Rounding, # Base types needed
    BTCCurrency, ETHCurrency, ETCCurrency, BCHCurrency, XRPCurrency,
    LTCCurrency, DASHCurrency, ZECCurrency
)

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var currency_data: CurrencyData

    if code == "BTC": currency_data = BTCCurrency().data
    elif code == "ETH": currency_data = ETHCurrency().data
    elif code == "ETC": currency_data = ETCCurrency().data
    elif code == "BCH": currency_data = BCHCurrency().data
    elif code == "XRP": currency_data = XRPCurrency().data
    elif code == "LTC": currency_data = LTCCurrency().data
    elif code == "DASH": currency_data = DASHCurrency().data
    elif code == "ZEC": currency_data = ZECCurrency().data
    else:
        print("Error: Unknown currency code '", code, "' in Mojo runner.")
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
        print("Usage: mojo crypto_runner.mojo <CurrencyCode>")
        return

    # Command-line arg is likely StringLiteral, convert to String
    var currency_code_arg = args[1]
    var currency_code = String(currency_code_arg)

    print_currency_properties(currency_code) 