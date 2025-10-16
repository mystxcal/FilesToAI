"""Setup script for FilesToAI package."""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

setup(
    name="filestoai",
    version="1.0.0",
    author="mystxcal",
    description="Export your codebase for AI consumption - CLI and Web Interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mystxcal/FilesToAI",
    py_modules=['cli', 'core', 'app', 'global_hotkey_listener'],
    install_requires=[
        "Flask>=2.3.0",
        "keyboard>=0.13.5",
        "pyperclip>=1.8.2",
        "requests>=2.31.0",
    ],
    entry_points={
        'console_scripts': [
            'filestoai=cli:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    keywords="ai, codebase, export, cli, llm, chatgpt, claude",
)

