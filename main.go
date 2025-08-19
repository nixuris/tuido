package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/help"
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Task represents a single todo item
type Task struct {
	ID       int      `json:"id"`
	Task     string   `json:"task"`
	Checked  bool     `json:"checked"`
	Context  string   `json:"context"`
	Priority string   `json:"priority,omitempty"` // low, medium, high
	Tags     []string `json:"tags,omitempty"`
	DueDate  string   `json:"due_date,omitempty"` // YYYY-MM-DD format
}

// ViewMode represents the current view
type ViewMode int

const (
	NormalView ViewMode = iota
	SearchView
	KanbanView
	StatsView
	InputView
	DateInputView
	RemoveTagView
)

// InputMode represents different input dialogs
type InputMode int

const (
	AddTaskInput InputMode = iota
	EditTaskInput
	AddContextInput
	RenameContextInput
	AddTagInput
	SearchInput
	DeleteConfirmInput
)

// Model represents the application state
type Model struct {
	// Core state
	tasks           []Task
	contexts        []string
	currentContext  string
	selectedIndex   int
	nextID          int

	// View state
	viewMode        ViewMode
	inputMode       InputMode
	searchResults   []Task
	prevContext     string
	prevIndex       int
	movingMode      bool
	movingTaskIndex int
	
	// Input handling
	textInput       textinput.Model
	dateInputs      []textinput.Model
	dateInputIndex  int
	removeTagIndex  int
	removeTagChecks []bool
	inputPrompt     string
	
	// UI state
	windowWidth     int
	windowHeight    int
	errorMessage    string
	
	// History for undo
	history         [][]Task
	maxHistory      int
	
	// Keybindings
	keyMap          KeyMap
	help            help.Model
	
	// Config
	configPath      string
}

// KeyMap defines key bindings
type KeyMap struct {
	Up             key.Binding
	Down           key.Binding
	Left           key.Binding
	Right          key.Binding
	Toggle         key.Binding
	Add            key.Binding
	Edit           key.Binding
	Delete         key.Binding
	Search         key.Binding
	AddContext     key.Binding
	RenameContext  key.Binding
	DeleteContext  key.Binding
	TogglePriority key.Binding
	AddTag         key.Binding
	RemoveTag      key.Binding
	SetDueDate     key.Binding
	ClearDueDate   key.Binding
	KanbanView     key.Binding
	StatsView      key.Binding
	Undo           key.Binding
	Move           key.Binding
	Quit           key.Binding
	Back           key.Binding
	Enter          key.Binding
	Nav            key.Binding
}

// DefaultKeyMap returns default key bindings
func DefaultKeyMap() KeyMap {
	return KeyMap{
		Up: key.NewBinding(
			key.WithKeys("up", "k"),
			key.WithHelp("↑/k", "move up"),
		),
		Down: key.NewBinding(
			key.WithKeys("down", "j"),
			key.WithHelp("↓/j", "move down"),
		),
		Left: key.NewBinding(
			key.WithKeys("left", "h"),
			key.WithHelp("←/h", "prev context"),
		),
		Right: key.NewBinding(
			key.WithKeys("right", "l"),
			key.WithHelp("→/l", "next context"),
		),
		Toggle: key.NewBinding(
			key.WithKeys(" "),
			key.WithHelp("space", "toggle"),
		),
		Add: key.NewBinding(
			key.WithKeys("a"),
			key.WithHelp("a", "add task"),
		),
		Edit: key.NewBinding(
			key.WithKeys("e"),
			key.WithHelp("e", "edit"),
		),
		Delete: key.NewBinding(
			key.WithKeys("d"),
			key.WithHelp("d", "delete"),
		),
		Search: key.NewBinding(
			key.WithKeys("/"),
			key.WithHelp("/", "search"),
		),
		AddContext: key.NewBinding(
			key.WithKeys("n"),
			key.WithHelp("n", "new context"),
		),
		RenameContext: key.NewBinding(
			key.WithKeys("r"),
			key.WithHelp("r", "rename context"),
		),
		DeleteContext: key.NewBinding(
			key.WithKeys("D"),
			key.WithHelp("D", "delete context"),
		),
		TogglePriority: key.NewBinding(
			key.WithKeys("p"),
			key.WithHelp("p", "priority"),
		),
		AddTag: key.NewBinding(
			key.WithKeys("t"),
			key.WithHelp("t", "add tag"),
		),
		RemoveTag: key.NewBinding(
			key.WithKeys("T"),
			key.WithHelp("T", "remove tag"),
		),
		SetDueDate: key.NewBinding(
			key.WithKeys("u"),
			key.WithHelp("u", "due date"),
		),
		ClearDueDate: key.NewBinding(
			key.WithKeys("U"),
			key.WithHelp("U", "clear due"),
		),
		KanbanView: key.NewBinding(
			key.WithKeys("v"),
			key.WithHelp("v", "kanban"),
		),
		StatsView: key.NewBinding(
			key.WithKeys("s"),
			key.WithHelp("s", "stats"),
		),
		Undo: key.NewBinding(
			key.WithKeys("z"),
			key.WithHelp("z", "undo"),
		),
		Move: key.NewBinding(
			key.WithKeys("m"),
			key.WithHelp("m", "move"),
		),
		Quit: key.NewBinding(
			key.WithKeys("q", "ctrl+c"),
			key.WithHelp("q", "quit"),
		),
		Back: key.NewBinding(
			key.WithKeys("esc"),
			key.WithHelp("esc", "back"),
		),
		Enter: key.NewBinding(
			key.WithKeys("enter"),
			key.WithHelp("enter", "confirm"),
		),
		Nav: key.NewBinding(
			key.WithKeys("↑", "↓", "←", "→"),
			key.WithHelp("↑↓←→", "navigation"),
		),
	}
}

