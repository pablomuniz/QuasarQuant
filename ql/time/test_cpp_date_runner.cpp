#include <ql/quantlib.hpp>
#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip> // For std::boolalpha
#include <stdexcept> // For std::stoi, std::stoll

// Helper to format date for toString, aiming to match Mojo\'s output
std::string qlDateToString(const QuantLib::Date& d) {
    if (d == QuantLib::Date()) {
        return "Null Date";
    }
    
    std::string weekday_names[] = {"Invalid", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"};
    std::string month_names[] = {"Invalid", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"};

    std::ostringstream oss;
    oss << weekday_names[d.weekday()] << ", " << d.dayOfMonth() << " " << month_names[d.month()] << " " << d.year();
    return oss.str();
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: test_cpp_date_runner <command> [args...]" << std::endl;
        std::cerr << "Commands:" << std::endl;
        std::cerr << "  inspect_dmy <d> <m> <y>" << std::endl;
        std::cerr << "  inspect_serial <serial>" << std::endl;
        std::cerr << "  toString_dmy <d> <m> <y>" << std::endl;
        std::cerr << "  toString_serial <serial>" << std::endl;
        std::cerr << "  isEndOfMonth_dmy <d> <m> <y>" << std::endl;
        std::cerr << "  isEndOfMonth_serial <serial>" << std::endl;
        std::cerr << "  nextWeekday_dmy <d> <m> <y> <target_wd_int>" << std::endl;
        std::cerr << "  nextWeekday_serial <serial> <target_wd_int>" << std::endl;
        std::cerr << "  nthWeekday <n_int> <wd_int> <m_int> <y_int>" << std::endl;
        return 1;
    }

    std::string command = argv[1];
    QuantLib::Date date;

    try {
        if (command == "inspect_dmy" && argc == 5) {
            date = QuantLib::Date(std::stoi(argv[2]), static_cast<QuantLib::Month>(std::stoi(argv[3])), std::stoi(argv[4]));
            std::cout << "SERIAL:" << date.serialNumber() << std::endl;
            std::cout << "YEAR:" << date.year() << std::endl;
            std::cout << "MONTH:" << static_cast<int>(date.month()) << std::endl;
            std::cout << "DAY:" << date.dayOfMonth() << std::endl;
            std::cout << "WEEKDAY:" << static_cast<int>(date.weekday()) << std::endl;
            std::cout << "DAYOFYEAR:" << date.dayOfYear() << std::endl;
        } else if (command == "inspect_serial" && argc == 3) {
            QuantLib::BigInteger serial = std::stoll(argv[2]);
            date = (serial == 0) ? QuantLib::Date() : QuantLib::Date(serial);
            std::cout << "SERIAL:" << date.serialNumber() << std::endl;
            if (serial != 0) {
                 std::cout << "YEAR:" << date.year() << std::endl;
                 std::cout << "MONTH:" << static_cast<int>(date.month()) << std::endl;
                 std::cout << "DAY:" << date.dayOfMonth() << std::endl;
                 std::cout << "WEEKDAY:" << static_cast<int>(date.weekday()) << std::endl;
                 std::cout << "DAYOFYEAR:" << date.dayOfYear() << std::endl;
            }
        } else if (command == "toString_dmy" && argc == 5) {
            date = QuantLib::Date(std::stoi(argv[2]), static_cast<QuantLib::Month>(std::stoi(argv[3])), std::stoi(argv[4]));
            std::cout << "STRING:" << qlDateToString(date) << std::endl;
        } else if (command == "toString_serial" && argc == 3) {
            QuantLib::BigInteger serial = std::stoll(argv[2]);
            date = (serial == 0) ? QuantLib::Date() : QuantLib::Date(serial);
            std::cout << "STRING:" << qlDateToString(date) << std::endl;
        } else if (command == "isEndOfMonth_dmy" && argc == 5) {
            date = QuantLib::Date(std::stoi(argv[2]), static_cast<QuantLib::Month>(std::stoi(argv[3])), std::stoi(argv[4]));
            std::cout << "ISEOM:" << std::boolalpha << QuantLib::Date::isEndOfMonth(date) << std::endl;
        } else if (command == "isEndOfMonth_serial" && argc == 3) {
            QuantLib::BigInteger serial = std::stoll(argv[2]);
            if (serial == 0) { // QL would throw for isEndOfMonth on a null date
                 std::cout << "ISEOM:false" << std::endl; // Match Mojo behavior
            } else {
                date = QuantLib::Date(serial);
                std::cout << "ISEOM:" << std::boolalpha << QuantLib::Date::isEndOfMonth(date) << std::endl;
            }
        } else if (command == "nextWeekday_dmy" && argc == 6) {
            date = QuantLib::Date(std::stoi(argv[2]), static_cast<QuantLib::Month>(std::stoi(argv[3])), std::stoi(argv[4]));
            QuantLib::Weekday target_wd = static_cast<QuantLib::Weekday>(std::stoi(argv[5]));
            QuantLib::Date next_date = QuantLib::Date::nextWeekday(date, target_wd);
            std::cout << "NEXTWEEKDAY_SERIAL:" << next_date.serialNumber() << std::endl;
        } else if (command == "nextWeekday_serial" && argc == 4) {
            QuantLib::BigInteger serial = std::stoll(argv[2]);
            QuantLib::Weekday target_wd = static_cast<QuantLib::Weekday>(std::stoi(argv[3]));
            if (serial == 0) { // QL would throw
                 std::cout << "NEXTWEEKDAY_SERIAL:0" << std::endl; // Match Mojo
            } else {
                date = QuantLib::Date(serial);
                QuantLib::Date next_date = QuantLib::Date::nextWeekday(date, target_wd);
                std::cout << "NEXTWEEKDAY_SERIAL:" << next_date.serialNumber() << std::endl;
            }
        } else if (command == "nthWeekday" && argc == 6) {
            QuantLib::Size n = std::stoul(argv[2]); // QL uses Size for n
            QuantLib::Weekday wd = static_cast<QuantLib::Weekday>(std::stoi(argv[3]));
            QuantLib::Month m = static_cast<QuantLib::Month>(std::stoi(argv[4]));
            QuantLib::Year y = std::stoi(argv[5]);
            try {
                QuantLib::Date result_date = QuantLib::Date::nthWeekday(n, wd, m, y);
                std::cout << "NTHWEEKDAY_SERIAL:" << result_date.serialNumber() << std::endl;
            } catch (const QuantLib::Error&) { // QL throws if date doesn\'t exist
                std::cout << "NTHWEEKDAY_SERIAL:0" << std::endl; // Match Mojo null date
            }
        } else {
            std::cerr << "Unknown command or incorrect arguments for: " << (argc > 1 ? argv[1] : "N/A") << std::endl;
            return 1;
        }
    } catch (const QuantLib::Error& e) { // Catch QL specific errors for unexpected cases
        std::cerr << "QuantLib runtime error: " << e.what() << std::endl;
        // Output a "0" or specific error marker if needed to help diffing, e.g. for an operation that should have produced a serial
        // std::cout << "ERROR_SERIAL:0" << std::endl; 
        return 1;
    } catch (const std::exception& e) { // Catch standard exceptions like std::invalid_argument from stoi
        std::cerr << "Standard C++ error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
} 