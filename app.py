from flask import Flask, render_template, request, jsonify, send_from_directory, session
import os
import secrets
import traceback
import logging
from pathlib import Path
import fnmatch
import re

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(16)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(f"Current Working Directory: {os.getcwd()}")


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

def gitignore_pattern_to_regex(pattern):
    """Converts a gitignore pattern to a regular expression."""

    # Handle trailing slashes (directories)
    is_dir_pattern = False
    if pattern.endswith('\\/'):  # Check for escaped slash
        pattern = pattern[:-2] + '/' # Remove the escaping
    elif pattern.endswith('/'):
        is_dir_pattern = True
        pattern = pattern[:-1]

    # Handle **
    pattern = pattern.replace('\\*\\*', '{starstar}')  # Temporary placeholder
    pattern = pattern.replace('**', '.*') # zero or more directories
    pattern = pattern.replace('{starstar}', '(?:.*/)?') # Match zero or more directories

    # Handle * and ? BEFORE escaping
    pattern = pattern.replace('\\?', '.')  # Match any single character (except /)
    pattern = pattern.replace('\\*', '[^/]*')  # Match anything except /
    
    # NEW: Handle character class [] BEFORE escaping
    parts = []
    in_class = False
    for i, char in enumerate(pattern):
        if char == '[':
            in_class = True
            parts.append(char)
        elif char == ']':
            in_class = False
            parts.append(char)
        elif in_class and char == '-':  # Only escape - inside [] if between chars
            # Check if '-' is at the start/end or next to another special char
            if i > 0 and pattern[i-1] != '[' and i < len(pattern) -1 and pattern[i+1] != ']':
              parts.append('\\-') # Escape it
            else:
              parts.append(char) # Don't escape
        else:
            parts.append(char)

    pattern = "".join(parts)

    # Escape special regex characters NOW, after [], *, and ?
    pattern = re.escape(pattern)

    # Unescape characters we handled earlier
    pattern = pattern.replace('\\.', '.') # Restore .
    pattern = pattern.replace('\\[', '[')  # Restore [
    pattern = pattern.replace('\\]', ']')  # Restore ]
    
    # Handle leading slash 
    if pattern.startswith('/'): 
        pattern = '^' + pattern[1:]  # Match from beginning of path, remove leading slash
    elif pattern.startswith('\\/'): # check for escaped slash second (less common)
        pattern = '^' + pattern[2:]  # Match from beginning of path, remove escaped slash
    else: # No leading slash
        pattern = '^(?:.*/)?' + pattern  # Match anywhere in the path


    if is_dir_pattern:
            pattern += '(?:/.*)?$' # Must be followed by / or end of string.
    else:
        pattern += '$'

    return pattern