// Styles
var (
	// Base styles
	baseStyle = lipgloss.NewStyle().
		PaddingLeft(1).
		PaddingRight(1)

	// Title styles
	titleStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#FFFDF5")).
		Background(lipgloss.Color("#25A065")).
		Padding(0, 1).
		Bold(true)

	// Task styles
	taskStyle = lipgloss.NewStyle().
		PaddingLeft(2)

	selectedTaskStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#EE6FF8")).
		Background(lipgloss.Color("#313244")).
		PaddingLeft(2)

	completedTaskStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#A6E3A1")).
		Strikethrough(true)

	// Priority styles
	highPriorityStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#F38BA8"))

	mediumPriorityStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#FAB387"))

	lowPriorityStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#F9E2AF"))

	// Context styles
	contextStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#89B4FA")).
		Bold(true)

	// Error style
	errorStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#F38BA8")).
		Bold(true)

	// Help style
	helpStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("#6C7086"))

	// Input styles
	inputStyle = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		Padding(1).
		Margin(1)
)

// Initialize creates a new model
func Initialize() Model {
	homeDir, _ := os.UserHomeDir()
	configPath := filepath.Join(homeDir, ".config", "tuido")

	ti := textinput.New()
	ti.Focus()
	ti.CharLimit = 200
	ti.Width = 50

	dateInputs := make([]textinput.Model, 3)
	for i := range dateInputs {
		dateInputs[i] = textinput.New()
		dateInputs[i].Focus()
		dateInputs[i].CharLimit = 4
		dateInputs[i].Width = 10
	}

	m := Model{
		textInput:      ti,
		dateInputs:     dateInputs,
		keyMap:         DefaultKeyMap(),
		help:           help.New(),
		configPath:     configPath,
		maxHistory:     50,
		viewMode:       NormalView,
	}

	m.loadConfig()
	m.updateContexts()

	return m
}

// Init implements tea.Model
func (m Model) Init() tea.Cmd {
	return textinput.Blink
}

// Update implements tea.Model  
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.windowWidth = msg.Width
		m.windowHeight = msg.Height
		m.help.Width = msg.Width
		return m, tea.ClearScreen

	case tea.KeyMsg:
		// Clear error message on any key press
		m.errorMessage = ""

		// Handle input mode
		if m.viewMode == InputView {
			return m.updateInputMode(msg)
		} else if m.viewMode == DateInputView {
			return m.updateDateInputMode(msg)
		} else if m.viewMode == RemoveTagView {
			return m.updateRemoveTagMode(msg)
		}

		// Handle different view modes
		switch m.viewMode {
		case NormalView, SearchView:
			return m.updateNormalView(msg)
		case KanbanView:
			return m.updateKanbanView(msg)
		case StatsView:
			return m.updateStatsView(msg)
		}
	}

	return m, nil
}

// updateInputMode handles input dialog updates
func (m Model) updateInputMode(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd

	switch {
	case key.Matches(msg, m.keyMap.Back):
		m.viewMode = NormalView
		return m, nil

	case key.Matches(msg, m.keyMap.Enter):
		input := strings.TrimSpace(m.textInput.Value())
		m.textInput.SetValue("")
		
		switch m.inputMode {
		case AddTaskInput:
			if input != "" {
				m.saveStateForUndo()
				m.addTask(input)
			}
		case EditTaskInput:
			if input != "" {
				m.saveStateForUndo()
				m.editCurrentTask(input)
			}
		case AddContextInput:
			if input != "" {
				m.addContext(input)
			}
		case RenameContextInput:
			if input != "" && input != m.currentContext {
				m.renameContext(input)
			}
		case AddTagInput:
			if input != "" {
				m.saveStateForUndo()
				m.addTagToCurrentTask(input)
			}
		case SearchInput:
			if input != "" {
				m.searchTasks(input)
			} else {
				m.viewMode = NormalView
			}
		case DeleteConfirmInput:
			if strings.ToLower(input) == "y" {
				m.saveStateForUndo()
				m.deleteContext()
			}
		}
		
		m.viewMode = NormalView
		return m, nil
	}

	m.textInput, cmd = m.textInput.Update(msg)
	return m, cmd
}

