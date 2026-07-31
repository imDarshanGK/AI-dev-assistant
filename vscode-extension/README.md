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
npm install
npm run compile
```

The compile step emits `extension.js`, which matches the package entrypoint declared in `package.json`.

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

```bash
npm install -g @vscode/vsce
vsce package
code --install-extension qyverixai-vscode-*.vsix
```

## License

MIT
