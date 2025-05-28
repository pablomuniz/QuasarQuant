# Mojo Runner to print Oceania currency properties for comparison with C++
from sys import argv as sys_argv

# Import the specific currency instances from the oceania module
from quantfork.ql.currencies.oceania import AUDCurrency, NZDCurrency
# Import the Currency type itself
from quantfork.ql.currency import Currency
# Import Rounding related types if specific rounding like RT_CLOSEST is needed, else not strictly necessary for base props
# from quantfork.ql.math.rounding import Rounding, RT_CLOSEST 

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var selected_currency: Currency

    # Assign the correct currency instance based on the code
    if code == "AUD": selected_currency = AUDCurrency
    elif code == "NZD": selected_currency = NZDCurrency
    else:
        print("Error: Unknown currency code '", code, "' in Mojo Oceania runner.")
        return

    # Print properties in the exact same format as the C++ runner
    print("Name:", selected_currency.name)
    print("Code:", selected_currency.code)
    print("NumericCode:", selected_currency.numeric_code)
    print("Symbol:", selected_currency.symbol)
    print("FractionSymbol:", selected_currency.fraction_symbol)
    print("FractionsPerUnit:", selected_currency.fractions_per_unit)
    
    # Print rounding details
    # The __str__ method of RoundingType handles conversion to string e.g. "Closest"
    print("RoundingType:", selected_currency.rounding.type.__str__())
    print("RoundingPrecision:", selected_currency.rounding.precision)
    print("RoundingDigit:", selected_currency.rounding.digit)

fn main() raises: # Raises needed for potential conversion errors
    var args = sys_argv()
    if len(args) != 2:
        print("Usage: mojo oceania_runner.mojo <CurrencyCode>") # Updated usage message
        return

    var currency_code = String(args[1]) # Ensure it's a String

    print_currency_properties(currency_code) 