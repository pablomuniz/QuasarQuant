# Mojo version of QuantLib's ql/currencies/crypto.cpp

from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
import time
from quantfork.ql.currency import Currency

# --- Currency Definitions ---

# Bitcoin (BTC)
var BTCCurrency = Currency("Bitcoin", "BTC", 10000, "BTC", "", 100000, Rounding())

# Ethereum (ETH)
var ETHCurrency = Currency("Ethereum", "ETH", 10001, "ETH", "", 100000, Rounding())

# Ethereum Classic (ETC)
var ETCCurrency = Currency("Ethereum Classic", "ETC", 10002, "ETC", "", 100000, Rounding())

# Bitcoin Cash (BCH)
var BCHCurrency = Currency("Bitcoin Cash", "BCH", 10003, "BCH", "", 100000, Rounding())

# Ripple (XRP)
var XRPCurrency = Currency("Ripple", "XRP", 10004, "XRP", "", 100000, Rounding())

# Litecoin (LTC)
var LTCCurrency = Currency("Litecoin", "LTC", 10005, "LTC", "", 100000, Rounding())

# Dash coin (DASH)
var DASHCurrency = Currency("Dash coin", "DASH", 10006, "DASH", "", 100000, Rounding())

# Zcash (ZEC)
var ZECCurrency = Currency("Zcash", "ZEC", 10007, "ZEC", "", 100000, Rounding())

# --- Currency Definitions (To be filled from crypto.cpp) --- 