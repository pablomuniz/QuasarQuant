# Mojo version of QuantLib's money.hpp/cpp

from quantfork.ql.currency import Currency
#add conversion type to match money.hpp
#as we dont have enums in mojo yet, we will constants
#todo this program is far from complete, we need to finish the exchange rate manager
from quantfork.ql.currencies.exchangeratemanager import ExchangeRateManager

struct ConversionType:
    var NOCONVERSION = 0
    var BASECURRENCYCONVERSION = 1
    var AUTOMATEDCONVERSION = 2
    
        
        

@value
struct Money:
    """
    Money class representing an amount in a specific currency.
    
    This class represents a cash amount in a given currency. It provides
    arithmetic and comparison operators for normal money operations.
    """
    var value: Float
    var currency: Currency
    var conversion_type: ConversionType
    var base_currency: Currency

    # Constructors
    fn __init__(out self):
        """Default constructor: creates a zero amount with empty currency."""
        self.value = 0.0
        self.currency = Currency()
    
    fn __init__(out self, value: Float, currency: Currency, conversion_type: ConversionType, base_currency: Currency):
        """Creates a money amount with the given value and currency."""
        self.value = value
        self.currency = currency
        self.conversion_type = conversion_type
        self.base_currency = base_currency
    
    fn convert_to(self, target_currency: Currency):
        """Converts the money amount to the target currency."""
        #todo we need to call the exchange rate manager to get the conversion rate
        if self.currency == target_currency:
            return self
        return Money(self.value, target_currency, self.conversion_type, self.base_currency)
    
    # Basic accessors
    fn get_value(self) -> Float:
        """Returns the amount stored in this money object."""
        return self.value
        
    fn get_currency_code(self) -> string:
        """Returns the currency code of this money object."""
        return self.currency.code
    
    # Arithmetic operations
    fn __add__(self, other: Money) raises -> Money:
        """Adds two money amounts with compatible currencies."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be added")
        return Money(self.value + other.value, self.currency)
    
    fn __sub__(self, other: Money) raises -> Money:
        """Subtracts a money amount from another with compatible currencies."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be subtracted")
        return Money(self.value - other.value, self.currency)
    
    fn __mul__(self, scalar: Float) -> Money:
        """Multiplies a money amount by a scalar value."""
        return Money(self.value * scalar, self.currency)
    
    fn __truediv__(self, scalar: Float) -> Money:
        """Divides a money amount by a scalar value."""
        return Money(self.value / scalar, self.currency)
    
    # Comparison operators
    fn __eq__(self, other: Money) raises -> Bool:
        """Checks if two money amounts are equal."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be compared")
        return self.value == other.value
    
    fn __ne__(self, other: Money) raises -> Bool:
        """Checks if two money amounts are not equal."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be compared")
        return self.value != other.value
    
    fn __lt__(self, other: Money) raises -> Bool:
        """Checks if this money amount is less than another."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be compared")
        return self.value < other.value
    
    fn __le__(self, other: Money) raises -> Bool:
        """Checks if this money amount is less than or equal to another."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be compared")
        return self.value <= other.value
    
    fn __gt__(self, other: Money) raises -> Bool:
        """Checks if this money amount is greater than another."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be compared")
        return self.value > other.value
    
    fn __ge__(self, other: Money) raises -> Bool:
        """Checks if this money amount is greater than or equal to another."""
        if self.currency.code != other.currency.code:
            raise Error("Money amounts with different currencies cannot be compared")
        return self.value >= other.value
    
    # Display method
    fn toString(self) -> string:
        """Returns a string representation of this money amount with currency code."""
        return String(self.value) + " " + self.currency.code 