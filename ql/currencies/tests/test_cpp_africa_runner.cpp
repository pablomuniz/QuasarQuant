// C++ Runner to print QuantLib currency properties for African currencies
#include <ql/quantlib.hpp> // Main QL header
#include <ql/currencies/africa.hpp> // Africa currencies
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
    if (code == "AOA") currency = QuantLib::AOACurrency();
    else if (code == "BWP") currency = QuantLib::BWPCurrency();
    else if (code == "EGP") currency = QuantLib::EGPCurrency();
    else if (code == "ETB") currency = QuantLib::ETBCurrency();
    else if (code == "GHS") currency = QuantLib::GHSCurrency();
    else if (code == "KES") currency = QuantLib::KESCurrency();
    else if (code == "MAD") currency = QuantLib::MADCurrency();
    else if (code == "MUR") currency = QuantLib::MURCurrency();
    else if (code == "NGN") currency = QuantLib::NGNCurrency();
    else if (code == "TND") currency = QuantLib::TNDCurrency();
    else if (code == "UGX") currency = QuantLib::UGXCurrency();
    else if (code == "XOF") currency = QuantLib::XOFCurrency();
    else if (code == "ZAR") currency = QuantLib::ZARCurrency();
    else if (code == "ZMW") currency = QuantLib::ZMWCurrency();
    else {
        std::cerr << "Error: Unknown currency code '" << code << "' in C++ Africa runner." << std::endl;
        exit(1); // Exit with error code
    }

    // Debug print (optional, can be restricted or removed for less verbosity)
    // std::string raw_symbol = currency.symbol();
    // std::cerr << "DEBUG C++ for [" << code << "]: Direct symbol from QL: '" << raw_symbol << "' (length: " << raw_symbol.length() << ")" << std::endl;

    // Print properties in a fixed format for easy comparison
    std::cout << "Name: " << currency.name() << std::endl;
    std::cout << "Code: " << currency.code() << std::endl;
    std::cout << "NumericCode: " << currency.numericCode() << std::endl;
    std::cout << "Symbol: " << currency.symbol() << std::endl;
    std::cout << "FractionSymbol: " << currency.fractionSymbol() << std::endl;
    std::cout << "FractionsPerUnit: " << std::to_string(currency.fractionsPerUnit()) << std::endl;
    
    const QuantLib::Rounding& rounding = currency.rounding();
    std::cout << "RoundingType: " << roundingTypeToString(rounding.type()) << std::endl;
    std::cout << "RoundingPrecision: " << rounding.precision() << std::endl;
    std::cout << "RoundingDigit: " << rounding.roundingDigit() << std::endl;
}

int main(int argc, char* argv[]) {
    char* locale_set_name = std::setlocale(LC_ALL, "en_US.UTF-8");
    if (!locale_set_name) {
        std::cerr << "Warning: C-style std::setlocale(LC_ALL, \"en_US.UTF-8\") failed. Trying C.UTF-8." << std::endl;
        locale_set_name = std::setlocale(LC_ALL, "C.UTF-8");
        if (!locale_set_name) {
            std::cerr << "Warning: C-style std::setlocale(LC_ALL, \"C.UTF-8\") failed. Trying environment default." << std::endl;
            locale_set_name = std::setlocale(LC_ALL, "");
            if (!locale_set_name) {
                std::cerr << "Warning: C-style std::setlocale(LC_ALL, \"\") also failed." << std::endl;
            }
        }
    }
    if (locale_set_name) {
        // std::cerr << "DEBUG C++: Effective C-style locale set to: " << locale_set_name << std::endl;
    }

    try {
        std::locale::global(std::locale("en_US.UTF-8"));
        std::cout.imbue(std::locale("en_US.UTF-8"));
        std::cerr.imbue(std::locale("en_US.UTF-8"));
        // std::cerr << "DEBUG C++: C++ std::locale successfully set to en_US.UTF-8" << std::endl;
    } catch (const std::runtime_error&) {
        // std::cerr << "Warning: Could not set C++ std::locale to en_US.UTF-8: " << e_en_us.what() << ". Trying C.UTF-8." << std::endl;
        try {
            std::locale::global(std::locale("C.UTF-8"));
            std::cout.imbue(std::locale("C.UTF-8"));
            std::cerr.imbue(std::locale("C.UTF-8"));
            // std::cerr << "DEBUG C++: C++ std::locale successfully set to C.UTF-8" << std::endl;
        } catch (const std::runtime_error&) {
            // std::cerr << "Warning: Could not set C++ std::locale to C.UTF-8: " << e_c_utf8.what() << ". Trying environment default (\"\")." << std::endl;
            try {
                std::locale::global(std::locale("")); 
                std::cout.imbue(std::locale(""));
                std::cerr.imbue(std::locale(""));
                // std::cerr << "DEBUG C++: C++ std::locale successfully set to environment default (\"\"). Current C++ locale: " << std::cout.getloc().name() << std::endl;
            } catch (const std::runtime_error&) {
                // std::cerr << "Warning: Could not set C++ std::locale using environment default (\"\"): " << e_default.what() << std::endl;
            }
        }
    }
    
    // try {
    //     std::cerr << "DEBUG C++: Final std::cout locale name: " << std::cout.getloc().name() << std::endl;
    // } catch (const std::exception& e) {
    //     std::cerr << "DEBUG C++: Error getting final cout locale name: " << e.what() << std::endl;
    // }

    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <CurrencyCode>" << std::endl;
        return 1;
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
    return 0;
} 