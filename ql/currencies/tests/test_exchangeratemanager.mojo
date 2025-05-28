from testing import assert_equal, assert_true, assert_almost_equal, assert_is_none
from quantfork.ql.time.date import Date, January, February, December # Month constants used
from quantfork.ql.currency import Currency
from quantfork.ql.math.rounding import Rounding # For create_test_currency helper
from quantfork.ql.currencies.exchangeratemanager import ExchangeRateManager, ExchangeRate # Main classes under test
from builtin.math import min, max # Used in tests for date comparison

# Helper to create dummy currencies for testing triangulation
fn create_test_currency(name: String, code: String, numeric_code: Int, triangulation_currency_code: String = "") -> Currency:
    return Currency(name, code, numeric_code, code, "", 100, Rounding(), triangulation_currency_code)

fn test_triangulation_smart_lookup():
    var manager = ExchangeRateManager(Date(1, January, 2023), Date(31, December, 2023))
    manager.rate_map.clear() # Start with a completely empty rate map

    let cur_x = create_test_currency("TestX", "TSX", 901)
    let cur_y = create_test_currency("TestY", "TSY", 902)
    let cur_z = create_test_currency("TestZ", "TSZ", 903)

    let date1_start = Date(1, January, 2023)
    let date1_end = Date(31, December, 2023)
    let date2_start = Date(15, January, 2023)
    let date2_end = Date(15, December, 2023)

    let rate_xy = 1.5
    let rate_yz = 2.0

    manager.add_rate(cur_x, cur_y, rate_xy, date1_start, date1_end)
    manager.add_rate(cur_y, cur_z, rate_yz, date2_start, date2_end)

    let lookup_date = Date(1, February, 2023)
    # smart_lookup is the fallback in the 'else' branch of the main lookup method
    let result = manager.lookup(cur_x, cur_z, lookup_date, "Derived")


    assert_true(result is not None, msg="Lookup should find a rate via smart_lookup")
    if result is not None:
        let chained_rate_obj = result.value()
        assert_equal(chained_rate_obj.source, cur_x.code, msg="Chained rate source should be X")
        assert_equal(chained_rate_obj.target, cur_z.code, msg="Chained rate target should be Z")
        assert_almost_equal(chained_rate_obj.rate, rate_xy * rate_yz, atol=0.000001, msg="Chained rate value incorrect")
        
        let expected_start_date = max(date1_start, date2_start)
        let expected_end_date = min(date1_end, date2_end)
        assert_equal(chained_rate_obj.start_date.serial_number(), expected_start_date.serial_number(), msg="Chained rate start_date incorrect")
        assert_equal(chained_rate_obj.end_date.serial_number(), expected_end_date.serial_number(), msg="Chained rate end_date incorrect")

fn test_triangulation_source_link():
    var manager = ExchangeRateManager(Date(1, January, 2023), Date(31, December, 2023))
    manager.rate_map.clear()

    let cur_l_for_link = create_test_currency("LinkL", "LNK", 905)
    let cur_s = create_test_currency("SourceS", "SRC", 904, cur_l_for_link.code)
    let cur_t = create_test_currency("TargetT", "TGT", 906)
    
    let date1_start = Date(1, January, 2023)
    let date1_end = Date(31, December, 2023) # S -> L
    let date2_start = Date(15, January, 2023)
    let date2_end = Date(15, December, 2023) # L -> T

    let rate_sl = 1.2
    let rate_lt = 0.8

    manager.add_rate(cur_s, cur_l_for_link, rate_sl, date1_start, date1_end)
    manager.add_rate(cur_l_for_link, cur_t, rate_lt, date2_start, date2_end)

    let lookup_date = Date(1, February, 2023)
    let result = manager.lookup(cur_s, cur_t, lookup_date, "Derived") 

    assert_true(result is not None, msg="Lookup should find a rate via source triangulation")
    if result is not None:
        let chained_rate_obj = result.value()
        assert_equal(chained_rate_obj.source, cur_s.code, msg="Chained rate source should be S")
        assert_equal(chained_rate_obj.target, cur_t.code, msg="Chained rate target should be T")
        assert_almost_equal(chained_rate_obj.rate, rate_sl * rate_lt, atol=0.000001, msg="Chained rate value incorrect for source link")
        
        let expected_start_date = max(date1_start, date2_start)
        let expected_end_date = min(date1_end, date2_end)
        assert_equal(chained_rate_obj.start_date.serial_number(), expected_start_date.serial_number(), msg="Chained rate start_date incorrect for source link")
        assert_equal(chained_rate_obj.end_date.serial_number(), expected_end_date.serial_number(), msg="Chained rate end_date incorrect for source link")

