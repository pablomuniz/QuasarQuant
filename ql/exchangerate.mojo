# Mojo version of QuantLib's ql/exchangerate.hpp/cpp

from quantfork.ql.currency import Currency
from quantfork.ql.money import Money
from collections.optional import Optional

# Constants for exchange rate types
alias Direct = 0
alias Derived = 1

@value
struct ExchangeRate:
    """
    Exchange rate between two currencies.
    
    This represents either a direct exchange rate (with an explicit rate)
    or a derived exchange rate (calculated from two linked exchange rates).
    """
    var source_currency: string
    var target_currency: string
    var rate: Float
    var type: Int  # 0 = Direct, 1 = Derived
    var chain_first: Optional[ExchangeRate]  # First leg of chained rate
    var chain_second: Optional[ExchangeRate]  # Second leg of chained rate
    
    # Default constructor
    fn __init__(out self):
        self.source_currency = ""
        self.target_currency = ""
        self.rate = 0.0
        self.type = Direct
        self.chain_first = None
        self.chain_second = None
    
    # Direct exchange rate constructor
    fn __init__(out self, source: Currency, target: Currency, rate: Float):
        self.source_currency = source.code
        self.target_currency = target.code
        self.rate = rate
        self.type = Direct
        self.chain_first = None
        self.chain_second = None
    
    # Derived exchange rate constructor (from a chain of two rates)
    fn __init__(out self, r1: ExchangeRate, r2: ExchangeRate):
        self.type = Derived
        self.chain_first = Optional[ExchangeRate](r1)
        self.chain_second = Optional[ExchangeRate](r2)
        
        # Calculate the source, target, and resulting rate based on how the currencies connect
        if r1.source_currency == r2.source_currency:
            self.source_currency = r1.target_currency
            self.target_currency = r2.target_currency
            self.rate = r2.rate / r1.rate
        elif r1.source_currency == r2.target_currency:
            self.source_currency = r1.target_currency
            self.target_currency = r2.source_currency
            self.rate = 1.0 / (r1.rate * r2.rate)
        elif r1.target_currency == r2.source_currency:
            self.source_currency = r1.source_currency
            self.target_currency = r2.target_currency
            self.rate = r1.rate * r2.rate
        elif r1.target_currency == r2.target_currency:
            self.source_currency = r1.source_currency
            self.target_currency = r2.source_currency
            self.rate = r1.rate / r2.rate
        else:
            # In C++ this would throw an exception with "exchange rates not chainable"
            print("Error: Exchange rates not chainable")
            self.source_currency = ""
            self.target_currency = ""
            self.rate = 0.0
    
    # Methods to get the currencies - these would need a way to look up Currency objects by code
    fn source(self) -> string:
        """Returns the source currency code"""
        return self.source_currency
        
    fn target(self) -> string:
        """Returns the target currency code"""
        return self.target_currency
    
    # Exchange method (converts an amount from one currency to another)
    fn exchange(self, money: Money) -> Money:
        """
        Convert money from one currency to another using this exchange rate.
        
        Parameters:
        - money: The Money object to convert
        
        Returns:
        - A new Money object in the target currency
        """
        var amount = money.get_value()
        var currency_code = money.get_currency_code()
        
        if self.type == Direct:
            if currency_code == self.source_currency:
                return Money(amount * self.rate, Currency(self.target_currency))
            elif currency_code == self.target_currency:
                return Money(amount / self.rate, Currency(self.source_currency))
            else:
                print("Error: Exchange rate not applicable")
                return Money(0.0, Currency(currency_code))  # Return zero in original currency on error
        elif self.type == Derived:
            if self.chain_first is None or self.chain_second is None:
                print("Error: Derived exchange rate missing chain components")
                return Money(0.0, Currency(currency_code))
                
            # For derived rates, the money gets converted through the chain
            if currency_code == self.source_currency:
                return Money(amount * self.rate, Currency(self.target_currency))
            elif currency_code == self.target_currency:
                return Money(amount / self.rate, Currency(self.source_currency))
            else:
                print("Error: Exchange rate not applicable for derived rate")
                return Money(0.0, Currency(currency_code))
        else:
            print("Error: Unknown exchange rate type")
            return Money(0.0, Currency(currency_code))
    
    # Static method to chain two exchange rates together
    @staticmethod
    fn chain(r1: ExchangeRate, r2: ExchangeRate) -> ExchangeRate:
        """
        Create a new exchange rate by chaining two exchange rates together.
        
        Parameters:
        - r1: First exchange rate
        - r2: Second exchange rate
        
        Returns:
        - A new ExchangeRate representing the chained conversion
        """
        return ExchangeRate(r1, r2)  # Uses the derived constructor

# Note: The original C++ implementation includes a Money class that represents
# an amount in a specific currency. We're using (Float, String) tuples instead.
# If a full Money implementation is needed, it could be added in a separate file. 