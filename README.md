# FilesToAI

A modern web application for selecting and exporting files from your local file system to use with AI tools like ChatGPT, Claude, and other large language models.

## Overview

FilesToAI helps you browse your local projects, select relevant files, and generate formatted output ready to paste into AI prompts. It handles file size limitations, supports ignore patterns, and provides useful statistics about your selection.

## Features

- **File Browser**: Navigate your local directories with an interactive tree view
- **Smart Filtering**:
  - Respect `.gitignore` patterns to exclude irrelevant files
  - Custom `.pathignore` patterns for additional filtering
  - Quick-select by file extensions
  - Hide files by extension type
  - Size limits to avoid processing large files
- **Project Analysis**:
  - Generate complete project maps
  - See file statistics (size, character count, token estimates)
  - Select files intelligently based on your project structure
- **Output Generation**:
  - Formatted file contents with clear file separators
  - Project structure visualization
  - Combined output with statistics
- **Modern UI**:
  - Clean, responsive Bootstrap interface
  - Dark mode for reduced eye strain
  - Path history for quick access to common projects

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd FilesToAI
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python app.py
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5023
   ```

## Usage Guide

1. **Load a Project**:
   - Enter a directory path in the input field
   - Click "Load" or press Enter
   - Previously used paths are saved for quick access

2. **Select Files**:
   - Browse through the file tree and check files you want to include
   - Use "Select All" or "Deselect All" buttons for quick operation
   - Expand/collapse folders as needed

3. **Filter Options**:
   - Enable/disable `.gitignore` patterns with the toggle
   - Add custom pathignore patterns if needed
   - Quick-select files by extension using the extension filter
   - Hide files with specific extensions (like `.min.js`, `.map`, etc.)

4. **Set Size Limit**:
   - Adjust the maximum file size slider to limit large files

5. **Generate Output**:
   - Click "Generate Output" to process selected files
   - "Generate Project Map" for structure-only visualization
   - "Generate Full Project Map" for complete project structure

6. **Use the Results**:
   - Copy output using the copy buttons
   - Download as text files
   - Use "Copy All Content" to combine everything into one clipboard

## Ignore File Support

### .gitignore
The application respects standard `.gitignore` files, automatically excluding build artifacts, dependencies, and other items typically excluded from Git repositories.

### pathignore Patterns
Custom patterns can be specified in the UI for additional filtering:
- Uses the same syntax as `.gitignore`
- Patterns can be tested for accuracy before applying
- Common patterns are pre-loaded for convenience

## API Endpoints

The application provides several API endpoints for programmatic access:
- `/api/browse` - Browse directory structure
- `/api/select` - Select files based on criteria
- `/api/generate` - Generate output from selected files
- `/api/file` - Get the content of a specific file
- `/api/hide` - Hide files with specific extensions
- `/api/reset` - Reset current selection state

## License

[MIT License]

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## Running Tests

The application includes a comprehensive test suite. To run the tests:

