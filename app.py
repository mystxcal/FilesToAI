from flask import Flask, render_template, request, jsonify, send_from_directory, session
import os
import secrets
import traceback
import logging
from pathlib import Path
import fnmatch

import json
import threading
import atexit
from global_hotkey_listener import setup_keyboard_listener, stop_keyboard_listener, logger as listener_logger # Import logger too
from core import (
    format_size,
    gitignore_pattern_to_regex,
    parse_ignore_file,
    parse_ignore_patterns,
    should_ignore_path,
    collect_files,
    generate_output_content,
    create_project_map
)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(16)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(f"Current Working Directory: {os.getcwd()}")

CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'filestoai_config.json')

# Favicon route to serve the app icon
@app.route('/favicon.ico')
def favicon():
    try:
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
        return send_from_directory(assets_dir, 'image.png', mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving favicon: {e}")
        # Fallback empty response to avoid noisy 404s in logs
        return ('', 204)

def write_current_config_to_file():
    """Writes the current relevant session settings to a JSON config file."""
    config_data = {
        'absolute_root': session.get('absolute_root'),
        'respect_gitignore': session.get('respect_gitignore', True),
        'respect_pathignore': session.get('respect_pathignore', True),
        'pathignore_patterns': session.get('pathignore_patterns', []), # Parsed patterns
        'pathignore_input_text': session.get('pathignore_input_text', ''), # Raw text for UI
        'max_size_kb': session.get('max_size_kb', 100),
        'last_selected_files': session.get('last_selected_files', []),
        'enable_global_hotkey': session.get('enable_global_hotkey', True) # Add this
    }
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        logger.info(f"Updated config file: {CONFIG_FILE_PATH} with data: {config_data}")
    except Exception as e:
        logger.error(f"Error writing config file {CONFIG_FILE_PATH}: {e}")

def is_valid_path(base_path, check_path):
    """
    Simple validation to ensure path exists and is accessible
    """
    try:
        # For an offline local app, we mainly want to ensure the path exists
        return os.path.exists(check_path)
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return False


def generate_file_tree(root_path, current_path, respect_gitignore=True, respect_pathignore=True, pathignore_patterns=None):
    """Generates HTML: folders first, checkboxes, subfolders initially hidden."""
    html = '<ul>'  # Top-level ul - always visible
    try:
        # Ensure the current path is valid and within the root path
        if not is_valid_path(root_path, current_path):
            return '<li>Error: Invalid path access</li></ul>'

        # Get and sort items: directories first, then files
        try:
            items = sorted(os.listdir(current_path))

            # Filter items based on ignore patterns
            filtered_items = []
            for item in items:
                item_path = os.path.join(current_path, item)
                # Adjust should_ignore_path call to match new signature in core
                if not should_ignore_path(item_path, root_path, respect_gitignore, pathignore_patterns):
                    filtered_items.append(item)

            items = filtered_items
            directories = [item for item in items if os.path.isdir(os.path.join(current_path, item))]
            files = [item for item in items if os.path.isfile(os.path.join(current_path, item))]
            sorted_items = sorted(directories) + sorted(files)
        except PermissionError:
            return '<li>Error: Permission denied for this directory</li></ul>'
        except Exception as e:
            logger.error(f"Error listing directory {current_path}: {e}")
            return f'<li>Error accessing directory: {str(e)}</li></ul>'

        for item in sorted_items:
            # Skip hidden files and directories unless we're looking at ignore files
            if item.startswith('.') and item not in ['.gitignore', '.pathignore']:
                continue

            item_absolute_path = os.path.join(current_path, item)
            relative_path = os.path.relpath(item_absolute_path, root_path)

            # Normalize path for consistent cross-platform behavior
            relative_path = relative_path.replace('\\', '/')

            if os.path.isdir(item_absolute_path):
                html += f'<li class="directory">'
                html += f'<input type="checkbox" class="dir-checkbox" data-path="{relative_path}"> '
                html += f'<span class="expand-button"><i class="fas fa-caret-right"></i></span>'
                html += f'<span class="directory-name" data-path="{relative_path}">{item}</span>'
                # Hide ONLY the direct child <ul> of a directory <li>
                html += '<ul style="display: none;">'  # Initially hide sub-trees
                html += generate_file_tree(root_path, item_absolute_path, respect_gitignore, respect_pathignore, pathignore_patterns)  # Recursive call
                html += '</ul>'
                html += '</li>'
            else:
                # Get file size and extension for better info
                try:
                    file_size = os.path.getsize(item_absolute_path)
                    file_size_str = format_size(file_size)
                    file_ext = os.path.splitext(item)[1].lower()
                except Exception:
                    file_size_str = "Unknown"
                    file_ext = ""

                html += f'<li class="file">'
                html += f'<input type="checkbox" class="file-checkbox" data-path="{relative_path}" data-size="{file_size}"> '
                html += f'<span class="file-name" data-ext="{file_ext}">{item}</span>'
                html += f'<span class="file-size badge badge-secondary">{file_size_str}</span></li>'
    except Exception as e:
        logger.error(f"Error generating file tree: {e}")
        html += f'<li>Error: {str(e)}</li>'

    html += '</ul>'  # Close top-level ul
    return html

@app.route('/', methods=['GET', 'POST'])
def index():
    absolute_root = session.get('absolute_root')
    # Ensure enable_global_hotkey is in session, default to True if not found
    enable_global_hotkey = session.get('enable_global_hotkey', True)

    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid request data'}), 400

            # Get optional ignore settings
            respect_gitignore = data.get('respect_gitignore', True)
            respect_pathignore = data.get('respect_pathignore', True)
            # Get raw pathignore text from JS and parse it
            pathignore_input_text = data.get('pathignore_input_text', session.get('pathignore_input_text', '')) # Use session as fallback
            parsed_pathignore_patterns = parse_ignore_patterns(pathignore_input_text) if respect_pathignore else []


            # Handle path from either navigation or initial input
            if 'path' in data:  # Navigation
                relative_path = data['path']
                if not absolute_root:
                    return jsonify({'error': 'Root path not set'}), 400

                # Security: ensure the path doesn't try to escape the root
                new_absolute_path = os.path.normpath(os.path.join(absolute_root, relative_path))
                if not is_valid_path(absolute_root, new_absolute_path):
                    return jsonify({'error': 'Invalid path access'}), 403

            elif 'absolute_path' in data:  # Initial path input
                new_absolute_path = os.path.normpath(data['absolute_path'])
            else:
                return jsonify({'error': "Invalid request parameters"}), 400

            # Verify the path exists and is a directory
            if not os.path.exists(new_absolute_path):
                return jsonify({'error': 'Directory does not exist'}), 404
            if not os.path.isdir(new_absolute_path):
                return jsonify({'error': 'Path is not a directory'}), 400

            session['absolute_root'] = new_absolute_path
            session['respect_gitignore'] = respect_gitignore
            session['respect_pathignore'] = respect_pathignore
            session['pathignore_patterns'] = parsed_pathignore_patterns # Store parsed list
            session['pathignore_input_text'] = pathignore_input_text # Store raw text for UI
            # max_size_kb is handled by generate_output or a dedicated settings update endpoint later
            write_current_config_to_file() # Write to config

            file_tree_html = generate_file_tree(
                new_absolute_path,
                new_absolute_path,
                respect_gitignore=respect_gitignore,
                respect_pathignore=respect_pathignore,
                pathignore_patterns=parsed_pathignore_patterns # Use parsed list for tree generation
            )
            return jsonify({'fileTree': file_tree_html})
        except Exception as e:
            logger.error(f"Error in index POST: {e}")
            return jsonify({'error': f"An error occurred: {str(e)}"}), 500

    else:  # GET request
        if absolute_root and os.path.exists(absolute_root):
            # If root is set (from previous navigation), regenerate tree
            file_tree_html = generate_file_tree(absolute_root, absolute_root)
        else:
            # Initial load: no root set, show empty tree
            file_tree_html = "<ul><li class='empty-prompt'>Enter a directory path above to begin.</li></ul>"

        return render_template('index.html', file_tree_html=file_tree_html, enable_global_hotkey=enable_global_hotkey)

@app.route('/api/settings/global_hotkey', methods=['POST'])
def api_settings_global_hotkey():
    try:
        data = request.get_json()
        if data is None or 'enabled' not in data:
            return jsonify({'success': False, 'error': 'Invalid request data. "enabled" field missing.'}), 400

        is_enabled = bool(data['enabled'])
        session['enable_global_hotkey'] = is_enabled
        write_current_config_to_file() # This will now include the new setting

        logger.info(f"Global hotkey setting updated to: {'Enabled' if is_enabled else 'Disabled'}")
        return jsonify({'success': True, 'message': f'Global hotkey has been {"enabled" if is_enabled else "disabled"}. Restart app for changes to take effect.'})
    except Exception as e:
        logger.error(f"Error updating global hotkey setting: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f'An internal error occurred: {str(e)}'}), 500

@app.route('/get_file_content', methods=['POST'])
def get_file_content():
    try:
        data = request.get_json()
        relative_path = data['path']
        absolute_root = session.get('absolute_root')

        if absolute_root is None:
            return jsonify({'error': "Root path not set."}), 400

        absolute_path = os.path.join(absolute_root, relative_path)

        # Security check
        if not is_valid_path(absolute_root, absolute_path):
            return jsonify({'error': 'Invalid path access'}), 403

        # Check file size before reading
        file_size = os.path.getsize(absolute_path)
        max_size = 5 * 1024 * 1024  # 5MB limit
        if file_size > max_size:
            return jsonify({'content': f"(File is too large ({format_size(file_size)}) to display inline)"})

        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252']
        content = None

        for encoding in encodings:
            try:
                with open(absolute_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break  # If successful, exit the loop
            except UnicodeDecodeError:
                continue

        if content is None:
            return jsonify({'content': "(Binary or non-text file - content not displayed)"})

        return jsonify({'content': content})

    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    except PermissionError:
        return jsonify({'error': 'Permission denied to access this file'}), 403
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_output', methods=['POST'])
def generate_output():
    try:
        data = request.get_json()
        selected_files = data.get('selectedFiles', [])
        max_size_kb = int(data.get('maxSizeKB', session.get('max_size_kb', 100))) # Use session as fallback
        session['max_size_kb'] = max_size_kb # Store/update in session
        write_current_config_to_file() # Update config file

        absolute_root = session.get('absolute_root')

        if not selected_files:
            return jsonify({'error': "No files selected"}), 400

        if absolute_root is None:
            return jsonify({'error': "Root path not set."}), 400

        # Use core function for generating output
        result = generate_output_content(selected_files, absolute_root, max_size_kb, include_binary=True)

        return jsonify({
            'message': 'Output generated successfully!',
            'files_txt': result['files_txt'],
            'project_map_txt': result['project_map_txt'],
            'skipped_files': result['stats']['skipped_files'],
            'binary_files': result['stats']['binary_files']
        })
    except Exception as e:
        logger.error(f"Error generating output: {e}")
        return jsonify({'error': str(e)}), 500


# API endpoints
@app.route('/api/browse', methods=['GET'])
def api_browse():
    """
    Browse a directory and get its file tree structure
    
    Query parameters:
    - path: Directory path to browse
    - respect_gitignore: Whether to respect .gitignore files (true/false)
    - respect_pathignore: Whether to apply custom ignore patterns (true/false)
    - pathignore_patterns: Custom ignore patterns (comma-separated)
    - show_hidden: Whether to show hidden files (true/false)
    - set_as_root: Whether to set this path as root for future operations (true/false)
    """
    path = request.args.get('path')
    respect_gitignore_arg = request.args.get('respect_gitignore', 'true').lower() == 'true'
    respect_pathignore_arg = request.args.get('respect_pathignore', 'false').lower() == 'true'
    # For /api/browse, pathignore_patterns is a comma-separated string from query params
    pathignore_patterns_str = request.args.get('pathignore_patterns', '')
    parsed_pathignore_patterns_for_browse = parse_ignore_patterns(pathignore_patterns_str.replace(',', '\n')) if respect_pathignore_arg else []

    show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
    set_as_root = request.args.get('set_as_root', 'true').lower() == 'true'
    
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Invalid path'}), 400
        
    if not os.path.isdir(path):
        return jsonify({'error': 'Path is not a directory'}), 400
    
    if set_as_root:
        session['absolute_root'] = path
        session['respect_gitignore'] = respect_gitignore_arg
        session['respect_pathignore'] = respect_pathignore_arg
        # When setting root via API, we store the parsed patterns from the API call
        # and also the raw string version for consistency if the UI expects it.
        session['pathignore_patterns'] = parsed_pathignore_patterns_for_browse
        session['pathignore_input_text'] = pathignore_patterns_str.replace(',', '\n')
        # We assume max_size_kb is not changed by /api/browse, so we don't update it here.
        # If it needs to be updatable via /api/browse, a new query param would be needed.
        write_current_config_to_file()
    
    # Use the specific patterns for this browse request, not necessarily what's in session for pathignore
    file_tree_data = generate_file_tree_json(path, path, respect_gitignore_arg, respect_pathignore_arg, parsed_pathignore_patterns_for_browse, show_hidden)
    return jsonify({
        'file_tree': file_tree_data,
        'root_path': path
    })

@app.route('/api/select', methods=['POST'])
def api_select():
    """
    Select files based on criteria
    
    Request body:
    {
        "extension_filters": [".js", ".py"],     // Extensions to include
        "path_patterns": ["src/*"],              // Glob patterns
        "max_size_kb": 100,                      // Size limit
        "exclude_extensions": [".min.js"],       // Extensions to exclude
        "select_all": false,                     // Whether to select all files first
        "in_directory": "src"                    // Optional: only look in this subdirectory
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
        
    extension_filters = data.get('extension_filters', [])
    path_patterns = data.get('path_patterns', [])
    max_size_kb = data.get('max_size_kb', 100)
    exclude_extensions = data.get('exclude_extensions', [])
    select_all = data.get('select_all', False)
    in_directory = data.get('in_directory', '')
    
    # Get the root path from the session
    absolute_root = session.get('absolute_root')
    if not absolute_root:
        return jsonify({'error': 'Root path not set. Use /api/browse with set_as_root=true first.'}), 400
    
    # If a subdirectory is specified, adjust the search root
    search_root = absolute_root
    if in_directory:
        subdirectory_path = os.path.join(absolute_root, in_directory)
        if os.path.isdir(subdirectory_path):
            search_root = subdirectory_path
        else:
            return jsonify({'error': f'Specified directory "{in_directory}" not found'}), 400
    
    # Find files matching the criteria
    selected_files = []
    for root, dirs, files in os.walk(search_root):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, absolute_root).replace('\\', '/')
            
            # Skip hidden files
            if file.startswith('.') and file not in ['.gitignore', '.pathignore']:
                continue
                
            # Check exclude extensions first
            if any(relative_path.lower().endswith(ext.lower()) for ext in exclude_extensions):
                continue
                
            # If not using select_all mode, check extension filter
            if not select_all and extension_filters and not any(relative_path.lower().endswith(ext.lower()) for ext in extension_filters):
                continue
                
            # Check path patterns if specified
            if path_patterns and not any(fnmatch.fnmatch(relative_path, pattern) for pattern in path_patterns):
                continue
                
            # Check file size
            try:
                file_size = os.path.getsize(file_path)
                if max_size_kb > 0 and file_size > max_size_kb * 1024:
                    continue
                    
                selected_files.append({
                    'path': relative_path,
                    'size': file_size,
                    'size_formatted': format_size(file_size),
                    'extension': os.path.splitext(file)[1].lower()
                })
            except Exception as e:
                logger.error(f"Error getting file size for {file_path}: {e}")
    
    return jsonify({
        'selected_files': selected_files,
        'count': len(selected_files),
        'root_path': absolute_root
    })

@app.route('/api/generate', methods=['POST'])
def api_generate():
    """
    Generate output from selected files
    
    Request body:
    {
        "selected_files": ["path/to/file1.js", "path/to/file2.py"],
        "max_size_kb": 100,
        "include_project_map": true,
        "include_binary_files": false
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
        
    selected_files = data.get('selected_files', [])
    max_size_kb = data.get('max_size_kb', 100)
    include_project_map = data.get('include_project_map', True)
    include_binary_files = data.get('include_binary_files', False)
    
    if not selected_files:
        return jsonify({'error': 'No files selected'}), 400
    
    absolute_root = session.get('absolute_root')
    if not absolute_root:
        return jsonify({'error': 'Root path not set. Use /api/browse with set_as_root=true first.'}), 400
        
    result = generate_output_content(selected_files, max_size_kb, absolute_root, include_binary_files)
    
    response = {
        'files_txt': result['files_txt'],
        'stats': result['stats']
    }
    
    if include_project_map:
        response['project_map_txt'] = result['project_map_txt']
    
    return jsonify(response)

@app.route('/api/file', methods=['GET'])
def api_get_file():
    """
    Get the content of a specific file
    
    Query parameters:
    - path: Relative path to the file from the root
    """
    file_path = request.args.get('path')
    if not file_path:
        return jsonify({'error': 'No file path specified'}), 400
        
    absolute_root = session.get('absolute_root')
    if not absolute_root:
        return jsonify({'error': 'Root path not set. Use /api/browse with set_as_root=true first.'}), 400
    
    absolute_path = os.path.join(absolute_root, file_path)
    
    # Security check (even for local-only app it's good practice)
    if not os.path.normpath(absolute_path).startswith(os.path.normpath(absolute_root)):
        return jsonify({'error': 'Invalid file path'}), 403
    
    if not os.path.exists(absolute_path):
        return jsonify({'error': 'File not found'}), 404
        
    if not os.path.isfile(absolute_path):
        return jsonify({'error': 'Path is not a file'}), 400
    
    # Check file size before reading
    file_size = os.path.getsize(absolute_path)
    max_size = 5 * 1024 * 1024  # 5MB limit
    if file_size > max_size:
        return jsonify({'error': f'File too large ({format_size(file_size)})'}), 413
    
    # Try different encodings
    content = None
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(absolute_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        return jsonify({'error': 'Binary or non-text file', 'is_binary': True}), 415
    
    return jsonify({
        'content': content,
        'size': file_size,
        'size_formatted': format_size(file_size),
        'path': file_path
    })

@app.route('/api/hide', methods=['POST'])
def api_hide_extensions():
    """
    Hide files with specific extensions from selection
    
    Request body:
    {
        "extensions": [".min.js", ".map"]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
        
    extensions = data.get('extensions', [])
    if not extensions:
        return jsonify({'error': 'No extensions specified'}), 400
    
    # Store the hide extensions in session for future use
    session['hide_extensions'] = extensions
    
    return jsonify({
        'message': f'Set {len(extensions)} extensions to hide',
        'extensions': extensions
    })

@app.route('/api/reset', methods=['POST'])
def api_reset():
    """
    Reset current selection state
    """
    # Clear any stored selection data from session
    if 'hide_extensions' in session:
        del session['hide_extensions']
    
    return jsonify({
        'message': 'Selection state reset successfully'
    })

# Helper functions for the API
def generate_file_tree_json(root_path, current_path, respect_gitignore=True, respect_pathignore=False, pathignore_patterns=None, show_hidden=False):
    """Generate a JSON representation of the file tree structure."""
    result = {
        'name': os.path.basename(current_path) or current_path,
        'path': os.path.relpath(current_path, root_path).replace('\\', '/') if current_path != root_path else '.',
        'type': 'directory',
        'children': []
    }
    
    try:
        items = sorted(os.listdir(current_path))
        
        # Filter items based on ignore patterns
        filtered_items = []
        for item in items:
            item_path = os.path.join(current_path, item)
            
            # Skip hidden files and directories unless explicitly requested
            if not show_hidden and item.startswith('.') and item not in ['.gitignore', '.pathignore']:
                continue
                
            # Merge respect_pathignore into custom_patterns for core function
            combined_patterns = pathignore_patterns if respect_pathignore and pathignore_patterns else None
            if not should_ignore_path(item_path, root_path, respect_gitignore, combined_patterns):
                filtered_items.append(item)
        
        items = filtered_items
        
        # Sort directories first, then files
        directories = [item for item in items if os.path.isdir(os.path.join(current_path, item))]
        files = [item for item in items if os.path.isfile(os.path.join(current_path, item))]
        sorted_items = sorted(directories) + sorted(files)
        
        for item in sorted_items:
            item_absolute_path = os.path.join(current_path, item)
            relative_path = os.path.relpath(item_absolute_path, root_path)
            
            # Normalize path for consistent cross-platform behavior
            relative_path = relative_path.replace('\\', '/')
            
            if os.path.isdir(item_absolute_path):
                # Recursively process directories
                child = generate_file_tree_json(root_path, item_absolute_path, respect_gitignore, respect_pathignore, pathignore_patterns, show_hidden)
                result['children'].append(child)
            else:
                # Process files
                try:
                    file_size = os.path.getsize(item_absolute_path)
                    file_ext = os.path.splitext(item)[1].lower()
                except Exception:
                    file_size = 0
                    file_ext = ""
                    
                result['children'].append({
                    'name': item,
                    'path': relative_path,
                    'type': 'file',
                    'size': file_size,
                    'size_formatted': format_size(file_size),
                    'extension': file_ext
                })
    except Exception as e:
        logger.error(f"Error generating file tree JSON: {e}")
        
    return result


@app.route('/api/global_trigger_generate_and_copy', methods=['POST'])
def api_global_trigger_generate_and_copy():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400

        absolute_root = data.get('absolute_root')
        respect_gitignore = data.get('respect_gitignore', True)
        respect_pathignore = data.get('respect_pathignore', True)
        pathignore_patterns = data.get('pathignore_patterns', []) # Expecting parsed patterns
        max_size_kb = int(data.get('max_size_kb', 100))

        if not absolute_root or not os.path.exists(absolute_root) or not os.path.isdir(absolute_root):
            return jsonify({'error': 'Invalid or missing absolute_root path in request.'}), 400

        # Use the core function to collect files
        combined_patterns = pathignore_patterns if respect_pathignore and pathignore_patterns else None
        all_files_in_root = collect_files(absolute_root, respect_gitignore, combined_patterns)
        
        if not all_files_in_root:
            return jsonify({'error': 'No files found in the specified root after applying ignore rules.'}), 400

        # Generate content using the core helper function
        # Pass include_binary=False as a default, can be made configurable if needed
        output_data = generate_output_content(all_files_in_root, absolute_root, max_size_kb, include_binary=False)

        # Combine files.txt and project_map.txt for the clipboard
        combined_content = "========== FILES ==========\n\n"
        combined_content += output_data.get('files_txt', '')
        combined_content += "\n\n========== PROJECT MAP ==========\n\n"
        combined_content += output_data.get('project_map_txt', '')
        # Get selected_files from the payload sent by the hotkey listener
        selected_files_from_hotkey = data.get('selected_files', [])

        if not selected_files_from_hotkey:
            # Fallback or error if no files were selected according to the config
            # For now, let's try to process all files if none are explicitly selected by hotkey config.
            # This maintains previous behavior if last_selected_files isn't in config yet.
            logger.warning("No 'selected_files' in hotkey payload, attempting to process all files in root.")
            combined_patterns = pathignore_patterns if respect_pathignore and pathignore_patterns else None
            all_files_in_root = collect_files(absolute_root, respect_gitignore, combined_patterns)
            
            if not all_files_in_root:
                 return jsonify({'error': 'No files found in the specified root after applying ignore rules (fallback).'}), 400
            selected_files_to_process = all_files_in_root
        else:
            selected_files_to_process = selected_files_from_hotkey
            logger.info(f"Global trigger processing specific files: {selected_files_to_process}")


        # Generate content using the core helper function with the determined list of files
        output_data = generate_output_content(selected_files_to_process, absolute_root, max_size_kb, include_binary=False)

        # Combine files.txt and project_map.txt for the clipboard
        combined_content = "========== FILES ==========\n\n"
        combined_content += output_data.get('files_txt', '')
        combined_content += "\n\n========== PROJECT MAP ==========\n\n"
        combined_content += output_data.get('project_map_txt', '')
        # Optionally add stats
        stats = output_data.get('stats', {})
        combined_content += "\n\n========== STATISTICS ==========\n\n"
        combined_content += f"Total Files Processed: {stats.get('total_files', len(selected_files_to_process))}\n" # Use count of processed files
        combined_content += f"Character Count: {stats.get('character_count', 0)}\n"
        combined_content += f"Estimated Tokens: {stats.get('estimated_tokens', 0)}\n"
        combined_content += f"Skipped Files (size): {stats.get('skipped_files', 0)}\n"
        combined_content += f"Binary Files (content not included): {stats.get('binary_files', 0)}\n"


        logger.info(f"Global trigger: Generated content for {len(selected_files_to_process)} files from {absolute_root}")
        return jsonify({
            'message': 'Content generated successfully for global trigger.',
            'combined_content': combined_content,
            'stats': output_data.get('stats')
        })

    except Exception as e:
        logger.error(f"Error in /api/global_trigger_generate_and_copy: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'An internal error occurred: {str(e)}'}), 500

@app.route('/api/update_current_selection', methods=['POST'])
def api_update_current_selection():
    try:
        data = request.get_json()
        selected_files = data.get('selectedFiles', [])
        
        # Store in session
        session['last_selected_files'] = selected_files
        
        # Also write to the config file so the hotkey listener can pick it up
        write_current_config_to_file()
        
        logger.info(f"Updated last_selected_files in session and config: {len(selected_files)} files.")
        return jsonify({'message': f'Successfully updated current selection with {len(selected_files)} files.'}), 200
    except Exception as e:
        logger.error(f"Error in /api/update_current_selection: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'An internal error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    # --- Start Keyboard Listener in a separate thread ---
    # Check if Flask is being run by the reloader or directly
    # We only want to start the listener thread in the main process, not the reloader's child process.
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        listener_logger.info("Flask reloader active or not main process, listener thread will not be started by this instance.")
    else:
        listener_logger.info("Main Flask process detected. Starting keyboard listener thread.")
        listener_thread = threading.Thread(target=setup_keyboard_listener, daemon=True)
        listener_thread.start()
        # Attempt to clean up hotkeys when the app exits
        atexit.register(stop_keyboard_listener)
        listener_logger.info("Keyboard listener thread started and atexit cleanup registered.")

    # Run Flask app
    # IMPORTANT: use_reloader=False is often recommended when managing background threads like this,
    # as the reloader can cause the setup_keyboard_listener to run multiple times or in unexpected ways.
    # However, for development, the reloader is very useful.
    # If issues arise with duplicate hotkey registrations or thread problems, set use_reloader=False.
    # For now, we'll rely on the WERKZEUG_RUN_MAIN check.
    app.run(debug=True, port=5023) # Default use_reloader is True if debug is True
