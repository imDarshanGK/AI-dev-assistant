#include "AIProvider.h"
#include <iostream>

class OpenAIProvider : public AIProvider {
public:
    std::string generateResponse(const std::string& prompt) override {
        // Simulate API call
        std::cout << "Calling OpenAI...\n";

        // Simulate failure
        throw std::runtime_error("OpenAI failed");

        return "OpenAI response";
    }

    std::string getName() override {
        return "OpenAI";
    }
};
