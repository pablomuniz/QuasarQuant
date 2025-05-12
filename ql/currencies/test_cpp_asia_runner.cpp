// C++ Runner to print QuantLib currency properties for Asian currencies
#include <ql/quantlib.hpp> // Main QL header
#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>

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
    if (code == "BDT") currency = QuantLib::BDTCurrency();
    else if (code == "CNY") currency = QuantLib::CNYCurrency();
    else if (code == "HKD") currency = QuantLib::HKDCurrency();
    else if (code == "IDR") currency = QuantLib::IDRCurrency();
    else if (code == "ILS") currency = QuantLib::ILSCurrency();
    else if (code == "INR") currency = QuantLib::INRCurrency();
    else if (code == "IQD") currency = QuantLib::IQDCurrency();
    else if (code == "IRR") currency = QuantLib::IRRCurrency();
    else if (code == "JPY") currency = QuantLib::JPYCurrency();
    else if (code == "KRW") currency = QuantLib::KRWCurrency();
    else if (code == "KWD") currency = QuantLib::KWDCurrency();
    else if (code == "KZT") currency = QuantLib::KZTCurrency();
    else if (code == "MYR") currency = QuantLib::MYRCurrency();
    else if (code == "NPR") currency = QuantLib::NPRCurrency();
    else if (code == "PKR") currency = QuantLib::PKRCurrency();
    else if (code == "SAR") currency = QuantLib::SARCurrency();
    else if (code == "SGD") currency = QuantLib::SGDCurrency();
    else if (code == "THB") currency = QuantLib::THBCurrency();
    else if (code == "TWD") currency = QuantLib::TWDCurrency();
    else if (code == "VND") currency = QuantLib::VNDCurrency();
    else if (code == "QAR") currency = QuantLib::QARCurrency();
    else if (code == "BHD") currency = QuantLib::BHDCurrency();
    else if (code == "OMR") currency = QuantLib::OMRCurrency();
    else if (code == "JOD") currency = QuantLib::JODCurrency();
    else if (code == "AED") currency = QuantLib::AEDCurrency();
    else if (code == "PHP") currency = QuantLib::PHPCurrency();
    else if (code == "CNH") currency = QuantLib::CNHCurrency();
    else if (code == "LKR") currency = QuantLib::LKRCurrency();
    else {
        std::cerr << "Error: Unknown currency code '" << code << "' in C++ runner." << std::endl;
        exit(1); // Exit with error code
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