# Mojo version of QuantLib's ql/currencies/asia.cpp

from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
import time
from quantfork.ql.currency import Currency

# --- Currency Definitions ---

# Bangladesh taka (BDT)
var BDTCurrency = Currency("Bangladesh taka", "BDT", 50, "Bt", "", 100, Rounding())

# Chinese yuan (CNY)
var CNYCurrency = Currency("Chinese yuan", "CNY", 156, "Y", "", 100, Rounding())

# Hong Kong dollar (HKD)
var HKDCurrency = Currency("Hong Kong dollar", "HKD", 344, "HK$", "", 100, Rounding())

# Indonesian Rupiah (IDR)
var IDRCurrency = Currency("Indonesian Rupiah", "IDR", 360, "Rp", "", 100, Rounding())

# Israeli shekel (ILS)
var ILSCurrency = Currency("Israeli shekel", "ILS", 376, "NIS", "", 100, Rounding())

# Indian rupee (INR)
var INRCurrency = Currency("Indian rupee", "INR", 356, "Rs", "", 100, Rounding())

# Iraqi dinar (IQD)
var IQDCurrency = Currency("Iraqi dinar", "IQD", 368, "ID", "", 1000, Rounding())

# Iranian rial (IRR)
var IRRCurrency = Currency("Iranian rial", "IRR", 364, "Rls", "", 1, Rounding())

# Japanese yen (JPY)
var JPYCurrency = Currency("Japanese yen", "JPY", 392, "\xA5", "", 100, Rounding())

# South-Korean won (KRW)
var KRWCurrency = Currency("South-Korean won", "KRW", 410, "W", "", 100, Rounding())

# Kuwaiti dinar (KWD)
var KWDCurrency = Currency("Kuwaiti dinar", "KWD", 414, "KD", "", 1000, Rounding())

# Kazakstani Tenge (KZT)
var KZTCurrency = Currency("Kazakstanti Tenge", "KZT", 398, "Kzt", "", 100, Rounding())

# Malaysian Ringgit (MYR)
var MYRCurrency = Currency("Malaysian Ringgit", "MYR", 458, "RM", "", 100, Rounding())

# Nepal rupee (NPR)
var NPRCurrency = Currency("Nepal rupee", "NPR", 524, "NRs", "", 100, Rounding())

# Pakistani rupee (PKR)
var PKRCurrency = Currency("Pakistani rupee", "PKR", 586, "Rs", "", 100, Rounding())

# Saudi riyal (SAR)
var SARCurrency = Currency("Saudi riyal", "SAR", 682, "SRls", "", 100, Rounding())

# Singapore dollar (SGD)
var SGDCurrency = Currency("Singapore dollar", "SGD", 702, "S$", "", 100, Rounding())

# Thai baht (THB)
var THBCurrency = Currency("Thai baht", "THB", 764, "Bht", "", 100, Rounding())

# Taiwan dollar (TWD)
var TWDCurrency = Currency("Taiwan dollar", "TWD", 901, "NT$", "", 100, Rounding())

# Vietnamese Dong (VND)
var VNDCurrency = Currency("Vietnamese Dong", "VND", 704, "", "", 100, Rounding())

# Qatari riyal (QAR)
var QARCurrency = Currency("Qatari riyal", "QAR", 634, "QAR", "", 100, Rounding())

# Bahraini dinar (BHD)
var BHDCurrency = Currency("Bahraini dinar", "BHD", 48, "BHD", "", 1000, Rounding())

# Omani rial (OMR)
var OMRCurrency = Currency("Omani rial", "OMR", 512, "OMR", "", 1000, Rounding())

# Jordanian dinar (JOD)
var JODCurrency = Currency("Jordanian dinar", "JOD", 400, "JOD", "", 1000, Rounding())

# United Arab Emirates dirham (AED)
var AEDCurrency = Currency("United Arab Emirates dirham", "AED", 784, "AED", "", 100, Rounding())

# Philippine peso (PHP)
var PHPCurrency = Currency("Philippine peso", "PHP", 608, "PHP", "", 100, Rounding())

# Chinese yuan (Hong Kong) (CNH)
var CNHCurrency = Currency("Chinese yuan (Hong Kong)", "CNH", 156, "CNH", "", 100, Rounding())

# Sri Lankan rupee (LKR)
var LKRCurrency = Currency("Sri Lankan rupee", "LKR", 144, "LKR", "", 100, Rounding())

# Note: Removed the main() function as this is a module. 