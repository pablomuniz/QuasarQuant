#include <ql/quantlib.hpp>
#include <iostream>
#include <vector>
#include <string>
#include <iomanip> // For std::setprecision if needed for rate printing

// Include specific currency headers
#include <ql/currencies/europe.hpp>
#include <ql/currencies/america.hpp>
#include <ql/currencies/oceania.hpp>
#include <ql/currencies/asia.hpp>
// Add more regional currency headers if needed

// Helper to map integer month to QuantLib::Month
QuantLib::Month intToQlMonth(int m) {
    if (m >= 1 && m <= 12) {
        return static_cast<QuantLib::Month>(m);
    }
    // Should be caught by Date constructor validation, but as a fallback:
    throw std::runtime_error("Invalid month integer for QuantLib::Month conversion");
}

// Helper function to get QuantLib::Currency from code
QuantLib::Currency getQlCurrencyFromCode(const std::string& code) {
    if (code == "EUR") return QuantLib::EURCurrency();
    if (code == "ATS") return QuantLib::ATSCurrency();
    if (code == "BEF") return QuantLib::BEFCurrency();
    if (code == "DEM") return QuantLib::DEMCurrency();
    if (code == "ESP") return QuantLib::ESPCurrency();
    if (code == "FIM") return QuantLib::FIMCurrency();
    if (code == "FRF") return QuantLib::FRFCurrency();
    if (code == "GRD") return QuantLib::GRDCurrency();
    if (code == "IEP") return QuantLib::IEPCurrency();
    if (code == "ITL") return QuantLib::ITLCurrency();
    if (code == "LUF") return QuantLib::LUFCurrency();
    if (code == "NLG") return QuantLib::NLGCurrency();
    if (code == "PTE") return QuantLib::PTECurrency(); // Corrected from PTOCurrency for QL C++
    if (code == "USD") return QuantLib::USDCurrency();
    if (code == "AUD") return QuantLib::AUDCurrency();
    if (code == "JPY") return QuantLib::JPYCurrency();
    // Add more currencies as needed
    
    // Fallback for unknown currency code
    throw std::runtime_error("Unknown currency code in getQlCurrencyFromCode: " + code);
}

int main(int argc, char* argv[]) {
    if (argc != 7) {
        std::cout << "STATUS:Error" << std::endl;
        std::cout << "MESSAGE:Invalid arguments. Usage: <program> <src_code> <tgt_code> <day> <month> <year> <type (Direct|Derived)>" << std::endl;
        return 1;
    }

    std::string source_code = argv[1];
    std::string target_code = argv[2];
    int day, month_int, year;
    std::string lookup_type_str = argv[6];

    try {
        day = std::stoi(argv[3]);
        month_int = std::stoi(argv[4]);
        year = std::stoi(argv[5]);
    } catch (const std::exception& e) {
        std::cout << "STATUS:Error" << std::endl;
        std::cout << "MESSAGE:Invalid date components. Day, month, and year must be integers." << std::endl;
        return 1;
    }

    QuantLib::ExchangeRate::Type lookup_type;
    if (lookup_type_str == "Direct") {
        lookup_type = QuantLib::ExchangeRate::Direct;
    } else if (lookup_type_str == "Derived") {
        lookup_type = QuantLib::ExchangeRate::Derived;
    } else {
        std::cout << "STATUS:Error" << std::endl;
        std::cout << "MESSAGE:Invalid lookup type. Must be 'Direct' or 'Derived'." << std::endl;
        return 1;
    }

    try {
        QuantLib::Currency source_currency = getQlCurrencyFromCode(source_code);
        QuantLib::Currency target_currency = getQlCurrencyFromCode(target_code);
        
        // QuantLib::Date constructor validates date components
        QuantLib::Date lookup_date(day, intToQlMonth(month_int), year);

        QuantLib::ExchangeRateManager& manager = QuantLib::ExchangeRateManager::instance();
        // For C++, we typically use the singleton instance and can clear it for isolated testing if needed,
        // or add rates directly to it.
        // Note: The QuantLib manager is a singleton and populates with known rates by default.
        // If we need a clean manager for each run like in Mojo tests, we might need to manage its state carefully
        // or not use the singleton for runner tests, but the Python test script will manage adding specific rates.

        QuantLib::ExchangeRate rate_obj = manager.lookup(source_currency, target_currency, lookup_date, lookup_type);

        // If lookup succeeds, QuantLib::ExchangeRate contains the rate correctly oriented.
        // We need to get the effective source and target of this specific rate object if it differs from requested.
        // However, QuantLib's lookup is expected to return a rate for source_currency -> target_currency directly.

        std::cout << "STATUS:Success" << std::endl;
        std::cout << "SOURCE:" << rate_obj.source().code() << std::endl;
        std::cout << "TARGET:" << rate_obj.target().code() << std::endl;
        // Ensure consistent floating point output format if necessary
        std::cout << "RATE:" << std::fixed << std::setprecision(15) << rate_obj.rate() << std::endl;
        
        // For ExchangeRateManager::lookup, the C++ version doesn't easily expose the specific start/end date 
        // of the particular rate *segment* that satisfied the lookup if it was chained or came from smart lookup.
        // The returned ExchangeRate object from lookup() is for S->T and doesn't retain sub-component dates.
        // It implies validity on the lookup_date.
        // For consistency with current Mojo output which *does* provide specific start/end dates of the found rate,
        // we will print QuantLib::Date::minDate() and QuantLib::Date::maxDate() here.
        // This is a known difference to be aware of if precise date matching is critical for chained rates.
        // The Python test script will likely focus on rate value and S/T codes.
        QuantLib::Date effective_start_date = QuantLib::Date::minDate(); 
        QuantLib::Date effective_end_date = QuantLib::Date::maxDate();

        std::cout << "START_DAY:" << effective_start_date.dayOfMonth() << std::endl;
        std::cout << "START_MONTH:" << static_cast<int>(effective_start_date.month()) << std::endl;
        std::cout << "START_YEAR:" << effective_start_date.year() << std::endl;
        std::cout << "END_DAY:" << effective_end_date.dayOfMonth() << std::endl;
        std::cout << "END_MONTH:" << static_cast<int>(effective_end_date.month()) << std::endl;
        std::cout << "END_YEAR:" << effective_end_date.year() << std::endl;

    } catch (const QuantLib::Error& e) {
        // QuantLib typically throws an error if the rate is not found.
        std::cout << "STATUS:NotFound" << std::endl;
        std::cout << "MESSAGE:No rate found for " << source_code << " to " << target_code << " on " 
                  << year << "-" << month_int << "-" << day << " (QL Error: " << e.what() << ")" << std::endl;
        return 0; // Return 0 for NotFound to allow output comparison, error signaled by STATUS
    } catch (const std::exception& e) {
        std::cout << "STATUS:Error" << std::endl;
        std::cout << "MESSAGE:An unexpected error occurred: " << e.what() << std::endl;
        return 1;
    }

    return 0;
} 