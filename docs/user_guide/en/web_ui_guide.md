# Frontend Web UI Quick Start Guide

This guide helps users quickly get started with the DevAll Web UI, covering main functional pages and operation workflows.

## 1. System Entry

After starting frontend and backend services, visit `http://localhost:5173` to access the Web UI.

## 2. Main Pages

### 2.1 Home

System homepage providing quick navigation links.

### 2.2 Workflow List

View and manage all available workflow YAML files.

**Features**:
- Browse workflows in `yaml_instance/` directory
- Preview YAML configuration content
- Select workflow to execute or edit
- **Generate**: describe a workflow in plain language and an agent writes the YAML (see below)

**Generating a workflow**: Generate runs `yaml_instance/workflow_designer.yaml` with the server's `BASE_URL`, `API_KEY` and its `MODEL_NAME` (default `gpt-4o`). The designer reads the authoring guide, node docs and bundled examples through function tools, then validates its YAML with the same check the save route uses. Its validator also requires every agent node to use the `${BASE_URL}`, `${API_KEY}` and `${MODEL_NAME}` placeholders and rejects anything that looks like an API key. The result opens in an editable preview; **Save and open** writes it to `yaml_instance/<name>.yaml` and opens it in the workbench. If the YAML still fails validation, the errors are listed as comments at the top; schema errors also block saving. The same workflow runs headless: `echo "your description" | uv run python run.py --path yaml_instance/workflow_designer.yaml --name designer`.

### 2.3 Launch View

The main interface for workflow execution, the most commonly used page.

**Operation Flow**:
1. **Select workflow**: Choose YAML file from the left panel
2. **Upload attachments** (optional): Click upload button to add files (CSV data, images, etc.)
3. **Enter task prompt**: Input instructions in the text box to guide workflow execution
4. **Click Launch**: Start workflow execution

**During Execution**:
- **Nodes View**: Observe node status changes (pending → running → success/failed)
- **Output Panel**: View real-time execution logs, node output context, and generated artifacts (all share the same panel)

**Human Input**:
- When execution reaches a `human` node, the interface displays an input prompt
- Fill in text content or upload attachments, then submit to continue execution

### 2.4 Workflow Workbench

Visual workflow editor.

**Features**:
- Drag-and-drop node editing
- Node configuration panel
- Edge connections and condition settings
- Export to YAML file

### 2.5 Tutorial

Built-in tutorial to help new users understand system features.

## 3. Common Operations

### 3.1 Running a Workflow

1. Go to **Launch View**
2. Select workflow from the left panel
3. Enter Task Prompt
4. Click **Launch** button
5. Monitor execution progress and wait for completion

### 3.2 Downloading Results

After execution completes:
1. Click the **Download** button on the right panel
2. Download the complete Session archive (includes context.json, attachments, logs, etc.)

### 3.3 Human Review Node Interaction

When workflow contains `human` nodes:
1. Execution pauses and displays prompt message
2. Read context content
3. Enter review comments or action instructions
4. Click submit to continue execution

## 4. Keyboard Shortcuts

| Shortcut | Function |
|----------|----------|
| `Ctrl/Cmd + Enter` | Submit input |
| `Esc` | Close popup/panel |

## 5. Troubleshooting

| Issue | Solution |
|-------|----------|
| Page won't load | Confirm frontend `npm run dev` is running |
| Cannot connect to backend | Confirm backend `uv run python server_main.py` is running |
| Empty workflow list | Check `yaml_instance/` directory for YAML files |
| Execution unresponsive | Check browser DevTools Network/Console logs |
| WebSocket disconnected | Refresh page to re-establish connection |

## 6. Related Documentation

- [Workflow Authoring](workflow_authoring.md) - YAML writing guide
