# Mojo Runner to print American currency properties for comparison with C++
from sys import argv as sys_argv, exit as sys_exit
from quantfork.ql.currency import Currency
from quantfork.ql.math.rounding import RoundingType, RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
from collections.vector import InlinedFixedVector

# Import the necessary currency INSTANCES from the main america definitions file
from quantfork.ql.currencies.america import (
    ARSCurrency, BRLCurrency, CADCurrency, CLPCurrency, COPCurrency,
    MXNCurrency, PENCurrency, PEICurrency, PEHCurrency, TTDCurrency,
    USDCurrency, VEBCurrency, MXVCurrency, COUCurrency, CLFCurrency,
    UYUCurrency
)

# Helper function to convert Mojo RoundingType enum to string like C++ runner
fn roundingTypeToString(type: RoundingType) -> String:
    if type == RT_NONE: return "None"
    if type == RT_UP: return "Up"
    if type == RT_DOWN: return "Down"
    if type == RT_CLOSEST: return "Closest"
    if type == RT_FLOOR: return "Floor"
    if type == RT_CEILING: return "Ceiling"
    return "UnknownRoundingType"


# Function to get currency data and print properties
fn print_currency_properties(code: String) raises:
    var target_currency: Currency
    
    # Select the correct currency instance
    if code == "ARS": target_currency = ARSCurrency
    elif code == "BRL": target_currency = BRLCurrency
    elif code == "CAD": target_currency = CADCurrency
    elif code == "CLP": target_currency = CLPCurrency
    elif code == "COP": target_currency = COPCurrency
    elif code == "MXN": target_currency = MXNCurrency
    elif code == "PEN": target_currency = PENCurrency
    elif code == "PEI": target_currency = PEICurrency
    elif code == "PEH": target_currency = PEHCurrency
    elif code == "TTD": target_currency = TTDCurrency
    elif code == "USD": target_currency = USDCurrency
    elif code == "VEB": target_currency = VEBCurrency
    elif code == "MXV": target_currency = MXVCurrency
    elif code == "COU": target_currency = COUCurrency
    elif code == "CLF": target_currency = CLFCurrency
    elif code == "UYU": target_currency = UYUCurrency
    else:
        print("Error: Unknown currency code \'", code, "\' in Mojo runner.")
        sys_exit(1) # Exit with error code like C++ runner
        return # Add explicit return to help compiler understand control flow
        
    # Print properties in the exact same format as the C++ runner
    print("Name:", target_currency.name)
    print("Code:", target_currency.code)
    print("NumericCode:", target_currency.numeric_code)
    print("Symbol:", target_currency.symbol)
    print("FractionSymbol:", target_currency.fraction_symbol)
    print("FractionsPerUnit:", target_currency.fractions_per_unit)
    
    # Print rounding details using the helper
    var rounding = target_currency.rounding
    print("RoundingType:", roundingTypeToString(rounding.type))
    print("RoundingPrecision:", rounding.precision)
    print("RoundingDigit:", rounding.digit)

fn main() raises: 
    var args = sys_argv()
    if len(args) != 2:
        print("Usage:", args[0], "<CurrencyCode>") # Use arg[0] for executable name
        sys_exit(1)

    # Command-line arg is String
    var currency_code = String(args[1]) # Explicitly convert to String
    
    print_currency_properties(currency_code) 

    sys_exit(0) # Success exit code 