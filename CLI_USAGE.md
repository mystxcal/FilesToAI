# FilesToAI CLI Usage

## Installation

### Install from source (development):
```bash
# Clone the repository
git clone https://github.com/mystxcal/FilesToAI
cd FilesToAI

# Install in editable mode
pip install -e .
```

### Install as a package:
```bash
pip install .
```

### Install for development:
```bash
pip install -r requirements.txt
```

## CLI Usage

Once installed, you can use the `filestoai` command from anywhere in your terminal.

### Basic Usage

```bash
# Export current directory
filestoai .

# Export specific directory
filestoai /path/to/project

# Export with path relative to current directory
filestoai ../my-project
```

### Options

#### `-gi, --gitignore`
Respect .gitignore files in the directory
```bash
filestoai . -gi
filestoai . --gitignore
```

#### `-s, --size KB`
Set maximum file size limit in KB (default: 100 KB)
```bash
filestoai . --size 200      # Max file size 200 KB
filestoai . -s 500          # Max file size 500 KB
```

#### `-i, --ignore PATTERNS`
Add custom ignore patterns (comma-separated, gitignore syntax)
```bash
filestoai . --ignore "*.log,*.tmp"
filestoai . -i "node_modules/,dist/,*.min.js"
filestoai . -gi -i "build/,*.cache"  # Combine with gitignore
```

#### `-o, --output FILE`
Save output to a file instead of clipboard
```bash
filestoai . -o output.txt
filestoai . -gi -o exported_code.txt
```

#### `--no-copy`
Don't copy to clipboard (only works with `--output`)
```bash
filestoai . -o output.txt --no-copy
```

#### `--include-binary`
Include binary files as placeholders in output
```bash
filestoai . --include-binary
```

#### `--project-map-only`
Only generate the project structure map, skip file contents
```bash
filestoai . --project-map-only
```

#### `--files-only`
Only generate file contents, skip project map
```bash
filestoai . --files-only
```

#### `--list-files`
List all files that would be processed (without generating output)
```bash
filestoai . --list-files
filestoai . -gi --list-files
```

#### `-v, --verbose`
Enable verbose output for debugging
```bash
filestoai . -v
filestoai . --verbose -gi
```

#### `--server`
Start the web interface server (Flask app)
```bash
filestoai --server               # Start on default port 5023
filestoai --server --port 8000   # Start on custom port
```

#### `--port PORT`
Specify port for web server (only works with `--server`)
```bash
filestoai --server --port 8080
```

## Examples

### Export a React project ignoring node_modules and build files
```bash
filestoai ~/my-react-app -gi -i "build/,*.log"
```

### Export only Python files under 50 KB
```bash
filestoai . --size 50 -i "*.py"
```

### Generate a project structure map only
```bash
filestoai . --project-map-only
```

### Export and save to file without copying to clipboard
```bash
filestoai . -gi -o codebase_export.txt --no-copy
```

### Preview which files will be exported
```bash
filestoai . -gi --list-files
```

### Export with verbose logging
```bash
filestoai . -gi -v
```

### Start the web interface
```bash
# Default port (5023)
filestoai --server

# Custom port
filestoai --server --port 8000

# Then open browser to http://127.0.0.1:5023 (or your custom port)
```

### Complex example: Export a large project with custom settings
```bash
filestoai ~/my-project \
  --gitignore \
  --size 200 \
  --ignore "*.log,*.cache,temp/,dist/" \
  --output my_project_export.txt \
  --verbose
```

## Output Format

The CLI generates output in the following format:

```
========== FILES ==========

=== File: example.py ===
=== Path: src/example.py ===

[file contents here]

========================================

[more files...]

========== PROJECT MAP ==========

Directory structure:
├── src/
│   ├── example.py
│   └── utils.py
└── README.md

========== STATISTICS ==========

Total Files: 15
Character Count: 50,234
Estimated Tokens: 12,558
Skipped (size): 2
Binary Files: 3
```

## Integration with Web Interface

The CLI tool shares the same core functionality with the web interface. You can use both:

### Start the web interface:
```bash
# Via CLI (recommended)
filestoai --server

# Or run directly
python app.py
```

Then open `http://127.0.0.1:5023` in your browser.

### Use CLI for quick exports:
```bash
filestoai . -gi
```

### Switch between modes:
```bash
# CLI mode for quick exports
filestoai . -gi -o output.txt

# Web mode when you need the GUI
filestoai --server
```

## Tips

1. **Use `--list-files` first** to preview what will be exported before generating the full output
2. **Combine `-gi` with custom patterns** using `-i` for fine-grained control
3. **Adjust `--size` based on your needs** - larger sizes for comprehensive exports, smaller for quick overviews
4. **Use `-o` for large exports** to avoid clipboard limitations
5. **The output is immediately copied to clipboard** by default - perfect for pasting into ChatGPT or Claude

## Troubleshooting

### Command not found
If `filestoai` is not recognized, make sure:
1. You've installed the package: `pip install -e .`
2. Your Python scripts directory is in PATH
3. Try running: `python -m cli` as an alternative

### Clipboard not working
On some systems, clipboard access may require additional dependencies:
- **Linux**: `sudo apt-get install xclip` or `sudo apt-get install xsel`
- **Windows/Mac**: Should work out of the box with `pyperclip`

Use `--output file.txt` as a workaround if clipboard fails.

### Permission errors
Make sure you have read access to the directory you're trying to export.

## Support

For issues or feature requests, please visit:
https://github.com/mystxcal/FilesToAI/issues

