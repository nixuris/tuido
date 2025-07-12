import curses
import time
from pathlib import Path
from config import ensure_config, load_tasks, load_keybinds, save_tasks, save_keybinds
from state import AppState
from ui import draw, get_key_str
from actions import (
    toggle_check, next_context, previous_context, move_down, move_up, 
    edit_task, add_task, add_context, delete_task, delete_context, 
    rename_context, add_tag, set_due_date, search_tasks, toggle_priority, 
    enter_kanban_view
)

class TodoApp:
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "tuido"
        self.tasks_file = self.config_dir / "tasks.json"
        self.keybinds_file = self.config_dir / "keybinds.json"
        
        ensure_config(self.config_dir, self.tasks_file, self.keybinds_file)
        
        todo_items = load_tasks(self.tasks_file)
        keybinds = load_keybinds(self.keybinds_file)
        
        self.state = AppState(todo_items, keybinds)

    def run(self, stdscr):
        try:
            curses.curs_set(0)
            stdscr.clear()
            
            if curses.has_colors():
                curses.start_color()
                curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
                curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
            
            draw(self.state, stdscr)
            
            while True:
                key = stdscr.getch()
                self.handle_input(key, stdscr)
                draw(self.state, stdscr)
                
                if self.state.should_save():
                    save_tasks(self.tasks_file, self.state.todo_items)
                    self.state._dirty = False
                    self.state._last_save_time = time.time()

        finally:
            save_tasks(self.tasks_file, self.state.todo_items)
            save_keybinds(self.keybinds_file, self.state.keybinds)

    def handle_input(self, key, stdscr):
        key_str = get_key_str(key)
        
        if self.state.in_search_mode and key == 27:
            self.state.exit_search_mode()
            return
        
        if self.state.editing_keybind_ui:
            self._handle_keybind_ui_input(key, key_str)
        elif self.state.editing_keybind is not None:
            self._handle_keybind_edit_input(key, key_str)
        else:
            self._handle_normal_input(key, key_str, stdscr)

    def _handle_keybind_ui_input(self, key, key_str):
        if key == curses.KEY_UP:
            self.state.selected_keybind = (self.state.selected_keybind - 1) % len(self.state.keybinds)
        elif key == curses.KEY_DOWN:
            self.state.selected_keybind = (self.state.selected_keybind + 1) % len(self.state.keybinds)
        elif key == 10:
            self.state.editing_keybind = list(self.state.keybinds.keys())[self.state.selected_keybind]
            self.state.editing_keybind_ui = False
        elif key == 27:
            self.state.editing_keybind_ui = False

    def _handle_keybind_edit_input(self, key, key_str):
        if key == 27:
            self.state.editing_keybind = None
            self.state.error_message = None
        elif 32 <= key <= 126 or key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]:
            if any(action != self.state.editing_keybind and existing_key == key_str 
                   for action, existing_key in self.state.keybinds.items()):
                self.state.error_message = "Duplication is not allowed!"
            else:
                self.state.keybinds[self.state.editing_keybind] = key_str
                self.state.editing_keybind = None
                self.state.error_message = None
                self.state.editing_keybind_ui = True

    def _handle_normal_input(self, key, key_str, stdscr):
        if not self.state.contexts:
            if key_str == self.state.keybinds['quit']:
                raise SystemExit()
            elif key_str == self.state.keybinds['add_context']:
                add_context(self.state, stdscr)
            return
            
        actions = {
            self.state.keybinds['quit']: lambda: self._action_quit(),
            self.state.keybinds['toggle']: lambda: toggle_check(self.state),
            self.state.keybinds['edit']: lambda: edit_task(self.state, stdscr),
            self.state.keybinds['add_task']: lambda: add_task(self.state, stdscr),
            self.state.keybinds['add_context']: lambda: add_context(self.state, stdscr),
            self.state.keybinds['next_context']: lambda: next_context(self.state),
            self.state.keybinds['previous_context']: lambda: previous_context(self.state),
            self.state.keybinds['move_down']: lambda: move_down(self.state),
            self.state.keybinds['move_up']: lambda: move_up(self.state),
            self.state.keybinds['edit_keybinds']: lambda: self._action_edit_keybinds(),
            self.state.keybinds['delete_task']: lambda: delete_task(self.state),
            self.state.keybinds['delete_context']: lambda: delete_context(self.state, stdscr),
            self.state.keybinds['rename_context']: lambda: rename_context(self.state, stdscr),
            self.state.keybinds['kanban_view']: lambda: enter_kanban_view(self.state, stdscr),
            self.state.keybinds['show_stats']: lambda: self.show_stats(stdscr),
            self.state.keybinds['add_tag']: lambda: add_tag(self.state, stdscr),
            self.state.keybinds['set_due_date']: lambda: set_due_date(self.state, stdscr),
            self.state.keybinds['search_tasks']: lambda: search_tasks(self.state, stdscr),
            self.state.keybinds['toggle_priority']: lambda: toggle_priority(self.state),
            self.state.keybinds['undo']: lambda: self.state.undo(),
        }
        
        if key_str in [self.state.keybinds[k] for k in ['toggle', 'edit', 'add_task', 'delete_task', 
                                                  'add_tag', 'set_due_date', 'toggle_priority']]:
            self.state.save_state_for_undo()
            
        if key_str in actions:
            actions[key_str]()

    def _action_quit(self):
        raise SystemExit()
        
    def _action_edit_keybinds(self):
        self.state.editing_keybind_ui = True
        self.state.selected_keybind = 0

    def show_stats(self, stdscr):
        from tuido.ui import show_stats
        show_stats(self.state, stdscr)

def main():
    app = TodoApp()
    curses.wrapper(app.run)

if __name__ == '__main__':
    main()