fn test_triangulation_target_link():
    var manager = ExchangeRateManager(Date(1, January, 2023), Date(31, December, 2023))
    manager.rate_map.clear()

    let cur_l_for_link = create_test_currency("LinkL", "LNK", 905)
    let cur_s = create_test_currency("SourceS", "SRC", 904)
    let cur_t = create_test_currency("TargetT", "TGT", 906, cur_l_for_link.code)

    let date1_start = Date(1, January, 2023)
    let date1_end = Date(31, December, 2023) # S -> L
    let date2_start = Date(15, January, 2023)
    let date2_end = Date(15, December, 2023) # L -> T

    let rate_sl = 1.2
    let rate_lt = 0.8

    manager.add_rate(cur_s, cur_l_for_link, rate_sl, date1_start, date1_end)
    manager.add_rate(cur_l_for_link, cur_t, rate_lt, date2_start, date2_end)

    let lookup_date = Date(1, February, 2023)
    let result = manager.lookup(cur_s, cur_t, lookup_date, "Derived")

    assert_true(result is not None, msg="Lookup should find a rate via target triangulation")
    if result is not None:
        let chained_rate_obj = result.value()
        assert_equal(chained_rate_obj.source, cur_s.code, msg="Chained rate source should be S")
        assert_equal(chained_rate_obj.target, cur_t.code, msg="Chained rate target should be T")
        assert_almost_equal(chained_rate_obj.rate, rate_sl * rate_lt, atol=0.000001, msg="Chained rate value incorrect for target link")
        
        let expected_start_date = max(date1_start, date2_start)
        let expected_end_date = min(date1_end, date2_end)
        assert_equal(chained_rate_obj.start_date.serial_number(), expected_start_date.serial_number(), msg="Chained rate start_date incorrect for target link")
        assert_equal(chained_rate_obj.end_date.serial_number(), expected_end_date.serial_number(), msg="Chained rate end_date incorrect for target link")

fn test_triangulation_source_link_is_target():
    var manager = ExchangeRateManager(Date(1, January, 2023), Date(31, December, 2023))
    manager.rate_map.clear()

    let cur_lkt = create_test_currency("LinkL_Target", "LKT", 908) 
    let cur_slt = create_test_currency("SourceS_SLT", "SLT", 907, cur_lkt.code) 
    
    let date1_start = Date(1, January, 2023)
    let date1_end = Date(31, December, 2023) 

    let rate_s_lkt = 0.75
    manager.add_rate(cur_slt, cur_lkt, rate_s_lkt, date1_start, date1_end)
    
    let lookup_date = Date(1, February, 2023)
    let result = manager.lookup(cur_slt, cur_lkt, lookup_date, "Derived")

    assert_true(result is not None, msg="Lookup should find a rate when source link IS target")
    if result is not None:
        let direct_rate_obj = result.value()
        assert_equal(direct_rate_obj.source, cur_slt.code, msg="Direct rate source (SLT) incorrect")
        assert_equal(direct_rate_obj.target, cur_lkt.code, msg="Direct rate target (LKT) incorrect")
        assert_almost_equal(direct_rate_obj.rate, rate_s_lkt, atol=0.000001, msg="Direct rate value incorrect")
        assert_equal(direct_rate_obj.start_date.serial_number(), date1_start.serial_number(), msg="Direct rate start_date incorrect")
        assert_equal(direct_rate_obj.end_date.serial_number(), date1_end.serial_number(), msg="Direct rate end_date incorrect")

fn test_triangulation_target_link_is_source():
    var manager = ExchangeRateManager(Date(1, January, 2023), Date(31, December, 2023))
    manager.rate_map.clear()

    let cur_lks = create_test_currency("LinkL_Source", "LKS", 910) 
    let cur_tls = create_test_currency("TargetT_TLS", "TLS", 909, cur_lks.code) 

    let date1_start = Date(1, January, 2023)
    let date1_end = Date(31, December, 2023) 

    let rate_lks_t = 1.33
    manager.add_rate(cur_lks, cur_tls, rate_lks_t, date1_start, date1_end)

    let lookup_date = Date(1, February, 2023)
    let result = manager.lookup(cur_lks, cur_tls, lookup_date, "Derived")

    assert_true(result is not None, msg="Lookup should find a rate when target link IS source")
    if result is not None:
        let direct_rate_obj = result.value()
        assert_equal(direct_rate_obj.source, cur_lks.code, msg="Direct rate source (LKS) incorrect")
        assert_equal(direct_rate_obj.target, cur_tls.code, msg="Direct rate target (TLS) incorrect")
        assert_almost_equal(direct_rate_obj.rate, rate_lks_t, atol=0.000001, msg="Direct rate value incorrect")
        assert_equal(direct_rate_obj.start_date.serial_number(), date1_start.serial_number(), msg="Direct rate start_date incorrect")
        assert_equal(direct_rate_obj.end_date.serial_number(), date1_end.serial_number(), msg="Direct rate end_date incorrect")

fn test_triangulation_no_path():
    var manager = ExchangeRateManager(Date(1, January, 2023), Date(31, December, 2023))
    manager.rate_map.clear()

    let cur_a = create_test_currency("TestA", "TSA", 911)
    let cur_b = create_test_currency("TestB", "TSB", 912)
    let cur_c = create_test_currency("TestC", "TSC", 913) # Unrelated
    let cur_d = create_test_currency("TestD", "TSD", 914)

    let date1_start = Date(1, January, 2023)
    let date1_end = Date(31, December, 2023)
    
    manager.add_rate(cur_a, cur_b, 1.0, date1_start, date1_end) # A -> B
    # No rate from B to D or A to D directly or via C

    let lookup_date = Date(1, February, 2023)
    let result = manager.lookup(cur_a, cur_d, lookup_date, "Derived")
    assert_is_none(result, msg="Lookup should return None when no triangulation path exists") 