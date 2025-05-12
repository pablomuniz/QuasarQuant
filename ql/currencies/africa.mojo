# Mojo version of QuantLib's ql/currencies/africa.cpp

from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
import time
from quantfork.ql.currency import Currency

# Angolan kwanza
var AOACurrency = Currency("Angolan kwanza", "AOA", 973, "AOA", "", 100, Rounding())

# Botswanan pula
var BWPCurrency = Currency("Botswanan pula", "BWP", 72, "P", "", 100, Rounding())

# Egyptian pound
var EGPCurrency = Currency("Egyptian pound", "EGP", 818, "EGP", "", 100, Rounding())

# Ethiopian birr
var ETBCurrency = Currency("Ethiopian birr", "ETB", 230, "ETB", "", 100, Rounding())

# Ghanaian cedi
var GHSCurrency = Currency("Ghanaian cedi", "GHS", 936, "GHS", "", 100, Rounding())

# Kenyan shilling
var KESCurrency = Currency("Kenyan shilling", "KES", 404, "KES", "", 100, Rounding())

# Moroccan dirham
var MADCurrency = Currency("Moroccan dirham", "MAD", 504, "MAD", "", 100, Rounding())

# Mauritian rupee
var MURCurrency = Currency("Mauritian rupee", "MUR", 480, "MUR", "", 100, Rounding())

# Nigerian Naira
var NGNCurrency = Currency("Nigerian Naira", "NGN", 566, "N", "K", 100, Rounding())

# Tunisian dinar
var TNDCurrency = Currency("Tunisian dinar", "TND", 788, "TND", "", 1000, Rounding())

# Ugandan shilling
var UGXCurrency = Currency("Ugandan shilling", "UGX", 800, "UGX", "", 1, Rounding())

# West African CFA franc
var XOFCurrency = Currency("West African CFA franc", "XOF", 952, "XOF", "", 100, Rounding())

# South-African rand
var ZARCurrency = Currency("South-African rand", "ZAR", 710, "R", "", 100, Rounding())

# Zambian kwacha
var ZMWCurrency = Currency("Zambian kwacha", "ZMW", 967, "ZMW", "", 100, Rounding())

# Example of how to use it (optional, for testing)
fn main():
    print("--- Testing Mojo Currency Structs ---")
    var aoa = AOACurrency
    print("AOA Name (Mojo struct):", aoa.name)
    print("AOA Code (Mojo struct):", aoa.code)
    print("AOA Numeric (Mojo struct):", aoa.numeric_code)
    print("AOA Symbol (Mojo struct):", aoa.symbol)
    print("AOA Frac Symbol (Mojo struct):", aoa.fraction_symbol)
    print("AOA Frac Per Unit (Mojo struct):", aoa.fractions_per_unit)
    print("AOA Rounding Type (Mojo struct):", String(aoa.rounding.type))
    print("AOA Rounding Precision (Mojo struct):", aoa.rounding.precision)
    print("AOA Rounding Digit (Mojo struct):", aoa.rounding.digit)

    var zar = ZARCurrency
    print("ZAR Name (Mojo struct):", zar.name)
    print("ZAR Symbol (Mojo struct):", zar.symbol)
    print("ZAR Rounding Type (Mojo struct):", String(zar.rounding.type))

    print("\n--- Testing Mojo Currency Rounding Integration ---")
    var test_value = 123.456
    var rounded_aoa = aoa.rounding.apply(test_value)
    print("AOA (default None rounding) applied to", test_value, "->", rounded_aoa)
    
    # Example with a different rounding (e.g. Closest, 2 decimal places)
    var zar_closest_rounding = Rounding(RT_CLOSEST, 2, 5) # Use the imported constant
    var zar_currency_data_custom_rounding = Currency(
        zar.name, zar.code, zar.numeric_code, zar.symbol,
        zar.fraction_symbol, zar.fractions_per_unit, zar_closest_rounding
    )
    var rounded_zar_custom = zar_currency_data_custom_rounding.rounding.apply(test_value)
