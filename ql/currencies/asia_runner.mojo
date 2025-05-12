# Mojo Runner to print Asian currency properties for comparison with C++
from sys import argv as sys_argv

# Import the necessary structs from the main asia definitions file
from quantfork.ql.currencies.asia import (
    CurrencyData, Rounding, # Base types needed
    BDTCurrency, CNYCurrency, HKDCurrency, IDRCurrency, ILSCurrency,
    INRCurrency, IQDCurrency, IRRCurrency, JPYCurrency, KRWCurrency,
    KWDCurrency, KZTCurrency, MYRCurrency, NPRCurrency, PKRCurrency,
    SARCurrency, SGDCurrency, THBCurrency, TWDCurrency, VNDCurrency,
    QARCurrency, BHDCurrency, OMRCurrency, JODCurrency, AEDCurrency,
    PHPCurrency, CNHCurrency, LKRCurrency
)

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var currency_data: CurrencyData

    if code == "BDT": currency_data = BDTCurrency().data
    elif code == "CNY": currency_data = CNYCurrency().data
    elif code == "HKD": currency_data = HKDCurrency().data
    elif code == "IDR": currency_data = IDRCurrency().data
    elif code == "ILS": currency_data = ILSCurrency().data
    elif code == "INR": currency_data = INRCurrency().data
    elif code == "IQD": currency_data = IQDCurrency().data
    elif code == "IRR": currency_data = IRRCurrency().data
    elif code == "JPY": currency_data = JPYCurrency().data
    elif code == "KRW": currency_data = KRWCurrency().data
    elif code == "KWD": currency_data = KWDCurrency().data
    elif code == "KZT": currency_data = KZTCurrency().data
    elif code == "MYR": currency_data = MYRCurrency().data
    elif code == "NPR": currency_data = NPRCurrency().data
    elif code == "PKR": currency_data = PKRCurrency().data
    elif code == "SAR": currency_data = SARCurrency().data
    elif code == "SGD": currency_data = SGDCurrency().data
    elif code == "THB": currency_data = THBCurrency().data
    elif code == "TWD": currency_data = TWDCurrency().data
    elif code == "VND": currency_data = VNDCurrency().data
    elif code == "QAR": currency_data = QARCurrency().data
    elif code == "BHD": currency_data = BHDCurrency().data
    elif code == "OMR": currency_data = OMRCurrency().data
    elif code == "JOD": currency_data = JODCurrency().data
    elif code == "AED": currency_data = AEDCurrency().data
    elif code == "PHP": currency_data = PHPCurrency().data
    elif code == "CNH": currency_data = CNHCurrency().data
    elif code == "LKR": currency_data = LKRCurrency().data
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
        print("Usage: mojo asia_runner.mojo <CurrencyCode>")
        return

    # Command-line arg is likely StringLiteral, convert to String
    var currency_code_arg = args[1]
    var currency_code = String(currency_code_arg)

    print_currency_properties(currency_code) 