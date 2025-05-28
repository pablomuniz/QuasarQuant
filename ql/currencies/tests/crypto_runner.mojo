# Mojo Runner to print crypto currency properties for comparison with C++
from sys import argv as sys_argv

# Import the specific currency instances from the crypto module
from quantfork.ql.currencies.crypto import (
    BTCCurrency, ETHCurrency, ETCCurrency, BCHCurrency, XRPCurrency,
    LTCCurrency, DASHCurrency, ZECCurrency
)
# Import the Currency type itself
from quantfork.ql.currency import Currency

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var selected_currency: Currency

    # Assign the correct currency instance based on the code
    if code == "BTC": selected_currency = BTCCurrency
    elif code == "ETH": selected_currency = ETHCurrency
    elif code == "ETC": selected_currency = ETCCurrency
    elif code == "BCH": selected_currency = BCHCurrency
    elif code == "XRP": selected_currency = XRPCurrency
    elif code == "LTC": selected_currency = LTCCurrency
    elif code == "DASH": selected_currency = DASHCurrency
    elif code == "ZEC": selected_currency = ZECCurrency
    else:
        print("Error: Unknown currency code '", code, "' in Mojo Crypto runner.")
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
        print("Usage: mojo crypto_runner.mojo <CurrencyCode>")
        return

    var currency_code = String(args[1])
    
    print_currency_properties(currency_code) 