// updateDateInputMode handles due date input updates
func (m Model) updateDateInputMode(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd

	switch {
	case key.Matches(msg, m.keyMap.Back):
		m.viewMode = NormalView
		return m, nil

	case key.Matches(msg, m.keyMap.Enter):
		day := m.dateInputs[0].Value()
		month := m.dateInputs[1].Value()
		year := m.dateInputs[2].Value()
		dateStr := fmt.Sprintf("%s-%s-%s", year, month, day)
		m.saveStateForUndo()
		m.setDueDateForCurrentTask(dateStr)
		m.viewMode = NormalView
		return m, nil

	case key.Matches(msg, m.keyMap.Up):
		m.dateInputs[m.dateInputIndex].Blur()
		m.dateInputIndex = (m.dateInputIndex - 1 + 3) % 3
		m.dateInputs[m.dateInputIndex].Focus()

	case key.Matches(msg, m.keyMap.Down):
		m.dateInputs[m.dateInputIndex].Blur()
		m.dateInputIndex = (m.dateInputIndex + 1) % 3
		m.dateInputs[m.dateInputIndex].Focus()
	}

	m.dateInputs[m.dateInputIndex], cmd = m.dateInputs[m.dateInputIndex].Update(msg)
	return m, cmd
}

// updateRemoveTagMode handles remove tag view updates
func (m Model) updateRemoveTagMode(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch {
	case key.Matches(msg, m.keyMap.Back):
		m.viewMode = NormalView
		return m, nil

	case key.Matches(msg, m.keyMap.Enter):
		m.saveStateForUndo()
		m.removeTagsFromCurrentTask()
		m.viewMode = NormalView
		return m, nil

	case key.Matches(msg, m.keyMap.Up):
		if m.removeTagIndex > 0 {
			m.removeTagIndex--
		}

	case key.Matches(msg, m.keyMap.Down):
		task := m.getCurrentTask()
		if m.removeTagIndex < len(task.Tags)-1 {
			m.removeTagIndex++
		}

	case key.Matches(msg, m.keyMap.Toggle):
		m.removeTagChecks[m.removeTagIndex] = !m.removeTagChecks[m.removeTagIndex]
	}

	return m, nil
}

// updateNormalView handles normal view updates
func (m Model) updateNormalView(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch {
	case key.Matches(msg, m.keyMap.Quit):
		m.saveConfig()
		return m, tea.Quit

	case key.Matches(msg, m.keyMap.Back):
		if m.viewMode == SearchView {
			m.exitSearchMode()
		}
		return m, nil

	case key.Matches(msg, m.keyMap.Up):
		if m.movingMode {
			m.moveTaskUp()
		} else {
			m.moveUp()
		}

	case key.Matches(msg, m.keyMap.Down):
		if m.movingMode {
			m.moveTaskDown()
		} else {
			m.moveDown()
		}

	case key.Matches(msg, m.keyMap.Left):
		m.previousContext()

	case key.Matches(msg, m.keyMap.Right):
		m.nextContext()

	case key.Matches(msg, m.keyMap.Toggle):
		if len(m.getFilteredTasks()) > 0 {
			m.saveStateForUndo()
			m.toggleCurrentTask()
		}

	case key.Matches(msg, m.keyMap.Add):
		m.showInputDialog(AddTaskInput, "Add new task:")

	case key.Matches(msg, m.keyMap.Edit):
		if len(m.getFilteredTasks()) > 0 {
			task := m.getCurrentTask()
			m.showInputDialog(EditTaskInput, "Edit task:")
			m.textInput.SetValue(task.Task)
		}

	case key.Matches(msg, m.keyMap.Delete):
		if len(m.getFilteredTasks()) > 0 {
			m.saveStateForUndo()
			m.deleteCurrentTask()
		}

	case key.Matches(msg, m.keyMap.AddContext):
		m.showInputDialog(AddContextInput, "New context name:")

	case key.Matches(msg, m.keyMap.RenameContext):
		m.showInputDialog(RenameContextInput, "Rename context to:")
		m.textInput.SetValue(m.currentContext)

	case key.Matches(msg, m.keyMap.DeleteContext):
		if len(m.contexts) > 1 {
			m.showInputDialog(DeleteConfirmInput, fmt.Sprintf("Delete context '%s'? (y/n):", m.currentContext))
		} else {
			m.errorMessage = "Cannot delete the only context"
		}

	case key.Matches(msg, m.keyMap.TogglePriority):
		if len(m.getFilteredTasks()) > 0 {
			m.saveStateForUndo()
			m.toggleCurrentTaskPriority()
		}

	case key.Matches(msg, m.keyMap.AddTag):
		if len(m.getFilteredTasks()) > 0 {
			m.showInputDialog(AddTagInput, "Add tag:")
		}

	case key.Matches(msg, m.keyMap.RemoveTag):
		if len(m.getFilteredTasks()) > 0 {
			m.showRemoveTagDialog()
		}

	case key.Matches(msg, m.keyMap.SetDueDate):
		if len(m.getFilteredTasks()) > 0 {
			m.showDateInputDialog()
		}

	case key.Matches(msg, m.keyMap.ClearDueDate):
		if len(m.getFilteredTasks()) > 0 {
			m.saveStateForUndo()
			m.setDueDateForCurrentTask("clear")
		}

	case key.Matches(msg, m.keyMap.Search):
		m.showInputDialog(SearchInput, "Search tasks:")

	case key.Matches(msg, m.keyMap.KanbanView):
		m.viewMode = KanbanView

	case key.Matches(msg, m.keyMap.StatsView):
		m.viewMode = StatsView

	case key.Matches(msg, m.keyMap.Undo):
		m.undo()

	case key.Matches(msg, m.keyMap.Move):
		if len(m.getFilteredTasks()) > 0 {
			m.movingMode = !m.movingMode
			if m.movingMode {
				m.movingTaskIndex = m.selectedIndex
			} else {
				m.saveStateForUndo()
			}
		}
	}

	return m, nil
}

