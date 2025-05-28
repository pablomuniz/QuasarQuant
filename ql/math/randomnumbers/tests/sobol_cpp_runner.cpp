#include <ql/quantlib.hpp>
#include <iostream>
#include <iomanip>
#include <cstdlib>

using namespace QuantLib;

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <dimensions> <sequences>" << std::endl;
        return 1;
    }
    
    int dimensions = std::atoi(argv[1]);
    int sequences = std::atoi(argv[2]);
    
    if (dimensions <= 0 || sequences <= 0) {
        std::cerr << "Dimensions and sequences must be positive integers" << std::endl;
        return 1;
    }
    
    // Set high precision output to match exactly
    std::cout << std::fixed << std::setprecision(15);
    
    try {
        // Create Sobol generator with Jaeckel direction integers (same as our Mojo default)
        SobolRsg sobol(dimensions, 0, SobolRsg::Jaeckel);
        
        for (int i = 0; i < sequences; i++) {
            auto sample = sobol.nextSequence();
            std::cout << "Sample " << i << " :";
            for (int j = 0; j < dimensions; j++) {
                std::cout << " " << sample.value[j];
            }
            std::cout << " weight: " << sample.weight << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
} 