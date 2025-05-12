# Mojo version of QuantLib's ql/currencies/oceania.cpp

from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
import time
from quantfork.ql.currency import Currency

# --- Currency Definitions (To be filled from oceania.cpp) --- 

# Australian dollar (AUD)
var AUDCurrency = Currency("Australian dollar", "AUD", 36, "A$", "", 100, Rounding())

# New Zealand dollar (NZD)
var NZDCurrency = Currency("New Zealand dollar", "NZD", 554, "NZ$", "", 100, Rounding()) 