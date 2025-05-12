// C++ Runner to print QuantLib currency properties for comparison with Mojo
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
    // Add all currencies defined in africa.cpp/africa.mojo
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