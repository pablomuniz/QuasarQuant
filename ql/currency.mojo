# Mojo version of QuantLib's ql/currency.hpp
from quantfork.ql.math.rounding import Rounding, RoundingType
from quantfork.ql.math.rounding import RT_NONE, RT_UP, RT_DOWN, RT_CLOSEST, RT_FLOOR, RT_CEILING
#todo in the future we should make this more performant by using a shared pointer or a reference to the currency object
@value
struct Currency:
    var name: String
    var code: String
    var numeric_code: Int
    var symbol: String
    var fraction_symbol: String
    var fractions_per_unit: Int
    var rounding: Rounding
    var triangulation_currency: String  # Code of triangulation currency

    fn __init__(out self):
        """Default constructor for empty currency"""
        self.name = ""
        self.code = ""
        self.numeric_code = 0
        self.symbol = ""
        self.fraction_symbol = ""
        self.fractions_per_unit = 0
        self.triangulation_currency = ""
        self.rounding = Rounding(0, RoundingType.RT_NONE)

    fn __init__(out self, name: String, code: String, numeric_code: Int, symbol: String, 
                fraction_symbol: String, fractions_per_unit: Int, rounding: Rounding,
                triangulation_currency: String = ""):
        """Constructor with all currency parameters"""
        self.name = name
        self.code = code
        self.numeric_code = numeric_code
        self.symbol = symbol
        self.fraction_symbol = fraction_symbol
        self.fractions_per_unit = fractions_per_unit
        self.rounding = rounding
        self.triangulation_currency = triangulation_currency
    
    fn __init__(out self, code: String):
        #todo check if we still need this
        """Simple constructor from currency code - for use in lookups"""
        self.name = ""  # These would ideally be populated by lookup
        self.code = code
        self.numeric_code = 0
        self.symbol = ""
        self.fraction_symbol = ""
        self.fractions_per_unit = 0
        self.triangulation_currency = ""
        self.rounding = Rounding(0, RoundingType.RT_NONE)
    
    fn is_empty(self) -> Bool:
        """Checks if this is an empty/invalid currency"""
        return self.code == ""
    

