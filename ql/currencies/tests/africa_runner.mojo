# Mojo Runner to print currency properties for comparison with C++
from sys import argv as sys_argv

# Import the specific currency instances from the africa module
from quantfork.ql.currencies.africa import (
    AOACurrency, BWPCurrency, EGPCurrency, ETBCurrency, GHSCurrency, KESCurrency,
    MADCurrency, MURCurrency, NGNCurrency, TNDCurrency, UGXCurrency, XOFCurrency,
    ZARCurrency, ZMWCurrency
)
# Import the Currency type itself
from quantfork.ql.currency import Currency

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var selected_currency: Currency

    # Assign the correct currency instance based on the code
    if code == "AOA": selected_currency = AOACurrency
    elif code == "BWP": selected_currency = BWPCurrency
    elif code == "EGP": selected_currency = EGPCurrency
    elif code == "ETB": selected_currency = ETBCurrency
    elif code == "GHS": selected_currency = GHSCurrency
    elif code == "KES": selected_currency = KESCurrency
    elif code == "MAD": selected_currency = MADCurrency
    elif code == "MUR": selected_currency = MURCurrency
    elif code == "NGN": selected_currency = NGNCurrency
    elif code == "TND": selected_currency = TNDCurrency
    elif code == "UGX": selected_currency = UGXCurrency
    elif code == "XOF": selected_currency = XOFCurrency
    elif code == "ZAR": selected_currency = ZARCurrency
    elif code == "ZMW": selected_currency = ZMWCurrency
    else:
        print("Error: Unknown currency code '", code, "' in Mojo Africa runner.")
        return
        
    # Print properties in the exact same format as the C++ runner
    print("Name:", selected_currency.name)
    print("Code:", selected_currency.code)
    print("NumericCode:", selected_currency.numeric_code)
    print("Symbol:", selected_currency.symbol)
    print("FractionSymbol:", selected_currency.fraction_symbol)
    print("FractionsPerUnit:", selected_currency.fractions_per_unit)
    
    # Print rounding details
    print("RoundingType:", selected_currency.rounding.type.__str__())
    print("RoundingPrecision:", selected_currency.rounding.precision)
    print("RoundingDigit:", selected_currency.rounding.digit)

fn main() raises:
    var args = sys_argv()
    if len(args) != 2:
        print("Usage: mojo africa_runner.mojo <CurrencyCode>")
        return

    var currency_code = String(args[1])
    
    print_currency_properties(currency_code) 