# Mojo Runner to print Asian currency properties for comparison with C++
from sys import argv as sys_argv

# Import the specific currency instances from the asia module
from quantfork.ql.currencies.asia import (
    BDTCurrency, CNYCurrency, HKDCurrency, IDRCurrency, ILSCurrency,
    INRCurrency, IQDCurrency, IRRCurrency, JPYCurrency, KRWCurrency,
    KWDCurrency, KZTCurrency, MYRCurrency, NPRCurrency, PKRCurrency,
    SARCurrency, SGDCurrency, THBCurrency, TWDCurrency, VNDCurrency,
    QARCurrency, BHDCurrency, OMRCurrency, JODCurrency, AEDCurrency,
    PHPCurrency, CNHCurrency, LKRCurrency
)
# Import the Currency type itself
from quantfork.ql.currency import Currency


# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var selected_currency: Currency

    # Assign the correct currency instance based on the code
    if code == "BDT": selected_currency = BDTCurrency
    elif code == "CNY": selected_currency = CNYCurrency
    elif code == "HKD": selected_currency = HKDCurrency
    elif code == "IDR": selected_currency = IDRCurrency
    elif code == "ILS": selected_currency = ILSCurrency
    elif code == "INR": selected_currency = INRCurrency
    elif code == "IQD": selected_currency = IQDCurrency
    elif code == "IRR": selected_currency = IRRCurrency
    elif code == "JPY": selected_currency = JPYCurrency
    elif code == "KRW": selected_currency = KRWCurrency
    elif code == "KWD": selected_currency = KWDCurrency
    elif code == "KZT": selected_currency = KZTCurrency
    elif code == "MYR": selected_currency = MYRCurrency
    elif code == "NPR": selected_currency = NPRCurrency
    elif code == "PKR": selected_currency = PKRCurrency
    elif code == "SAR": selected_currency = SARCurrency
    elif code == "SGD": selected_currency = SGDCurrency
    elif code == "THB": selected_currency = THBCurrency
    elif code == "TWD": selected_currency = TWDCurrency
    elif code == "VND": selected_currency = VNDCurrency
    elif code == "QAR": selected_currency = QARCurrency
    elif code == "BHD": selected_currency = BHDCurrency
    elif code == "OMR": selected_currency = OMRCurrency
    elif code == "JOD": selected_currency = JODCurrency
    elif code == "AED": selected_currency = AEDCurrency
    elif code == "PHP": selected_currency = PHPCurrency
    elif code == "CNH": selected_currency = CNHCurrency
    elif code == "LKR": selected_currency = LKRCurrency
    else:
        print("Error: Unknown currency code '", code, "' in Mojo Asia runner.")
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
        print("Usage: mojo asia_runner.mojo <CurrencyCode>")
        return

    var currency_code = String(args[1])
    
    print_currency_properties(currency_code) 