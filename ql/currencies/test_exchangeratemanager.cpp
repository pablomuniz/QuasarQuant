#include <ql/currencies/exchangeratemanager.hpp>
#include <ql/currencies/europe.hpp>
#include <ql/currencies/america.hpp>
#include <ql/currencies/asia.hpp>
#include <ql/currencies/oceania.hpp>
#include <iostream>
#include <iomanip>
#include <fstream>

using namespace QuantLib;

void print_test_header(const std::string& test_name, const Currency& source, const Currency& target, double rate = -1.0) {
    std::cout << "\n" << test_name << std::endl;
    std::cout << "--------------------------------" << std::endl;
    std::cout << "Input:" << std::endl;
    std::cout << "  Source Currency: " << source.code() << std::endl;
    std::cout << "  Target Currency: " << target.code() << std::endl;
    if (rate > 0) {
        std::cout << "  Rate to add: " << rate << std::endl;
    }
}

void print_result(const ExchangeRate& rate, const Date& date) {
    std::cout << "\nResults:" << std::endl;
    std::cout << "  C++ output: ";
    std::cout << rate.source().code() << "/" << rate.target().code() 
              << " = " << std::fixed << std::setprecision(6) << rate.rate() << std::endl;
    std::cout << "--------------------------------" << std::endl;
}

int main() {
    try {
        // Get the singleton instance
        ExchangeRateManager& manager = ExchangeRateManager::instance();
        
        // Clear any existing rates to start fresh
        manager.clear();
        
        // Test date
        Date test_date(1, January, 2024);
        
        // Test 1: Direct lookup (EUR/USD)
        print_test_header("Test 1: Direct lookup", EURCurrency(), USDCurrency(), 1.0850);
        manager.add(ExchangeRate(EURCurrency(), USDCurrency(), 1.0850),
                   Date(1, January, 2024), Date(31, December, 2024));
        auto rate1 = manager.lookup(EURCurrency(), USDCurrency(), test_date);
        print_result(rate1, test_date);
        
        // Test 2: Inverse lookup (USD/EUR)
        print_test_header("Test 2: Inverse lookup", USDCurrency(), EURCurrency());
        auto rate2 = manager.lookup(USDCurrency(), EURCurrency(), test_date);
        print_result(rate2, test_date);
        
        // Test 3: Triangulation (EUR -> USD -> JPY)
        print_test_header("Test 3: Triangulation", EURCurrency(), JPYCurrency(), 148.50);
        manager.add(ExchangeRate(USDCurrency(), JPYCurrency(), 148.50),
                   Date(1, January, 2024), Date(31, December, 2024));
        auto rate3 = manager.lookup(EURCurrency(), JPYCurrency(), test_date);
        print_result(rate3, test_date);
        
        // Test 4: Smart lookup with multiple paths
        print_test_header("Test 4: Smart lookup with multiple paths", EURCurrency(), JPYCurrency());
        manager.add(ExchangeRate(EURCurrency(), GBPCurrency(), 0.8550),
                   Date(1, January, 2024), Date(31, December, 2024));
        manager.add(ExchangeRate(GBPCurrency(), JPYCurrency(), 173.50),
                   Date(1, January, 2024), Date(31, December, 2024));
        auto rate4 = manager.lookup(EURCurrency(), JPYCurrency(), test_date);
        print_result(rate4, test_date);
        
        // Test 5: Obsoleted currency conversion (EUR -> DEM)
        print_test_header("Test 5: Obsoleted currency conversion", EURCurrency(), DEMCurrency());
        auto rate5 = manager.lookup(EURCurrency(), DEMCurrency(), test_date);
        print_result(rate5, test_date);
        
        // Test 6: Clear and reinitialize
        print_test_header("Test 6: Clear and reinitialize", EURCurrency(), DEMCurrency());
        manager.clear();
        auto rate6 = manager.lookup(EURCurrency(), DEMCurrency(), test_date);
        print_result(rate6, test_date);
        
        // Test 7: Invalid date
        print_test_header("Test 7: Invalid date", EURCurrency(), DEMCurrency());
        Date invalid_date(1, January, 1998);  // Before Euro introduction
        try {
            auto rate7 = manager.lookup(EURCurrency(), DEMCurrency(), invalid_date);
            print_result(rate7, invalid_date);
        } catch (const std::exception& e) {
            std::cout << "\nResults:" << std::endl;
            std::cout << "  C++ output: No rate available (Error: " << e.what() << ")" << std::endl;
            std::cout << "--------------------------------" << std::endl;
        }
        
        // Test 8: Non-existent rate
        print_test_header("Test 8: Non-existent rate", EURCurrency(), AUDCurrency());
        try {
            auto rate8 = manager.lookup(EURCurrency(), AUDCurrency(), test_date);
            print_result(rate8, test_date);
        } catch (const std::exception& e) {
            std::cout << "\nResults:" << std::endl;
            std::cout << "  C++ output: No rate available (Error: " << e.what() << ")" << std::endl;
            std::cout << "--------------------------------" << std::endl;
        }
        
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
} 