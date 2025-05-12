# Mojo version of QuantLib's ql/math/rounding.cpp
# from builtin import abs, pow # Commented out as they are not found in builtin
from sys import argv as sys_argv
# Importing numojo seems unused here, can be removed if not needed for other parts
# import numojo as nm
# from numojo.prelude import *
from math import trunc, ceil, floor, modf # Updated import
# Remove deprecated str import, String() constructor is preferred

# Pure Mojo helper functions
fn fabs_mojo(value: Float64) -> Float64:
    if value < 0.0:
        return -value
    else:
        return value 

fn power_of_10_mojo(exponent: Int) -> Float64:
    if exponent == 0:
        return 1.0
    
    var result: Float64 = 1.0
    if exponent > 0:
        for _ in range(exponent): # Assuming range iterates exponent times
            result *= 10.0
    else: # exponent < 0
        # Calculate 10.0 ^ abs(exponent) for the denominator
        var denominator: Float64 = 1.0
        # -exponent will be positive
        for _ in range(-exponent): 
            denominator *= 10.0
        if denominator == 0.0: # Should be very rare for base 10 and typical precision
            return 0.0 # Or handle error appropriately
        result = 1.0 / denominator
    return result

# Simplified RoundingType for @value compatibility
@value
struct RoundingType:
    var value: Int
    # @value synthesizes __init__, __copyinit__, __moveinit__

    fn __eq__(self, other: RoundingType) -> Bool:
        return self.value == other.value
        
    fn __str__(self) -> String:
        if self.value == RT_NONE.value: return "None"
        if self.value == RT_UP.value: return "Up"
        if self.value == RT_DOWN.value: return "Down"
        if self.value == RT_CLOSEST.value: return "Closest"
        if self.value == RT_FLOOR.value: return "Floor"
        if self.value == RT_CEILING.value: return "Ceiling"
        return "UnknownRoundingType(" + String(self.value) + ")" # Use String() constructor

# Define RoundingType constants at the top level using var
var RT_NONE = RoundingType(0)
var RT_UP = RoundingType(1)
var RT_DOWN = RoundingType(2)
var RT_CLOSEST = RoundingType(3)
var RT_FLOOR = RoundingType(4)
var RT_CEILING = RoundingType(5)

fn string_to_rounding_type(s: String) -> RoundingType:
    if s == "None": 
        return RT_NONE
    if s == "Up": 
        return RT_UP
    if s == "Down": 
        return RT_DOWN
    if s == "Closest":
        return RT_CLOSEST
    if s == "Floor": 
        return RT_FLOOR
    if s == "Ceiling": 
        return RT_CEILING
    print("Error: Invalid rounding type string in Mojo: ", s)
    return RT_NONE # Fallback

# Removed @value, will implement move/copy manually
struct Rounding:
    var type: RoundingType
    var precision: Int
    var digit: Int

    # Constructor that takes an explicit type
    fn __init__(mut self, type: RoundingType, precision: Int = 0, digit: Int = 5):
        self.type = type
        self.precision = precision
        self.digit = digit

    # Overloaded constructor that defaults type to RT_NONE
    # This version specifically sets digit to 0 to match C++ default behavior
    fn __init__(mut self, precision: Int = 0):
        self.type = RT_NONE
        self.precision = precision
        self.digit = 0 # Set digit to 0 for default (None) rounding type
        
    # Manual Move Initializer
    fn __moveinit__(mut self, owned existing: Self):
        self.type = existing.type^ # Requires type to be movable
        self.precision = existing.precision # Int is copyable/movable
        self.digit = existing.digit       # Int is copyable/movable

    # Manual Copy Initializer
    fn __copyinit__(mut self, existing: Self):
        # RoundingType is @value, so copyable
        self.type = existing.type 
        # Int is copyable
        self.precision = existing.precision
        self.digit = existing.digit
        
    # Manual Destructor (needed if implementing move/copy manually)
    # Although for types like RoundingType/Int, it might be trivial?
    # Let's add an empty one for now if needed.
    fn __del__(owned self):
        pass # Nothing specific to destroy if members handle themselves

    # Apply is now pure Mojo, no 'raises' needed for itself
    fn apply(self, value: Float64) -> Float64:
        if self.type == RT_NONE:
            return value

        var mult = power_of_10_mojo(self.precision)
        var neg = value < 0.0
        var lvalue_intermediate_abs = fabs_mojo(value)
        var lvalue = lvalue_intermediate_abs * mult

        # Use math.modf to get integral and fractional parts
        var modf_result_tuple = modf(lvalue)
        # Assuming Mojo's modf returns (integral, fractional) contrary to Python's (fractional, integral)
        var extracted_integral_part = modf_result_tuple[0]
        var extracted_fractional_part = modf_result_tuple[1]

        var modVal = extracted_fractional_part # modVal is the fractional part for comparison
        lvalue = extracted_integral_part      # lvalue becomes the integral part as the base for rounding

        # The original C++ code does:
        # Real integral = 0.0;
        # Real modVal = std::modf(lvalue,&integral);
        # lvalue -= modVal; -> this makes lvalue the integral part.
        # So using `lvalue = modVal_tuple_int` is correct.

        if self.type == RT_UP:
            if modVal != 0.0: # Compare fractional part
                lvalue += 1.0
        elif self.type == RT_DOWN:
            pass # Integral part is already correct for truncation
        elif self.type == RT_CLOSEST:
            if modVal >= (Float64(self.digit) / 10.0):
                lvalue += 1.0
        elif self.type == RT_FLOOR:
            if not neg: # For positive numbers
                if modVal >= (Float64(self.digit) / 10.0):
                    lvalue += 1.0
            # For negative numbers, QL Floor effectively truncates towards zero
            # which is already handled by `lvalue = modVal_tuple_int`
        elif self.type == RT_CEILING:
            if neg: # For negative numbers
                 if modVal >= (Float64(self.digit) / 10.0):
                    lvalue += 1.0
            # For positive numbers, QL Ceiling effectively truncates towards zero
            # which is already handled by `lvalue = modVal_tuple_int`
        else:
            print("Error: Unknown rounding method! Type: ", self.type.value)
            # Consider raising an error or returning specific error value
            return value # Fallback

        var result_val: Float64
        if mult == 0.0: # Avoid division by zero if power_of_10_mojo resulted in 0
            result_val = 0.0 # Or handle as an error
        else:
            result_val = lvalue / mult
            
        if neg:
            return -result_val
        else:
            return result_val

