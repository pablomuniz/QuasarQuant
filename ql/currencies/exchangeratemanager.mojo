# Mojo version of QuantLib's ql/currencies/exchangeratemanager.hpp

from quantfork.ql.time.date import Date, January, July, December, February, May, August, September, October, November # Import month constants
from quantfork.ql.currencies.europe import *
from quantfork.ql.currencies.america import *
from quantfork.ql.currencies.asia import JPYCurrency
from quantfork.ql.currencies.oceania import AUDCurrency
from sys import exit as sys_exit, argv as sys_argv # Import exit and argv
from quantfork.ql.currency import Currency
from builtin.math import min, max

# Import Dictionary for rate map
from collections.dict import Dict
from collections.list import List
from collections.optional import Optional

@value 
struct ExchangeRate:
    var source: String  # Currency code
    var target: String  # Currency code
    var rate: Float64   # Changed Float to Float64
    var start_date: Date
    var end_date: Date
  
    fn __init__(out self, source: Currency, target: Currency, rate: Float64, start_date: Date, end_date: Date):
        self.source = source.code
        self.target = target.code
        self.rate = rate
        self.start_date = start_date
        self.end_date = end_date
        
    fn is_valid_at(self, date: Date) -> Bool:
        return date >= self.start_date and date <= self.end_date
  
