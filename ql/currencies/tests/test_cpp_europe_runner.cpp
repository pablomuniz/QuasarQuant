// C++ Runner to print QuantLib currency properties for European currencies
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