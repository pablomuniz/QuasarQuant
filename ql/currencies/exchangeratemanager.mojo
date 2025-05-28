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
#TODO: There are some rouning discrepancies between the mojo and cpp versions.

@fieldwise_init
struct ExchangeRate(Copyable, Movable):
    var source: String  # Currency code
    var target: String  # Currency code
    var rate: Float64   # Changed Float to Float64
    var start_date: Date
    var end_date: Date

    fn __copyinit__(out self, other: Self):
        self.source = other.source
        self.target = other.target
        self.rate = other.rate
        self.start_date = other.start_date
        self.end_date = other.end_date

    fn __moveinit__(out self, owned other: Self):
        self.source = other.source^
        self.target = other.target^
        self.rate = other.rate # Float64 is trivial
        self.start_date = other.start_date^
        self.end_date = other.end_date^
  
    fn is_valid_at(self, date: Date) -> Bool:
        return date >= self.start_date and date <= self.end_date
  
@value 
struct ExchangeRateManager:
    var rate_map: Dict[Int, List[ExchangeRate]]  # Map of hash -> list of rates
    #change base_currency to optional
    var base_currency: Optional[Currency]
    
    # Helper to get fully defined currency objects by code
    # This function needs to be aware of all globally defined currencies.
    fn _get_full_currency_by_code(self, code: String) -> Optional[Currency]:
        # European Currencies (from europe.mojo)
        if code == EURCurrency.code: return EURCurrency
        if code == ATSCurrency.code: return ATSCurrency
        if code == BEFCurrency.code: return BEFCurrency
        if code == DEMCurrency.code: return DEMCurrency
        if code == ESPCurrency.code: return ESPCurrency
        if code == FIMCurrency.code: return FIMCurrency
        if code == FRFCurrency.code: return FRFCurrency
        if code == GRDCurrency.code: return GRDCurrency
        if code == IEPCurrency.code: return IEPCurrency
        if code == ITLCurrency.code: return ITLCurrency
        if code == LUFCurrency.code: return LUFCurrency
        if code == NLGCurrency.code: return NLGCurrency
        if code == PTECurrency.code: return PTECurrency
        # Add other European currencies if needed for smart_lookup logic (e.g., TRY, RON, PEN, PEI, PEH)
        if code == TRYCurrency.code: return TRYCurrency
        if code == TRLCurrency.code: return TRLCurrency # Historic
        if code == RONCurrency.code: return RONCurrency
        if code == ROLCurrency.code: return ROLCurrency # Historic

        # American Currencies (from america.mojo)
        if code == USDCurrency.code: return USDCurrency
        if code == PENCurrency.code: return PENCurrency
        if code == PEICurrency.code: return PEICurrency # Historic
        if code == PEHCurrency.code: return PEHCurrency # Historic
        # Add other American currencies if needed (e.g., CAD, ARS, BRL, CLP, COP, MXN, TTD, VEB)
        if code == CADCurrency.code: return CADCurrency
        if code == ARSCurrency.code: return ARSCurrency
        if code == BRLCurrency.code: return BRLCurrency
        if code == CLPCurrency.code: return CLPCurrency
        if code == COPCurrency.code: return COPCurrency
        if code == MXNCurrency.code: return MXNCurrency
        if code == TTDCurrency.code: return TTDCurrency
        if code == VEBCurrency.code: return VEBCurrency


        # Asian Currencies (from asia.mojo)
        if code == JPYCurrency.code: return JPYCurrency
        # Add other Asian currencies if needed

        # Oceanian Currencies (from oceania.mojo)
        if code == AUDCurrency.code: return AUDCurrency
        # Add other Oceanian currencies if needed
        
        # Fallback for unknown codes during smart_lookup
        print("ExchangeRateManager._get_full_currency_by_code: Unknown currency code encountered: " + code)
        return None

    fn __init__(out self, start_date: Date, end_date: Date, base_currency: Optional[Currency] = None) raises:
        self.rate_map = Dict[Int, List[ExchangeRate]]()
        self.base_currency = base_currency
        self.add_known_rates()

    fn add_rate(mut self, source: Currency, target: Currency, rate: Float64, start_date: Date, end_date: Date) raises:
        var hash_val = self.get_hash(source, target)
        var exchange_rate = ExchangeRate(source.code, target.code, rate, start_date, end_date)
        
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
            return ExchangeRate(source.code, target.code, 1.0, Date.minDate(), Date.maxDate())
        
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
                    return ExchangeRateManager.chain_rates(rate1.value(), rate2.value())
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
                    return ExchangeRateManager.chain_rates(rate1.value(), rate2.value())
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
            var rate_definition = rates_list[i] # This is the rate as stored
            if rate_definition.is_valid_at(date):
                # Check if the stored rate directly matches the request
                if rate_definition.source == source.code and rate_definition.target == target.code:
                    return rate_definition
                # Check if the inverse of the stored rate matches the request
                elif rate_definition.source == target.code and rate_definition.target == source.code:
                    # Return an oriented rate
                    return ExchangeRate(source.code, target.code, 1.0 / rate_definition.rate, 
                                        rate_definition.start_date, rate_definition.end_date)
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
        self.add_rate(EURCurrency, ATSCurrency, 13.7603, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, BEFCurrency, 40.3399, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, DEMCurrency, 1.95583, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, ESPCurrency, 166.386, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, FIMCurrency, 5.94573, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, FRFCurrency, 6.55957, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, GRDCurrency, 340.750, Date(1,January,2001), max_date)
        self.add_rate(EURCurrency, IEPCurrency, 0.787564, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, ITLCurrency, 1936.27, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, LUFCurrency, 40.3399, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, NLGCurrency, 2.20371, Date(1,January,1999), max_date)
        self.add_rate(EURCurrency, PTECurrency, 200.482, Date(1,January,1999), max_date)
        
        # Other obsoleted currencies
        self.add_rate(TRYCurrency, TRLCurrency, 1000000.0, Date(1,January,2005), max_date)
        self.add_rate(RONCurrency, ROLCurrency, 10000.0, Date(1,July,2005), max_date)
        self.add_rate(PENCurrency, PEICurrency, 1000000.0, Date(1,July,1991), max_date)
        self.add_rate(PEICurrency, PEHCurrency, 1000.0, Date(1,February,1985), max_date)

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
        # var source = Currency(head.source) # No longer needed
        # var target = Currency(tail.target) # No longer needed
        
        # Use the intersection of the validity periods
        var start_date = max(head.start_date, tail.start_date)
        var end_date = min(head.end_date, tail.end_date)
        
        return ExchangeRate(head.source, tail.target, chained_rate, start_date, end_date)

    fn smart_lookup(self, source: Currency, target: Currency, date: Date, forbidden_list_param: List[Int]) raises -> Optional[ExchangeRate]:
        print("\nDEBUG smart_lookup: Entered with source=" + source.code + ", target=" + target.code + ", date=" + date.toString())
        var forbidden_list_str: String = "DEBUG smart_lookup: forbidden_list_param = ["
        for i_fpl in range(len(forbidden_list_param)):
            forbidden_list_str += String(forbidden_list_param[i_fpl])
            if i_fpl < len(forbidden_list_param) - 1: forbidden_list_str += ", "
        forbidden_list_str += "]"
        print(forbidden_list_str)

        # Direct exchange rates are preferred.
        var direct_rate = self.fetch(source, target, date)
        if direct_rate is not None:
            print("DEBUG smart_lookup: Found direct rate for " + source.code + "->" + target.code)
            return direct_rate

        # If none is found, turn to smart lookup. The source currency
        # is forbidden to subsequent lookups in order to avoid cycles.
        var forbidden_list = forbidden_list_param # Mojo List is a value type, a copy is made.
        forbidden_list.append(source.numeric_code)
        
        var new_forbidden_list_str: String = "DEBUG smart_lookup: forbidden_list (after adding " + source.code + "(" + String(source.numeric_code) + ")) = ["
        for i_fl in range(len(forbidden_list)):
            new_forbidden_list_str += String(forbidden_list[i_fl])
            if i_fl < len(forbidden_list) - 1: new_forbidden_list_str += ", "
        new_forbidden_list_str += "]"
        print(new_forbidden_list_str)

        # Iterate through all entries in the rate_map
        for hash_key_ptr in self.rate_map.keys():
            var current_hash_val = hash_key_ptr[]
            print("DEBUG smart_lookup: Iterating rate_map, current_hash_val=" + String(current_hash_val))

            if self.hashes(current_hash_val, source): # Check if source currency is part of this hash pair
                print("DEBUG smart_lookup: Hash " + String(current_hash_val) + " involves source " + source.code)
                var rates_for_hash = self.rate_map[current_hash_val]
                if len(rates_for_hash) > 0:
                    var other_numeric_code_from_hash: Int
                    if source.numeric_code == current_hash_val % 1000:
                        other_numeric_code_from_hash = current_hash_val // 1000
                    else:
                        other_numeric_code_from_hash = current_hash_val % 1000
                    print("DEBUG smart_lookup: other_numeric_code_from_hash=" + String(other_numeric_code_from_hash))
                    
                    var is_other_forbidden_by_numeric = False
                    for i in range(len(forbidden_list)):
                        var f_code_val = forbidden_list[i]
                        if f_code_val == other_numeric_code_from_hash:
                            is_other_forbidden_by_numeric = True
                            break
                    print("DEBUG smart_lookup: is_other_forbidden_by_numeric (code " + String(other_numeric_code_from_hash) + ")=" + String(is_other_forbidden_by_numeric))
                    
                    if not is_other_forbidden_by_numeric:
                        print("DEBUG smart_lookup: Other (num_code=" + String(other_numeric_code_from_hash) + ") not forbidden, iterating rates in hash list.")
                        for r_idx in range(len(rates_for_hash)):
                            var current_entry_rate = rates_for_hash[r_idx]
                            print("DEBUG smart_lookup:  Current_entry_rate: " + current_entry_rate.source + "->" + current_entry_rate.target)
                            var potential_other_code_str: String

                            if current_entry_rate.source == source.code:
                                potential_other_code_str = current_entry_rate.target
                            elif current_entry_rate.target == source.code:
                                potential_other_code_str = current_entry_rate.source
                            else:
                                print("DEBUG smart_lookup:   Skipping entry rate, does not involve source.code directly.")
                                continue 
                            print("DEBUG smart_lookup:   Potential_other_code_str=" + potential_other_code_str)
                            
                            var temp_other_curr = Currency(potential_other_code_str)
                            var actual_other_currency_opt = self._get_full_currency_by_code(temp_other_curr.code)

                            if actual_other_currency_opt is None:
                                print("DEBUG smart_lookup:   Could not get full currency for " + temp_other_curr.code + ", skipping this path.")
                                continue
                            
                            var actual_other_currency = actual_other_currency_opt.value()
                            print("DEBUG smart_lookup:   Actual_other_currency: code=" + actual_other_currency.code + ", num_code=" + String(actual_other_currency.numeric_code))

                            print("DEBUG smart_lookup:   Attempting fetch for head_rate: " + source.code + " -> " + actual_other_currency.code)
                            var head_rate = self.fetch(source, actual_other_currency, date)
                            if head_rate is not None:
                                print("DEBUG smart_lookup:   Found head_rate: " + head_rate.value().source + "->" + head_rate.value().target + " rate=" + String(head_rate.value().rate))
                                print("DEBUG smart_lookup:   Attempting recursive smart_lookup for tail: " + actual_other_currency.code + " -> " + target.code)
                                var tail_rate = self.smart_lookup(actual_other_currency, target, date, forbidden_list)
                                if tail_rate is not None:
                                    print("DEBUG smart_lookup:   Found tail_rate. Chaining and returning.")
                                    return ExchangeRateManager.chain_rates(head_rate.value(), tail_rate.value())
                                else:
                                    print("DEBUG smart_lookup:   Recursive smart_lookup for tail " + actual_other_currency.code + " -> " + target.code + " returned None.")
                            else:
                                print("DEBUG smart_lookup:   Fetch for head_rate " + source.code + " -> " + actual_other_currency.code + " returned None.")
                    else:
                        print("DEBUG smart_lookup: Other (num_code=" + String(other_numeric_code_from_hash) + ") IS forbidden by numeric code pre-check.")


        print("DEBUG smart_lookup: No conversion found for " + source.code + "->" + target.code + ". Returning None.")
        return None

    fn clear(mut self) raises:
        """
        Clear all exchange rates and reinitialize with known rates.
        This matches the C++ implementation's clear() method.
        """
        self.rate_map.clear()
        self.add_known_rates()