// updateKanbanView handles kanban view updates
func (m Model) updateKanbanView(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch {
	case key.Matches(msg, m.keyMap.Back), key.Matches(msg, m.keyMap.Quit), key.Matches(msg, m.keyMap.KanbanView):
		m.viewMode = NormalView
	}
	return m, nil
}

// updateStatsView handles stats view updates  
func (m Model) updateStatsView(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch {
	case key.Matches(msg, m.keyMap.Back), key.Matches(msg, m.keyMap.Quit), key.Matches(msg, m.keyMap.StatsView):
		m.viewMode = NormalView
	}
	return m, nil
}

// View implements tea.Model
func (m Model) View() string {
	switch m.viewMode {
	case InputView:
		return m.renderInputView()
	case DateInputView:
		return m.renderDateInputView()
	case RemoveTagView:
		return m.renderRemoveTagView()
	case KanbanView:
		return m.renderKanbanView()
	case StatsView:
		return m.renderStatsView()
	default:
		return m.renderNormalView()
	}
}

// renderNormalView renders the main task list view
func (m Model) renderNormalView() string {
	var content strings.Builder

	// Header
	contextText := fmt.Sprintf("Context: %s", m.currentContext)
	if m.viewMode == SearchView {
		contextText = "Search Results (ESC to exit)"
	}
	content.WriteString(titleStyle.Render(contextText) + "\n\n")

	// Tasks
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		if m.viewMode == SearchView {
			content.WriteString("No matching tasks found.\n")
		} else if len(m.contexts) == 0 {
			content.WriteString("No contexts exist. Press 'n' to create one.\n")
		} else {
			content.WriteString("No tasks in this context. Press 'a' to add one.\n")
		}
	} else {
		for i, task := range tasks {
			taskLine := m.renderTask(task, i == m.selectedIndex, i == m.movingTaskIndex && m.movingMode)
			content.WriteString(taskLine + "\n")
		}
	}

	// Error message
	if m.errorMessage != "" {
		content.WriteString("\n" + errorStyle.Render(m.errorMessage) + "\n")
	}

	// Help
	m.help.ShowAll = true
	content.WriteString("\n" + helpStyle.Render(m.help.View(m.keyMap)))

	return baseStyle.Render(content.String())
}

