# Git Ingest

A file selection and processing tool that helps you export file contents from your local file system in a format suitable for use with AI tools or code documentation.

## Features

- Browse and select files from your local file system
- Respect `.gitignore` and `.pathignore` patterns
- Generate combined file contents and project structure map
- Limit file sizes to avoid processing large files
- Modern dark mode UI with responsive design

## Usage

1. Enter a directory path in the input field
2. Browse through the file tree and select files of interest
3. Use the quick controls to manage file selection (Select All, Deselect All, etc.)
4. Adjust the maximum file size using the slider if needed
5. Toggle respecting of `.gitignore` and `.pathignore` files as needed
6. Click "Generate Output" to produce the file contents and project map
7. Copy the generated output using the Copy buttons

## Ignore File Support

### .gitignore

The application can respect standard `.gitignore` files, which is useful for excluding build artifacts, dependencies, and other items typically excluded from Git repositories.

### .pathignore

In addition to `.gitignore`, the application supports `.pathignore` files that follow the same syntax as `.gitignore` but are specific to this application. This allows you to set up ignore patterns specifically for file browsing without affecting your Git configuration.

## Running Tests

The application includes a comprehensive test suite. To run the tests:

