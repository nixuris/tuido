
import curses

def get_key_str(key):
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

def get_user_input(stdscr, prompt, allow_empty=False):
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
        return None, "Input cannot be empty."
        
    return user_input, None

def draw(app, stdscr):
    """Draw the appropriate UI based on the current state."""
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    stdscr.border()

    if app.editing_keybind_ui:
        _draw_keybind_ui(app, stdscr, height, width)
    elif app.editing_keybind is not None:
        _draw_keybind_edit(app, stdscr, height, width)
    else:
        _draw_normal_ui(app, stdscr, height, width)
    
    # Show error message if present
    if app.error_message:
        stdscr.addstr(height - 2, 2, app.error_message, curses.A_BOLD)
        
    stdscr.refresh()
    
def _draw_keybind_ui(app, stdscr, height, width):
    """Draw the keybind settings UI."""
    stdscr.addstr(1, 2, "Keybind Settings", curses.A_BOLD)
    stdscr.addstr(2, 2, "↑/↓: Navigate | Enter: Edit | ESC: Exit")
    
    # Draw keybind list with proper formatting
    keybind_list = list(app.keybinds.items())
    max_display = height - 7  # Account for borders and headers
    start_idx = max(0, app.selected_keybind - max_display // 2)
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
        key_display = _format_key_display(key)
        
        line = f"{action}: {key_display}"
        if i == app.selected_keybind:
            stdscr.addstr(y_pos, 4, line, curses.A_REVERSE)
        else:
            stdscr.addstr(y_pos, 4, line)
            
def _draw_keybind_edit(app, stdscr, height, width):
    """Draw the single keybind edit UI."""
    stdscr.addstr(1, 2, f"Press a key to rebind '{app.editing_keybind}'", curses.A_BOLD)
    stdscr.addstr(2, 2, "Press ESC to cancel")
    
def _draw_normal_ui(app, stdscr, height, width):
    """Draw the normal task UI."""
    # Check if there are any contexts
    if not app.contexts:
        # No contexts exist, show message and prompt
        stdscr.addstr(3, 4, "There are currently no contexts. Press 'n' to create one.", curses.A_BOLD)
        _draw_keybind_help(app, stdscr, height, width)
        return
        
    # Normal context and task display
    header_text = f"Context: {app.current_context}"
    if app.in_search_mode:
        header_text = "Search Results (ESC to exit)"
    stdscr.addstr(1, 2, header_text, curses.A_BOLD)
    
    # Get filtered tasks using cache
    filtered_tasks = app.get_filtered_tasks()
    
    if not filtered_tasks:
        if app.in_search_mode:
            stdscr.addstr(3, 4, "No matching tasks found.")
        else:
            stdscr.addstr(3, 4, "No tasks in this context.")
    else:
        _draw_tasks(app, stdscr, filtered_tasks, height, width)
    
    _draw_keybind_help(app, stdscr, height, width)
    
def _draw_tasks(app, stdscr, tasks, height, width):
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
    selected_task_idx = app.selected_index % total_tasks if total_tasks > 0 else 0
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
            
def _draw_keybind_help(app, stdscr, height, width):
    """Draw keybind help text at the bottom of the screen."""
    # Select most important keybinds to display based on available space
    important_actions = ['quit', 'add_task', 'toggle', 'edit', 'next_context', 
                        'previous_context', 'kanban_view', 'search_tasks', 
                        'toggle_priority', 'undo']
    
    # If in search mode, show different key options
    if app.in_search_mode:
        important_actions = ['exit_search', 'toggle', 'edit']
        
    keybind_display = []
    
    # Add important keybinds first
    for action in important_actions:
        if action in app.keybinds:
            key_display = _format_key_display(app.keybinds[action])
            keybind_display.append(f"{key_display}:{action}")
    
    # Add remaining keybinds if space allows
    for action, key in app.keybinds.items():
        if action not in important_actions:
            key_display = _format_key_display(key)
            keybind_display.append(f"{key_display}:{action}")
    
    help_text = " | ".join(keybind_display)
    
    # Display keybinds on last line, truncating if needed
    y_pos = height - 2
    max_width = width - 4
    
    if len(help_text) > max_width:
        help_text = help_text[:max_width-3] + "..."
        
    stdscr.addstr(y_pos, 2, help_text)
        
def _format_key_display(key):
    """Format a key for display in the UI."""
    key_display = key
    if key in ['KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT']:
        key_display = {'KEY_UP': '↑', 'KEY_DOWN': '↓', 'KEY_LEFT': '←', 'KEY_RIGHT': '→'}[key]
    elif key == ' ':
        key_display = 'SPACE'
    return key_display

def show_stats(app, stdscr):
    """Show statistics about tasks and contexts."""
    height, width = stdscr.getmaxyx()
    stats_win = curses.newwin(height-4, width-4, 2, 2)
    stats_win.clear()
    stats_win.box()
    
    # Calculate statistics
    total_tasks = len(app.todo_items)
    completed = sum(1 for task in app.todo_items if task['checked'])
    completion_rate = (completed / total_tasks * 100) if total_tasks else 0
    
    # Context statistics
    context_stats = {}
    for context in app.contexts:
        tasks = app.get_filtered_tasks(context)
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

def kanban_view(app, stdscr):
    """Display tasks in a kanban board layout with contexts as columns."""
    height, width = stdscr.getmaxyx()
    
    # Calculate column width based on available space and number of contexts
    num_contexts = len(app.contexts)
    col_width = max(15, (width - 4) // num_contexts)
    
    # Draw board header
    stdscr.clear()
    stdscr.border()
    stdscr.addstr(1, 2, "KANBAN VIEW (Press 'ESC' to return)", curses.A_BOLD)
    
    # Draw column headers and separators
    for i, context in enumerate(app.contexts):
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
    for i, context in enumerate(app.contexts):
        x_pos = 2 + (i * col_width)
        tasks = app.get_filtered_tasks(context)
        
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
