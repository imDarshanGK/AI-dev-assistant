# QyverixAI VS Code Extension

A VS Code extension that connects your editor to the QyverixAI API for code analysis, debugging, and explanation in a single workflow.

## What this extension does

- Sends the active file content to the QyverixAI API.
- Shows analysis results in a WebView panel.
- Adds inline diagnostics for detected bugs, warnings, and suggestions.
- Supports three commands: Analyze, Debug, and Explain.

## Features

- **🧪 Analyze Current File** (`qyverixai.analyze`)
  - Reviews the file and returns a detailed analysis with improvement suggestions.
  - Shows inline diagnostics for issues and weaknesses.
- **🐛 Debug Current File** (`qyverixai.debug`)
  - Scans for errors, bug patterns, and common pitfalls.
  - Highlights problematic lines directly in the editor.
- **📖 Explain Current File** (`qyverixai.explain`)
  - Provides a plain-English summary of what the code does.
  - Describes structure, intent, and important areas of the file.

## Installation

### Install from source

1. Open the `vscode-extension` folder in VS Code.
2. Install Node dependencies:
   ```bash
   cd vscode-extension
   npm install
   ```
3. Compile the extension:
   ```bash
   npm run compile
   ```
4. Run the extension in the Extension Development Host by pressing `F5`.

### Install a packaged VSIX

```bash
npm install -g @vscode/vsce
cd vscode-extension
vsce package
code --install-extension qyverixai-vscode-*.vsix
```

## Usage

1. Open any source file in VS Code.
2. Run one of the commands from the Command Palette (`Ctrl+Shift+P`):
   - `QyverixAI: Analyze Current File`
   - `QyverixAI: Debug Current File`
   - `QyverixAI: Explain Current File`
3. Alternatively, right-click in the editor and choose the same command from the context menu.
4. Review the results in the WebView panel.
5. For Analyze and Debug, open the Problems panel (`Ctrl+Shift+M`) to see inline diagnostics.

## Requirements

- VS Code 1.82 or later
- Node.js and npm installed for development
- Access to the QyverixAI API endpoint

## Configuration

Set the following extension settings in your workspace or user settings:

| Setting | Default | Description |
|---|---|---|
| `qyverixai.apiUrl` | `https://qyverixai.onrender.com` | Base URL of the QyverixAI API |
| `qyverixai.timeout` | `30` | Request timeout in seconds |

### Example

```json
{
  "qyverixai.apiUrl": "http://localhost:8000",
  "qyverixai.timeout": 45
}
```

## Development Notes

- Source TypeScript files are in `vscode-extension/src/`.
- The compiled entry point is `vscode-extension/extension.js`.
- `package.json` includes the extension commands and activation events.

## Troubleshooting

- If the extension fails to communicate with the API, verify `qyverixai.apiUrl` and network access.
- If commands do not appear, reload the window and check for any extension errors in the Output panel.
- For best results, use files with valid syntax and avoid extremely large single-file payloads.

## Compatibility

- Designed for VS Code versions matching `^1.82.0`.
- Works with any language file, but accuracy depends on the QyverixAI API and file content.

## License

MIT
