import keyboard
import pyperclip
import requests
import json
import os
import time
import logging
import traceback
from logging.handlers import RotatingFileHandler

# --- Configuration ---
FLASK_APP_URL = "http://127.0.0.1:5023"  # Default Flask server URL
API_ENDPOINT = f"{FLASK_APP_URL}/api/global_trigger_generate_and_copy"
CONFIG_FILE_NAME = 'filestoai_config.json'
# Place config file in the same directory as this script
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE_NAME)
HOTKEY = "ctrl+shift+space"
DEBOUNCE_SECONDS = 2 # Prevent multiple rapid triggers

# --- Logging Setup ---
LOG_FILE_NAME = 'global_hotkey_listener.log'
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILE_NAME)

# Configure logger
logger = logging.getLogger("GlobalHotkeyListener")
logger.setLevel(logging.INFO)
# Create a rotating file handler
# Max 1MB per file, keep 3 backup files
rfh = RotatingFileHandler(LOG_FILE_PATH, maxBytes=1*1024*1024, backupCount=3, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
rfh.setFormatter(formatter)
logger.addHandler(rfh)
# Also log to console for immediate feedback when running directly
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

last_triggered_time = 0

def read_config():
    """Reads the configuration from the JSON file."""
    try:
        if not os.path.exists(CONFIG_FILE_PATH):
            logger.warning(f"Config file not found at {CONFIG_FILE_PATH}. Waiting for app to create it.")
            return None
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.info(f"Successfully read config: {config}")
            return config
    except FileNotFoundError:
        logger.error(f"Config file {CONFIG_FILE_PATH} not found.")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {CONFIG_FILE_PATH}.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while reading config: {e}")
        return None

def trigger_generate_and_copy():
    """Reads config, calls the Flask API, and copies the result to clipboard."""
    global last_triggered_time
    logger.info(f"--- Hotkey callback triggered for '{HOTKEY}' ---") # Log entry immediately
    global last_triggered_time
    current_time = time.time()

    if current_time - last_triggered_time < DEBOUNCE_SECONDS:
        logger.info(f"Debounce: Hotkey '{HOTKEY}' triggered too soon. Ignoring. Last: {last_triggered_time:.2f}, Current: {current_time:.2f}, Diff: {current_time - last_triggered_time:.2f}s")
        return

    logger.info(f"Processing hotkey '{HOTKEY}' press. Attempting to trigger generation.")
    
    config = read_config()
    if not config:
        logger.error("Failed to read configuration. Aborting.")
        # Optionally, provide user feedback here (e.g., system notification)
        return

    absolute_root = config.get('absolute_root')
    if not absolute_root:
        logger.error("Absolute root path not found in config. Aborting.")
        return
    
    # Ensure all necessary keys are present, providing defaults if reasonable
    payload = {
        'absolute_root': absolute_root,
        'respect_gitignore': config.get('respect_gitignore', True),
        'respect_pathignore': config.get('respect_pathignore', True),
        'pathignore_patterns': config.get('pathignore_patterns', []),
        'max_size_kb': config.get('max_size_kb', 250),
        'selected_files': config.get('last_selected_files', []) # Add this
    }

    if not payload['selected_files']:
        logger.warning("No 'last_selected_files' found in config. The API will likely process all files in the root.")
        # The API endpoint has a fallback to process all files if 'selected_files' is empty or missing.

    logger.info(f"Sending payload to API: {payload}")

    try:
        response = requests.post(API_ENDPOINT, json=payload, timeout=60) # 60 second timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        response_data = response.json()
        if response_data.get('combined_content'):
            pyperclip.copy(response_data['combined_content'])
            logger.info("Successfully generated and copied content to clipboard.")
            logger.info(f"Stats: {response_data.get('stats')}")
            # Optionally, show a success notification to the user here
        else:
            logger.error(f"API response missing 'combined_content'. Response: {response_data}")

    except requests.exceptions.ConnectionError:
        logger.error(f"Connection to Flask app ({FLASK_APP_URL}) failed. Is the app running?")
    except requests.exceptions.Timeout:
        logger.error("Request to Flask app timed out.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
    except pyperclip.PyperclipException as e:
        logger.error(f"Error with clipboard: {e}. Is a copy/paste mechanism installed (e.g., xclip or xsel on Linux)?")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        logger.error(traceback.format_exc())
    
    last_triggered_time = current_time

# Store registered hotkeys to unhook them specifically if needed, though unhook_all is usually fine.
_registered_hotkeys = []

def setup_keyboard_listener():
    global _registered_hotkeys
    logger.info("--- Global Hotkey Listener starting up (called by app.py) ---")
    logger.info(f"Attempting to register main hotkey: {HOTKEY}")
    logger.info(f"Flask API endpoint: {API_ENDPOINT}")
    logger.info(f"Config file path: {CONFIG_FILE_PATH}")
    logger.info(f"Log file path: {LOG_FILE_PATH}")
    logger.info(f"Debounce time: {DEBOUNCE_SECONDS} seconds")

    # --- Test Hotkey (for basic keyboard library functionality check) ---
    TEST_HOTKEY = "f12" # Keep this for debugging if needed
    def test_hotkey_callback():
        logger.info(f"--- TEST HOTKEY ({TEST_HOTKEY}) PRESSED SUCCESSFULLY! Keyboard library is hooking keys. ---")
    
    try:
        # keyboard.add_hotkey(TEST_HOTKEY, test_hotkey_callback) # Comment out for production to avoid F12 doing this
        # logger.info(f"Successfully registered TEST hotkey: {TEST_HOTKEY}. Press {TEST_HOTKEY} to check if basic hooking works.")
        _registered_hotkeys.append(TEST_HOTKEY) # Still track if we were to enable it
        pass # Not registering test hotkey by default when run by app.py
    except Exception as e:
        logger.error(f"Failed to register TEST hotkey ({TEST_HOTKEY}): {e}.")

    # --- Main Hotkey Registration ---
    try:
        keyboard.add_hotkey(HOTKEY, trigger_generate_and_copy)
        _registered_hotkeys.append(HOTKEY)
        logger.info(f"Successfully registered MAIN hotkey: {HOTKEY}")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to register MAIN hotkey ({HOTKEY}): {e}")
        logger.error("The application's core hotkey functionality will NOT work.")
        logger.error("Try running the main Flask app (app.py) with administrator/root privileges.")
        return # Important to return if main hotkey fails

    # Check if config file exists at start, create a default one if not
    # This logic is good to keep, as app.py might be run for the first time
    if not os.path.exists(CONFIG_FILE_PATH):
        logger.warning(f"Config file {CONFIG_FILE_PATH} not found. Creating a default one.")
        logger.warning("Please run the FilesToAI web application once to populate it with your desired settings.")
        default_config = {
            'absolute_root': None, # User needs to set this via the web app
            'respect_gitignore': True,
            'respect_pathignore': True,
            'pathignore_patterns': ["node_modules/", "*.log", ".DS_Store", "__pycache__/"], # Default parsed
            'pathignore_input_text': "node_modules/\n*.log\n.DS_Store\n__pycache__/", # Default raw text
            'max_size_kb': 250,
            'last_selected_files': [] # Default empty list
        }
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            logger.info(f"Created default config file: {CONFIG_FILE_PATH}")
        except Exception as e:
            logger.error(f"Error creating default config file: {e}")


    logger.info(f"Keyboard listener setup complete. Hotkeys '{HOTKEY}' (and test '{TEST_HOTKEY}' if enabled) are active.")
    # No keyboard.wait() here, as this function will be run in a thread managed by app.py
    # The keyboard library handles listening in its own background threads.

def stop_keyboard_listener():
    logger.info("--- Attempting to stop Global Hotkey Listener and unhook keys ---")
    try:
        # Unhook specific hotkeys if tracked, or all
        # for hotkey_str in _registered_hotkeys:
        #     keyboard.remove_hotkey(hotkey_str)
        # logger.info(f"Unhooked specific hotkeys: {_registered_hotkeys}")
        keyboard.unhook_all() # Simpler and generally effective
        logger.info("All global hotkeys have been unhooked.")
    except Exception as e:
        logger.error(f"Error during keyboard listener stop: {e}")
        logger.error(traceback.format_exc())

# This block is for running the listener standalone (for testing/debugging)
if __name__ == "__main__":
    setup_keyboard_listener()
    if HOTKEY in keyboard.all_hotkeys(): # Check if main hotkey was actually registered
        logger.info(f"Listener is active (standalone mode). Press '{HOTKEY}' to trigger. Press 'Esc' to stop this script.")
        try:
            keyboard.wait('esc')
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received in standalone mode.")
        finally:
            stop_keyboard_listener()
    else:
        logger.error(f"Main hotkey {HOTKEY} failed to register in standalone mode. Exiting.")
