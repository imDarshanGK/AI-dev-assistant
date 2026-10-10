#pragma once
#include <string>

struct AIResponse {
    std::string text;
    std::string provider;
};

class AIProvider {
public:
    virtual AIResponse generateResponse(const std::string& prompt) = 0;
    virtual std::string getName() const = 0;
    virtual ~AIProvider() {}
};
