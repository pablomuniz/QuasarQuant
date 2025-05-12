# Mojo version of QuantLib's ql/time/date.hpp

# --- Helper Types ---

alias Day = Int
alias Year = Int

# Month Enum (using Int constants for simplicity for now)
# TODO: Consider using @value struct like RoundingType later if needed
alias January = 1
alias February = 2
alias March = 3
alias April = 4
alias May = 5
alias June = 6
alias July = 7
alias August = 8
alias September = 9
alias October = 10
alias November = 11
alias December = 12
alias Month = Int # Using Int as the type for Month

# Weekday Enum (using Int constants for simplicity)
# Sunday = 1 (matches QL internal), Saturday = 7
# TODO: Consider using @value struct later
alias Sunday = 1
alias Monday = 2
alias Tuesday = 3
alias Wednesday = 4
alias Thursday = 5
alias Friday = 6
alias Saturday = 7
alias Weekday = Int # Using Int as the type for Weekday

# --- Date Struct --- 

@value # Date should be copyable and movable
struct Date:
    # QL uses a 32-bit signed int for serial number.
    # We use Int, assuming it's 64-bit usually, which is fine.
    var serialNumber: Int 
    # Note: QL's serial number represents days since Dec 30, 1899
    # 0 represents a null date in this struct, matching QL's default constructor behaviour.
    # Valid QL serial numbers start from 367 (Jan 1, 1901) to 109574 (Dec 31, 2199) or similar range.

    # --- Private Static Helper Methods (Ported from C++) ---

    @staticmethod
    fn _isLeap(y: Year) -> Bool:
        """Checks if a year is a leap year (standard Gregorian rule)."""
        # Note: QL C++ considers 1900 a leap year for Excel compatibility,
        # but 1900 is outside the standard QL date range [1901, 2199].
        # We implement the standard rule.
        if y % 4 != 0: return False
        if y % 100 == 0 and y % 400 != 0: return False
        return True

    @staticmethod
    fn _monthLength(m: Month, leapYear: Bool) -> Day:
        """Returns the number of days in the given month."""
        # Using direct values instead of array lookup for Mojo clarity
        if m == February:
            return 29 if leapYear else 28
        elif m == April or m == June or m == September or m == November:
            return 30
        else: # Jan, Mar, May, Jul, Aug, Oct, Dec
            return 31
            
    @staticmethod
    fn _monthOffset(m: Month, leapYear: Bool) -> Int:
        """Returns days in year before the given month begins (0 for Jan)."""
        # Precomputed offsets (days before month m starts)
        # Non-leap year offsets
        var MonthOffset: List[Int] = List(0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
        # Leap year offsets
        var MonthLeapOffset: List[Int] = List(0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335)
        
        # Month is 1-based, index is 0-based
        if m < 1 or m > 12: 
             # Should be caught by validation, but handle defensively
             # print("Error: Invalid month in _monthOffset") # Silenced as per user request
             return -1 # Error indicator
             
        if leapYear:
            return MonthLeapOffset[m-1]
        else:
            return MonthOffset[m-1]

    @staticmethod
    fn _yearOffset(y: Year) -> Int:
        """Returns serial number for Dec 31st of the preceding year (y-1).
           Based on Dec 30, 1899 = serial 0.
           So, Dec 31, 1899 = serial 1.
           The formula calculates days from Dec 31, 1899 as if it were 0, so add 1."""
        # Original formula: 365*(y-1900) + (y-1901)//4 - (y-1901)//100 + (y-1601)//400
        # This result is serial for Dec 31 of y-1, if Dec 31, 1899 was epoch 0.
        # Since Dec 30, 1899 is epoch 0, Dec 31, 1899 is epoch 1. Add 1.
        # The formula correctly yields 1 for y=1900 (Dec 31, 1899), so special case removed.
        return 365*(y-1900) + (y-1901)//4 - (y-1901)//100 + (y-1601)//400 + 1
        
    @staticmethod
    fn _checkSerialNumber(serial: Int):
        """Validates the serial number is within QL range."""
        # Note: QL range is [367, 109574] corresponding to [Jan 1 1901, Dec 31 2199]
        # 0 is allowed for the null date.
        var minSerial = 367
        var maxSerial = 109574 
        if serial != 0 and (serial < minSerial or serial > maxSerial):
            # print("Error: Serial number ", serial, " out of valid range [") # Silenced
            # print(minSerial, ", ", maxSerial, "]") # Silenced
            # TODO: Raise Error
            # For now, maybe allow it but warn? This function is a check, not an enforcer by default.
            pass

    # --- Constructors ---

    # Default constructor -> Null date (serial 0)
    fn __init__(mut self):
        """Default constructor: creates a null date (serial number 0)."""
        self.serialNumber = 0

    # Constructor from serial number
    fn __init__(mut self, serial: Int):
        """Constructs Date from a serial number."""
        # Date._checkSerialNumber(serial) # Perform validation
        # TODO: Decide on validation enforcement (raise error or allow invalid serials)
        self.serialNumber = serial

    # Constructor from day, month, year
    fn __init__(mut self, d: Day, m: Month, y: Year):
        """Constructs Date from day, month, year."""
        # Validation first
        if y < 1901 or y > 2199:
             print("Error: Year ", y, " out of valid range [1901, 2199]")
             # TODO: Raise Error
             self.serialNumber = 0 # Null date on error
             return 
        if m < 1 or m > 12:
             print("Error: Month ", m, " out of valid range [1, 12]")
             # TODO: Raise Error
             self.serialNumber = 0
             return
             
        var leap = Date._isLeap(y)
        var len = Date._monthLength(m, leap)
        if d < 1 or d > len:
             print("Error: Day ", d, " out of valid range [1, ", len, "] for month ", m)
             # TODO: Raise Error
             self.serialNumber = 0
             return
             
        # Calculation based on ported QL logic
        var mo = Date._monthOffset(m, leap)
        var yo = Date._yearOffset(y) # yo is now serial of Dec 31 of y-1
        self.serialNumber = d + mo + yo # Corrected: removed +1 as yo is now correctly based
        # Old: self.serialNumber = d + mo + yo + 1

    # --- Basic Inspectors ---
    fn serial_number(self) -> Int:
        "Returns the underlying serial number." 
        return self.serialNumber
        
    fn year(self) -> Year:
        """Returns the year of the date."""
        if self.serialNumber == 0: return 0 # Or raise error for null date?
        # Ported logic from C++
        var y: Year = self.serialNumber // 365 + 1900 # Integer division
        # yearOffset(y) is Dec 31st of the preceding year
        if self.serialNumber <= Date._yearOffset(y):
             y -= 1
        return y
        
    fn dayOfYear(self) -> Day:
        """Returns the day of the year (1-366)."""
        if self.serialNumber == 0: return 0 # Null date
        # self.serialNumber is days from epoch (Dec 30, 1899 = 0)
        # Date._yearOffset(self.year()) is serial of Dec 31 of (year-1)
        # Difference is the 1-based day number in the current year.
        return self.serialNumber - Date._yearOffset(self.year())
        # Old: return self.serialNumber - Date._yearOffset(self.year()) - 1
        
    fn month(self) -> Month:
        """Returns the month of the date (1-12)."""
        if self.serialNumber == 0:
            # print("Warning: month() called on null Date")
            return 0 # Or raise error

        # _checkSerialNumber(self.serialNumber) # TODO: decide on error handling

        var y = self.year() # year() will handle its own null check if necessary
        var d = self.dayOfYear() # dayOfYear() will handle its own null check

        if d == 0 and self.serialNumber != 0: # Should not happen if dayOfYear is correct
            # print("Error: dayOfYear is 0 for non-null date in month()") # Silenced internal assertion
            return 0 # Error

        var m_val: Month = d // 30 + 1 # Renamed to avoid conflict with input 'm'
        if m_val > 12: m_val = 12
        if m_val < 1: m_val = 1 # Should not happen if d > 0

        var leap = Date._isLeap(y)

        # In QL, monthOffset(m, leap) is days *before* month m.
        # So, d <= monthOffset(m, leap) means d is in a month *before* m.
        while m_val > 1 and d <= Date._monthOffset(m_val, leap):
            m_val -= 1
        
        # In QL, monthOffset(Month(m+1), leap) is days *before* month m+1,
        # which is effectively the last day of month m (if m < 12).
        # So, d > monthOffset(Month(m+1), leap) means d is in a month *after* m.
        # The term (Date._monthOffset(m, leap) + Date._monthLength(m, leap))
        # calculates the serial number of the last day of month 'm' within its year.
        # If 'd' (dayOfYear) is greater than this, it means 'd' falls into a subsequent month.
        while m_val < 12 and d > (Date._monthOffset(m_val, leap) + Date._monthLength(m_val, leap)):
            m_val += 1
            
        return m_val
        
    fn dayOfMonth(self) -> Day:
        """Returns the day of the month (1-31)."""
        if self.serialNumber == 0:
            # print("Warning: dayOfMonth() called on null Date")
            return 0 # Or raise error
        
        # _checkSerialNumber(self.serialNumber)

        var y = self.year() # year() handles null checks
        var m = self.month() # month() handles null checks
        
        if m == 0 and self.serialNumber != 0: # Error from month() if serialNumber is not null
             return 0

        var leap = Date._isLeap(y) # y would be 0 if serialNumber is 0, _isLeap(0) is True
                                 # but m would be 0 in that case, so we'd return above.

        # For a non-null date, dayOfYear and _monthOffset(m, leap) will be valid.
        # dayOfMonth = dayOfYear_value - monthOffset_value (where monthOffset is days before current month)
        return self.dayOfYear() - Date._monthOffset(m, leap)
        
    fn weekday(self) -> Weekday:
        """Returns the weekday (Sunday=1, ..., Saturday=7)."""
        if self.serialNumber <= 0: # Catches null (0) and invalid negative serials
            # print("Warning: weekday() called on null or invalid Date")
            return 0 # Or raise error

        # _checkSerialNumber(self.serialNumber) 
        
        # Based on QL's logic: Jan 1, 1901 (serial 367) is Tuesday.
        # (367 - 1) % 7 = 366 % 7 = 2.
        # If Sunday=0, Monday=1, Tuesday=2, this is correct.
        # To map to Sunday=1, ..., Saturday=7, we add 1.
        var result_day_index = (self.serialNumber - 1) % 7 # 0 for Sunday-like, 1 for Monday-like, etc.
        return result_day_index + 1 # Adjusts to Sunday=1, Monday=2, ..., Saturday=7

    # --- Static Date Factory Methods ---

    @staticmethod
    fn minDate() -> Date:
        """Returns the earliest allowed date in QuantLib (Jan 1, 1901)."""
        return Date(367) # Serial for Jan 1, 1901

    @staticmethod
    fn maxDate() -> Date:
        """Returns the latest allowed date in QuantLib (Dec 31, 2199)."""
        return Date(109574) # Serial for Dec 31, 2199

    # --- Comparison Operators ---
    fn __eq__(self, other: Date) -> Bool:
        """Checks if two dates are equal."""
        return self.serialNumber == other.serialNumber

    fn __ne__(self, other: Date) -> Bool:
        """Checks if two dates are not equal."""
        return self.serialNumber != other.serialNumber

    fn __lt__(self, other: Date) -> Bool:
        """Checks if this date is less than another date."""
        return self.serialNumber < other.serialNumber

    fn __le__(self, other: Date) -> Bool:
        """Checks if this date is less than or equal to another date."""
        return self.serialNumber <= other.serialNumber

    fn __gt__(self, other: Date) -> Bool:
        """Checks if this date is greater than another date."""
        return self.serialNumber > other.serialNumber

    fn __ge__(self, other: Date) -> Bool:
        """Checks if this date is greater than or equal to another date."""
        return self.serialNumber >= other.serialNumber


    @staticmethod
    fn isLeap(y: Year) -> Bool:
         return Date._isLeap(y)

    # --- Date Arithmetic ---

    fn __add__(self, days: Int) -> Date:
        """Adds or subtracts a number of days to this date. Returns a new Date.
        To subtract days, pass a negative integer.
        E.g., date + 10 (add 10 days), date + (-5) (subtract 5 days)."""
        # TODO: Consider serial number range validation for the result
        return Date(self.serialNumber + days)

    # For D1 - D2 (duration in days)
    fn __sub__(self, other: Date) -> Int:
        """Calculates the number of days between this date and another date (self - other)."""
        return self.serialNumber - other.serialNumber

    fn __inc__(mut self) -> Date:
        """Pre-increment operator (++date). Modifies the date and returns it."""
        self.serialNumber += 1
        # TODO: Consider serial number range validation for the result
        return self

    fn __dec__(mut self) -> Date:
        """Pre-decrement operator (--date). Modifies the date and returns it."""
        self.serialNumber -= 1
        # TODO: Consider serial number range validation for the result
        return self

    # --- Utility Methods ---

    fn toString(self) -> String:
        """Returns a string representation of the date (e.g., "Tuesday, 26 July 2024").
           Returns "Null Date" if the serial number is 0."""
        if self.serialNumber == 0:
            return "Null Date"

        # Helper lists for names - consider making these static members or global if used elsewhere
        var weekday_names = List[String]("InvalidWeekday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
        var month_names = List[String](
            "InvalidMonth", "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        )

        var wd_val = self.weekday()
        var d_val = self.dayOfMonth()
        var m_val = self.month()
        var y_val = self.year()

        if wd_val < 1 or wd_val > 7 or m_val < 1 or m_val > 12:
            return "Invalid Date Components"

        # Using Python interop for string formatting for now, as Mojo's String capabilities are evolving.
        # from Python import Python
        # var py = Python.import_module("builtins")
        # return py.str("{weekday_name}, {day} {month_name} {year}").format(
        #     weekday_name=weekday_names[wd_val],
        #     day=d_val,
        #     month_name=month_names[m_val],
        #     year=y_val
        # ).to_string() # to_string might not be needed depending on PyObject to String conversion
        # Simpler approach for now without Python interop, using string concatenation:
        var s: String = weekday_names[wd_val]
        s += ", "
        s += String(d_val) # Assuming Int to String conversion exists
        s += " "
        s += month_names[m_val]
        s += " "
        s += String(y_val)
        return s

    # --- Static Date Utilities ---

    @staticmethod
    fn isEndOfMonth(date_to_check: Date) -> Bool:
        """Checks if the given date is the last day of its month."""
        if date_to_check.serialNumber == 0:
            return False # Or raise error for null date
        
        var d = date_to_check.dayOfMonth()
        var m = date_to_check.month()
        var y = date_to_check.year()

        if m == 0: # Should not happen if date is valid and not null
            return False

        return d == Date._monthLength(m, Date._isLeap(y))

    @staticmethod
    fn nextWeekday(current_date: Date, target_wd: Weekday) -> Date:
        """Finds the date of the next given weekday *after* the current_date.
           If current_date.weekday() == target_wd, QL returns current_date + 0 days."""
        if current_date.serialNumber == 0:
            # print("Warning: nextWeekday called with null current_date")
            return Date(0) # Return null date
        
        if target_wd < Sunday or target_wd > Saturday:
            # print("Error: nextWeekday called with invalid target_wd")
            return Date(0) # Return null date for invalid weekday

        var current_wd = current_date.weekday()
        if current_wd == 0: # Error from current_date.weekday()
            # print("Error: could not determine weekday of current_date in nextWeekday")
            return Date(0)
            
        var days_to_add = (target_wd - current_wd + 7) % 7
        # If target_wd == current_wd, (target_wd - current_wd + 7) % 7 results in 0.
        # QL returns the same date in this case (d + 0).
        # The old logic `if days_to_add == 0: days_to_add = 7` is removed.
        
        var new_serial = current_date.serialNumber + days_to_add
        # TODO: Validate new_serial against minDate/maxDate serials?
        return Date(new_serial)

    @staticmethod
    fn nthWeekday(n_orig: Int, target_wd_orig: Weekday, m: Month, y: Year) -> Date:
        """Calculates the date of the n-th occurrence of a given weekday in a specific month and year.
           (e.g., 3rd Friday in July 2024).
           n must be > 0. If n is too large (e.g. 5th Sunday in a month with only 4), 
           this function returns a null Date, as QL would raise an error.
           Observed QL behavior for specific inputs like (n=1, target_wd=8, m, y) needs careful matching."""
        # FIXME: The C++ test runner for date tests has a specific case for
        # nthWeekday(1, 8, July, 2024) which results in serial 45480 (July 26, 2024 - 4th Friday).
        # Our current Mojo logic correctly identifies weekday 8 as invalid and returns Date(0).
        # This discrepancy causes one test to fail. If this specific QL behavior for wd=8
        # is crucial for higher-level functions, the QL C++ source for this specific
        # test case or the underlying Date::nthWeekday logic for such inputs should be investigated further.
        # For now, we maintain the robust behavior of returning Date(0) for invalid weekday input.
        
        var n = n_orig
        var target_wd = target_wd_orig

        # Reverted specific hardcoding for (1,8,7,2024)
        # General validation for target_wd first
        if target_wd_orig < Sunday or target_wd_orig > Saturday:
            # print("Error: nthWeekday called with invalid target_wd_orig: ", target_wd_orig)
            return Date(0) 
        
        if n <= 0:
            # print("Error: n must be > 0 for nthWeekday")
            return Date(0) 

        # Month and Year validation
        if m < January or m > December:
            # print("Error: nthWeekday called with invalid month")
            return Date(0)
        if y < Date.minDate().year() or y > Date.maxDate().year():
            # print("Error: nthWeekday called with year out of QL range")
            return Date(0)

        var first_of_month = Date(1, m, y)
        if first_of_month.serialNumber == 0: 
            # print("Error: Could not construct 1st day of month in nthWeekday")
            return Date(0)

        var first_day_wd = first_of_month.weekday()
        if first_day_wd == 0: 
            # print("Error: Could not get weekday of 1st day of month")
            return Date(0)

        var day_offset_to_first_occurrence = (target_wd - first_day_wd + 7) % 7
        var day_of_month_for_first_occurrence = 1 + day_offset_to_first_occurrence
        var target_day_of_month = day_of_month_for_first_occurrence + (n - 1) * 7
        
        var month_len = Date._monthLength(m, Date._isLeap(y))
        if target_day_of_month > month_len:
            # print("Warning: Nth weekday does not exist in the month.")
            return Date(0) 
            
        return Date(target_day_of_month, m, y)

# --- Placeholder main for testing ---
fn main():
    from sys import argv, exit

    var args = argv()
    if len(args) < 2:
        print("Usage: mojo date.mojo <command> [params...]")
        print("Commands:")
        print("  inspect_dmy <d> <m> <y>")
        print("  inspect_serial <serial>")
        print("  toString_dmy <d> <m> <y>")
        print("  toString_serial <serial>")
        print("  isEndOfMonth_dmy <d> <m> <y>")
        print("  isEndOfMonth_serial <serial>")
        print("  nextWeekday_dmy <d> <m> <y> <target_wd_int>")
        print("  nextWeekday_serial <serial> <target_wd_int>")
        print("  nthWeekday <n_int> <wd_int> <m_int> <y_int>")
        exit(1)

    var command = args[1]
    var date_obj: Date

    try:
        if command == "inspect_dmy":
            if len(args) != 5: print("Usage: inspect_dmy <d> <m> <y>"); exit(1)
            var d_in = Int(args[2])
            var m_in = Int(args[3])
            var y_in = Int(args[4])
            date_obj = Date(d_in,m_in,y_in) # Constructor prints specific Mojo error and sets serial=0 if invalid
            
            if date_obj.serialNumber == 0:
                # Date constructor failed. Mimic QL error reporting.
                # Check original inputs to attempt a more specific QL-like error.
                var y_valid_check = (y_in >= 1901 and y_in <= 2199)
                var m_valid_check = (m_in >= 1 and m_in <= 12)
                if not y_valid_check:
                    print("QuantLib runtime error: year " + String(y_in) + " out of valid range [1901,2199]")
                elif not m_valid_check:
                    print("QuantLib runtime error: month " + String(m_in) + " out of valid range [1,12]")
                elif y_valid_check and m_valid_check: # If year/month ok, check day
                    var month_len_check = Date._monthLength(m_in, Date._isLeap(y_in))
                    if not (d_in >= 1 and d_in <= month_len_check):
                        print("QuantLib runtime error: day outside month (" + String(m_in) + ") day-range [1," + String(month_len_check) +"]")
                    else: # Should not happen if serial is 0 and y,m,d were in range
                        print("QuantLib runtime error: invalid date arguments") 
                else: # Should not be reached if above logic is complete
                    print("QuantLib runtime error: invalid date arguments")
                exit(1)

            print("SERIAL:" + String(date_obj.serial_number()))
            if date_obj.serialNumber != 0: # This check is redundant now due to exit above, but harmless
                print("YEAR:" + String(date_obj.year()))
                print("MONTH:" + String(date_obj.month()))
                print("DAY:" + String(date_obj.dayOfMonth()))
                print("WEEKDAY:" + String(date_obj.weekday()))
                print("DAYOFYEAR:" + String(date_obj.dayOfYear()))
            # elif d_in < 1 or d_in > Date._monthLength(m_in, Date._isLeap(y_in)) or m_in < 1 or m_in > 12 or y_in < 1901 or y_in > 2199 :
            #    pass # This logic is now handled by the exit(1) above

        elif command == "inspect_serial":
            if len(args) != 3: print("Usage: inspect_serial <serial>"); exit(1)
            var serial = Int(args[2])
            date_obj = Date(serial)
            print("SERIAL:" + String(date_obj.serial_number()))
            if serial != 0:
                 print("YEAR:" + String(date_obj.year()))
                 print("MONTH:" + String(date_obj.month()))
                 print("DAY:" + String(date_obj.dayOfMonth()))
                 print("WEEKDAY:" + String(date_obj.weekday()))
                 print("DAYOFYEAR:" + String(date_obj.dayOfYear()))

        elif command == "toString_dmy":
            if len(args) != 5: print("Usage: toString_dmy <d> <m> <y>"); exit(1)
            var d_in = Int(args[2])
            var m_in = Int(args[3])
            var y_in = Int(args[4])
            date_obj = Date(Int(args[2]), Int(args[3]), Int(args[4])) # Constructor prints specific Mojo error
            
            if date_obj.serialNumber == 0:
                var y_valid_check = (y_in >= 1901 and y_in <= 2199)
                var m_valid_check = (m_in >= 1 and m_in <= 12)
                if not y_valid_check:
                    print("QuantLib runtime error: year " + String(y_in) + " out of valid range [1901,2199]")
                elif not m_valid_check:
                    print("QuantLib runtime error: month " + String(m_in) + " out of valid range [1,12]")
                elif y_valid_check and m_valid_check: 
                    var month_len_check = Date._monthLength(m_in, Date._isLeap(y_in))
                    if not (d_in >= 1 and d_in <= month_len_check):
                        print("QuantLib runtime error: day outside month (" + String(m_in) + ") day-range [1," + String(month_len_check) +"]")
                    else: 
                        print("QuantLib runtime error: invalid date arguments")
                else: 
                    print("QuantLib runtime error: invalid date arguments")
                exit(1)
            print("STRING:" + date_obj.toString())

        elif command == "toString_serial":
            if len(args) != 3: print("Usage: toString_serial <serial>"); exit(1)
            date_obj = Date(Int(args[2]))
            print("STRING:" + date_obj.toString())

        elif command == "isEndOfMonth_dmy":
            if len(args) != 5: print("Usage: isEndOfMonth_dmy <d> <m> <y>"); exit(1)
            var d_in = Int(args[2])
            var m_in = Int(args[3])
            var y_in = Int(args[4])
            date_obj = Date(Int(args[2]), Int(args[3]), Int(args[4])) # Constructor prints specific Mojo error
            
            if date_obj.serialNumber == 0:
                var y_valid_check = (y_in >= 1901 and y_in <= 2199)
                var m_valid_check = (m_in >= 1 and m_in <= 12)
                if not y_valid_check:
                    print("QuantLib runtime error: year " + String(y_in) + " out of valid range [1901,2199]")
                elif not m_valid_check:
                    print("QuantLib runtime error: month " + String(m_in) + " out of valid range [1,12]")
                elif y_valid_check and m_valid_check: 
                    var month_len_check = Date._monthLength(m_in, Date._isLeap(y_in))
                    if not (d_in >= 1 and d_in <= month_len_check):
                        print("QuantLib runtime error: day outside month (" + String(m_in) + ") day-range [1," + String(month_len_check) +"]")
                    else: 
                        print("QuantLib runtime error: invalid date arguments")
                else: 
                    print("QuantLib runtime error: invalid date arguments")
                exit(1)
            
            # The C++ test for invalid DMY ISEOM also exits with error code 1 and prints the QL error.
            # Our date_obj.serialNumber == 0 check above handles this.
            # If serial is 0, it implies ISEOM is false for the purposes of the test.
            # The original test has "ISEOM:false" printed after the QL error for invalid DMY in Mojo.
            # QL would have exited. So if serialNumber is 0, we've exited.
            # The below `if` is for the case where serialNumber was non-zero from the start,
            # or the previous block didn't exit (which it should for invalid DMY).
            # For valid dates that are null (e.g. Date()), serial can be 0.
            # But Date(d,m,y) only makes serial 0 on bad d,m,y.
            
            # The logic from previous version:
            # if date_obj.serialNumber == 0: # Handle cases where d,m,y results in null date
            #      print("ISEOM:false")
            # else:
            #      print("ISEOM:" + Bool(Date.isEndOfMonth(date_obj)).__str__().lower() )
            # This needs to be conditional on *not* exiting due to invalid d,m,y
            print("ISEOM:" + Bool(Date.isEndOfMonth(date_obj)).__str__().lower())


        elif command == "isEndOfMonth_serial":
            if len(args) != 3: print("Usage: isEndOfMonth_serial <serial>"); exit(1)
            var serial = Int(args[2])
            date_obj = Date(serial)
            if serial == 0:
                 print("ISEOM:false")
            else:
                 print("ISEOM:" + Bool(Date.isEndOfMonth(date_obj)).__str__().lower() )

        elif command == "nextWeekday_dmy":
            if len(args) != 6: print("Usage: nextWeekday_dmy <d> <m> <y> <target_wd>"); exit(1)
            var d_in = Int(args[2])
            var m_in = Int(args[3])
            var y_in = Int(args[4])
            var target_wd = Int(args[5])
            date_obj = Date(d_in, m_in, y_in) # Constructor prints specific Mojo error
            
            if date_obj.serialNumber == 0: # If initial date is null from bad d,m,y
                var y_valid_check = (y_in >= 1901 and y_in <= 2199)
                var m_valid_check = (m_in >= 1 and m_in <= 12)
                if not y_valid_check:
                    print("QuantLib runtime error: year " + String(y_in) + " out of valid range [1901,2199]")
                elif not m_valid_check:
                    print("QuantLib runtime error: month " + String(m_in) + " out of valid range [1,12]")
                elif y_valid_check and m_valid_check: 
                    var month_len_check = Date._monthLength(m_in, Date._isLeap(y_in))
                    if not (d_in >= 1 and d_in <= month_len_check):
                        print("QuantLib runtime error: day outside month (" + String(m_in) + ") day-range [1," + String(month_len_check) +"]")
                    else: 
                        print("QuantLib runtime error: invalid date arguments")
                else: 
                    print("QuantLib runtime error: invalid date arguments")
                exit(1)
            
            var next_date = Date.nextWeekday(date_obj, target_wd)
            print("NEXTWEEKDAY_SERIAL:" + String(next_date.serial_number()))

        elif command == "nextWeekday_serial":
            if len(args) != 4: print("Usage: nextWeekday_serial <serial> <target_wd>"); exit(1)
            var serial = Int(args[2])
            date_obj = Date(serial)
            var target_wd = Int(args[3])
            if serial == 0:
                print("NEXTWEEKDAY_SERIAL:0")
            else:
                var next_date = Date.nextWeekday(date_obj, target_wd)
                print("NEXTWEEKDAY_SERIAL:" + String(next_date.serial_number()))

        elif command == "nthWeekday":
            if len(args) != 6: print("Usage: nthWeekday <n> <wd> <m> <y>"); exit(1)
            var n = Int(args[2])
            var wd = Int(args[3])
            var m = Int(args[4])
            var y = Int(args[5])
            var result_date = Date.nthWeekday(n, wd, m, y)
            print("NTHWEEKDAY_SERIAL:" + String(result_date.serial_number()))

        else:
            print(String("Unknown command: ") + command)
            exit(1)

    except e: # Basic error handling for Int conversion etc.
        print(String("Error during mojo execution: ") + e.__str__())
        # Potentially output a specific error code or message format for diffing
        exit(1) 