#include "AIProvider.h"
#include <iostream>
#include <stdexcept>

class GeminiProvider : public AIProvider {
public:
    std::string generateResponse(const std::string& prompt) override {
        std::cout << "Calling Gemini...\n";

        return "Gemini response for: " + prompt;
    }

    std::string getName() override {
        return "Gemini";
    }
};
