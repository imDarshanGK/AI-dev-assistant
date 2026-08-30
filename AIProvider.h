#pragma once
#include <string>

class AIProvider {
public:
    virtual std::string generateResponse(const std::string& prompt) = 0;
    virtual std::string getName() = 0;
    virtual ~AIProvider() {}
};