// renderTask renders a single task
func (m Model) renderTask(task Task, selected, moving bool) string {
	// Checkbox
	checkbox := "[ ]"
	if task.Checked {
		checkbox = "[✓]"
	}

	// Priority indicator
	priority := ""
	switch task.Priority {
	case "high":
		priority = highPriorityStyle.Render("!!! ")
	case "medium":
		priority = mediumPriorityStyle.Render("!! ")
	case "low":
		priority = lowPriorityStyle.Render("! ")
	}

	// Task text
	taskText := task.Task

	// Tags
	tags := ""
	if len(task.Tags) > 0 {
		tags = " > " + strings.Join(task.Tags, ", ")
	}

	// Due date
	dueDate := ""
	if task.DueDate != "" {
		dueDate = fmt.Sprintf(" [Due: %s]", task.DueDate)
	}

	// Combine text
	text := fmt.Sprintf("%s %s%s%s", checkbox, taskText, tags, dueDate)

	// Apply styles
	style := taskStyle
	if task.Checked {
		style = completedTaskStyle
	}

	if selected {
		style = style.Copy().Background(lipgloss.Color("#313244"))
	}

	if moving {
		style = style.Copy().Bold(true)
	}

	return priority + style.Render(text)
}

// renderInputView renders input dialogs
func (m Model) renderInputView() string {
	return inputStyle.Render(
		fmt.Sprintf("%s\n\n%s", m.inputPrompt, m.textInput.View()),
	)
}

// renderDateInputView renders due date input dialog
func (m Model) renderDateInputView() string {
	var content strings.Builder
	content.WriteString("Set due date (YYYY-MM-DD):\n\n")
	inputs := []string{
		fmt.Sprintf("Day: %s", m.dateInputs[0].View()),
		fmt.Sprintf("Month: %s", m.dateInputs[1].View()),
		fmt.Sprintf("Year: %s", m.dateInputs[2].View()),
	}
	for i, input := range inputs {
		if i == m.dateInputIndex {
			content.WriteString(selectedTaskStyle.Render(input) + "\n")
		} else {
			content.WriteString(input + "\n")
		}
	}
	return inputStyle.Render(content.String())
}

// renderRemoveTagView renders remove tag view
func (m Model) renderRemoveTagView() string {
	var content strings.Builder
	content.WriteString("Select tags to remove:\n\n")
	task := m.getCurrentTask()
	for i, tag := range task.Tags {
		checkbox := "[ ]"
		if m.removeTagChecks[i] {
			checkbox = "[✓]"
		}
		line := fmt.Sprintf("%s %s", checkbox, tag)
		if i == m.removeTagIndex {
			content.WriteString(selectedTaskStyle.Render(line) + "\n")
		} else {
			content.WriteString(line + "\n")
		}
	}
	return inputStyle.Render(content.String())
}

// renderKanbanView renders the kanban board
func (m Model) renderKanbanView() string {
	var content strings.Builder
	
	content.WriteString(titleStyle.Render("Kanban View (ESC to return)") + "\n\n")

	if len(m.contexts) == 0 {
		content.WriteString("No contexts available.\n")
		return baseStyle.Render(content.String())
	}

	// Calculate column width
	colWidth := (m.windowWidth - 4) / len(m.contexts)
	if colWidth < 20 {
		colWidth = 20
	}

	// Render columns
	var columns []string
	for _, context := range m.contexts {
		var column strings.Builder
		
		// Column header
		header := contextStyle.Render(context)
		column.WriteString(header + "\n")
		column.WriteString(strings.Repeat("─", colWidth) + "\n")

		// Tasks in this context
		tasks := m.getTasksForContext(context)
		for _, task := range tasks {
			taskText := task.Task
			if len(taskText) > colWidth-4 {
				taskText = taskText[:colWidth-7] + "..."
			}

			tags := ""
			if len(task.Tags) > 0 {
				tags = " > " + strings.Join(task.Tags, ", ")
			}

			dueDate := ""
			if task.DueDate != "" {
				dueDate = fmt.Sprintf(" [Due: %s]", task.DueDate)
			}

			if task.Checked {
				column.WriteString(completedTaskStyle.Render(fmt.Sprintf("✓ %s%s%s", taskText, tags, dueDate)) + "\n")
			} else {
				column.WriteString(taskStyle.Render(fmt.Sprintf("• %s%s%s", taskText, tags, dueDate)) + "\n")
			}
		}

		columns = append(columns, column.String())
	}

	// Combine columns side by side (simplified - in real implementation you'd use lipgloss.JoinHorizontal)
	for i, col := range columns {
		if i > 0 {
			content.WriteString(" | ")
		}
		content.WriteString(col)
	}

	return baseStyle.Render(content.String())
}

