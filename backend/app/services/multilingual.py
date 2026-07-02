"""Multilingual support for QyverixAI AI responses."""

# Language code to (language_name, language_native) mapping
LANGUAGE_MAP = {
    "en": ("English", "English"),
    "ta": ("Tamil", "தமிழ்"),
    "hi": ("Hindi", "हिन्दी"),
    "fr": ("French", "Français"),
}

# Translation dictionary for rule-based engine outputs
TRANSLATIONS = {
    "en": {
        "non_blank_lines": "non-blank lines of code",
        "defines_functions": "Defines",
        "function_s": "function(s):",
        "contains_classes": "Contains",
        "class_es": "class(es):",
        "imports_modules": "Imports",
        "external_dependencies": "module(s) — external dependencies present",
        "contains_loops": "Contains loop(s) — iterative data processing detected",
        "contains_conditionals": "Contains conditional logic — branching control flow",
        "recursive_call": "⚠ Recursive call detected — ensure a proper base case exists",
        "beginner": "A short {language} snippet ({lines} lines) that performs a focused task. Good starting point for learners",
        "intermediate": "A {language} module with {funcs} function(s) and moderate complexity. Demonstrates solid programming fundamentals",
        "advanced": "A well-structured {language} codebase with {classes} class(es) and {funcs} function(s). Shows advanced design patterns",
        "expert": "A large-scale {language} system ({lines} lines). Expert-level architecture with significant abstraction layers",
        "excellent": "Excellent code! Consider adding integration tests",
        "good_work": "Good work. Address the medium-priority items next",
        "solid_foundation": "Solid foundation. Focus on error handling and testing",
        "needs_improvement": "Needs significant improvement — start with the high-priority items",
        "major_issues": "Major issues detected. Refactor with error handling, tests, and type safety",
        "documentation": "Documentation",
        "less_than_ten": "Less than 10% of lines are comments. Add docstrings/comments to explain intent",
        "refactoring": "Refactoring",
        "function_length": "function(s) is {length} lines — consider splitting into smaller helpers",
        "readability": "Readability",
        "magic_numbers": "Magic numbers detected ({count} occurrence(s)). Replace with named constants",
        "error_handling": "Error Handling",
        "io_operations": "I/O operations detected ({count} line(s)) with no try/except block",
        "type_safety": "Type Safety",
        "functions_missing_types": "function(s) missing type annotations",
        "testing": "Testing",
        "no_tests": "No tests detected. Unit tests catch regressions early",
        "performance": "Performance",
        "logging": "Logging",
        "no_logging": "No logging detected. Structured logging helps with debugging and monitoring",
    },
    "hi": {
        "non_blank_lines": "कोड की पंक्तियाँ",
        "defines_functions": "परिभाषित करता है",
        "function_s": "function(s):",
        "contains_classes": "शामिल है",
        "class_es": "class(es):",
        "imports_modules": "आयात करता है",
        "external_dependencies": "module(s) — बाहरी निर्भरताएं मौजूद हैं",
        "contains_loops": "लूप(s) शामिल है — पुनरावृत्तीय डेटा प्रोसेसिंग का पता चला",
        "contains_conditionals": "कंडीशनल लॉजिक शामिल है — शाखा नियंत्रण प्रवाह",
        "recursive_call": "⚠ पुनरावर्ती कॉल का पता चला — सुनिश्चित करें कि उचित आधार मामला मौजूद है",
        "beginner": "एक छोटा {language} स्निपेट ({lines} पंक्तियाँ) जो एक केंद्रित कार्य करता है। शुरुआती लोगों के लिए अच्छा प्रारंभिक बिंदु",
        "intermediate": "एक {language} मॉड्यूल {funcs} function(s) और मध्यम जटिलता के साथ। ठोस प्रोग्रामिंग बुनियादी बातें प्रदर्शित करता है",
        "advanced": "एक अच्छी तरह से संरचित {language} कोडबेस {classes} class(es) और {funcs} function(s) के साथ। उन्नत डिजाइन पैटर्न दिखाता है",
        "expert": "एक बड़े पैमाने पर {language} प्रणाली ({lines} पंक्तियाँ)। विशेषज्ञ-स्तर की आर्किटेक्चर महत्वपूर्ण अमूर्तन परतों के साथ",
        "excellent": "उत्कृष्ट कोड! एकीकरण परीक्षण जोड़ने पर विचार करें",
        "good_work": "अच्छा काम। अगले मध्यम-प्राथमिकता वाली वस्तुओं को संबोधित करें",
        "solid_foundation": "ठोस आधार। त्रुटि हैंडलिंग और परीक्षण पर ध्यान दें",
        "needs_improvement": "महत्वपूर्ण सुधार की आवश्यकता है — उच्च-प्राथमिकता वाली वस्तुओं से शुरुआत करें",
        "major_issues": "प्रमुख समस्याएं पाई गईं। त्रुटि हैंडलिंग, परीक्षण और प्रकार सुरक्षा के साथ रीफ्रेक्टर करें",
        "documentation": "प्रलेखन",
        "less_than_ten": "10% से कम पंक्तियाँ टिप्पणियाँ हैं। इरादे को समझाने के लिए डॉकस्ट्रिंग/टिप्पणियाँ जोड़ें",
        "refactoring": "पुनर्रचना",
        "function_length": "function(s) {length} पंक्तियाँ है — छोटे सहायकों में विभाजित करने पर विचार करें",
        "readability": "पठनीयता",
        "magic_numbers": "जादुई संख्याएं पाई गईं ({count} occurrence(s))। नामित स्थिरांक से बदलें",
        "error_handling": "त्रुटि संभालना",
        "io_operations": "I/O operations पाए गए ({count} पंक्तियाँ) कोई try/except ब्लॉक नहीं",
        "type_safety": "प्रकार सुरक्षा",
        "functions_missing_types": "function(s) प्रकार की व्याख्या से छूट गई",
        "testing": "परीक्षण",
        "no_tests": "कोई परीक्षण नहीं पाया गया। यूनिट परीक्षण प्रतिगमन को जल्दी पकड़ता है",
        "performance": "प्रदर्शन",
        "logging": "लॉगिंग",
        "no_logging": "कोई लॉगिंग नहीं पाई गई। संरचित लॉगिंग डीबगिंग और निगरानी में मदद करती है",
    },
    "ta": {
        "non_blank_lines": "நிரல் வரிகள்",
        "defines_functions": "வரையறுக்கிறது",
        "function_s": "function(s):",
        "contains_classes": "அடங்கியுள்ளது",
        "class_es": "class(es):",
        "imports_modules": "இறக்குமதி செய்கிறது",
        "external_dependencies": "module(s) — வெளிப்புற சார்புகள் உள்ளன",
        "contains_loops": "Loop(s) உள்ளது — மறுபடி தரவு செயலாக்கம் கண்டறியப்பட்டது",
        "contains_conditionals": "நிபந்தனை தர்க்கம் உள்ளது — கிளை கட்டுப்பாட்டு ப्रवाह",
        "recursive_call": "⚠ மறுநுட்பமான அழைப்பு கண்டறியப்பட்டது — சரியான அடிப்படை வழக்கு உள்ளது என்பதை உறுதிப்படுத்தவும்",
        "beginner": "குறுகிய {language} பகுதி ({lines} வரிகள்) கவனம் செலுத்திய பணியைச் செய்கிறது। கற்பவர்களுக்கு நல்ல தொடக்க புள்ளி",
        "intermediate": "{language} தொகுதி {funcs} function(s) மற்றும் நடுத்தர சிக்கலுடன். உறுதியான நிரலாக்க அடிப்படைகளை நிரூபிக்கிறது",
        "advanced": "நன்றாக கட்டமைக்கப்பட்ட {language} கோட்பேஸ் {classes} class(es) மற்றும் {funcs} function(s) உடன். மேம்பட்ட ডிज़াइன பैட்டர்ன் காட்டுகிறது",
        "expert": "பெரிய அளவிலான {language} கணினி ({lines} வரிகள்). நிபுணர் நிலை கட்டிடக்கலை குறிப்பிடத்தக்க சுருக்க அடுக்குடன்",
        "excellent": "சிறந்த நிரல்! ஒருங்கிணைப்பு சோதனைகளைச் சேர்க்க பரிசீலிக்கவும்",
        "good_work": "நல்ல வேலை. அடுத்த நடுத்தர-অগ்राதிகார பொருட்களைக் கூறுங்கள்",
        "solid_foundation": "திடமான அடிப்படை. பிழை கையாளுதல் மற்றும் சோதனையில் கவனம் செலுத்தவும்",
        "needs_improvement": "கணிசமான மேம்பாடு தேவை — அதிக-অগ்राதிகார பொருட்களிலிருந்து தொடங்கவும்",
        "major_issues": "முக்கிய சிக்கல்கள் கண்டறியப்பட்டன. பிழை கையாளுதல், சோதனை மற்றும் வகை பாதுகாப்பு மூலம் மீண்டும் செயல்படுத்தவும்",
        "documentation": "ஆவணம்",
        "less_than_ten": "10% க்கும் குறைவான வரிகள் கருத்துக்கள். உददेश்யத்தை விளக்க docstrings/கருத்துக்கள் சேர்க்கவும்",
        "refactoring": "மீண்டும் குறிப்பிடுதல்",
        "function_length": "function(s) {length} வரிகள் — சிறிய உதவியாளர்களாக பிரிக்க பரிசீலிக்கவும்",
        "readability": "வாசிப்பு திறன்",
        "magic_numbers": "மந்திர எண்கள் கண்டறியப்பட்டன ({count} நிகழ்வுகள்)). பெயரிடப்பட்ட மாறிலிகளுடன் மாற்றவும்",
        "error_handling": "பிழை கையாளுதல்",
        "io_operations": "I/O operations கண்டறியப்பட்டது ({count} வரிகள்) try/except தொகுதி இல்லை",
        "type_safety": "வகை பாதுகாப்பு",
        "functions_missing_types": "function(s) வகை குறிப்பிலிருந்து தவறவிடப்பட்டது",
        "testing": "சோதனை",
        "no_tests": "சோதனைகள் கண்டறியப்படவில்லை. அலகு சோதனை பின்னடைவுகளை விரைவாக பிடிக்கிறது",
        "performance": "செயல்திறன்",
        "logging": "பதிவு செய்தல்",
        "no_logging": "பதிவு செய்தல் கண்டறியப்படவில்லை. கட்டமைக்கப்பட்ட பதிவு செய்தல் பிழையேற்றம் மற்றும் கண்காணிப்பு உதவி",
    },
    "fr": {
        "non_blank_lines": "lignes de code",
        "defines_functions": "Définit",
        "function_s": "function(s):",
        "contains_classes": "Contient",
        "class_es": "class(es):",
        "imports_modules": "Importe",
        "external_dependencies": "module(s) — dépendances externes présentes",
        "contains_loops": "Contient des boucle(s) — traitement itératif des données détecté",
        "contains_conditionals": "Contient la logique conditionnelle — flux de contrôle de branchement",
        "recursive_call": "⚠ Appel récursif détecté — assurez-vous qu'un cas de base approprié existe",
        "beginner": "Un extrait {language} court ({lines} lignes) qui effectue une tâche ciblée. Bon point de départ pour les apprenants",
        "intermediate": "Un module {language} avec {funcs} function(s) et complexité modérée. Démontre les principes fondamentaux de la programmation solide",
        "advanced": "Une base de code {language} bien structurée avec {classes} class(es) et {funcs} function(s). Montre les modèles de conception avancés",
        "expert": "Un grand système {language} ({lines} lignes). Architecture au niveau des experts avec des couches d'abstraction importantes",
        "excellent": "Code excellent! Envisagez d'ajouter des tests d'intégration",
        "good_work": "Bon travail. Adressez les éléments de priorité moyenne ensuite",
        "solid_foundation": "Base solide. Concentrez-vous sur la gestion des erreurs et les tests",
        "needs_improvement": "Amélioration significative nécessaire — commencez par les éléments hautement prioritaires",
        "major_issues": "Problèmes majeurs détectés. Refactorisez avec gestion d'erreurs, tests et sécurité des types",
        "documentation": "Documentation",
        "less_than_ten": "Moins de 10% des lignes sont des commentaires. Ajoutez des docstrings/commentaires pour expliquer l'intention",
        "refactoring": "Refactorisation",
        "function_length": "function(s) est {length} lignes — envisagez de diviser en assistants plus petits",
        "readability": "Lisibilité",
        "magic_numbers": "Nombres magiques détectés ({count} occurrence(s)). Remplacer par des constantes nommées",
        "error_handling": "Gestion des erreurs",
        "io_operations": "Opérations E/S détectées ({count} ligne(s)) sans bloc try/except",
        "type_safety": "Sécurité des types",
        "functions_missing_types": "function(s) annotations de type manquantes",
        "testing": "Test",
        "no_tests": "Aucun test détecté. Les tests unitaires détectent rapidement les régressions",
        "performance": "Rendimiento",
        "logging": "Enregistrement",
        "no_logging": "Aucune journalisation détectée. La journalisation structurée aide au débogage et à la surveillance",
    },
}

