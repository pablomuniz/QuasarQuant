# Mojo version of QuantLib's ql/currencies/europe.cpp

from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
import time
from quantfork.ql.currency import Currency

# --- Currency Definitions ---

# Bulgarian lev (BGL)
var BGLCurrency = Currency("Bulgarian lev", "BGL", 100, "lv", "", 100, Rounding())

# Belarussian ruble (BYR)
var BYRCurrency = Currency("Belarussian ruble", "BYR", 974, "BR", "", 1, Rounding())

# Swiss franc (CHF)
var CHFCurrency = Currency("Swiss franc", "CHF", 756, "SwF", "", 100, Rounding())

# Cyprus pound (CYP)
var CYPCurrency = Currency("Cyprus pound", "CYP", 196, "\xA3C", "", 100, Rounding())

# Czech koruna (CZK)
var CZKCurrency = Currency("Czech koruna", "CZK", 203, "Kc", "", 100, Rounding())

# Danish krone (DKK)
var DKKCurrency = Currency("Danish krone", "DKK", 208, "Dkr", "", 100, Rounding())

# Estonian kroon (EEK)
var EEKCurrency = Currency("Estonian kroon", "EEK", 233, "KR", "", 100, Rounding())

# European Euro (EUR)
var EURCurrency = Currency("European Euro", "EUR", 978, "", "", 100, Rounding(RT_CLOSEST, 2))

# British pound sterling (GBP)
var GBPCurrency = Currency("British pound sterling", "GBP", 826, "\xA3", "p", 100, Rounding())

# Hungarian forint (HUF)
var HUFCurrency = Currency("Hungarian forint", "HUF", 348, "Ft", "", 1, Rounding())

# Icelandic krona (ISK)
var ISKCurrency = Currency("Iceland krona", "ISK", 352, "IKr", "", 100, Rounding())

# Lithuanian litas (LTL)
var LTLCurrency = Currency("Lithuanian litas", "LTL", 440, "Lt", "", 100, Rounding())

# Latvian lat (LVL)
var LVLCurrency = Currency("Latvian lat", "LVL", 428, "Ls", "", 100, Rounding())

# Norwegian krone (NOK)
var NOKCurrency = Currency("Norwegian krone", "NOK", 578, "NKr", "", 100, Rounding())

# Polish zloty (PLN)
var PLNCurrency = Currency("Polish zloty", "PLN", 985, "zl", "", 100, Rounding())

# Romanian leu (ROL) - Historical
var ROLCurrency = Currency("Romanian leu", "ROL", 642, "L", "", 100, Rounding())

# Romanian new leu (RON)
var RONCurrency = Currency("Romanian new leu", "RON", 946, "L", "", 100, Rounding())

# Russian ruble (RUB)
var RUBCurrency = Currency("Russian ruble", "RUB", 643, "", "", 100, Rounding())

# Swedish krona (SEK)
var SEKCurrency = Currency("Swedish krona", "SEK", 752, "kr", "", 100, Rounding())

# Slovenian tolar (SIT)
var SITCurrency = Currency("Slovenian tolar", "SIT", 705, "SlT", "", 100, Rounding())

# Turkish lira (TRL) - Historical
var TRLCurrency = Currency("Turkish lira", "TRL", 792, "TL", "", 100, Rounding())

# New Turkish lira (TRY)
var TRYCurrency = Currency("New Turkish lira", "TRY", 949, "YTL", "", 100, Rounding())

# --- Currencies obsoleted by Euro ---

# Austrian shilling (ATS)
var ATSCurrency = Currency("Austrian shilling", "ATS", 40, "", "", 100, Rounding())

# Belgian franc (BEF)
var BEFCurrency = Currency("Belgian franc", "BEF", 56, "", "", 1, Rounding())

# Deutsche mark (DEM)
var DEMCurrency = Currency("Deutsche mark", "DEM", 276, "DM", "", 100, Rounding())

# Spanish peseta (ESP)
var ESPCurrency = Currency("Spanish peseta", "ESP", 724, "Pta", "", 100, Rounding())

# Finnish markka (FIM)
var FIMCurrency = Currency("Finnish markka", "FIM", 246, "mk", "", 100, Rounding())

# French franc (FRF)
var FRFCurrency = Currency("French franc", "FRF", 250, "", "", 100, Rounding())

# Greek drachma (GRD)
var GRDCurrency = Currency("Greek drachma", "GRD", 300, "", "", 100, Rounding())

# Irish punt (IEP)
var IEPCurrency = Currency("Irish punt", "IEP", 372, "", "", 100, Rounding())

# Italian lira (ITL)
var ITLCurrency = Currency("Italian lira", "ITL", 380, "L", "", 1, Rounding())

# Luxembourg franc (LUF)
var LUFCurrency = Currency("Luxembourg franc", "LUF", 442, "F", "", 100, Rounding())

# Maltese lira (MTL)
var MTLCurrency = Currency("Maltese lira", "MTL", 470, "Lm", "", 100, Rounding())

# Dutch guilder (NLG)
var NLGCurrency = Currency("Dutch guilder", "NLG", 528, "f", "", 100, Rounding())

# Portuguese escudo (PTE)
var PTECurrency = Currency("Portuguese escudo", "PTE", 620, "Esc", "", 100, Rounding())

# Slovak koruna (SKK)
var SKKCurrency = Currency("Slovak koruna", "SKK", 703, "Sk", "", 100, Rounding())

# Ukrainian hryvnia (UAH)
var UAHCurrency = Currency("Ukrainian hryvnia", "UAH", 980, "hrn", "", 100, Rounding())

# Serbian dinar (RSD)
var RSDCurrency = Currency("Serbian dinar", "RSD", 941, "RSD", "", 100, Rounding())

# Croatian kuna (HRK)
var HRKCurrency = Currency("Croatian kuna", "HRK", 191, "HRK", "", 100, Rounding())

# Bulgarian lev (BGN)
var BGNCurrency = Currency("Bulgarian lev", "BGN", 975, "BGN", "", 100, Rounding())

# Georgian lari (GEL)
var GELCurrency = Currency("Georgian lari", "GEL", 981, "GEL", "", 100, Rounding()) 