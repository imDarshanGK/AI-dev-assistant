# QyverixAI VS Code Extension

A VS Code extension that connects your editor to the QyverixAI API for code analysis, debugging, and explanation in a single workflow.

## What this extension does

- Sends the active file content to the QyverixAI API.
- Shows analysis results in a WebView panel.
- Adds inline diagnostics for detected bugs, warnings, and suggestions.
- Supports three commands: Analyze, Debug, and Explain.

## Features

- ** Analyze Current File** (`qyverixai.analyze`)
  - Reviews the file and returns a detailed analysis with improvement suggestions.
  - Shows inline diagnostics for issues and weaknesses.
- ** Debug Current File** (`qyverixai.debug`)
  - Scans for errors, bug patterns, and common pitfalls.
  - Highlights problematic lines directly in the editor.
- ** Explain Current File** (`qyverixai.explain`)
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
## Running the Extension Locally

After compiling the extension:

1. Open the `vscode-extension` folder in VS Code.
2. Press **F5** or navigate to **Run → Start Debugging**.
3. A new **Extension Development Host** window will open.
4. Open any source file in the new window.
5. Open the Command Palette (`Ctrl+Shift+P`) and run one of:

   * `QyverixAI: Analyze Current File`
   * `QyverixAI: Debug Current File`
   * `QyverixAI: Explain Current File`

The command results will appear in a WebView panel, and diagnostics will be displayed in the editor where applicable.

## Debugging

### Setting Breakpoints

Breakpoints can be added by clicking in the margin next to a line number in `src/extension.ts`.

Useful locations include:

* `postToApi()` – inspect outgoing API requests and responses.
* Command handlers – verify command execution flow.
* Diagnostic creation logic – inspect generated warnings and errors.
* WebView rendering functions – inspect response formatting.

### Example Breakpoint

Place a breakpoint on the following line:

```ts
function postToApi<T>(endpoint: string, body: object, timeoutS: number): Promise<T> {
```

Then:

1. Press **F5** to launch the Extension Development Host.
2. Run any QyverixAI command.
3. VS Code will pause execution when the breakpoint is reached.
4. Inspect variables using the Debug panel.

### Debug Console

While debugging, open:

**View → Debug Console**

The Debug Console displays:

* Runtime errors
* Breakpoint information
* Logged messages
* Stack traces

## Example Launch Configuration

If a launch configuration is not automatically generated, create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run Extension",
      "type": "extensionHost",
      "request": "launch",
      "runtimeExecutable": "${execPath}",
      "args": [
        "--extensionDevelopmentPath=${workspaceFolder}"
      ]
    }
  ]
}
```

## Testing Tips

* Run all three extension commands after making changes.
* Verify diagnostics appear in the editor and Problems panel.
* Test with multiple programming languages when possible.
* Use `Ctrl+Shift+P → Developer: Reload Window` after rebuilding.
* Keep `npm run watch` running during development for automatic recompilation.

To build an installable VSIX package:

## Compatibility

- Designed for VS Code versions matching `^1.82.0`.
- Works with any language file, but accuracy depends on the QyverixAI API and file content.

## License

MIT
