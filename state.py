
import time
import copy

class AppState:
    def __init__(self, todo_items, keybinds):
        self.todo_items = todo_items
        self.keybinds = keybinds
        self.contexts = list(set(item['context'] for item in self.todo_items))
        self.current_context = self.contexts[0] if self.contexts else "Work"
        self.selected_index = 0
        self.editing_keybind = None
        self.editing_keybind_ui = False
        self.selected_keybind = 0
        self.error_message = None
        self.in_kanban_view = False
        self.in_search_mode = False
        self._search_results = []
        self._prev_state = None
        self._filtered_tasks_cache = {}
        self._last_save_time = time.time()
        self._dirty = False
        self.history = []
        self.future = []
        self.max_history = 50

    def get_filtered_tasks(self, context=None):
        """Get tasks filtered by context, with caching."""
        if self.in_search_mode:
            return self._search_results
            
        context = context or self.current_context
        
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
            self._filtered_tasks_cache = {}
        self._dirty = True

    def should_save(self):
        """Check if we should save based on time elapsed since last save."""
        current_time = time.time()
        return self._dirty and (current_time - self._last_save_time > 2.0)

    def save_state_for_undo(self):
        """Save current state for undo functionality."""
        state = {
            'todo_items': copy.deepcopy(self.todo_items),
            'contexts': self.contexts.copy(),
            'current_context': self.current_context,
            'selected_index': self.selected_index
        }
        self.history.append(state)
        self.future = []
        
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
    def undo(self):
        """Restore previous state."""
        if not self.history:
            self.error_message = "Nothing to undo"
            return
        
        current = {
            'todo_items': self.todo_items,
            'contexts': self.contexts,
            'current_context': self.current_context,
            'selected_index': self.selected_index
        }
        self.future.append(current)
        
        state = self.history.pop()
        self.todo_items = state['todo_items']
        self.contexts = state['contexts']
        self.current_context = state['current_context']
        self.selected_index = state['selected_index']
        self.invalidate_cache()

    def exit_search_mode(self):
        """Exit search mode and return to previous state."""
        if self.in_search_mode and self._prev_state:
            self.current_context, self.selected_index = self._prev_state
            self.in_search_mode = False
            self._search_results = []
            self._prev_state = None
