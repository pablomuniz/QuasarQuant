# Mojo version of QuantLib's ql/currencies/america.cpp

from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
# todo: fix these imports
from quantfork.ql.currency import Currency

# Argentinian peso (ARS)
var ARSCurrency = Currency("Argentinian peso", "ARS", 32, "", "", 100, Rounding())

# Brazilian real (BRL)
var BRLCurrency = Currency("Brazilian real", "BRL", 986, "R$", "", 100, Rounding())

# Canadian dollar (CAD)
var CADCurrency = Currency("Canadian dollar", "CAD", 124, "Can$", "", 100, Rounding())

# Chilean peso (CLP)
var CLPCurrency = Currency("Chilean peso", "CLP", 152, "Ch$", "", 100, Rounding())

# Colombian peso (COP)
var COPCurrency = Currency("Colombian peso", "COP", 170, "Col$", "", 100, Rounding())

# Mexican peso (MXN)
var MXNCurrency = Currency("Mexican peso", "MXN", 484, "Mex$", "", 100, Rounding())

# Peruvian nuevo sol (PEN)
var PENCurrency = Currency("Peruvian nuevo sol", "PEN", 604, "S/.", "", 100, Rounding())

# Peruvian inti (PEI) - Note: User-defined numeric code 998
var PEICurrency = Currency("Peruvian inti", "PEI", 998, "I/.", "", 100, Rounding())

# Peruvian sol (PEH) - Note: User-defined numeric code 999
var PEHCurrency = Currency("Peruvian sol", "PEH", 999, "S./", "", 100, Rounding())

# Trinidad & Tobago dollar (TTD)
var TTDCurrency = Currency("Trinidad & Tobago dollar", "TTD", 780, "TT$", "", 100, Rounding())

# U.S. dollar (USD)
var USDCurrency = Currency("U.S. dollar", "USD", 840, "$", "\xA2", 100, Rounding())

# Venezuelan bolivar (VEB)
var VEBCurrency = Currency("Venezuelan bolivar", "VEB", 862, "Bs", "", 100, Rounding())

# Mexican Unidad de Inversion (MXV)
var MXVCurrency = Currency("Mexican Unidad de Inversion", "MXV", 979, "MXV", "", 1, Rounding())

# Unidad de Valor Real (COU) - Colombia
var COUCurrency = Currency("Unidad de Valor Real (UVR) (funds code)", "COU", 970, "COU", "", 100, Rounding())

# Unidad de Fomento (CLF) - Chile
var CLFCurrency = Currency("Unidad de Fomento (funds code)", "CLF", 990, "CLF", "", 1, Rounding())

# Uruguayan peso (UYU)
var UYUCurrency = Currency("Uruguayan peso", "UYU", 858, "UYU", "", 1, Rounding())