// renderStatsView renders the statistics view
func (m Model) renderStatsView() string {
	var content strings.Builder
	
	content.WriteString(titleStyle.Render("Statistics (ESC to return)") + "\n\n")

	// Overall stats
	total := len(m.tasks)
	completed := 0
	for _, task := range m.tasks {
		if task.Checked {
			completed++
		}
	}

	completionRate := 0.0
	if total > 0 {
		completionRate = float64(completed) / float64(total) * 100
	}

	content.WriteString(fmt.Sprintf("Total Tasks: %d\n", total))
	content.WriteString(fmt.Sprintf("Completed: %d (%.1f%%)\n\n", completed, completionRate))

	// Context stats
	content.WriteString("Context Statistics:\n")
	for _, context := range m.contexts {
		tasks := m.getTasksForContext(context)
		ctxTotal := len(tasks)
		ctxCompleted := 0
		for _, task := range tasks {
			if task.Checked {
				ctxCompleted++
			}
		}

		ctxRate := 0.0
		if ctxTotal > 0 {
			ctxRate = float64(ctxCompleted) / float64(ctxTotal) * 100
		}

		content.WriteString(fmt.Sprintf("  %s: %d/%d (%.1f%%)\n", 
			contextStyle.Render(context), ctxCompleted, ctxTotal, ctxRate))
	}

	return baseStyle.Render(content.String())
}

// Helper methods

func (m *Model) showInputDialog(mode InputMode, prompt string) {
	m.viewMode = InputView
	m.inputMode = mode
	m.inputPrompt = prompt
	m.textInput.SetValue("")
	m.textInput.Focus()
}

func (m *Model) showDateInputDialog() {
	m.viewMode = DateInputView
	m.dateInputIndex = 0
	now := time.Now()
	m.dateInputs[0].SetValue(fmt.Sprintf("%02d", now.Day()))
	m.dateInputs[1].SetValue(fmt.Sprintf("%02d", now.Month()))
	m.dateInputs[2].SetValue(fmt.Sprintf("%d", now.Year()))
	for i := range m.dateInputs {
		m.dateInputs[i].Focus()
	}
}

func (m *Model) showRemoveTagDialog() {
	task := m.getCurrentTask()
	if len(task.Tags) == 0 {
		m.errorMessage = "No tags to remove"
		return
	}
	m.viewMode = RemoveTagView
	m.removeTagIndex = 0
	m.removeTagChecks = make([]bool, len(task.Tags))
}

func (m *Model) getFilteredTasks() []Task {
	if m.viewMode == SearchView {
		return m.searchResults
	}
	return m.getTasksForContext(m.currentContext)
}

func (m *Model) getTasksForContext(context string) []Task {
	var filtered []Task
	for _, task := range m.tasks {
		if task.Context == context {
			filtered = append(filtered, task)
		}
	}
	return filtered
}

func (m *Model) getCurrentTask() Task {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 || m.selectedIndex >= len(tasks) {
		return Task{}
	}
	return tasks[m.selectedIndex]
}

func (m *Model) moveUp() {
	tasks := m.getFilteredTasks()
	if len(tasks) > 0 {
		m.selectedIndex = (m.selectedIndex - 1 + len(tasks)) % len(tasks)
	}
}

func (m *Model) moveDown() {
	tasks := m.getFilteredTasks()
	if len(tasks) > 0 {
		m.selectedIndex = (m.selectedIndex + 1) % len(tasks)
	}
}

func (m *Model) moveTaskUp() {
	tasks := m.getFilteredTasks()
	if m.selectedIndex > 0 {
		taskToMove := tasks[m.selectedIndex]
		for i := range m.tasks {
			if m.tasks[i].ID == taskToMove.ID {
				m.tasks[i], m.tasks[i-1] = m.tasks[i-1], m.tasks[i]
				break
			}
		}
		m.selectedIndex--
	}
}

func (m *Model) moveTaskDown() {
	tasks := m.getFilteredTasks()
	if m.selectedIndex < len(tasks)-1 {
		taskToMove := tasks[m.selectedIndex]
		for i := range m.tasks {
			if m.tasks[i].ID == taskToMove.ID {
				m.tasks[i], m.tasks[i+1] = m.tasks[i+1], m.tasks[i]
				break
			}
		}
		m.selectedIndex++
	}
}

func (m *Model) nextContext() {
	if len(m.contexts) > 0 {
		currentIdx := m.findContextIndex(m.currentContext)
		nextIdx := (currentIdx + 1) % len(m.contexts)
		m.currentContext = m.contexts[nextIdx]
		m.selectedIndex = 0
	}
}

func (m *Model) previousContext() {
	if len(m.contexts) > 0 {
		currentIdx := m.findContextIndex(m.currentContext)
		prevIdx := (currentIdx - 1 + len(m.contexts)) % len(m.contexts)
		m.currentContext = m.contexts[prevIdx]
		m.selectedIndex = 0
	}
}

func (m *Model) findContextIndex(context string) int {
	for i, ctx := range m.contexts {
		if ctx == context {
			return i
		}
	}
	return 0
}

func (m *Model) toggleCurrentTask() {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			m.tasks[i].Checked = !m.tasks[i].Checked
			break
		}
	}
}

