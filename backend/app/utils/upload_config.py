ALLOWED_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".txt"
]

ALLOWED_MIME_TYPES = {

    ".py": [
        "text/x-python",
        "application/x-python-code",
        "text/plain",
        "application/octet-stream",
    ],

    ".js": [
        "application/javascript",
        "text/javascript",
        "text/plain",
    ],

    ".ts": [
        "application/typescript",
        "text/typescript",
        "application/x-typescript",
        "video/mp2t",
        "text/plain",
    ],

    ".java": [
        "text/x-java-source",
        "text/java",
        "application/java",
        "text/plain",
        "application/octet-stream",

    ],

    ".cpp": [
        "text/x-c++src",
        "text/x-c",
        "application/x-c++",
        "text/x-csrc",
        "application/x-cplusplus",
        "text/plain",
        "application/octet-stream",
        "text/x-csrc",
        "application/x-cplusplus",
        "text/plain",
        "application/octet-stream",
    ],

    ".txt": [
        "text/plain",
    ]

}

BLOCKED_EXTENSIONS = [
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".ps1",
    ".dll",
    ".scr",
    ".msi",
    ".apk",
]

max_file_size = 5 * 1024 * 1024  # 5 MB

UPLOAD_ERROR_MESSAGES = {
    "invalid_extension": (
        "Unsupported file type. "
        "Allowed types: .py, .js, .ts, .java, .cpp"
    ),
    "blocked_file": "Executable files are not allowed.",
    "invalid_mime": "Invalid MIME type detected.",
}
