from sys import argv, exit

from quantfork.ql.currencies.exchangeratemanager import ExchangeRateManager, ExchangeRate
from quantfork.ql.currency import Currency
from quantfork.ql.time.date import Date, January, February, March, April, May, June, July, August, September, October, November, December
# Import predefined currency instances
from quantfork.ql.currencies.europe import (
    EURCurrency, ATSCurrency, BEFCurrency, DEMCurrency, ESPCurrency, FIMCurrency, 
    FRFCurrency, GRDCurrency, IEPCurrency, ITLCurrency, LUFCurrency, NLGCurrency, 
    PTECurrency
)
# Import other known currencies (add more as needed)
from quantfork.ql.currencies.america import USDCurrency # Assuming this exists
from quantfork.ql.currencies.oceania import AUDCurrency # Assuming this exists
from quantfork.ql.currencies.asia import JPYCurrency # Assuming this exists


# Helper function to get a Currency instance from its code
fn get_currency_from_code(code: String) -> Optional[Currency]:
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
    if code == USDCurrency.code: return USDCurrency
    if code == AUDCurrency.code: return AUDCurrency
    if code == JPYCurrency.code: return JPYCurrency
    # Add more currencies here as they are defined and imported
    print("Debug: Unknown currency code in get_currency_from_code:", code)
    return None

fn main() raises:
    if len(argv()) != 7:
        print("STATUS:Error")
        print("MESSAGE:Invalid arguments. Usage: <program> <src_code> <tgt_code> <day> <month> <year> <type (Direct|Derived)>")
        exit(1)

    var source_code = argv()[1]
    var target_code = argv()[2]
    var day_str = argv()[3]
    var month_str = argv()[4]
    var year_str = argv()[5]
    var lookup_type_str = argv()[6]

    var day: Int = 0
    var month: Int = 0
    var year: Int = 0

    try:
        day = Int(day_str)
        month = Int(month_str)
        year = Int(year_str)
    except e:
        print("STATUS:Error")
        print("MESSAGE:Invalid date components. Day, month, and year must be integers.")
        exit(1)
    
    if lookup_type_str != "Direct" and lookup_type_str != "Derived":
        print("STATUS:Error")
        print("MESSAGE:Invalid lookup type. Must be 'Direct' or 'Derived'.")
        exit(1)

    var source_currency_opt = get_currency_from_code(source_code)
    var target_currency_opt = get_currency_from_code(target_code)

    if source_currency_opt is None:
        print("STATUS:Error")
        print("MESSAGE:Unknown or unsupported source currency code provided: " + source_code)
        exit(1)
    
    if target_currency_opt is None:
        print("STATUS:Error")
        print("MESSAGE:Unknown or unsupported target currency code provided: " + target_code)
        exit(1)

    var source_currency = source_currency_opt.value()
    var target_currency = target_currency_opt.value()
    
    # The Date constructor will validate day, month, year ranges.
    # If invalid, it prints its own error and results in a null date (serial 0).
    # We should ideally catch this or check serialNumber if we want custom runner error messages.
    # For now, let's rely on Date's behavior. If Date becomes null, lookup might fail gracefully.
    var lookup_date = Date(day, month, year)
    if lookup_date.serial_number() == 0 :
        # This check relies on the Date constructor setting serial to 0 for invalid DMY.
        # The Date constructor itself prints specific errors.
        print("STATUS:Error")
        # The specific error was already printed by Date's constructor.
        print("MESSAGE:Invalid lookup date provided (e.g., day out of month range, or year out of QL range).")
        exit(1)


    # Instantiate ExchangeRateManager. 
    # The constructor needs start_date and end_date which are not used by the manager logic itself,
    # but are required by its signature. Using min/max date for broadest possible manager "lifespan".
    var manager = ExchangeRateManager(Date.minDate(), Date.maxDate())

    var result: Optional[ExchangeRate] = manager.lookup(source_currency, target_currency, lookup_date, lookup_type_str)

    if result is not None:
        var rate_obj = result.value()
        print("STATUS:Success")
        print("SOURCE:" + rate_obj.source)
        print("TARGET:" + rate_obj.target)
        print("RATE:" + String(rate_obj.rate)) # Ensure Float64 to String conversion
        print("START_DAY:" + String(rate_obj.start_date.dayOfMonth()))
        print("START_MONTH:" + String(rate_obj.start_date.month()))
        print("START_YEAR:" + String(rate_obj.start_date.year()))
        print("END_DAY:" + String(rate_obj.end_date.dayOfMonth()))
        print("END_MONTH:" + String(rate_obj.end_date.month()))
        print("END_YEAR:" + String(rate_obj.end_date.year()))
    else:
        print("STATUS:NotFound")
        print("MESSAGE:No rate found for " + source_code + " to " + target_code + " on " + year_str + "-" + month_str + "-" + day_str) 