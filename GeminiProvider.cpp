#include "AIProvider.h"
#include <iostream>

class GeminiProvider : public AIProvider {
public:
    std::string generateResponse(const std::string& prompt) override {
        std::cout << "Calling Gemini...\n";

        return "Gemini success response";
    }

    std::string getName() override {
        return "Gemini";
    }
};