SYSTEM_PROMPT_TEMPLATE = """You are QyverixAI, an expert code analysis assistant.

You help developers by:
- Explaining what their code does in plain, simple terms
- Detecting bugs, errors, and anti-patterns
- Suggesting improvements for readability, performance, and best practices

LANGUAGE INSTRUCTION:
You MUST respond ENTIRELY in {language_name} ({language_native}).
This applies to ALL parts of your response without exception:
- Explanations, bug descriptions, improvement suggestions
- Section headers (e.g. translate "Bugs Found" → equivalent in {language_name})
- Any labels, notes, or commentary you generate

Do NOT mix languages. Do NOT default to English at any point.

Exception: Keep code-specific terms like `return`, `null`, `TypeError`,
variable names, and function names in English — they are language-agnostic.

If you cannot respond fully in {language_name}, explicitly say so
in {language_name} first, then fall back to English."""


def get_system_prompt(ai_language: str | None = None) -> str:
    """
    Get the system prompt for QyverixAI, optionally with language instruction.

    Args:
        ai_language: Language code (e.g., "en", "ta", "hi", "fr").
                     If None, uses the template without language-specific instruction.

    Returns:
        The system prompt string.
    """
    if not ai_language or ai_language not in LANGUAGE_MAP:
        # Default behavior: no language-specific instruction
        return SYSTEM_PROMPT_TEMPLATE.replace(
            "\nLANGUAGE INSTRUCTION:\nYou MUST respond ENTIRELY in {language_name} ({language_native})."
            "\nThis applies to ALL parts of your response without exception:"
            "\n- Explanations, bug descriptions, improvement suggestions"
            '\n- Section headers (e.g. translate "Bugs Found" → equivalent in {language_name})'
            "\n- Any labels, notes, or commentary you generate"
            "\n\nDo NOT mix languages. Do NOT default to English at any point."
            "\n\nException: Keep code-specific terms like `return`, `null`, `TypeError`,"
            "\nvariable names, and function names in English — they are language-agnostic."
            "\n\nIf you cannot respond fully in {language_name}, explicitly say so"
            "\nin {language_name} first, then fall back to English.",
            "",
        )

    language_name, language_native = LANGUAGE_MAP[ai_language]
    return SYSTEM_PROMPT_TEMPLATE.format(
        language_name=language_name, language_native=language_native
    )


def translate_key(key: str, language_code: str | None = None) -> str:
    """
    Translate a key using the translations dictionary.

    Args:
        key: The translation key (e.g., "documentation", "less_than_ten").
        language_code: The target language code (e.g., "en", "hi", "ta", "fr").
                      If None or invalid, uses "en".

    Returns:
        The translated string, or English version if not found.
    """
    if not language_code or language_code not in TRANSLATIONS:
        language_code = "en"

    return TRANSLATIONS[language_code].get(key, TRANSLATIONS["en"].get(key, key))