def parse_ignore_file(ignore_file_path):
    """Parse .gitignore or .pathignore file and return patterns"""
    patterns = []
    if not os.path.exists(ignore_file_path):
        return patterns

    try:
        with open(ignore_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'): # Skip empty lines/comments
                    patterns.append(line)
    except Exception as e:
        logger.error(f"Error parsing ignore file {ignore_file_path}: {e}")

    return patterns

def parse_ignore_patterns(patterns_text):
    """Parse ignore patterns from a string (each pattern on a new line)"""
    patterns = []
    if not patterns_text:
        return patterns

    for line in patterns_text.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            patterns.append(line)
    return patterns


def should_ignore_path(path, root_path, respect_gitignore=True, respect_pathignore=True, pathignore_patterns=None, debug=False):
    """
    Check if a path should be ignored based on ignore patterns.
    """
    rel_path = os.path.relpath(path, root_path).replace('\\', '/')
    is_dir = os.path.isdir(path)

    if debug:
        logger.debug(f"Checking ignore status for: {rel_path} (is_dir={is_dir})")

    ignored = False  # Default: not ignored
    patterns = []

    # Gather patterns from .gitignore, if enabled
    if respect_gitignore:
        gitignore_path = os.path.join(root_path, '.gitignore')
        patterns.extend(parse_ignore_file(gitignore_path))

    # Add custom pathignore patterns, if enabled
    if respect_pathignore and pathignore_patterns:
        patterns.extend(pathignore_patterns)

    if not patterns:
        if debug: logger.debug("No ignore patterns to check.")
        return False

    for pattern in patterns:
        # Handle negation
        negate = False
        if pattern.startswith('!'):
            negate = True
            pattern = pattern[1:]

        regex_pattern = gitignore_pattern_to_regex(pattern)
        if debug: logger.debug(f"  Testing pattern: {pattern}  (regex: {regex_pattern})")

        match = re.search(regex_pattern, rel_path)

        if match:
            if debug: logger.debug(f"    Matched! Negate: {negate}")
            if negate:
                ignored = False  # Un-ignore
            else:
                # Directory check ONLY if it is a dir pattern.
                if pattern.endswith('/') and not is_dir:
                  continue # Skip.
                ignored = True  # Ignore

    if debug: logger.debug(f"Final ignore status for {rel_path}: {ignored}")
    return ignored


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
                if not should_ignore_path(item_path, root_path, respect_gitignore, respect_pathignore, pathignore_patterns):
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

def format_size(size_bytes):
    """Convert size in bytes to human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

@app.route('/', methods=['GET', 'POST'])
def index():
    absolute_root = session.get('absolute_root')

    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid request data'}), 400

            # Get optional ignore settings
            respect_gitignore = data.get('respect_gitignore', True)
            respect_pathignore = data.get('respect_pathignore', True)
            pathignore_patterns = data.get('pathignore_patterns', [])

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

            session['absolute_root'] = new_absolute_path  # Update session
            file_tree_html = generate_file_tree(
                new_absolute_path,
                new_absolute_path,
                respect_gitignore=respect_gitignore,
                respect_pathignore=respect_pathignore,
                pathignore_patterns=pathignore_patterns
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

        return render_template('index.html', file_tree_html=file_tree_html)

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
        max_size_kb = int(data.get('maxSizeKB', 250))
        absolute_root = session.get('absolute_root')

        if not selected_files:
            return jsonify({'error': "No files selected"}), 400

        if absolute_root is None:
            return jsonify({'error': "Root path not set."}), 400

        max_size_bytes = max_size_kb * 1024
        files_txt_content = ""
        skipped_files = []
        binary_files = []

        for relative_file_path in selected_files:
            # Normalize path
            relative_file_path = relative_file_path.replace('\\', '/')
            absolute_file_path = os.path.join(absolute_root, relative_file_path)

            # Security check
            if not is_valid_path(absolute_root, absolute_file_path):
                continue

            logger.info(f"Processing file: {absolute_file_path}")

            try:
                file_size = os.path.getsize(absolute_file_path)
                if file_size > max_size_bytes:
                    files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                    files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                    files_txt_content += f"(File size {format_size(file_size)} exceeds limit of {max_size_kb} KB)\n"
                    files_txt_content += "\n\n" + "=" * 40 + "\n\n"
                    skipped_files.append(relative_file_path)
                    continue

                # Try different encodings
                content = None
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(absolute_file_path, "r", encoding=encoding) as infile:
                            content = infile.read()
                        break
                    except UnicodeDecodeError:
                        continue

                if content is None:
                    files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                    files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                    files_txt_content += "(Binary or non-text file - content not included)\n"
                    files_txt_content += "\n\n" + "=" * 40 + "\n\n"
                    binary_files.append(relative_file_path)
                else:
                    files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                    files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                    files_txt_content += content
                    files_txt_content += "\n\n" + "=" * 40 + "\n\n"

            except Exception as e:
                logger.error(f"Error processing file {relative_file_path}: {e}")
                files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                files_txt_content += f"Error reading file: {e}\n"
                files_txt_content += "\n\n" + "=" * 40 + "\n\n"

        project_map_txt_content = create_project_map(selected_files, absolute_root)

        return jsonify({
            'message': 'Output generated successfully!',
            'files_txt': files_txt_content,
            'project_map_txt': project_map_txt_content,
            'skipped_files': len(skipped_files),
            'binary_files': len(binary_files)
        })
    except Exception as e:
        logger.error(f"Error generating output: {e}")
        return jsonify({'error': str(e)}), 500

def create_project_map(file_paths, absolute_root):
    """Creates a project map."""
    root = {}
    try:
        for relative_file_path in file_paths:
            # Normalize path
            relative_file_path = relative_file_path.replace('\\', '/')
            parts = relative_file_path.split('/')

            current_level = root
            for part in parts[:-1]:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
            current_level[parts[-1]] = None
    except Exception as e:
        logger.error(f"Error creating project map: {e}")
        return "Error generating project map."

    def dict_to_map_string(d, prefix=""):
        map_str = ""
        
        # Process directories first (with values that are dicts)
        dirs = {k: v for k, v in d.items() if isinstance(v, dict)}
        files = [k for k, v in d.items() if v is None]
        
        # Sort directories and files
        sorted_dirs = sorted(dirs.items())
        sorted_files = sorted(files)
        
        # Total items = dirs + files
        total_items = len(sorted_dirs) + len(sorted_files)
        
        # Track the current item for proper tree lines
        current_item = 0
        
        # Process directories
        for key, value in sorted_dirs:
            current_item += 1
            is_last = current_item == total_items
            
            # Use proper branch characters based on position
            if is_last:
                branch = "└── "
                child_prefix = prefix + "    "  # 4 spaces for alignment
            else:
                branch = "├── "
                child_prefix = prefix + "│   "  # Vertical line for children
            
            # Add directory with trailing slash
            map_str += f"{prefix}{branch}{key}/\n"
            
            # Process children with updated prefix
            map_str += dict_to_map_string(value, child_prefix)
            
        # Process files
        for i, key in enumerate(sorted_files):
            current_item += 1
            is_last = current_item == total_items
            
            # Use proper branch characters based on position
            if is_last:
                branch = "└── "
            else:
                branch = "├── "
                
            map_str += f"{prefix}{branch}{key}\n"
            
        return map_str

    project_map = "Directory structure:\n" + dict_to_map_string(root)
    return project_map

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
    respect_gitignore = request.args.get('respect_gitignore', 'true').lower() == 'true'
    respect_pathignore = request.args.get('respect_pathignore', 'false').lower() == 'true'
    pathignore_patterns = request.args.get('pathignore_patterns', '').split(',') if request.args.get('pathignore_patterns') else []
    show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
    set_as_root = request.args.get('set_as_root', 'true').lower() == 'true'
    
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Invalid path'}), 400
        
    if not os.path.isdir(path):
        return jsonify({'error': 'Path is not a directory'}), 400
    
    if set_as_root:
        session['absolute_root'] = path
    
    file_tree_data = generate_file_tree_json(path, path, respect_gitignore, respect_pathignore, pathignore_patterns, show_hidden)
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
        "max_size_kb": 250,                      // Size limit
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
    max_size_kb = data.get('max_size_kb', 250)
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
        "max_size_kb": 250,
        "include_project_map": true,
        "include_binary_files": false
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
        
    selected_files = data.get('selected_files', [])
    max_size_kb = data.get('max_size_kb', 250)
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
                
            if not should_ignore_path(item_path, root_path, respect_gitignore, respect_pathignore, pathignore_patterns):
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

def generate_output_content(selected_files, max_size_kb, absolute_root, include_binary_files=False):
    """Generate output content for files.txt and project_map.txt"""
    max_size_bytes = max_size_kb * 1024
    files_txt_content = ""
    skipped_files = []
    binary_files = []
    
    for relative_file_path in selected_files:
        # Normalize path
        relative_file_path = relative_file_path.replace('\\', '/')
        absolute_file_path = os.path.join(absolute_root, relative_file_path)
        
        try:
            file_size = os.path.getsize(absolute_file_path)
            if file_size > max_size_bytes:
                files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                files_txt_content += f"(File size {format_size(file_size)} exceeds limit of {max_size_kb} KB)\n"
                files_txt_content += "\n\n" + "=" * 40 + "\n\n"
                skipped_files.append(relative_file_path)
                continue
                
            # Try different encodings
            content = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(absolute_file_path, "r", encoding=encoding) as infile:
                        content = infile.read()
                    break
                except UnicodeDecodeError:
                    continue
                    
            if content is None:
                binary_files.append(relative_file_path)
                if include_binary_files:
                    files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                    files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                    files_txt_content += "(Binary or non-text file - content not included)\n"
                    files_txt_content += "\n\n" + "=" * 40 + "\n\n"
            else:
                files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
                files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
                files_txt_content += content
                files_txt_content += "\n\n" + "=" * 40 + "\n\n"
                
        except Exception as e:
            logger.error(f"Error processing file {relative_file_path}: {e}")
            files_txt_content += f"=== File: {os.path.basename(relative_file_path)} ===\n"
            files_txt_content += f"=== Path: {relative_file_path} ===\n\n"
            files_txt_content += f"Error reading file: {e}\n"
            files_txt_content += "\n\n" + "=" * 40 + "\n\n"
            
    project_map_txt_content = create_project_map(selected_files, absolute_root)
    
    # Calculate statistics
    char_count = len(files_txt_content)
    token_estimate = char_count // 4  # Rough estimate of tokens
    
    return {
        'files_txt': files_txt_content,
        'project_map_txt': project_map_txt_content,
        'stats': {
            'character_count': char_count,
            'estimated_tokens': token_estimate,
            'skipped_files': len(skipped_files),
            'binary_files': len(binary_files),
            'total_files': len(selected_files)
        }
    }

if __name__ == '__main__':
    app.run(debug=True, port=5023)