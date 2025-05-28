// C++ Runner to print QuantLib currency properties for European currencies
#include <ql/quantlib.hpp> // Main QL header
#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <locale> // Required for std::locale
#include <clocale> // Required for C-style setlocale

// Helper function to convert QuantLib::Rounding::Type to string
std::string roundingTypeToString(QuantLib::Rounding::Type type) {
    switch (type) {
        case QuantLib::Rounding::None:    return "None";
        case QuantLib::Rounding::Up:      return "Up";
        case QuantLib::Rounding::Down:    return "Down";
        case QuantLib::Rounding::Closest: return "Closest";
        case QuantLib::Rounding::Floor:   return "Floor";
        case QuantLib::Rounding::Ceiling: return "Ceiling";
        default:                    return "UnknownRoundingType";
    }
}

// Function to get currency and print properties
void printCurrencyProperties(const std::string& code) {
    QuantLib::Currency currency;

    // Map string code to QuantLib currency object
    if (code == "BGL") currency = QuantLib::BGLCurrency();

    
    else if (code == "BYR") currency = QuantLib::BYRCurrency();
    else if (code == "CHF") currency = QuantLib::CHFCurrency();
    else if (code == "CYP") currency = QuantLib::CYPCurrency();
    else if (code == "CZK") currency = QuantLib::CZKCurrency();
    else if (code == "DKK") currency = QuantLib::DKKCurrency();
    else if (code == "EEK") currency = QuantLib::EEKCurrency();
    else if (code == "EUR") currency = QuantLib::EURCurrency();
    else if (code == "GBP") currency = QuantLib::GBPCurrency();
    else if (code == "HUF") currency = QuantLib::HUFCurrency();
    else if (code == "ISK") currency = QuantLib::ISKCurrency();
    else if (code == "LTL") currency = QuantLib::LTLCurrency();
    else if (code == "LVL") currency = QuantLib::LVLCurrency();
    else if (code == "NOK") currency = QuantLib::NOKCurrency();
    else if (code == "PLN") currency = QuantLib::PLNCurrency();
    else if (code == "ROL") currency = QuantLib::ROLCurrency();
    else if (code == "RON") currency = QuantLib::RONCurrency();
    else if (code == "RUB") currency = QuantLib::RUBCurrency();
    else if (code == "SEK") currency = QuantLib::SEKCurrency();
    else if (code == "SIT") currency = QuantLib::SITCurrency();
    else if (code == "TRL") currency = QuantLib::TRLCurrency();
    else if (code == "TRY") currency = QuantLib::TRYCurrency();
    // Obsoleted by Euro
    else if (code == "ATS") currency = QuantLib::ATSCurrency();
    else if (code == "BEF") currency = QuantLib::BEFCurrency();
    else if (code == "DEM") currency = QuantLib::DEMCurrency();
    else if (code == "ESP") currency = QuantLib::ESPCurrency();
    else if (code == "FIM") currency = QuantLib::FIMCurrency();
    else if (code == "FRF") currency = QuantLib::FRFCurrency();
    else if (code == "GRD") currency = QuantLib::GRDCurrency();
    else if (code == "IEP") currency = QuantLib::IEPCurrency();
    else if (code == "ITL") currency = QuantLib::ITLCurrency();
    else if (code == "LUF") currency = QuantLib::LUFCurrency();
    else if (code == "MTL") currency = QuantLib::MTLCurrency();
    else if (code == "NLG") currency = QuantLib::NLGCurrency();
    else if (code == "PTE") currency = QuantLib::PTECurrency();
    else if (code == "SKK") currency = QuantLib::SKKCurrency();
    // Other European currencies
    else if (code == "UAH") currency = QuantLib::UAHCurrency();
    else if (code == "RSD") currency = QuantLib::RSDCurrency();
    else if (code == "HRK") currency = QuantLib::HRKCurrency();
    else if (code == "BGN") currency = QuantLib::BGNCurrency();
    else if (code == "GEL") currency = QuantLib::GELCurrency();
    else {
        std::cerr << "Error: Unknown currency code '" << code << "' in C++ runner." << std::endl;
        exit(1); // Exit with error code
    }

    // Debug print to stderr for specific currencies before normal output
    if (code == "EUR" || code == "RUB" || code == "UAH") {
        std::string raw_symbol = currency.symbol();
        std::cerr << "DEBUG C++ for [" << code << "]: Direct symbol from QL: '" << raw_symbol << "' (length: " << raw_symbol.length() << ")" << std::endl;
    }

    // Print properties in a fixed format for easy comparison
    std::cout << "Name: " << currency.name() << std::endl;
    std::cout << "Code: " << currency.code() << std::endl;
    std::cout << "NumericCode: " << currency.numericCode() << std::endl;
    std::cout << "Symbol: " << currency.symbol() << std::endl;
    std::cout << "FractionSymbol: " << currency.fractionSymbol() << std::endl;
    std::cout << "FractionsPerUnit: " << currency.fractionsPerUnit() << std::endl;
    
    // Print rounding details
    const QuantLib::Rounding& rounding = currency.rounding();
    std::cout << "RoundingType: " << roundingTypeToString(rounding.type()) << std::endl;
    std::cout << "RoundingPrecision: " << rounding.precision() << std::endl;
    std::cout << "RoundingDigit: " << rounding.roundingDigit() << std::endl;
}

int main(int argc, char* argv[]) {
    // Attempt to set a robust UTF-8 locale for the C++ program's environment.
    // Try C-style setlocale first for broad impact.
    char* locale_set = std::setlocale(LC_ALL, "en_US.UTF-8");

    // Then set C++ locale system.
    try {
        std::locale::global(std::locale("en_US.UTF-8")); 
        std::cout.imbue(std::locale("en_US.UTF-8")); 
        std::cerr.imbue(std::locale("en_US.UTF-8")); 
    } catch (const std::runtime_error& e) {
        std::cerr << "Warning: Could not set C++ std::locale to en_US.UTF-8: " << e.what() << std::endl;
        // As a fallback, try to imbue with the locale derived from C-style setlocale result if it was successful
        // Or with the system default "" if C-style also failed or returned null for en_US.UTF-8
        try {
            if (locale_set) { // If setlocale returned a non-null pointer (meaning it might have succeeded)
                 std::locale effective_locale(locale_set);
                 std::locale::global(effective_locale);
                 std::cout.imbue(effective_locale);
                 std::cerr.imbue(effective_locale);
            } else {
                 // If setlocale failed for en_US.UTF-8, try system default for C++.
                 std::locale::global(std::locale(""));
                 std::cout.imbue(std::locale(""));
                 std::cerr.imbue(std::locale(""));
            }
        } catch (const std::runtime_error& e2) {
            std::cerr << "Warning: Could not set C++ std::locale using fallback: " << e2.what() << std::endl;
        }
    }

    if (locale_set) {
        std::cerr << "DEBUG C++: C-style locale set to: " << locale_set << std::endl;
    } else {
        std::cerr << "Warning: C-style std::setlocale(LC_ALL, \"en_US.UTF-8\") failed." << std::endl;
    }
    try {
        std::cerr << "DEBUG C++: std::cout locale name: " << std::cout.getloc().name() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "DEBUG C++: Error getting cout locale name: " << e.what() << std::endl;
    }

    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <CurrencyCode>" << std::endl;
        return 1; // Return error
    }

    std::string currencyCode = argv[1];

    try {
        printCurrencyProperties(currencyCode);
    } catch (const std::exception& e) {
        std::cerr << "QuantLib Error: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Unknown error occurred." << std::endl;
        return 1;
    }

    return 0; // Success
} 