from ui import get_user_input, show_stats, kanban_view

def toggle_check(app):
    """Toggle checked status of the selected task."""
    filtered_tasks = app.get_filtered_tasks()
    if filtered_tasks:
        task = filtered_tasks[app.selected_index % len(filtered_tasks)]
        task['checked'] = not task['checked']
        app.invalidate_cache(app.current_context)

def next_context(app):
    """Switch to the next context."""
    if app.contexts:
        current_index = app.contexts.index(app.current_context)
        app.current_context = app.contexts[(current_index + 1) % len(app.contexts)]
        app.selected_index = 0

def previous_context(app):
    """Switch to the previous context."""
    if app.contexts:
        current_index = app.contexts.index(app.current_context)
        app.current_context = app.contexts[(current_index - 1) % len(app.contexts)]
        app.selected_index = 0

def move_down(app):
    """Move selection down."""
    filtered_tasks = app.get_filtered_tasks()
    if filtered_tasks:
        app.selected_index = (app.selected_index + 1) % len(filtered_tasks)

def move_up(app):
    """Move selection up."""
    filtered_tasks = app.get_filtered_tasks()
    if filtered_tasks:
        app.selected_index = (app.selected_index - 1) % len(filtered_tasks)

def edit_task(app, stdscr):
    """Edit the selected task."""
    filtered_tasks = app.get_filtered_tasks()
    if not filtered_tasks:
        return
        
    task_idx = app.selected_index % len(filtered_tasks)
    task = filtered_tasks[task_idx]
    new_task, error = get_user_input(stdscr, f"Edit task: ", allow_empty=False)
    
    if error:
        app.error_message = error
        return

    if new_task is not None:
        task['task'] = new_task
        app.invalidate_cache(app.current_context)

def add_task(app, stdscr):
    """Add a new task to the current context."""
    new_task, error = get_user_input(stdscr, "Add new task: ")
    
    if error:
        app.error_message = error
        return

    if new_task is not None:
        app.todo_items.append({'task': new_task, 'checked': False, 'context': app.current_context})
        app.invalidate_cache(app.current_context)
        filtered_tasks = app.get_filtered_tasks()
        app.selected_index = len(filtered_tasks) - 1

def add_context(app, stdscr):
    """Add a new context."""
    new_context, error = get_user_input(stdscr, "Create new context: ")
    
    if error:
        app.error_message = error
        return

    if new_context is not None:
        if new_context not in app.contexts:
            app.contexts.append(new_context)
            app.current_context = new_context
            app.selected_index = 0
            app.invalidate_cache()

def delete_task(app):
    """Delete the currently selected task."""
    filtered_tasks = app.get_filtered_tasks()
    if not filtered_tasks:
        return
    
    task_idx = app.selected_index % len(filtered_tasks)
    task_to_delete = filtered_tasks[task_idx]
    
    app.todo_items.remove(task_to_delete)
    app.invalidate_cache(app.current_context)
    
    if app.selected_index > 0 and app.selected_index >= len(filtered_tasks) - 1:
        app.selected_index -= 1

def delete_context(app, stdscr):
    """Delete the current context and all its tasks."""
    if len(app.contexts) <= 1:
        app.error_message = "Cannot delete the only context."
        return
    
    confirmation, error = get_user_input(
        stdscr, 
        f"Delete context '{app.current_context}'? (y/n): ",
        allow_empty=True
    )

    if error:
        app.error_message = error
        return
    
    if confirmation and confirmation.lower() == 'y':
        app.todo_items = [item for item in app.todo_items 
                           if item['context'] != app.current_context]
        
        current_index = app.contexts.index(app.current_context)
        app.contexts.remove(app.current_context)
        
        app.invalidate_cache()
        
        if not app.contexts:
            return
            
        next_index = min(current_index, len(app.contexts) - 1)
        app.current_context = app.contexts[next_index]
        app.selected_index = 0

def rename_context(app, stdscr):
    """Rename the current context."""
    app.error_message = None
    
    new_name, error = get_user_input(stdscr, f"Rename '{app.current_context}' to: ")
    
    if error:
        app.error_message = error
        return

    if new_name is None or new_name == app.current_context:
        return
        
    if new_name in app.contexts:
        app.error_message = "Context name already exists."
        return
        
    old_context = app.current_context
    
    for item in app.todo_items:
        if item['context'] == old_context:
            item['context'] = new_name
    
    app.contexts.remove(old_context)
    app.contexts.append(new_name)
    app.current_context = new_name
    
    app.invalidate_cache(old_context)
    app._filtered_tasks_cache[new_name] = app._filtered_tasks_cache.get(old_context, [])

def add_tag(app, stdscr):
    """Add a tag to the selected task."""
    filtered_tasks = app.get_filtered_tasks()
    if not filtered_tasks:
        return
    
    task = filtered_tasks[app.selected_index % len(filtered_tasks)]
    tag, error = get_user_input(stdscr, "Add tag: ")
    
    if error:
        app.error_message = error
        return

    if tag:
        if 'tags' not in task:
            task['tags'] = []
        if tag not in task['tags']:
            task['tags'].append(tag)
    
        app.invalidate_cache(app.current_context)

def set_due_date(app, stdscr):
    """Set a due date for the selected task."""
    filtered_tasks = app.get_filtered_tasks()
    if not filtered_tasks:
        return
    
    task = filtered_tasks[app.selected_index % len(filtered_tasks)]
    date_str, error = get_user_input(stdscr, "Due date (YYYY-MM-DD or 'clear'): ")
    
    if error:
        app.error_message = error
        return

    if date_str == "clear":
        if 'due_date' in task:
            del task['due_date']
    elif date_str:
        try:
            year, month, day = map(int, date_str.split('-'))
            task['due_date'] = date_str
        except ValueError:
            app.error_message = "Invalid date format. Use YYYY-MM-DD."
            return
    
    app.invalidate_cache(app.current_context)

def search_tasks(app, stdscr):
    """Search tasks across all contexts."""
    query, error = get_user_input(stdscr, "Search: ")

    if error:
        app.error_message = error
        return

    if not query:
        return
    
    prev_context = app.current_context
    
    results = []
    for item in app.todo_items:
        if query.lower() in item['task'].lower():
            results.append(item)
    
    if not results:
        app.error_message = f"No tasks matching '{query}'"
        return
    
    app._search_results = results
    app._prev_state = (prev_context, app.selected_index)
    app.in_search_mode = True

def toggle_priority(app):
    """Cycle through priority levels (none, low, medium, high)."""
    filtered_tasks = app.get_filtered_tasks()
    if not filtered_tasks:
        return
    
    task = filtered_tasks[app.selected_index % len(filtered_tasks)]
    
    priorities = [None, "low", "medium", "high"]
    current = task.get('priority', None)
    next_idx = (priorities.index(current) + 1) % len(priorities)
    task['priority'] = priorities[next_idx] 
    
    app.invalidate_cache(app.current_context)

def enter_kanban_view(app, stdscr):
    """Enter kanban view mode."""
    if not app.contexts:
        app.error_message = "No contexts available for kanban view."
        return
        
    kanban_view(app, stdscr)