func (m *Model) addTask(taskText string) {
	newTask := Task{
		ID:      m.nextID,
		Task:    taskText,
		Checked: false,
		Context: m.currentContext,
	}
	m.tasks = append(m.tasks, newTask)
	m.nextID++
	
	// Move selection to new task
	filtered := m.getFilteredTasks()
	m.selectedIndex = len(filtered) - 1
}

func (m *Model) editCurrentTask(newText string) {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			m.tasks[i].Task = newText
			break
		}
	}
}

func (m *Model) deleteCurrentTask() {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			m.tasks = append(m.tasks[:i], m.tasks[i+1:]...)
			break
		}
	}

	// Adjust selection
	newTasks := m.getFilteredTasks()
	if m.selectedIndex >= len(newTasks) && len(newTasks) > 0 {
		m.selectedIndex = len(newTasks) - 1
	}
}

func (m *Model) addContext(contextName string) {
	// Check if context already exists
	for _, ctx := range m.contexts {
		if ctx == contextName {
			m.errorMessage = "Context already exists"
			return
		}
	}

	m.contexts = append(m.contexts, contextName)
	m.currentContext = contextName
	m.selectedIndex = 0
}

func (m *Model) renameContext(newName string) {
	if newName == m.currentContext {
		return
	}

	// Check if new name already exists
	for _, ctx := range m.contexts {
		if ctx == newName {
			m.errorMessage = "Context name already exists"
			return
		}
	}

	oldName := m.currentContext

	// Update context in contexts list
	for i, ctx := range m.contexts {
		if ctx == oldName {
			m.contexts[i] = newName
			break
		}
	}

	// Update context in all tasks
	for i := range m.tasks {
		if m.tasks[i].Context == oldName {
			m.tasks[i].Context = newName
		}
	}

	m.currentContext = newName
}

func (m *Model) deleteContext() {
	if len(m.contexts) <= 1 {
		m.errorMessage = "Cannot delete the only context"
		return
	}

	// Remove all tasks in this context
	var newTasks []Task
	for _, task := range m.tasks {
		if task.Context != m.currentContext {
			newTasks = append(newTasks, task)
		}
	}
	m.tasks = newTasks

	// Remove context from list
	var newContexts []string
	for _, ctx := range m.contexts {
		if ctx != m.currentContext {
			newContexts = append(newContexts, ctx)
		}
	}
	m.contexts = newContexts

	// Switch to first remaining context
	if len(m.contexts) > 0 {
		m.currentContext = m.contexts[0]
		m.selectedIndex = 0
	}
}

func (m *Model) toggleCurrentTaskPriority() {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			priorities := []string{"", "low", "medium", "high"}
			currentIdx := 0
			for j, p := range priorities {
				if p == m.tasks[i].Priority {
					currentIdx = j
					break
				}
			}
			nextIdx := (currentIdx + 1) % len(priorities)
			m.tasks[i].Priority = priorities[nextIdx]
			break
		}
	}
}

func (m *Model) addTagToCurrentTask(tag string) {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			// Check if tag already exists
			for _, existingTag := range m.tasks[i].Tags {
				if existingTag == tag {
					return
				}
			}
			m.tasks[i].Tags = append(m.tasks[i].Tags, tag)
			break
		}
	}
}

func (m *Model) removeTagsFromCurrentTask() {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			var newTags []string
			for j, tag := range m.tasks[i].Tags {
				if !m.removeTagChecks[j] {
					newTags = append(newTags, tag)
				}
			}
			m.tasks[i].Tags = newTags
			break
		}
	}
}

func (m *Model) setDueDateForCurrentTask(dateStr string) {
	tasks := m.getFilteredTasks()
	if len(tasks) == 0 {
		return
	}

	currentTask := tasks[m.selectedIndex]
	for i := range m.tasks {
		if m.tasks[i].ID == currentTask.ID {
			if strings.ToLower(dateStr) == "clear" {
				m.tasks[i].DueDate = ""
			} else if dateStr != "" {
				// Basic date validation (YYYY-MM-DD format)
				parts := strings.Split(dateStr, "-")
				if len(parts) == 3 {
					if year, err := strconv.Atoi(parts[0]); err == nil && year > 1900 && year < 3000 {
						if month, err := strconv.Atoi(parts[1]); err == nil && month >= 1 && month <= 12 {
							if day, err := strconv.Atoi(parts[2]); err == nil && day >= 1 && day <= 31 {
								m.tasks[i].DueDate = dateStr
								return
							}
						}
					}
				}
				m.errorMessage = "Invalid date format. Use YYYY-MM-DD"
			}
			break
		}
	}
}

