#include <ql/math/randomnumbers/mt19937uniformrng.hpp>
#include <iostream>
#include <iomanip>
#include <string>
#include <cstdlib>

using namespace QuantLib;

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " <number_of_sequences>" << std::endl;
        return 1;
    }

    // Parse number of sequences
    int sequences = std::atoi(argv[1]);
    if (sequences <= 0) {
        std::cerr << "Error: number of sequences must be positive" << std::endl;
        return 1;
    }

    // Initialize MT19937 with a fixed seed for reproducibility
    MersenneTwisterUniformRng rng(42);

    // Set output precision to match Mojo's output
    std::cout << std::setprecision(15) << std::fixed;

    // Generate and print sequences
    for (int i = 0; i < sequences; ++i) {
        auto sample = rng.next();
        std::cout << "Sample " << i << " : " << sample.value << " weight: " << sample.weight << std::endl;
    }

    return 0;
} 