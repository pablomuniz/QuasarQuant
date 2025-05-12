# Mojo Runner to print European currency properties for comparison with C++
from sys import argv as sys_argv

# Import the necessary structs from the main europe definitions file
from quantfork.ql.currencies.europe import (
    CurrencyData, Rounding, # ClosestRounding no longer needed here explicitly by name
    BGLCurrency, BYRCurrency, CHFCurrency, CYPCurrency, CZKCurrency, 
    DKKCurrency, EEKCurrency, EURCurrency, GBPCurrency, HUFCurrency, 
    ISKCurrency, LTLCurrency, LVLCurrency, NOKCurrency, PLNCurrency, 
    ROLCurrency, RONCurrency, RUBCurrency, SEKCurrency, SITCurrency, 
    TRLCurrency, TRYCurrency, ATSCurrency, BEFCurrency, DEMCurrency, 
    ESPCurrency, FIMCurrency, FRFCurrency, GRDCurrency, IEPCurrency, 
    ITLCurrency, LUFCurrency, MTLCurrency, NLGCurrency, PTECurrency, 
    SKKCurrency, UAHCurrency, RSDCurrency, HRKCurrency, BGNCurrency, 
    GELCurrency
)
# Import rounding type constants for EURCurrency
from quantfork.ql.math.rounding import RT_CLOSEST

# Function to get currency data and print properties
fn print_currency_properties(code: String):
    var currency_data: CurrencyData

    if code == "BGL": currency_data = BGLCurrency().data
    elif code == "BYR": currency_data = BYRCurrency().data
    elif code == "CHF": currency_data = CHFCurrency().data
    elif code == "CYP": currency_data = CYPCurrency().data
    elif code == "CZK": currency_data = CZKCurrency().data
    elif code == "DKK": currency_data = DKKCurrency().data
    elif code == "EEK": currency_data = EEKCurrency().data
    elif code == "EUR": currency_data = EURCurrency().data
    elif code == "GBP": currency_data = GBPCurrency().data
    elif code == "HUF": currency_data = HUFCurrency().data
    elif code == "ISK": currency_data = ISKCurrency().data
    elif code == "LTL": currency_data = LTLCurrency().data
    elif code == "LVL": currency_data = LVLCurrency().data
    elif code == "NOK": currency_data = NOKCurrency().data
    elif code == "PLN": currency_data = PLNCurrency().data
    elif code == "ROL": currency_data = ROLCurrency().data
    elif code == "RON": currency_data = RONCurrency().data
    elif code == "RUB": currency_data = RUBCurrency().data
    elif code == "SEK": currency_data = SEKCurrency().data
    elif code == "SIT": currency_data = SITCurrency().data
    elif code == "TRL": currency_data = TRLCurrency().data
    elif code == "TRY": currency_data = TRYCurrency().data
    # Obsoleted by Euro
    elif code == "ATS": currency_data = ATSCurrency().data
    elif code == "BEF": currency_data = BEFCurrency().data
    elif code == "DEM": currency_data = DEMCurrency().data
    elif code == "ESP": currency_data = ESPCurrency().data
    elif code == "FIM": currency_data = FIMCurrency().data
    elif code == "FRF": currency_data = FRFCurrency().data
    elif code == "GRD": currency_data = GRDCurrency().data
    elif code == "IEP": currency_data = IEPCurrency().data
    elif code == "ITL": currency_data = ITLCurrency().data
    elif code == "LUF": currency_data = LUFCurrency().data
    elif code == "MTL": currency_data = MTLCurrency().data
    elif code == "NLG": currency_data = NLGCurrency().data
    elif code == "PTE": currency_data = PTECurrency().data
    elif code == "SKK": currency_data = SKKCurrency().data
    # Other European currencies
    elif code == "UAH": currency_data = UAHCurrency().data
    elif code == "RSD": currency_data = RSDCurrency().data
    elif code == "HRK": currency_data = HRKCurrency().data
    elif code == "BGN": currency_data = BGNCurrency().data
    elif code == "GEL": currency_data = GELCurrency().data
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
    # The __str__ method of RoundingType handles conversion to string e.g. "Closest"
    print("RoundingType:", currency_data.rounding.type.__str__())
    print("RoundingPrecision:", currency_data.rounding.precision)
    print("RoundingDigit:", currency_data.rounding.digit)

fn main() raises: # Raises needed for potential conversion errors
    var args = sys_argv()
    if len(args) != 2:
        print("Usage: mojo europe_runner.mojo <CurrencyCode>")
        return

    # Command-line arg is likely StringLiteral, convert to String
    var currency_code_arg = args[1]
    var currency_code = String(currency_code_arg)

    print_currency_properties(currency_code) 