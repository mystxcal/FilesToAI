# FilesToAI

A modern web application for selecting and exporting files from your local file system to use with AI tools like ChatGPT, Claude, and other large language models.

## Overview

FilesToAI helps you browse your local projects, select relevant files, and generate formatted output ready to paste into AI prompts. It handles file size limitations, supports ignore patterns (.gitignore and custom), provides useful statistics about your selection, and offers a global hotkey for quick generation and copying.

## Features

-   **Interactive File Browser**: Navigate your local directories with a dynamic tree view.
-   **Smart Filtering & Selection**:
    -   Respects `.gitignore` patterns.
    -   Custom `pathignore` patterns for additional, user-defined filtering with a built-in tester.
    -   Quick-select files by common extensions.
    -   Ignore/hide files by specific extensions (e.g., `.min.js`, `.log`, image files).
    -   Adjustable maximum file size limit for individual files.
    -   Select/deselect all, expand/collapse all folders.
-   **Output Generation**:
    -   Consolidated text output of selected files (`files.txt` format).
    -   Project structure visualization (`project_map.txt` format for selected or all files).
    -   Combined output of files, project map, and statistics.
-   **File Statistics**:
    -   Real-time display of combined file size, character count, estimated token count, and number of selected files.
-   **User-Friendly Interface**:
    -   Clean, responsive design using Bootstrap.
    -   Dark mode theme for comfortable viewing.
    -   Path history for quick access to recently used directories.
    -   Toast notifications for user feedback.
-   **Global Hotkey**:
    -   Press `Ctrl+Shift+Space` (configurable) anywhere on your system to automatically generate and copy the content of the files based on the last active session's configuration (root path, selected files, ignore settings, max file size).
-   **Configuration Persistence**:
    -   Saves settings like root path, ignore rules, max file size, and last selected files to a `filestoai_config.json` file, allowing the global hotkey to use the latest configuration.
-   **API Access**:
    -   Provides RESTful API endpoints for programmatic interaction (browsing, selecting files, generating output).

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url> # Replace <repository-url> with the actual URL
    cd FilesToAI
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    (Ensure you have Python and pip installed.)

3.  Run the application:
    ```bash
    python app.py
    ```

4.  Open your browser and navigate to:
    ```
    http://127.0.0.1:5023
    ```

## Usage Guide

1.  **Load a Project**:
    -   Enter the absolute directory path in the input field.
    -   Click "Load" or press Enter.
    -   Use the history button to access recently used paths.

2.  **Configure Settings (Left Panel)**:
    -   **Ignore Rules**:
        -   Toggle "Respect .gitignore" to enable/disable `.gitignore` processing.
        -   Toggle "Use custom pathignore patterns" to enable custom rules. Enter patterns (one per line, `.gitignore` syntax) in the textarea and click "Apply". Use "Test Patterns" to see how they would affect sample paths.
    -   **Maximum File Size**: Adjust the slider to set the limit for individual file content inclusion.
    -   **Quick Select by Extensions**: Add extensions to a list (e.g., `.py`, `.js`) and click "Select Files with These Extensions".
    -   **Ignore by Extensions**: Add extensions to a list to hide and unselect corresponding files (e.g., `.log`, `.map`). Click "Hide Files..." or "Show All Files".

3.  **Select Files & Folders (File Tree)**:
    -   Click checkboxes next to files or directories. Selecting a directory checkbox selects all its contents.
    -   Use "Select All" / "Deselect All" / "Expand All" / "Collapse All" buttons for bulk actions.
    -   The number of selected files is displayed.

4.  **Generate Output (Right Panel)**:
    -   Click "Generate Output" to process the currently selected files.
        -   `files.txt` will contain the concatenated content of selected files.
        -   `project_map.txt` will show the directory structure of selected files.
    -   "Generate Project Map": Creates a map of only the selected files.
    -   "Generate Full Project Map": Creates a map of all files in the loaded directory (respecting ignore rules).
    -   Output statistics (size, char count, tokens, selected files) are displayed and can be refreshed.

5.  **Use the Results**:
    -   Use "Copy" or "Download" buttons for individual output sections (`files.txt`, `project_map.txt`, `Statistics`).
    -   Use "Copy All Content" or "Download All Content" for a combined output including files, project map, and statistics.

## Global Hotkey

-   **Default Hotkey**: `Ctrl+Shift+Space`
-   **Functionality**: When pressed, the application (if `app.py` is running) will:
    1.  Read the last saved configuration from `filestoai_config.json` (includes root path, ignore settings, max file size, and importantly, `last_selected_files`).
    2.  If `last_selected_files` is populated, it generates content for those specific files.
    3.  If `last_selected_files` is empty, it attempts to process all files in the `absolute_root` directory, respecting ignore rules.
    4.  The combined output (files content, project map, and stats) is copied to the clipboard.
-   **Setup**: The global hotkey listener (`global_hotkey_listener.py`) is started automatically when `app.py` runs. Ensure `app.py` is running for the hotkey to function.
-   **Configuration**: The hotkey itself and debounce time can be configured in `global_hotkey_listener.py`.

## Ignore File Support

### .gitignore
The application respects standard `.gitignore` files found in the root of the loaded directory, automatically excluding files and folders as defined.

### pathignore Patterns
Custom patterns can be specified in the UI for additional, more granular filtering:
-   Uses the same syntax as `.gitignore`.
-   Patterns can be tested directly in the UI to verify their behavior.
-   Common default patterns (e.g., `node_modules/`, `*.log`) are pre-filled.

## API Endpoints

The application provides several API endpoints for programmatic access:

-   `GET /api/browse`: Browse directory structure.
    -   Params: `path`, `respect_gitignore`, `respect_pathignore`, `pathignore_patterns`, `show_hidden`, `set_as_root`.
-   `POST /api/select`: Select files based on criteria.
    -   Body: JSON with `extension_filters`, `path_patterns`, `max_size_kb`, `exclude_extensions`, `select_all`, `in_directory`.
-   `POST /api/generate`: Generate output from a list of selected files.
    -   Body: JSON with `selected_files`, `max_size_kb`, `include_project_map`, `include_binary_files`.
-   `GET /api/file`: Get the content of a specific file.
    -   Params: `path`.
-   `POST /api/hide`: (Internally used concept, not a direct API for hiding in tree but influences selection logic if implemented).
-   `POST /api/reset`: Reset current selection state (clears `hide_extensions` from session if used).
-   `POST /api/global_trigger_generate_and_copy`: Endpoint called by the global hotkey listener to generate and prepare content for clipboard.
-   `POST /api/update_current_selection`: Updates the server (and `filestoai_config.json`) with the list of currently selected files in the UI. This is used by the global hotkey.

*Refer to `app.py` for detailed request/response structures.*

## License

This project is licensed under the MIT License. See the LICENSE file for details (assuming one exists, if not, this is a placeholder).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
