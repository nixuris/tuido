
import json
from pathlib import Path

def ensure_config(config_dir, tasks_file, keybinds_file):
    """Create the config directory and default files if they don't exist."""
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Default tasks
    if not tasks_file.exists():
        default_tasks = [
            {'task': 'Task 1', 'checked': False, 'context': 'Work'},
            {'task': 'Task 2', 'checked': True, 'context': 'Personal'},
            {'task': 'Task 3', 'checked': False, 'context': 'Work'},
        ]
        with open(tasks_file, 'w') as f:
            json.dump(default_tasks, f, indent=2)
    
    # Default keybinds
    if not keybinds_file.exists():
        default_keybinds = {
            'toggle': ' ',
            'edit': 'e',
            'add_task': 'a',
            'add_context': 'n',
            'next_context': 'KEY_RIGHT',
            'previous_context': 'KEY_LEFT',
            'move_down': 'KEY_DOWN',
            'move_up': 'KEY_UP',
            'quit': 'q',
            'edit_keybinds': 'k',
            'delete_task': 'd',
            'delete_context': 'D',
            'rename_context': 'r',
            'kanban_view': 'v',
            'show_stats': 's',
            'add_tag': 't',
            'set_due_date': 'u',
            'search_tasks': '/',
            'toggle_priority': 'p',
            'undo': 'z',
            'exit_search': 'ESC'
        }
        with open(keybinds_file, 'w') as f:
            json.dump(default_keybinds, f, indent=2)

def load_tasks(tasks_file):
    """Load tasks from the JSON file. Fall back to defaults if the file is invalid."""
    try:
        with open(tasks_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [
            {'task': 'Task 1', 'checked': False, 'context': 'Work'},
            {'task': 'Task 2', 'checked': True, 'context': 'Personal'},
            {'task': 'Task 3', 'checked': False, 'context': 'Work'},
        ]

def load_keybinds(keybinds_file):
    """Load keybinds from the JSON file. Fall back to defaults if the file is invalid."""
    try:
        with open(keybinds_file, 'r') as f:
            keybinds = json.load(f)
            
            # Ensure all required keybinds exist
            default_keys = {
                'toggle': ' ', 'edit': 'e', 'add_task': 'a', 'add_context': 'n',
                'next_context': 'KEY_RIGHT', 'previous_context': 'KEY_LEFT',
                'move_down': 'KEY_DOWN', 'move_up': 'KEY_UP', 'quit': 'q',
                'edit_keybinds': 'k', 'delete_task': 'd',
                'delete_context': 'D', 'rename_context': 'r', 'kanban_view': 'v',
                'show_stats': 's', 'add_tag': 't', 'set_due_date': 'u',
                'search_tasks': '/', 'toggle_priority': 'p', 'undo': 'z',
                'exit_search': 'ESC'
            }
            
            # Add any missing keys
            for action, key in default_keys.items():
                if action not in keybinds:
                    keybinds[action] = key
            return keybinds
            
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'toggle': ' ', 'edit': 'e', 'add_task': 'a', 'add_context': 'n',
            'next_context': 'KEY_RIGHT', 'previous_context': 'KEY_LEFT',
            'move_down': 'KEY_DOWN', 'move_up': 'KEY_UP', 'quit': 'q',
            'edit_keybinds': 'k', 'delete_task': 'd',
            'delete_context': 'D', 'rename_context': 'r', 'kanban_view': 'v',
            'show_stats': 's', 'add_tag': 't', 'set_due_date': 'u',
            'search_tasks': '/', 'toggle_priority': 'p', 'undo': 'z',
            'exit_search': 'ESC'
        }

def save_tasks(tasks_file, todo_items):
    """Save tasks to the JSON file."""
    with open(tasks_file, 'w') as f:
        json.dump(todo_items, f, indent=2)

def save_keybinds(keybinds_file, keybinds):
    """Save keybinds to the JSON file."""
    with open(keybinds_file, 'w') as f:
        json.dump(keybinds, f, indent=2)