func (m *Model) searchTasks(query string) {
	var results []Task
	query = strings.ToLower(query)
	
	for _, task := range m.tasks {
		if strings.Contains(strings.ToLower(task.Task), query) {
			results = append(results, task)
		}
	}

	if len(results) == 0 {
		m.errorMessage = fmt.Sprintf("No tasks matching '%s'", query)
		return
	}

	m.prevContext = m.currentContext
	m.prevIndex = m.selectedIndex
	m.searchResults = results
	m.viewMode = SearchView
	m.selectedIndex = 0
}

func (m *Model) exitSearchMode() {
	m.viewMode = NormalView
	m.currentContext = m.prevContext
	m.selectedIndex = m.prevIndex
	m.searchResults = nil
}

func (m *Model) updateContexts() {
	contextMap := make(map[string]bool)
	for _, task := range m.tasks {
		contextMap[task.Context] = true
	}

	m.contexts = make([]string, 0, len(contextMap))
	for context := range contextMap {
		m.contexts = append(m.contexts, context)
	}
	sort.Strings(m.contexts)

	// Set current context if not set or if current doesn't exist
	if m.currentContext == "" || !contextMap[m.currentContext] {
		if len(m.contexts) > 0 {
			m.currentContext = m.contexts[0]
		} else {
			m.currentContext = "Work" // Default context
			m.contexts = []string{"Work"}
		}
	}
}

func (m *Model) saveStateForUndo() {
	// Deep copy current tasks
	stateCopy := make([]Task, len(m.tasks))
	copy(stateCopy, m.tasks)
	
	m.history = append(m.history, stateCopy)
	
	// Limit history size
	if len(m.history) > m.maxHistory {
		m.history = m.history[1:]
	}
}

func (m *Model) undo() {
	if len(m.history) == 0 {
		m.errorMessage = "Nothing to undo"
		return
	}

	// Restore previous state
	m.tasks = m.history[len(m.history)-1]
	m.history = m.history[:len(m.history)-1]
	
	// Update contexts and ensure current context is valid
	m.updateContexts()
	
	// Reset selection
	m.selectedIndex = 0
}

// Configuration and persistence

func (m *Model) loadConfig() {
	// Ensure config directory exists
	os.MkdirAll(m.configPath, 0755)
	
	configFile := filepath.Join(m.configPath, "config.json")
	
	// Try to load existing config
	data, err := ioutil.ReadFile(configFile)
	if err != nil {
		// Create default config
		m.createDefaultConfig()
		return
	}

	var config struct {
		Tasks  []Task `json:"tasks"`
		NextID int    `json:"next_id"`
	}

	if err := json.Unmarshal(data, &config); err != nil {
		m.createDefaultConfig()
		return
	}

	m.tasks = config.Tasks
	m.nextID = config.NextID
	
	// Ensure we have a valid next ID
	if m.nextID == 0 {
		maxID := 0
		for _, task := range m.tasks {
			if task.ID > maxID {
				maxID = task.ID
			}
		}
		m.nextID = maxID + 1
	}
}

func (m *Model) createDefaultConfig() {
	m.tasks = []Task{
		{ID: 1, Task: "Welcome to your todo app!", Checked: false, Context: "Work"},
		{ID: 2, Task: "Press 'a' to add a new task", Checked: false, Context: "Work"},
		{ID: 3, Task: "Press space to toggle completion", Checked: true, Context: "Personal"},
		{ID: 4, Task: "Use arrow keys to navigate", Checked: false, Context: "Personal"},
	}
	m.nextID = 5
}

func (m *Model) saveConfig() {
	configFile := filepath.Join(m.configPath, "config.json")
	
	config := struct {
		Tasks  []Task `json:"tasks"`
		NextID int    `json:"next_id"`
	}{
		Tasks:  m.tasks,
		NextID: m.nextID,
	}

	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return
	}

	ioutil.WriteFile(configFile, data, 0644)
}

// KeyMap methods to implement help.KeyMap interface
func (k KeyMap) ShortHelp() []key.Binding {
	return []key.Binding{k.Nav, k.Toggle, k.Add, k.Edit, k.Delete, k.Quit}
}

func (k KeyMap) FullHelp() [][]key.Binding {
	return [][]key.Binding{
		{k.Nav},
		{k.Toggle, k.Add, k.Edit, k.Delete, k.Move},
		{k.AddContext, k.RenameContext, k.DeleteContext},
		{k.TogglePriority, k.AddTag, k.RemoveTag, k.SetDueDate, k.ClearDueDate},
		{k.Search, k.KanbanView, k.StatsView},
		{k.Undo, k.Back, k.Quit},
	}
}

// Main function
func main() {
	p := tea.NewProgram(Initialize(), tea.WithAltScreen())
	
	if _, err := p.Run(); err != nil {
		fmt.Printf("Error running program: %v", err)
		os.Exit(1)
	}
}