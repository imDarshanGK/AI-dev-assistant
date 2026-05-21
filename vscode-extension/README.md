# QyverixAI VS Code Extension

Analyze, debug, and explain code directly from VS Code using the [QyverixAI](https://qyverixai.onrender.com) API.

## Features

- **🧪 Analyze** (`qyverixai.analyze`) — Full code analysis: explanation, bug detection, and improvement suggestions in one go. Sets inline diagnostics (squiggly lines) for detected issues.
- **🐛 Debug** (`qyverixai.debug`) — Scan the current file for bugs, errors, and warnings. Inline diagnostics highlight problem areas in the editor.
- **📖 Explain** (`qyverixai.explain`) — Get a plain-English summary of what the code does, its complexity, key points, and structure.

## Usage

1. Open any file in VS Code.
2. Right-click in the editor and select:
   - **QyverixAI: Analyze Current File**
   - **QyverixAI: Debug Current File**
   - **QyverixAI: Explain Current File**

   Or use the Command Palette (`Ctrl+Shift+P`) and type `QyverixAI`.

3. A WebView panel opens beside your editor with the results.
4. For **Analyze** and **Debug**, squiggly lines appear in the editor at the locations of detected issues. Open the **Problems** panel (`Ctrl+Shift+M`) to see the full list.

## Requirements

- VS Code 1.82+
- The QyverixAI API must be running and reachable. The extension defaults to the hosted API at `https://qyverixai.onrender.com`.

## Extension Settings

This extension contributes the following settings:

| Setting | Default | Description |
|---|---|---|
| `qyverixai.apiUrl` | `https://qyverixai.onrender.com` | Base URL of the QyverixAI API |
| `qyverixai.timeout` | `30` | Request timeout in seconds |

## Known Issues

- The API works best with complete, syntactically valid files.
- Very large files (>50 KB) may be truncated by the API's 50 000 character limit.

## Development

```bash
cd vscode-extension
npm install -g @vscode/vsce
vsce package
code --install-extension qyverixai-vscode-*.vsix
```

## License

MIT
