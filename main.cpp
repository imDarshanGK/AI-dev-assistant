#include "ProviderManager.cpp"
#include "OpenAIProvider.cpp"
#include "GeminiProvider.cpp"

int main() {
    ProviderManager manager;

    OpenAIProvider openai;
    GeminiProvider gemini;

    manager.addProvider(&openai);
    manager.addProvider(&gemini);

    std::string result = manager.getResponse("Hello AI");

    std::cout << "Final Response: " << result << std::endl;

    return 0;
}
