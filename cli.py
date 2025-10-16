#!/usr/bin/env python3
"""Command-line interface for FilesToAI."""
import argparse
import sys
import os
import logging
from pathlib import Path
import pyperclip
from core import (
    collect_files,
    generate_output_content,
    parse_ignore_patterns,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='FilesToAI - Export your codebase for AI consumption',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  filestoai .                          # Export current directory
  filestoai /path/to/project           # Export specific directory
  filestoai . -gi                      # Respect .gitignore
  filestoai . --size 200               # Set max file size to 200 KB
  filestoai . -gi --ignore "*.log,*.tmp"  # Custom ignore patterns
  filestoai . -o output.txt            # Save to file instead of clipboard
  filestoai . --no-copy                # Don't copy to clipboard
  filestoai . --project-map-only       # Only generate project map
  filestoai --server                   # Start web interface
  filestoai --server --port 8000       # Start web interface on custom port
        """
    )
    
    # Positional argument
    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Directory to process (default: current directory)'
    )
    
    # Optional arguments
    parser.add_argument(
        '-gi', '--gitignore',
        action='store_true',
        help='Respect .gitignore files'
    )
    
    parser.add_argument(
        '-s', '--size',
        type=int,
        default=100,
        metavar='KB',
        help='Maximum file size in KB (default: 100)'
    )
    
    parser.add_argument(
        '-i', '--ignore',
        type=str,
        default='',
        metavar='PATTERNS',
        help='Comma-separated ignore patterns (e.g., "*.log,node_modules/,*.tmp")'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        metavar='FILE',
        help='Output file path (default: copy to clipboard)'
    )
    
    parser.add_argument(
        '--no-copy',
        action='store_true',
        help='Do not copy to clipboard (only works with --output)'
    )
    
    parser.add_argument(
        '--include-binary',
        action='store_true',
        help='Include binary files in output (as placeholders)'
    )
    
    parser.add_argument(
        '--project-map-only',
        action='store_true',
        help='Only generate project map, skip file contents'
    )
    
    parser.add_argument(
        '--files-only',
        action='store_true',
        help='Only generate file contents, skip project map'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--list-files',
        action='store_true',
        help='List files that would be processed and exit'
    )
    
    parser.add_argument(
        '--server',
        action='store_true',
        help='Start the web interface server (Flask app)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5023,
        metavar='PORT',
        help='Port for web server (default: 5023, only works with --server)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle --server mode
    if args.server:
        logger.info(f"Starting FilesToAI web server on port {args.port}...")
        logger.info(f"Open your browser to: http://127.0.0.1:{args.port}")
        
        try:
            # Import Flask app
            from app import app as flask_app
            
            # Run the server
            flask_app.run(debug=True, port=args.port)
        except ImportError as e:
            logger.error(f"Error: Could not import Flask app. Make sure all dependencies are installed.")
            logger.error(f"Run: pip install -r requirements.txt")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            sys.exit(1)
        
        # Server mode exits here
        return
    
    # Resolve directory path
    directory = os.path.abspath(args.directory)
    
    if not os.path.exists(directory):
        logger.error(f"Error: Directory '{directory}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(directory):
        logger.error(f"Error: '{directory}' is not a directory")
        sys.exit(1)
    
    logger.info(f"Processing directory: {directory}")
    
    # Parse custom ignore patterns
    custom_patterns = []
    if args.ignore:
        custom_patterns = [p.strip() for p in args.ignore.split(',') if p.strip()]
        logger.info(f"Custom ignore patterns: {custom_patterns}")
    
    # Collect files
    logger.info("Collecting files...")
    files = collect_files(
        directory,
        respect_gitignore=args.gitignore,
        custom_patterns=custom_patterns
    )
    
    if not files:
        logger.warning("No files found to process")
        sys.exit(0)
    
    logger.info(f"Found {len(files)} files")
    
    # If --list-files, just print and exit
    if args.list_files:
        print(f"\nFiles to be processed ({len(files)} total):\n")
        for file in sorted(files):
            file_path = os.path.join(directory, file)
            try:
                size = os.path.getsize(file_path)
                size_str = format_file_size(size)
                print(f"  {file} ({size_str})")
            except:
                print(f"  {file}")
        sys.exit(0)
    
    # Generate output
    logger.info("Generating output...")
    result = generate_output_content(
        files,
        directory,
        max_size_kb=args.size,
        include_binary=args.include_binary
    )
    
    # Build final output
    output_parts = []
    
    if args.project_map_only:
        output_parts.append("========== PROJECT MAP ==========\n")
        output_parts.append(result['project_map_txt'])
    elif args.files_only:
        output_parts.append("========== FILES ==========\n")
        output_parts.append(result['files_txt'])
    else:
        # Include both
        output_parts.append("========== FILES ==========\n")
        output_parts.append(result['files_txt'])
        output_parts.append("\n========== PROJECT MAP ==========\n")
        output_parts.append(result['project_map_txt'])
    
    # Add statistics
    stats = result['stats']
    output_parts.append("\n========== STATISTICS ==========\n")
    output_parts.append(f"Total Files: {stats['total_files']}\n")
    output_parts.append(f"Character Count: {stats['character_count']:,}\n")
    output_parts.append(f"Estimated Tokens: {stats['estimated_tokens']:,}\n")
    output_parts.append(f"Skipped (size): {stats['skipped_files']}\n")
    output_parts.append(f"Binary Files: {stats['binary_files']}\n")
    
    final_output = ''.join(output_parts)
    
    # Display statistics
    print("\n" + "="*50)
    print("STATISTICS")
    print("="*50)
    print(f"Total Files: {stats['total_files']}")
    print(f"Character Count: {stats['character_count']:,}")
    print(f"Estimated Tokens: {stats['estimated_tokens']:,}")
    print(f"Skipped (size): {stats['skipped_files']}")
    print(f"Binary Files: {stats['binary_files']}")
    print("="*50 + "\n")
    
    # Handle output
    if args.output:
        # Save to file
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(final_output)
            logger.info(f"Output saved to: {args.output}")
            
            # Also copy to clipboard unless --no-copy is set
            if not args.no_copy:
                try:
                    pyperclip.copy(final_output)
                    logger.info("Output copied to clipboard")
                except Exception as e:
                    logger.warning(f"Could not copy to clipboard: {e}")
        except Exception as e:
            logger.error(f"Error saving output file: {e}")
            sys.exit(1)
    else:
        # Copy to clipboard by default
        try:
            pyperclip.copy(final_output)
            logger.info("✓ Output copied to clipboard!")
            print("✓ Content has been copied to your clipboard!")
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            print("\nOutput content:\n")
            print(final_output)
            sys.exit(1)


def format_file_size(size_bytes):
    """Format file size for display."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


if __name__ == '__main__':
    main()

