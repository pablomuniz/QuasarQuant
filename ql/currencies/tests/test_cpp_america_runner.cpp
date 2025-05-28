// C++ Runner to print QuantLib currency properties for American currencies
#include <ql/quantlib.hpp>         // Main QL header
#include <ql/currencies/america.hpp> // America currencies
#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <locale>  // Required for std::locale
#include <clocale> // Required for C-style setlocale

// Helper function to convert QuantLib::Rounding::Type to string
std::string roundingTypeToString(QuantLib::Rounding::Type type) {
    switch (type) {
    case QuantLib::Rounding::None: return "None";
    case QuantLib::Rounding::Up: return "Up";
    case QuantLib::Rounding::Down: return "Down";
    case QuantLib::Rounding::Closest: return "Closest";
    case QuantLib::Rounding::Floor: return "Floor";
    case QuantLib::Rounding::Ceiling: return "Ceiling";
    default: return "UnknownRoundingType";
    }
}

// Function to get currency and print properties
void printCurrencyProperties(const std::string &code) {
    QuantLib::Currency currency;

    // Map string code to QuantLib currency object
    if (code == "ARS") currency = QuantLib::ARSCurrency();
    else if (code == "BRL") currency = QuantLib::BRLCurrency();
    else if (code == "CAD") currency = QuantLib::CADCurrency();
    else if (code == "CLP") currency = QuantLib::CLPCurrency();
    else if (code == "COP") currency = QuantLib::COPCurrency();
    else if (code == "MXN") currency = QuantLib::MXNCurrency();
    else if (code == "PEN") currency = QuantLib::PENCurrency();
    else if (code == "PEI") currency = QuantLib::PEICurrency(); // User defined in QL, check definition
    else if (code == "PEH") currency = QuantLib::PEHCurrency(); // User defined in QL, check definition
    else if (code == "TTD") currency = QuantLib::TTDCurrency();
    else if (code == "USD") currency = QuantLib::USDCurrency();
    else if (code == "VEB") currency = QuantLib::VEBCurrency();
    else if (code == "MXV") currency = QuantLib::MXVCurrency();
    else if (code == "COU") currency = QuantLib::COUCurrency();
    else if (code == "CLF") currency = QuantLib::CLFCurrency();
    else if (code == "UYU") currency = QuantLib::UYUCurrency();
    else {
        std::cerr << "Error: Unknown currency code '" << code << "' in C++ America runner." << std::endl;
        exit(1); // Exit with error code
    }

    std::cout << "Name: " << currency.name() << std::endl;
    std::cout << "Code: " << currency.code() << std::endl;
    std::cout << "NumericCode: " << currency.numericCode() << std::endl;
    std::cout << "Symbol: " << currency.symbol() << std::endl;
    std::cout << "FractionSymbol: " << currency.fractionSymbol() << std::endl;
    std::cout << "FractionsPerUnit: " << std::to_string(currency.fractionsPerUnit()) << std::endl;

    const QuantLib::Rounding &rounding = currency.rounding();
    std::cout << "RoundingType: " << roundingTypeToString(rounding.type()) << std::endl;
    std::cout << "RoundingPrecision: " << rounding.precision() << std::endl;
    std::cout << "RoundingDigit: " << rounding.roundingDigit() << std::endl;
}

int main(int argc, char *argv[]) {
    char *locale_set_name = std::setlocale(LC_ALL, "en_US.UTF-8");
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

    try {
        std::locale::global(std::locale("en_US.UTF-8"));
        std::cout.imbue(std::locale("en_US.UTF-8"));
        std::cerr.imbue(std::locale("en_US.UTF-8"));
    } catch (const std::runtime_error &) {
        try {
            std::locale::global(std::locale("C.UTF-8"));
            std::cout.imbue(std::locale("C.UTF-8"));
            std::cerr.imbue(std::locale("C.UTF-8"));
        } catch (const std::runtime_error &) {
            try {
                std::locale::global(std::locale(""));
                std::cout.imbue(std::locale(""));
                std::cerr.imbue(std::locale(""));
            } catch (const std::runtime_error &) {
                // If all locale settings fail, proceed with default C locale
            }
        }
    }

    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <CurrencyCode>" << std::endl;
        return 1;
    }
    std::string currencyCode = argv[1];
    try {
        printCurrencyProperties(currencyCode);
    } catch (const std::exception &e) {
        std::cerr << "QuantLib Error: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Unknown error occurred." << std::endl;
        return 1;
    }
    return 0;
} 