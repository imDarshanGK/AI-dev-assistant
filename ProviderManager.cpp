#include <vector>
#include <iostream>
#include "AIProvider.h"

class ProviderManager {
private:
    std::vector<AIProvider*> providers;

public:
    void addProvider(AIProvider* provider) {
        providers.push_back(provider);
    }

    std::string getResponse(const std::string& prompt) {
        for (auto provider : providers) {
            try {
                std::string res = provider->generateResponse(prompt);

                if (!res.empty()) {
                    std::cout << "Success from: " << provider->getName() << "\n";
                    return res;
                }
            } catch (const std::exception& e) {
                std::cout << provider->getName() << " failed: " << e.what() << "\n";
            }
        }

        throw std::runtime_error("All providers failed");
    }
};
