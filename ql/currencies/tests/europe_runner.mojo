# Mojo Runner to print European currency properties for comparison with C++
from sys import argv as sys_argv

# Import the specific currency instances from the europe module
from quantfork.ql.currencies.europe import *
# Import the Currency type itself and Rounding related types
from quantfork.ql.currency import Currency
from quantfork.ql.math.rounding import Rounding, RT_CLOSEST # RT_CLOSEST might be needed for EUR specifics

# If ExchangeRateManager is truly needed by this runner, it should be imported separately
# from quantfork.ql.currencies.exchangeratemanager import ExchangeRateManager

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var selected_currency: Currency

    # Assign the correct currency instance based on the code
    if code == "BGL": selected_currency = BGLCurrency
    elif code == "BYR": selected_currency = BYRCurrency
    elif code == "CHF": selected_currency = CHFCurrency
    elif code == "CYP": selected_currency = CYPCurrency
    elif code == "CZK": selected_currency = CZKCurrency
    elif code == "DKK": selected_currency = DKKCurrency
    elif code == "EEK": selected_currency = EEKCurrency
    elif code == "EUR": selected_currency = EURCurrency
    elif code == "GBP": selected_currency = GBPCurrency
    elif code == "HUF": selected_currency = HUFCurrency
    elif code == "ISK": selected_currency = ISKCurrency
    elif code == "LTL": selected_currency = LTLCurrency
    elif code == "LVL": selected_currency = LVLCurrency
    elif code == "NOK": selected_currency = NOKCurrency
    elif code == "PLN": selected_currency = PLNCurrency
    elif code == "ROL": selected_currency = ROLCurrency
    elif code == "RON": selected_currency = RONCurrency
    elif code == "RUB": selected_currency = RUBCurrency
    elif code == "SEK": selected_currency = SEKCurrency
    elif code == "SIT": selected_currency = SITCurrency
    elif code == "TRL": selected_currency = TRLCurrency
    elif code == "TRY": selected_currency = TRYCurrency
    # Obsoleted by Euro
    elif code == "ATS": selected_currency = ATSCurrency
    elif code == "BEF": selected_currency = BEFCurrency
    elif code == "DEM": selected_currency = DEMCurrency
    elif code == "ESP": selected_currency = ESPCurrency
    elif code == "FIM": selected_currency = FIMCurrency
    elif code == "FRF": selected_currency = FRFCurrency
    elif code == "GRD": selected_currency = GRDCurrency
    elif code == "IEP": selected_currency = IEPCurrency
    elif code == "ITL": selected_currency = ITLCurrency
    elif code == "LUF": selected_currency = LUFCurrency
    elif code == "MTL": selected_currency = MTLCurrency
    elif code == "NLG": selected_currency = NLGCurrency
    elif code == "PTE": selected_currency = PTECurrency
    elif code == "SKK": selected_currency = SKKCurrency
    # Other European currencies
    elif code == "UAH": selected_currency = UAHCurrency

    else:
        print("Error: Unknown currency code '", code, "' in Mojo runner.")
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
        print("Usage: mojo europe_runner.mojo <CurrencyCode>")
        return

    # Command-line arg is likely StringLiteral, convert to String
    var currency_code_arg = args[1]
    var currency_code = String(currency_code_arg)

    print_currency_properties(currency_code) 