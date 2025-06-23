import os
import json
import curses
import time
from pathlib import Path
import copy

class TodoApp:
    def __init__(self):
        # Set up config directory and file paths
        self.config_dir = Path.home() / ".config" / "tuido"
        self.tasks_file = self.config_dir / "tasks.json"
        self.keybinds_file = self.config_dir / "keybinds.json"
        
        # Ensure the config directory and files exist
        self.ensure_config()
        
        # Load tasks and keybinds
        self.load_tasks()
        self.load_keybinds()
        
        # Set initial state
        self.current_context = self.contexts[0] if self.contexts else "Work"
        self.selected_index = 0
        self.editing_keybind = None  # Track which keybind is being edited
        self.editing_keybind_ui = False  # Track if keybind UI is active
        self.selected_keybind = 0  # Selected keybind in the list
        self.error_message = None  # Error message during keybind editing
        self.in_kanban_view = False  # Track if we're in kanban view
        self.in_search_mode = False  # Track if we're in search mode
        self._search_results = []  # Store search results
        self._prev_state = None  # Store state before search
        
        # Caching variables
        self._filtered_tasks_cache = {}  # Cache for filtered tasks by context
        self._last_save_time = time.time()  # For batched saving
        self._dirty = False  # Flag to track if data needs saving
        
        self.history = []
        self.future = []
        self.max_history = 50

    def ensure_config(self):
        """Create the config directory and default files if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Default tasks
        if not self.tasks_file.exists():
            default_tasks = [
                {'task': 'Task 1', 'checked': False, 'context': 'Work'},
                {'task': 'Task 2', 'checked': True, 'context': 'Personal'},
                {'task': 'Task 3', 'checked': False, 'context': 'Work'},
            ]
            with open(self.tasks_file, 'w') as f:
                json.dump(default_tasks, f, indent=2)
        
        # Default keybinds
        if not self.keybinds_file.exists():
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
            with open(self.keybinds_file, 'w') as f:
                json.dump(default_keybinds, f, indent=2)

    def load_tasks(self):
        """Load tasks from the JSON file. Fall back to defaults if the file is invalid."""
        try:
            with open(self.tasks_file, 'r') as f:
                self.todo_items = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.todo_items = [
                {'task': 'Task 1', 'checked': False, 'context': 'Work'},
                {'task': 'Task 2', 'checked': True, 'context': 'Personal'},
                {'task': 'Task 3', 'checked': False, 'context': 'Work'},
            ]
        self.contexts = list(set(item['context'] for item in self.todo_items))
        # Clear cache when loading tasks
        self._filtered_tasks_cache = {}

    def load_keybinds(self):
        """Load keybinds from the JSON file. Fall back to defaults if the file is invalid."""
        try:
            with open(self.keybinds_file, 'r') as f:
                self.keybinds = json.load(f)
                
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
                    if action not in self.keybinds:
                        self.keybinds[action] = key
                        
        except (FileNotFoundError, json.JSONDecodeError):
            self.keybinds = {
                'toggle': ' ', 'edit': 'e', 'add_task': 'a', 'add_context': 'n',
                'next_context': 'KEY_RIGHT', 'previous_context': 'KEY_LEFT',
                'move_down': 'KEY_DOWN', 'move_up': 'KEY_UP', 'quit': 'q',
                'edit_keybinds': 'k', 'delete_task': 'd',
                'delete_context': 'D', 'rename_context': 'r', 'kanban_view': 'v',
                'show_stats': 's', 'add_tag': 't', 'set_due_date': 'u',
                'search_tasks': '/', 'toggle_priority': 'p', 'undo': 'z',
                'exit_search': 'ESC'
            }

    def get_filtered_tasks(self, context=None):
        """Get tasks filtered by context, with caching."""
        # If in search mode, return search results instead
        if self.in_search_mode:
            return self._search_results
            
        context = context or self.current_context
        
        # Check if we have a cached result
        if context not in self._filtered_tasks_cache:
            self._filtered_tasks_cache[context] = [
                item for item in self.todo_items if item['context'] == context
            ]
        
        return self._filtered_tasks_cache[context]

    def invalidate_cache(self, context=None):
        """Invalidate the cache for a specific context or all contexts."""
        if context:
            if context in self._filtered_tasks_cache:
                del self._filtered_tasks_cache[context]
        else:
            self._filtered_tasks_cache = {}  # Clear all cache
        self._dirty = True  # Mark as needing save

    def should_save(self):
        """Check if we should save based on time elapsed since last save."""
        current_time = time.time()
        return self._dirty and (current_time - self._last_save_time > 2.0)

    def save_tasks(self):
        """Save tasks to the JSON file if needed."""
        if self._dirty:
            with open(self.tasks_file, 'w') as f:
                json.dump(self.todo_items, f, indent=2)
            self._last_save_time = time.time()
            self._dirty = False

    def save_keybinds(self):
        """Save keybinds to the JSON file."""
        with open(self.keybinds_file, 'w') as f:
            json.dump(self.keybinds, f, indent=2)

    def run(self, stdscr):
        """Main application loop."""
        try:
            curses.curs_set(0)  # Hide cursor
            stdscr.clear()
            
            # Set up color pairs if terminal supports colors
            if curses.has_colors():
                curses.start_color()
                curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # For completed tasks
                curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)   # For selected items
            
            self.draw(stdscr)
            
            # Main event loop
            while True:
                key = stdscr.getch()
                self.handle_input(key, stdscr)
                self.draw(stdscr)
                
                # Periodic saves to avoid excessive I/O
                if self.should_save():
                    self.save_tasks()
        finally:
            # Ensure data is saved when exiting
            self.save_tasks()
            self.save_keybinds()

    def handle_input(self, key, stdscr):
        """Central input handler for all app states."""
        key_str = self.get_key_str(key)
        
        # Special case for exiting search mode
        if self.in_search_mode and key == 27:  # ESC key
            self.exit_search_mode()
            return
        
        # Handle based on current UI state
        if self.editing_keybind_ui:
            self._handle_keybind_ui_input(key, key_str)
        elif self.editing_keybind is not None:
            self._handle_keybind_edit_input(key, key_str)
        else:
            self._handle_normal_input(key, key_str, stdscr)

    def _handle_keybind_ui_input(self, key, key_str):
        """Handle input in the keybind settings UI."""
        if key == curses.KEY_UP:
            self.selected_keybind = (self.selected_keybind - 1) % len(self.keybinds)
        elif key == curses.KEY_DOWN:
            self.selected_keybind = (self.selected_keybind + 1) % len(self.keybinds)
        elif key == 10:  # Enter key - edit the selected keybind
            self.editing_keybind = list(self.keybinds.keys())[self.selected_keybind]
            self.editing_keybind_ui = False  # Switch to single keybind edit mode
        elif key == 27:  # Escape key - exit keybind UI
            self.editing_keybind_ui = False

    def _handle_keybind_edit_input(self, key, key_str):
        """Handle input when editing a single keybind."""
        if key == 27:  # Escape key - cancel editing
            self.editing_keybind = None
            self.error_message = None
        elif 32 <= key <= 126 or key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]:
            # Check for duplicates
            if any(action != self.editing_keybind and existing_key == key_str 
                   for action, existing_key in self.keybinds.items()):
                self.error_message = "Duplication is not allowed!"
            else:
                self.keybinds[self.editing_keybind] = key_str
                self.editing_keybind = None
                self.error_message = None
                self.editing_keybind_ui = True  # Return to keybind list

    def _handle_normal_input(self, key, key_str, stdscr):
        """Handle input in the normal app state."""
        # If there are no contexts, only respond to add_context and quit
        if not self.contexts:
            if key_str == self.keybinds['quit']:
                raise SystemExit()
            elif key_str == self.keybinds['add_context']:
                self.add_context(stdscr)
            return
            
        # Map keybinds to actions
        actions = {
            self.keybinds['quit']: lambda: self._action_quit(),
            self.keybinds['toggle']: lambda: self.toggle_check(),
            self.keybinds['edit']: lambda: self.edit_task(stdscr),
            self.keybinds['add_task']: lambda: self.add_task(stdscr),
            self.keybinds['add_context']: lambda: self.add_context(stdscr),
            self.keybinds['next_context']: lambda: self.next_context(),
            self.keybinds['previous_context']: lambda: self.previous_context(),
            self.keybinds['move_down']: lambda: self.move_down(),
            self.keybinds['move_up']: lambda: self.move_up(),
            self.keybinds['edit_keybinds']: lambda: self._action_edit_keybinds(),
            self.keybinds['delete_task']: lambda: self.delete_task(),
            self.keybinds['delete_context']: lambda: self.delete_context(stdscr),
            self.keybinds['rename_context']: lambda: self.rename_context(stdscr),
            self.keybinds['kanban_view']: lambda: self._enter_kanban_view(stdscr),
            self.keybinds['show_stats']: lambda: self.show_stats(stdscr),
            self.keybinds['add_tag']: lambda: self.add_tag(stdscr),
            self.keybinds['set_due_date']: lambda: self.set_due_date(stdscr),
            self.keybinds['search_tasks']: lambda: self.search_tasks(stdscr),
            self.keybinds['toggle_priority']: lambda: self.toggle_priority(),
            self.keybinds['undo']: lambda: self._action_undo(),
        }
        
        # Save state before modifying tasks for undo functionality
        if key_str in [self.keybinds[k] for k in ['toggle', 'edit', 'add_task', 'delete_task', 
                                                  'add_tag', 'set_due_date', 'toggle_priority']]:
            self.save_state()
            
        # Execute the action if the key is mapped
        if key_str in actions:
            actions[key_str]()

    def _action_quit(self):
        """Quit the application."""
        raise SystemExit()
        
    def _action_edit_keybinds(self):
        """Enter keybind editing mode."""
        self.editing_keybind_ui = True
        self.selected_keybind = 0

    def get_key_str(self, key):
        """Convert a keycode to a string representation."""
        key_map = {
            curses.KEY_RIGHT: 'KEY_RIGHT',
            curses.KEY_LEFT: 'KEY_LEFT',
            curses.KEY_DOWN: 'KEY_DOWN',
            curses.KEY_UP: 'KEY_UP',
            27: 'ESC'  # Escape key
        }
        
        if key in key_map:
            return key_map[key]
        elif 32 <= key <= 126:  # Printable ASCII
            return chr(key)
        else:
            return f"KEY_{key}"  # For other special keys
            
    def get_user_input(self, stdscr, prompt, allow_empty=False):
        """General method to get user input with escape to cancel."""
        # Save the current screen state
        height, width = stdscr.getmaxyx()
        
        # Create an input window at the top
        input_win = curses.newwin(3, width - 4, 2, 2)
        input_win.clear()
        input_win.box()
        input_win.addstr(1, 2, prompt)
        input_win.refresh()
        
        # Get user input
        curses.echo()
        key = 0
        user_input = ""
        cursor_pos = len(prompt) + 2
        
        while key != 10 and key != 27:  # Enter or Escape
            input_win.move(1, cursor_pos)
            input_win.refresh()
            key = stdscr.getch()
            
            if key == 8 or key == 127:  # Backspace or Delete
                if user_input:
                    user_input = user_input[:-1]
                    cursor_pos -= 1
                    input_win.addstr(1, cursor_pos, " ")
                    input_win.move(1, cursor_pos)
            elif 32 <= key <= 126:  # Printable characters
                if cursor_pos < width - 5:  # Leave space for border
                    user_input += chr(key)
                    input_win.addstr(1, cursor_pos, chr(key))
                    cursor_pos += 1
        
        curses.noecho()
        
        # Handle cancel
        if key == 27:  # Escape
            return None
            
        # Handle empty input
        if not user_input and not allow_empty:
            self.error_message = "Input cannot be empty."
            return None
            
        return user_input

    def draw(self, stdscr):
        """Draw the appropriate UI based on the current state."""
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        stdscr.border()

        if self.editing_keybind_ui:
            self._draw_keybind_ui(stdscr, height, width)
        elif self.editing_keybind is not None:
            self._draw_keybind_edit(stdscr, height, width)
        else:
            self._draw_normal_ui(stdscr, height, width)
        
        # Show error message if present
        if self.error_message:
            stdscr.addstr(height - 2, 2, self.error_message, curses.A_BOLD)
            
        stdscr.refresh()
        
    def _draw_keybind_ui(self, stdscr, height, width):
        """Draw the keybind settings UI."""
        stdscr.addstr(1, 2, "Keybind Settings", curses.A_BOLD)
        stdscr.addstr(2, 2, "↑/↓: Navigate | Enter: Edit | ESC: Exit")
        
        # Draw keybind list with proper formatting
        keybind_list = list(self.keybinds.items())
        max_display = height - 7  # Account for borders and headers
        start_idx = max(0, self.selected_keybind - max_display // 2)
        end_idx = min(len(keybind_list), start_idx + max_display)
        
        # Show scroll indicators if needed
        if start_idx > 0:
            stdscr.addstr(3, width // 2, "↑ More Above ↑")
        if end_idx < len(keybind_list):
            stdscr.addstr(height - 3, width // 2, "↓ More Below ↓")
        
        for i in range(start_idx, end_idx):
            action, key = keybind_list[i]
            y_pos = i - start_idx + 4
            
            # Format the display for special keys
            key_display = self._format_key_display(key)
            
            line = f"{action}: {key_display}"
            if i == self.selected_keybind:
                stdscr.addstr(y_pos, 4, line, curses.A_REVERSE)
            else:
                stdscr.addstr(y_pos, 4, line)
                
    def _draw_keybind_edit(self, stdscr, height, width):
        """Draw the single keybind edit UI."""
        stdscr.addstr(1, 2, f"Press a key to rebind '{self.editing_keybind}'", curses.A_BOLD)
        stdscr.addstr(2, 2, "Press ESC to cancel")
        
    def _draw_normal_ui(self, stdscr, height, width):
        """Draw the normal task UI."""
        # Check if there are any contexts
        if not self.contexts:
            # No contexts exist, show message and prompt
            stdscr.addstr(3, 4, "There are currently no contexts. Press 'n' to create one.", curses.A_BOLD)
            self._draw_keybind_help(stdscr, height, width)
            return
            
        # Normal context and task display
        header_text = f"Context: {self.current_context}"
        if self.in_search_mode:
            header_text = "Search Results (ESC to exit)"
        stdscr.addstr(1, 2, header_text, curses.A_BOLD)
        
        # Get filtered tasks using cache
        filtered_tasks = self.get_filtered_tasks()
        
        if not filtered_tasks:
            if self.in_search_mode:
                stdscr.addstr(3, 4, "No matching tasks found.")
            else:
                stdscr.addstr(3, 4, "No tasks in this context.")
        else:
            self._draw_tasks(stdscr, filtered_tasks, height, width)
        
        self._draw_keybind_help(stdscr, height, width)
        
    def _draw_tasks(self, stdscr, tasks, height, width):
        """Draw the task list with boxes and separators."""
        # Constants for the task display
        checkbox_width = 6
        separator_col = checkbox_width + 2
        task_start_col = separator_col + 2
        row_height = 3  # Each task takes 3 rows (content + separator)
        
        # Calculate visible range based on screen height
        max_visible_tasks = (height - 7) // row_height
        total_tasks = len(tasks)
        
        # Calculate start index based on selection
        selected_task_idx = self.selected_index % total_tasks if total_tasks > 0 else 0
        start_idx = max(0, selected_task_idx - max_visible_tasks // 2)
        end_idx = min(total_tasks, start_idx + max_visible_tasks)
        
        # Draw the header row with column titles
        stdscr.addstr(3, 3, "Status")
        stdscr.addstr(3, task_start_col, "Task")
        
        # Draw horizontal separator below header
        for x in range(2, width - 2):
            stdscr.addch(4, x, curses.ACS_HLINE)
        
        # Show scroll indicators if needed
        if start_idx > 0:
            stdscr.addstr(5, width // 2, "↑ More Above ↑")
        if end_idx < total_tasks:
            stdscr.addstr(height - 3, width // 2, "↓ More Below ↓")
        
        # Draw visible tasks
        for i in range(start_idx, end_idx):
            y_offset = i - start_idx
            row_y = 5 + (y_offset * row_height)
            
            # Draw vertical separator between checkbox and task
            for y in range(row_y, row_y + 2):
                stdscr.addch(y, separator_col, curses.ACS_VLINE)
            
            item = tasks[i]
            
            # Draw checkbox - make it bigger and more visible
            checkbox = "[X]" if item['checked'] else "[ ]"
            
            # Determine if this task is selected
            is_selected = (i == selected_task_idx)
            
            # Add attributes based on selection and completion status
            attrs = 0
            if is_selected:
                attrs |= curses.A_REVERSE
            if item['checked'] and curses.has_colors():
                attrs |= curses.color_pair(1)
            
            # Draw the checkbox and task with proper attributes
            stdscr.addstr(row_y, 3, checkbox, attrs | curses.A_BOLD)
            
            # Truncate task text if it's too long for display
            task_text = item['task']
            
            # Add priority indicator if present
            priority_indicator = ""
            if 'priority' in item and item['priority']:
                indicators = {'high': '!!! ', 'medium': '!! ', 'low': '! '}
                priority_indicator = indicators.get(item['priority'], "")
                
            # Add due date if present
            due_date_display = ""
            if 'due_date' in item and item['due_date']:
                due_date_display = f" [Due: {item['due_date']}]"
                
            # Add tags if present
            tags_display = ""
            if 'tags' in item and item['tags']:
                tags = ', '.join([f"#{tag}" for tag in item['tags']])
                tags_display = f" [{tags}]"
                
            # Combine and limit display text
            display_text = f"{priority_indicator}{task_text}{due_date_display}{tags_display}"
            max_text_width = width - task_start_col - 3
            if len(display_text) > max_text_width:
                display_text = display_text[:max_text_width-3] + "..."
            
            stdscr.addstr(row_y, task_start_col, display_text, attrs)
            
            # Draw horizontal separator after each task (except the last one)
            if i < end_idx - 1:
                for x in range(2, width - 2):
                    stdscr.addch(row_y + 2, x, curses.ACS_HLINE)
                
                # Add intersection where vertical and horizontal lines meet
                stdscr.addch(row_y + 2, separator_col, curses.ACS_PLUS)
                
    def _draw_keybind_help(self, stdscr, height, width):
        """Draw keybind help text at the bottom of the screen."""
        # Select most important keybinds to display based on available space
        important_actions = ['quit', 'add_task', 'toggle', 'edit', 'next_context', 
                            'previous_context', 'kanban_view', 'search_tasks', 
                            'toggle_priority', 'undo']
        
        # If in search mode, show different key options
        if self.in_search_mode:
            important_actions = ['exit_search', 'toggle', 'edit']
            
        keybind_display = []
        
        # Add important keybinds first
        for action in important_actions:
            if action in self.keybinds:
                key_display = self._format_key_display(self.keybinds[action])
                keybind_display.append(f"{key_display}:{action}")
        
        # Add remaining keybinds if space allows
        for action, key in self.keybinds.items():
            if action not in important_actions:
                key_display = self._format_key_display(key)
                keybind_display.append(f"{key_display}:{action}")
        
        help_text = " | ".join(keybind_display)
        
        # Display keybinds on last line, truncating if needed
        y_pos = height - 2
        max_width = width - 4
        
        if len(help_text) > max_width:
            help_text = help_text[:max_width-3] + "..."
            
        stdscr.addstr(y_pos, 2, help_text)
            
    def _format_key_display(self, key):
        """Format a key for display in the UI."""
        key_display = key
        if key in ['KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT']:
            key_display = {'KEY_UP': '↑', 'KEY_DOWN': '↓', 'KEY_LEFT': '←', 'KEY_RIGHT': '→'}[key]
        elif key == ' ':
            key_display = 'SPACE'
        return key_display

    def toggle_check(self):
        """Toggle checked status of the selected task."""
        filtered_tasks = self.get_filtered_tasks()
        if filtered_tasks:
            task = filtered_tasks[self.selected_index % len(filtered_tasks)]
            task['checked'] = not task['checked']
            self.invalidate_cache(self.current_context)

    def next_context(self):
        """Switch to the next context."""
        if self.contexts:
            current_index = self.contexts.index(self.current_context)
            self.current_context = self.contexts[(current_index + 1) % len(self.contexts)]
            self.selected_index = 0

    def previous_context(self):
        """Switch to the previous context."""
        if self.contexts:
            current_index = self.contexts.index(self.current_context)
            self.current_context = self.contexts[(current_index - 1) % len(self.contexts)]
            self.selected_index = 0

    def move_down(self):
        """Move selection down."""
        filtered_tasks = self.get_filtered_tasks()
        if filtered_tasks:
            self.selected_index = (self.selected_index + 1) % len(filtered_tasks)

    def move_up(self):
        """Move selection up."""
        filtered_tasks = self.get_filtered_tasks()
        if filtered_tasks:
            self.selected_index = (self.selected_index - 1) % len(filtered_tasks)

    def edit_task(self, stdscr):
        """Edit the selected task."""
        filtered_tasks = self.get_filtered_tasks()
        if not filtered_tasks:
            return
            
        task_idx = self.selected_index % len(filtered_tasks)
        task = filtered_tasks[task_idx]
        new_task = self.get_user_input(stdscr, f"Edit task: ", allow_empty=False)
        
        if new_task is not None:
            task['task'] = new_task
            self.invalidate_cache(self.current_context)

    def add_task(self, stdscr):
        """Add a new task to the current context."""
        new_task = self.get_user_input(stdscr, "Add new task: ")
        
        if new_task is not None:
            self.todo_items.append({'task': new_task, 'checked': False, 'context': self.current_context})
            self.invalidate_cache(self.current_context)
            # Set selection to the new task
            filtered_tasks = self.get_filtered_tasks()
            self.selected_index = len(filtered_tasks) - 1

    def add_context(self, stdscr):
        """Add a new context."""
        new_context = self.get_user_input(stdscr, "Create new context: ")
        
        if new_context is not None:
            if new_context not in self.contexts:
                self.contexts.append(new_context)
                self.current_context = new_context
                self.selected_index = 0
                self.invalidate_cache()

    def delete_task(self):
        """Delete the currently selected task."""
        filtered_tasks = self.get_filtered_tasks()
        if not filtered_tasks:
            return
        
        # Find the task to delete
        task_idx = self.selected_index % len(filtered_tasks)
        task_to_delete = filtered_tasks[task_idx]
        
        # Remove it from the list
        self.todo_items.remove(task_to_delete)
        self.invalidate_cache(self.current_context)
        
        # Adjust selected index if needed
        if self.selected_index > 0 and self.selected_index >= len(filtered_tasks) - 1:
            self.selected_index -= 1

    def delete_context(self, stdscr):
        """Delete the current context and all its tasks."""
        if len(self.contexts) <= 1:
            self.error_message = "Cannot delete the only context."
            return
        
        # Ask for confirmation
        confirmation = self.get_user_input(
            stdscr, 
            f"Delete context '{self.current_context}'? (y/n): ",
            allow_empty=True
        )
        
        if confirmation and confirmation.lower() == 'y':
            # Remove all tasks in this context
            self.todo_items = [item for item in self.todo_items 
                               if item['context'] != self.current_context]
            
            # Remove the context from the list
            current_index = self.contexts.index(self.current_context)
            self.contexts.remove(self.current_context)
            
            # Clear the cache for this context
            self.invalidate_cache()
            
            # If we have no contexts left, just return
            if not self.contexts:
                return
                
            # Move to another context
            next_index = min(current_index, len(self.contexts) - 1)
            self.current_context = self.contexts[next_index]
            self.selected_index = 0

    def rename_context(self, stdscr):
        """Rename the current context."""
        # Clear any previous error message
        self.error_message = None
        
        new_name = self.get_user_input(stdscr, f"Rename '{self.current_context}' to: ")
        
        if new_name is None or new_name == self.current_context:
            return
            
        # Check if the new name already exists
        if new_name in self.contexts:
            self.error_message = "Context name already exists."
            return
            
        old_context = self.current_context
        
        # Update all tasks with this context
        for item in self.todo_items:
            if item['context'] == old_context:
                item['context'] = new_name
        
        # Update the contexts list
        self.contexts.remove(old_context)
        self.contexts.append(new_name)
        self.current_context = new_name
        
        # Invalidate cache
        self.invalidate_cache(old_context)
        self._filtered_tasks_cache[new_name] = self._filtered_tasks_cache.get(old_context, [])

    def show_stats(self, stdscr):
        """Show statistics about tasks and contexts."""
        height, width = stdscr.getmaxyx()
        stats_win = curses.newwin(height-4, width-4, 2, 2)
        stats_win.clear()
        stats_win.box()
        
        # Calculate statistics
        total_tasks = len(self.todo_items)
        completed = sum(1 for task in self.todo_items if task['checked'])
        completion_rate = (completed / total_tasks * 100) if total_tasks else 0
        
        # Context statistics
        context_stats = {}
        for context in self.contexts:
            tasks = self.get_filtered_tasks(context)
            done = sum(1 for task in tasks if task['checked'])
            context_stats[context] = {
                'total': len(tasks),
                'done': done,
                'rate': (done / len(tasks) * 100) if tasks else 0
            }
        
        # Display statistics
        stats_win.addstr(1, 2, f"Total Tasks: {total_tasks}")
        stats_win.addstr(2, 2, f"Completed: {completed} ({completion_rate:.1f}%)")
        stats_win.addstr(4, 2, "Context Statistics:", curses.A_BOLD)
        
        for i, (context, stats) in enumerate(context_stats.items()):
            stats_win.addstr(6+i, 4, f"{context}: {stats['done']}/{stats['total']} ({stats['rate']:.1f}%)")
        
        stats_win.addstr(height-6, 2, "Press any key to return")
        stats_win.refresh()
        stats_win.getch()

    def add_tag(self, stdscr):
        """Add a tag to the selected task."""
        filtered_tasks = self.get_filtered_tasks()
        if not filtered_tasks:
            return
        
        task = filtered_tasks[self.selected_index % len(filtered_tasks)]
        tag = self.get_user_input(stdscr, "Add tag: ")
        
        if tag:
            if 'tags' not in task:
                task['tags'] = []
            if tag not in task['tags']:
                task['tags'].append(tag)
        
            self.invalidate_cache(self.current_context)

    def set_due_date(self, stdscr):
        """Set a due date for the selected task."""
        filtered_tasks = self.get_filtered_tasks()
        if not filtered_tasks:
            return
        
        task = filtered_tasks[self.selected_index % len(filtered_tasks)]
        date_str = self.get_user_input(stdscr, "Due date (YYYY-MM-DD or 'clear'): ")
        
        if date_str == "clear":
            if 'due_date' in task:
                del task['due_date']
        elif date_str:
            # Simple validation
            try:
                year, month, day = map(int, date_str.split('-'))
                # Store as string since we don't need datetime objects
                task['due_date'] = date_str
            except ValueError:
                self.error_message = "Invalid date format. Use YYYY-MM-DD."
                return
        
        self.invalidate_cache(self.current_context)

    def search_tasks(self, stdscr):
        """Search tasks across all contexts."""
        query = self.get_user_input(stdscr, "Search: ")
        if not query:
            return
        
        # Store previous state to return to later
        prev_context = self.current_context
        
        # Find matching tasks across all contexts
        results = []
        for item in self.todo_items:
            if query.lower() in item['task'].lower():
                results.append(item)
        
        if not results:
            self.error_message = f"No tasks matching '{query}'"
            return
        
        # Create temporary context for results
        self._search_results = results
        self._prev_state = (prev_context, self.selected_index)
        self._in_search_mode = True

    def toggle_priority(self):
        """Cycle through priority levels (none, low, medium, high)."""
        filtered_tasks = self.get_filtered_tasks()
        if not filtered_tasks:
            return
        
        task = filtered_tasks[self.selected_index % len(filtered_tasks)]
        
        # Get current priority and cycle to next
        priorities = [None, "low", "medium", "high"]
        current = task.get('priority', None)
        next_idx = (priorities.index(current) + 1) % len(priorities)
        task['priority'] = priorities[next_idx] 
        
        self.invalidate_cache(self.current_context)

    def save_state(self):
        """Save current state for undo functionality."""
        state = {
            'todo_items': copy.deepcopy(self.todo_items),
            'contexts': self.contexts.copy(),
            'current_context': self.current_context,
            'selected_index': self.selected_index
        }
        self.history.append(state)
        self.future = []  # Clear redo stack
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
    def undo(self):
        """Restore previous state."""
        if not self.history:
            self.error_message = "Nothing to undo"
            return
        
        # Save current state to redo stack
        current = {
            'todo_items': self.todo_items,
            'contexts': self.contexts,
            'current_context': self.current_context,
            'selected_index': self.selected_index
        }
        self.future.append(current)
        
        # Restore previous state
        state = self.history.pop()
        self.todo_items = state['todo_items']
        self.contexts = state['contexts']
        self.current_context = state['current_context']
        self.selected_index = state['selected_index']
        self.invalidate_cache()

    def kanban_view(self, stdscr):
        """Display tasks in a kanban board layout with contexts as columns."""
        height, width = stdscr.getmaxyx()
        
        # Calculate column width based on available space and number of contexts
        num_contexts = len(self.contexts)
        col_width = max(15, (width - 4) // num_contexts)
        
        # Draw board header
        stdscr.clear()
        stdscr.border()
        stdscr.addstr(1, 2, "KANBAN VIEW (Press 'ESC' to return)", curses.A_BOLD)
        
        # Draw column headers and separators
        for i, context in enumerate(self.contexts):
            x_pos = 2 + (i * col_width)
            # Draw column header
            stdscr.addstr(3, x_pos + col_width//2 - len(context)//2, context, curses.A_BOLD)
            # Draw separator line
            for y in range(2, height-2):
                if i > 0:  # Don't draw left edge separator
                    stdscr.addch(y, x_pos-1, curses.ACS_VLINE)
        
        # Draw horizontal separator below headers
        for x in range(1, width-1):
            stdscr.addch(4, x, curses.ACS_HLINE)
        
        # Draw tasks in each column
        for i, context in enumerate(self.contexts):
            x_pos = 2 + (i * col_width)
            tasks = self.get_filtered_tasks(context)
            
            # Display tasks in column
            for j, task in enumerate(tasks[:height-8]):  # Limit by visible area
                task_text = task['task']
                # Truncate task text to fit column
                if len(task_text) > col_width - 4:
                    task_text = task_text[:col_width-7] + "..."
                    
                # Format based on status
                attr = 0
                if task['checked']:
                    attr |= curses.color_pair(1)
                
                # Display task card
                card_y = 6 + j*3
                if card_y + 2 < height - 2:  # Ensure card fits on screen
                    # Draw card border
                    for cy in range(3):
                        stdscr.addstr(card_y + cy, x_pos, " " * (col_width-2), attr)
                    # Draw task text
                    stdscr.addstr(card_y + 1, x_pos + 1, task_text, attr | curses.A_BOLD)
        
        # Wait for user input to return
        while stdscr.getch() != 27:  # ESC
            pass

    def _enter_kanban_view(self, stdscr):
        """Enter kanban view mode."""
        if not self.contexts:
            self.error_message = "No contexts available for kanban view."
            return
            
        self.kanban_view(stdscr)

    def exit_search_mode(self):
        """Exit search mode and return to previous state."""
        if self.in_search_mode and self._prev_state:
            self.current_context, self.selected_index = self._prev_state
            self.in_search_mode = False
            self._search_results = []
            self._prev_state = None

    def _action_undo(self):
        """Handle undo action."""
        self.undo()

if __name__ == '__main__':
    app = TodoApp()
    curses.wrapper(app.run)