#include <ql/currencies/exchangeratemanager.hpp>
#include <ql/currencies/europe.hpp>
#include <ql/currencies/america.hpp>
#include <ql/currencies/asia.hpp>
#include <ql/currencies/oceania.hpp>
// Add other regional currency headers if needed for specific tests, e.g. Africa, Crypto
#include <ql/time/date.hpp>
#include <ql/settings.hpp> // Required for evaluationDate
#include <iostream>
#include <string>
#include <vector>
#include <iomanip> // For std::fixed and std::setprecision

// Helper function to get QuantLib::Currency object from its code
// This needs to be updated if more currencies are used in tests.
QuantLib::Currency get_currency_by_code(const std::string& code) {
    if (code == "EUR") return QuantLib::EURCurrency();
    if (code == "DEM") return QuantLib::DEMCurrency();
    if (code == "USD") return QuantLib::USDCurrency();
    if (code == "GBP") return QuantLib::GBPCurrency();
    if (code == "JPY") return QuantLib::JPYCurrency();
    if (code == "CAD") return QuantLib::CADCurrency();
    if (code == "CHF") return QuantLib::CHFCurrency();
    if (code == "AUD") return QuantLib::AUDCurrency();
    // For addKnownRates
    if (code == "ATS") return QuantLib::ATSCurrency();
    if (code == "BEF") return QuantLib::BEFCurrency();
    if (code == "ESP") return QuantLib::ESPCurrency();
    if (code == "FIM") return QuantLib::FIMCurrency();
    if (code == "FRF") return QuantLib::FRFCurrency();
    if (code == "GRD") return QuantLib::GRDCurrency();
    if (code == "IEP") return QuantLib::IEPCurrency();
    if (code == "ITL") return QuantLib::ITLCurrency();
    if (code == "LUF") return QuantLib::LUFCurrency();
    if (code == "NLG") return QuantLib::NLGCurrency();
    if (code == "PTE") return QuantLib::PTECurrency();
    if (code == "TRY") return QuantLib::TRYCurrency();
    if (code == "TRL") return QuantLib::TRLCurrency();
    if (code == "RON") return QuantLib::RONCurrency();
    if (code == "ROL") return QuantLib::ROLCurrency();
    if (code == "PEN") return QuantLib::PENCurrency();
    // PEI and PEH are not standard QL currencies, used in example but might not be defined in ql/currencies
    // For now, we'll throw an error if they are requested by the test script directly.
    // The ExchangeRateManager::addKnownRates handles their specific rates internally if defined.

    // Fallback for any other codes - QL_FAIL would be better but complicates runner
    std::cerr << "Error: Unknown currency code in C++ runner: " << code << std::endl;
    throw std::runtime_error("Unknown currency code: " + code);
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <command> [args...]" << std::endl;
        std::cerr << "Commands:" << std::endl;
        std::cerr << "  inspect_known_rate <SOURCE_CODE> <TARGET_CODE> <d> <m> <y>" << std::endl;
        // Add more commands later, e.g., add_custom_rate, direct_lookup, smart_lookup
        return 1;
    }

    std::string command = argv[1];
    QuantLib::ExchangeRateManager& erm = QuantLib::ExchangeRateManager::instance();
    // erm.clear(); // Clear to ensure a fresh state with only known rates if desired for some tests
                 // but QL ERM is a singleton, addKnownRates is called on first construction.
                 // Subsequent calls to instance() return the same object.
                 // Forcing `addKnownRates` can be done via `clear()` which calls it.
                 // Let's call clear() to ensure we are testing the rates added by addKnownRates.
    erm.clear();


    std::cout << std::fixed << std::setprecision(10); // Consistent float output

    try {
        if (command == "inspect_known_rate") {
            if (argc != 7) {
                std::cerr << "Usage: inspect_known_rate <SOURCE_CODE> <TARGET_CODE> <d> <m> <y>" << std::endl;
                return 1;
            }
            std::string source_code_str = argv[2];
            std::string target_code_str = argv[3];
            QuantLib::Day d = std::stoi(argv[4]);
            QuantLib::Month m = static_cast<QuantLib::Month>(std::stoi(argv[5]));
            QuantLib::Year y = std::stoi(argv[6]);
            QuantLib::Date date(d, m, y);

            QuantLib::Currency source_ccy = get_currency_by_code(source_code_str);
            QuantLib::Currency target_ccy = get_currency_by_code(target_code_str);
            
            // Set evaluation date for lookups that might rely on it, though explicit date is better
            QuantLib::Settings::instance().evaluationDate() = date;

            QuantLib::ExchangeRate rate = erm.lookup(source_ccy, target_ccy, date);

            std::cout << "RATE_VALUE:" << rate.rate() << std::endl;
            std::cout << "RATE_SOURCE:" << rate.source().code() << std::endl;
            std::cout << "RATE_TARGET:" << rate.target().code() << std::endl;
            // QL ExchangeRate::Type is an enum {Direct, Derived}
            std::cout << "RATE_TYPE:" << (rate.type() == QuantLib::ExchangeRate::Type::Direct ? "Direct" : "Derived") << std::endl;

        } else {
            std::cerr << "Unknown command: " << command << std::endl;
            return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "QuantLib runtime error: " << e.what() << std::endl;
        return 1; // Exit with error
    } catch (...) {
        std::cerr << "Unknown QuantLib error" << std::endl;
        return 1; // Exit with error
    }

    return 0;
} 