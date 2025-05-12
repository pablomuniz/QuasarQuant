#include <ql/math/rounding.hpp>
#include <ql/types.hpp> // For QuantLib::Decimal
#include <iostream>
#include <string>
#include <vector>
#include <iomanip> // For std::fixed and std::setprecision
#include <stdexcept> // For std::invalid_argument, std::stod, std::stoi

// Helper function to convert string to QuantLib::Rounding::Type
QuantLib::Rounding::Type stringToRoundingType(const std::string& s) {
    if (s == "None") return QuantLib::Rounding::Type::None;
    if (s == "Up") return QuantLib::Rounding::Type::Up;
    if (s == "Down") return QuantLib::Rounding::Type::Down;
    if (s == "Closest") return QuantLib::Rounding::Type::Closest;
    if (s == "Floor") return QuantLib::Rounding::Type::Floor;
    if (s == "Ceiling") return QuantLib::Rounding::Type::Ceiling;
    throw std::invalid_argument("Invalid rounding type string: " + s);
}

int main(int argc, char* argv[]) {
    if (argc != 5) {
        std::cerr << "Usage: " << argv[0] << " <RoundingType> <precision> <digit> <value>" << std::endl;
        std::cerr << "RoundingType: None, Up, Down, Closest, Floor, Ceiling" << std::endl;
        return 1;
    }

    try {
        std::string typeStr = argv[1];
        int precision = std::stoi(argv[2]);
        int digit = std::stoi(argv[3]);
        QuantLib::Decimal value = std::stod(argv[4]);

        QuantLib::Rounding::Type roundingType = stringToRoundingType(typeStr);
        QuantLib::Rounding qlRounding(precision, roundingType, digit);
        
        // The C++ Rounding constructor signature is:
        // Rounding(Integer precision, Type type = Type::Closest, Integer digit = 5);
        // So we need to create it slightly differently if we want to match how it's often used.
        // Let's re-create it based on how the type is usually primary.
        QuantLib::Rounding ql_rounding_instance; // Default
        if (typeStr == "None") {
            ql_rounding_instance = QuantLib::Rounding(precision, QuantLib::Rounding::None, digit);
        } else {
            // For specific types, the QL constructor often takes precision first, then type, then digit.
            // Or use the default constructor and set members if public, or use a more fitting constructor.
            // The primary QL Rounding constructor is (precision, type, digit)
            ql_rounding_instance = QuantLib::Rounding(precision, roundingType, digit);
        }


        QuantLib::Decimal result = ql_rounding_instance(value);

        std::cout << std::fixed << std::setprecision(15) << result << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
} 