@value 
struct ExchangeRateManager:
    var rate_map: Dict[Int, List[ExchangeRate]]  # Map of hash -> list of rates
    #change base_currency to optional
    var base_currency: Optional[Currency]
    
    fn __init__(out self, start_date: Date, end_date: Date, base_currency: Optional[Currency] = None) raises:
        self.rate_map = Dict[Int, List[ExchangeRate]]()
        self.base_currency = base_currency
        self.add_known_rates()

    fn add_rate(mut self, source: Currency, target: Currency, rate: Float64) raises:
        var hash_val = self.get_hash(source, target)
        var max_date = Date.maxDate()
        #TODO: check if minDate is correct applying it here
        var exchange_rate = ExchangeRate(source, target, rate, Date.minDate(), max_date)
        
        # Initialize list for this hash if needed
        if hash_val not in self.rate_map:
            self.rate_map[hash_val] = List[ExchangeRate]()
            
        # Add to the beginning of the list (like in C++ implementation)
        self.rate_map[hash_val].insert(0, exchange_rate)

    fn get_rate(self, source: Currency, target: Currency) raises -> Optional[Float64]:
        """
        Get the exchange rate between two currencies.
        Returns None if no rate is available.
        
        Note: This function may raise exceptions when accessing the rate_map.
        """
        var hash_val = self.get_hash(source, target)
        
        if hash_val not in self.rate_map:
            return None
            
        # We need to iterate carefully over the exchange rates and check each one
        # TODO: check cpp implementation
        var rates_list = self.rate_map[hash_val]
        for i in range(len(rates_list)):
            var rate = rates_list[i]
            # Direct rate: source → target
            if rate.source == source.code and rate.target == target.code:
                return rate.rate
            # Inverse rate: target → source (need to invert the rate)
            elif rate.source == target.code and rate.target == source.code:
                return 1.0 / rate.rate
                
        return None
    #TODO: type should be a enum, not present in mojo at the moment
    fn lookup(self, source: Currency, target: Currency, date: Date = Date(), type: String = "Derived") raises -> Optional[ExchangeRate]:
        """
        Look up the exchange rate between two currencies at a given date.
        
        Args:
                source: The source currency.
                target: The target currency.
                date: The date for which the rate is requested (defaults to current date if not specified).
                type: Type of lookup - "Direct" for direct rates only, "Derived" to allow derived rates.
        
        Returns:
                Optional[ExchangeRate]: The found exchange rate or None if not available.
        
        Note: 
            - This function may raise exceptions when accessing the rate_map.
        """
        # If same currency, return rate of 1.0
        if source.code == target.code:
            return ExchangeRate(source, target, 1.0, Date.minDate(), Date.maxDate())
        
        # Use current date if no date specified
        var lookup_date = date
        if lookup_date == Date():
            # In C++ this would use Settings::instance().evaluationDate()
            # For now we'll use the default date since we don't have todaysDate()
            # Todo Fix this
            lookup_date = Date(1, January, 2023)  # Use a fixed date instead of todaysDate()
        
        # For direct lookups only, just call direct_lookup
        if type == "Direct":
            return self.direct_lookup(source, target, lookup_date)
        
        # If source has a triangulation currency, try to use it
        if source.triangulation_currency != "":
            # Get the triangulation currency object
            var link = Currency(source.triangulation_currency)
            
            if link.code == target.code:
                # If triangulation currency is the target, just do direct lookup
                return self.direct_lookup(source, link, lookup_date)
            else:
                # Otherwise chain the lookups: source -> link -> target
                var rate1 = self.direct_lookup(source, link, lookup_date)
                #recursive call to lookup
                var rate2 = self.lookup(link, target, lookup_date)
                
                if rate1 is not None and rate2 is not None:
                    # Chain the rates (implementation of ExchangeRate.chain needed)
                    # For now just return the first rate
                    return rate1
                else:
                    return None
        
        # If target has a triangulation currency, try to use it
        elif target.triangulation_currency != "":
            # Get the triangulation currency object
            var link = Currency(target.triangulation_currency)
            
            if source.code == link.code:
                # If source is the triangulation currency, just do direct lookup
                return self.direct_lookup(link, target, lookup_date)
            else:
                # Otherwise chain the lookups: source -> link -> target
                var rate1 = self.lookup(source, link, lookup_date)
                var rate2 = self.direct_lookup(link, target, lookup_date)
                
                if rate1 is not None and rate2 is not None:
                    # Chain the rates (implementation of ExchangeRate.chain needed)
                    # For now just return the first rate
                    return rate1
                else:
                    return None
        
        # As a last resort, try smart lookup with an empty forbidden list
        return self.smart_lookup(source, target, lookup_date, List[Int]())
        
    fn direct_lookup(self, source: Currency, target: Currency, date: Date) raises -> Optional[ExchangeRate]:
        """
        Look up a direct exchange rate between two currencies for a specific date.
        Returns None if no conversion is available.
        
        Note: This function may raise exceptions when accessing the rate_map.
        """
        var rate = self.fetch(source, target, date)
        if rate is not None:
            return rate
        else:
            # In C++ this would raise an exception
            print("No direct conversion available from", source.code, "to", target.code, "for", date.toString())
            return None
            
    fn fetch(self, source: Currency, target: Currency, date: Date) raises -> Optional[ExchangeRate]:
        """
        Find a valid exchange rate between two currencies for a specific date.
        Returns None if no valid rate is found.
        
        Note: This function may raise exceptions when accessing the rate_map.
        """
        var hash_val = self.get_hash(source, target)
        
        # If no rates for this hash, return None immediately
        if hash_val not in self.rate_map:
            return None
            
        # Check each rate with matching hash for validity at the specified date
        var rates_list = self.rate_map[hash_val]
        for i in range(len(rates_list)):
            var rate = rates_list[i]
            if rate.is_valid_at(date):
                # Check which direction the rate is stored
                if (rate.source == source.code and rate.target == target.code) or \
                   (rate.source == target.code and rate.target == source.code):
                    return rate
                
        return None

    fn get_hash(self, source: Currency, target: Currency) -> Int:
        return min(source.numeric_code, target.numeric_code) * 1000 + max(source.numeric_code, target.numeric_code)
        
    fn add_known_rates(mut self) raises:
        """
        Add standard known exchange rates for obsoleted currencies.
        """
        # Add EUR conversion rates for obsoleted currencies
        var max_date = Date.maxDate()
        
        # Currencies obsoleted by Euro
        self.add_rate(EURCurrency, ATSCurrency, 13.7603)
        self.add_rate(EURCurrency, BEFCurrency, 40.3399)
        self.add_rate(EURCurrency, DEMCurrency, 1.95583)
        self.add_rate(EURCurrency, ESPCurrency, 166.386)
        self.add_rate(EURCurrency, FIMCurrency, 5.94573)
        self.add_rate(EURCurrency, FRFCurrency, 6.55957)
        self.add_rate(EURCurrency, GRDCurrency, 340.750)
        self.add_rate(EURCurrency, IEPCurrency, 0.787564)
        self.add_rate(EURCurrency, ITLCurrency, 1936.27)
        self.add_rate(EURCurrency, LUFCurrency, 40.3399)
        self.add_rate(EURCurrency, NLGCurrency, 2.20371)
        self.add_rate(EURCurrency, PTECurrency, 200.482)
        
        # Other obsoleted currencies
        self.add_rate(TRYCurrency, TRLCurrency, 1000000.0)
        self.add_rate(RONCurrency, ROLCurrency, 10000.0)
        self.add_rate(PENCurrency, PEICurrency, 1000000.0)
        self.add_rate(PEICurrency, PEHCurrency, 1000.0)

    fn hashes(self, hash_val: Int, currency: Currency) -> Bool:
        """
        Check if a currency is part of a hash value.
        
        Args:
            hash_val: The hash value to check.
            currency: The currency to look for.
        
        Returns:
            Bool: True if the currency is part of the hash, False otherwise.
        """
        return currency.numeric_code == hash_val % 1000 or currency.numeric_code == hash_val // 1000
        
    fn is_in_list(self, list: List[Int], value: Int) -> Bool:
        """
        Check if a value is in a list.
        
        Args:
            list: The list to search in.
            value: The value to look for.
        
        Returns:
            Bool: True if the value is in the list, False otherwise.
        """
        for i in range(len(list)):
            if list[i] == value:
                return True
        return False

    @staticmethod
    @always_inline
    fn chain_rates(head: ExchangeRate, tail: ExchangeRate) -> ExchangeRate:
        """
        Chain two exchange rates together to create a new rate.
        Static method that can be used without an instance of ExchangeRateManager.
        
        Args:
            head: The first rate in the chain.
            tail: The second rate in the chain.
        
        Returns:
            ExchangeRate: The chained rate.
        """
        # Calculate the chained rate
        var chained_rate = head.rate * tail.rate
        
        # Use the source from the head and target from the tail
        var source = Currency(head.source)
        var target = Currency(tail.target)
        
        # Use the intersection of the validity periods
        var start_date = max(head.start_date, tail.start_date)
        var end_date = min(head.end_date, tail.end_date)
        
        return ExchangeRate(source, target, chained_rate, start_date, end_date)

    fn smart_lookup(self, source: Currency, target: Currency, date: Date, forbidden: Optional[List[Int]] = None) raises -> Optional[ExchangeRate]:
        """
        Try to find a chain of exchange rates to connect source and target currencies.
        Uses a recursive search with cycle detection to find a valid path.
        
        Args:
                source: The source currency.
                target: The target currency.
                date: The date for which the rate is requested.
                forbidden: Optional list of currency numeric codes that have been visited (to prevent cycles).
        
        Returns:
                Optional[ExchangeRate]: The found exchange rate chain or None if not found.
        
        Note: 
                - This function may raise exceptions when accessing the rate_map.
        """
        # First try direct lookup
        var direct_rate = self.fetch(source, target, date)
        if direct_rate is not None:
            return direct_rate
            
        # Initialize or use existing forbidden list
        var forbidden_list = List[Int]()
        if forbidden:
            forbidden_list = forbidden.value()
        else:
            forbidden_list = List[Int]()
            
        # Add source currency to forbidden list to prevent cycles
        forbidden_list.append(source.numeric_code)
        
        # Iterate through all rates in the map
        for hash_val_ptr in self.rate_map:
            var hash_val = hash_val_ptr[]
            # Check if this hash involves our source currency
            if self.hashes(hash_val, source):
                var rates_list = self.rate_map[hash_val]
                if len(rates_list) > 0:
                    # Get the first rate in the list
                    var first_rate = rates_list[0]
                    
                    # Determine the other currency in this rate
                    var other_currency: Currency
                    if first_rate.source == source.code:
                        other_currency = Currency(first_rate.target)
                    else:
                        other_currency = Currency(first_rate.source)
                        
                    # Check if the other currency is not forbidden
                    if not self.is_in_list(forbidden_list, other_currency.numeric_code):
                        # Try to get a rate from source to other currency
                        var head_rate = self.fetch(source, other_currency, date)
                        if head_rate:
                            # Recursively try to get from other currency to target
                            var tail_rate = self.smart_lookup(other_currency, target, date, forbidden_list)
                            if tail_rate is not None:
                                # Chain the rates together using static method
                                return ExchangeRateManager.chain_rates(head_rate.value(), tail_rate.value())
        
        # If we get here, no valid path was found
        print("No conversion path available from", source.code, "to", target.code, "for", date.toString())
        return None

    fn clear(mut self) raises:
        """
        Clear all exchange rates and reinitialize with known rates.
        This matches the C++ implementation's clear() method.
        """
        self.rate_map.clear()
        #TODO: maybe we should change the next line.
        # I really dont like that clear() also adds rates.
        # Solution might be to change the name to reset()
        self.add_known_rates()