"""Core functionality for FilesToAI - reusable logic for both CLI and web interface."""
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def format_size(size_bytes):
    """Convert size in bytes to human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


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
    
    # Handle character class [] BEFORE escaping
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


def should_ignore_path(path, root_path, respect_gitignore=True, custom_patterns=None, debug=False):
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

    # Add custom patterns
    if custom_patterns:
        patterns.extend(custom_patterns)

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


def collect_files(root_path, respect_gitignore=True, custom_patterns=None):
    """
    Collect all files from the root path, respecting ignore patterns.
    Returns a list of relative file paths.
    """
    collected_files = []
    
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter directories to ignore
        abs_dirnames = [os.path.join(dirpath, dn) for dn in dirnames]
        dirnames[:] = [
            dn for dn, abs_dn in zip(dirnames, abs_dirnames)
            if not should_ignore_path(abs_dn, root_path, respect_gitignore, custom_patterns)
        ]

        for filename in filenames:
            # Skip hidden files except .gitignore
            if filename.startswith('.') and filename not in ['.gitignore', '.pathignore']:
                continue
                
            file_path = os.path.join(dirpath, filename)
            if not should_ignore_path(file_path, root_path, respect_gitignore, custom_patterns):
                rel_path = os.path.relpath(file_path, root_path).replace('\\', '/')
                collected_files.append(rel_path)
    
    return collected_files


def generate_output_content(selected_files, root_path, max_size_kb=100, include_binary=False):
    """
    Generate the output content for selected files.
    Returns a dictionary with files_txt, project_map_txt, and stats.
    """
    max_size_bytes = max_size_kb * 1024
    files_txt_content = ""
    skipped_files = []
    binary_files = []
    
    for relative_file_path in selected_files:
        relative_file_path = relative_file_path.replace('\\', '/')
        absolute_file_path = os.path.join(root_path, relative_file_path)
        
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
                if include_binary:
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
    
    project_map_txt_content = create_project_map(selected_files)
    
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


def create_project_map(file_paths):
    """Creates a project map from file paths."""
    root = {}
    try:
        for relative_file_path in file_paths:
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
            
            if is_last:
                branch = "└── "
                child_prefix = prefix + "    "
            else:
                branch = "├── "
                child_prefix = prefix + "│   "
            
            map_str += f"{prefix}{branch}{key}/\n"
            map_str += dict_to_map_string(value, child_prefix)
            
        # Process files
        for i, key in enumerate(sorted_files):
            current_item += 1
            is_last = current_item == total_items
            
            if is_last:
                branch = "└── "
            else:
                branch = "├── "
                
            map_str += f"{prefix}{branch}{key}\n"
            
        return map_str

    project_map = "Directory structure:\n" + dict_to_map_string(root)
    return project_map