fn main() raises:
    var args = sys_argv()
    var argc = len(args)

    if argc != 5:
        print("Usage: mojo roundingpepe.mojo <RoundingType> <precision> <digit> <value>")
        print("RoundingType: None, Up, Down, Closest, Floor, Ceiling")
        print("Received ", argc - 1, " arguments.")
        return

    var type_str = args[1]
    var precision_str = args[2]
    var digit_str = args[3]
    var value_str = args[4]

    var precision: Int = 0
    var digit: Int = 0
    var value_float: Float64 = 0.0

    try:
        precision = Int(precision_str)
    except:
        print("Error: Could not convert precision '", precision_str, "' to Int.")
        return
    
    try:
        digit = Int(digit_str)
    except:
        print("Error: Could not convert digit '", digit_str, "' to Int.")
        return

    try:
        value_float = Float64(value_str)
    except:
        print("Error: Could not convert value '", value_str, "' to Float64.")
        return

    var rounding_type = string_to_rounding_type(String(type_str))
    # Create Rounding object - no Python math object needed now
    var mojo_rounding = Rounding(rounding_type, precision, digit)
    var result = mojo_rounding.apply(value_float)
    
    # Print the result directly. Formatting to match C++ high precision 
    # would require a separate pure Mojo formatting function or Python interop.
    print(result)

# Example main for testing (optional)
#     let closest_rounding = Rounding(RoundingType.Closest, 2, 5) # 2 decimal places, round .5 up
#     let up_rounding = Rounding(RoundingType.Up, 0)          # 0 decimal places, always round up
#     let none_rounding = Rounding()                           # No rounding
#
#     print("Closest rounding for 1.234: ", closest_rounding.apply(1.234)) # Expected: 1.23
#     print("Closest rounding for 1.235: ", closest_rounding.apply(1.235)) # Expected: 1.24
#     print("Closest rounding for 1.237: ", closest_rounding.apply(1.237)) # Expected: 1.24
#     print("Closest rounding for -1.235: ", closest_rounding.apply(-1.235))# Expected: -1.24
#
#     print("Up rounding for 1.2: ", up_rounding.apply(1.2))       # Expected: 2.0
#     print("Up rounding for 1.0: ", up_rounding.apply(1.0))       # Expected: 1.0
#     print("Up rounding for -1.2: ", up_rounding.apply(-1.2))     # Expected: -2.0 (fabs, then add 1, then negate)
#
#     print("None rounding for 3.14159: ", none_rounding.apply(3.14159)) # Expected: 3.14159
#
#     # Testing QL's specific Floor/Ceiling based on C++ logic
#     # Floor: if positive & modVal >= digit/10, lvalue +=1. if negative, truncate.
#     # Ceiling: if negative & modVal >= digit/10, lvalue +=1. if positive, truncate.
#     # Assuming digit = 5 for these examples, precision = 2
#     let ql_floor_rounding = Rounding(RoundingType.Floor, 2, 5)
#     print("QL Floor for 1.235: ", ql_floor_rounding.apply(1.235)) # Positive, modVal=0.5 >= 0.5. Expected: 1.24
#     print("QL Floor for 1.234: ", ql_floor_rounding.apply(1.234)) # Positive, modVal=0.4 < 0.5. Expected: 1.23
#     print("QL Floor for -1.235: ", ql_floor_rounding.apply(-1.235))# Negative. Expected: -1.23 (truncates after fabs)
#     print("QL Floor for -1.237: ", ql_floor_rounding.apply(-1.237))# Negative. Expected: -1.23 (truncates after fabs)
#
#
#     let ql_ceiling_rounding = Rounding(RoundingType.Ceiling, 2, 5)
#     print("QL Ceiling for 1.235: ", ql_ceiling_rounding.apply(1.235)) # Positive. Expected: 1.23 (truncates after fabs)
#     print("QL Ceiling for 1.234: ", ql_ceiling_rounding.apply(1.234)) # Positive. Expected: 1.23 (truncates after fabs)
#     print("QL Ceiling for -1.235: ", ql_ceiling_rounding.apply(-1.235))# Negative, modVal=0.5 >= 0.5. Expected: -1.24
#     print("QL Ceiling for -1.237: ", ql_ceiling_rounding.apply(-1.237))# Negative, modVal=0.7 >= 0.5. Expected: -1.24 