# WebSocket Connection Lifecycle Analysis

## Scenario: Workflow Completed/Cancelled → File Change/Relaunch → Launch

### Initial State (Workflow Completed/Cancelled)
**Variables:**
- `status.value = 'Completed'` or `'Cancelled'`
- `isWorkflowRunning.value = false`
- `shouldGlow.value = true` (set by watch on status)
- `ws` = existing WebSocket connection (still open)
- `sessionId` = current session ID
- `isConnectionReady.value = true`

---

## Scenario 1: Another File is Chosen

### Step 1: File Selection Triggers Watch
**Function:** `watch(selectedFile, (newFile) => {...})` (line 879)

**Process:**
1. `taskPrompt.value = ''` - clears input
2. `fileSearchQuery.value = newFile || ''` - updates search query
3. `isFileSearchDirty.value = false` - resets search state

### Step 2: WebSocket Disconnection
**Function:** `resetConnectionState({ closeSocket: true })` (line 443)
**Called at:** line 891

**What happens:**
- ✅ **WebSocket DISCONNECTED** - `ws.close()` is called (line 446)
- `ws = null` (line 452)
- `sessionId = null` (line 453)
- `isConnectionReady.value = false` (line 454)
- `shouldGlow.value = false` (line 455)
- `isWorkflowRunning.value = false` (line 456)
- `activeNodes.value = []` (line 457)
- Clears attachment timeouts and uploaded attachments

**Status:** `status.value = 'Connecting...'` (line 892)

### Step 3: Load YAML
**Function:** `handleYAMLSelection(newFile)` (line 706)
**Called at:** line 893

**What happens:**
- Clears `chatMessages.value = []`
- Fetches YAML file content
- Parses YAML and stores in `workflowYaml.value`
- Displays `initial_instruction` as notification
- Loads VueFlow graph

### Step 4: WebSocket Reconnection
**Function:** `establishWebSocketConnection()` (line 807)
**Called at:** line 894

**What happens:**
1. **Double Reset:** Calls `resetConnectionState()` again (line 809) - ensures clean state
2. **New WebSocket Created:**
   - `const socket = new WebSocket('ws://localhost:8000/ws')` (line 816)
   - `ws = socket` (line 817)
3. **Connection Events:**
   - `socket.onopen` (line 819): Logs "WebSocket connected"
   - `socket.onmessage` (line 825): 
     - Receives `connection` message with `session_id`
     - Sets `sessionId` (line 832)
     - Sets `isConnectionReady.value = true` (line 842)
     - Sets `shouldGlow.value = true` (line 843)
     - Sets `status.value = 'Waiting for launch...'` (line 844)
   - `socket.onerror` (line 854): Handles connection errors
   - `socket.onclose` (line 864): Handles disconnection

**Status:** `status.value = 'Waiting for launch...'` (after connection message received)

---

## Scenario 2: Relaunch Button Clicked

### Step 1: Button Click Handler
**Function:** `handleButtonClick()` (line 740)
**Triggered:** When Launch button is clicked and status is 'Completed'/'Cancelled'

**Condition Check:**
```javascript
else if (status.value === 'Completed' || status.value === 'Cancelled')
```

### Step 2: WebSocket Disconnection
**Function:** `resetConnectionState()` (line 443)
**Called at:** line 754

**What happens:**
- ✅ **WebSocket DISCONNECTED** - `ws.close()` is called
- All state variables reset (same as Scenario 1, Step 2)

**Status:** `status.value = 'Connecting...'` (line 755)

### Step 3: Load YAML
**Function:** `handleYAMLSelection(selectedFile.value)` (line 706)
**Called at:** line 756

**What happens:** Same as Scenario 1, Step 3

### Step 4: WebSocket Reconnection
**Function:** `establishWebSocketConnection()` (line 807)
**Called at:** line 757

**What happens:** Same as Scenario 1, Step 4

**Status:** `status.value = 'Waiting for launch...'` (after connection message received)

---

## Step 5: Launch Button Clicked (After Reconnection)

### Launch Workflow
**Function:** `launchWorkflow()` (line 1124)
**Triggered:** When Launch button is clicked and status is 'Waiting for launch...'

**Prerequisites Check:**
- `selectedFile.value` must exist
- `taskPrompt.value.trim()` or `attachmentIds.length > 0` must exist
- `ws`, `isConnectionReady.value`, and `sessionId` must be valid

**What happens:**
1. Sets `shouldGlow.value = false` (line 1150)
2. Sets `status.value = 'Launching...'` (line 1151)
3. Sends POST request to `/api/workflow/execute` with:
   - `yaml_file`: selected file name
   - `task_prompt`: user input
   - `session_id`: current session ID
   - `attachments`: uploaded attachment IDs
4. On success:
   - Clears uploaded attachments
   - Adds user dialogue to chat
   - Sets `status.value = 'Running...'` (line 1185)
   - Sets `isWorkflowRunning.value = true` (line 1186)

**Status:** `status.value = 'Running...'`

---

## Key Variables and Their Roles

### WebSocket State Variables
| Variable | Type | Purpose | Changes When |
|----------|------|---------|--------------|
| `ws` | `WebSocket \| null` | Current WebSocket connection | Set to `null` on disconnect, new socket on connect |
| `sessionId` | `string \| null` | Current session identifier | Set from connection message, cleared on reset |
| `isConnectionReady` | `ref<boolean>` | Whether connection is ready for launch | `true` after connection message, `false` on reset |

### Status Variables
| Variable | Type | Purpose | Values |
|----------|------|---------|--------|
| `status` | `ref<string>` | Current workflow status | 'Completed', 'Cancelled', 'Connecting...', 'Waiting for launch...', 'Launching...', 'Running...' |
| `isWorkflowRunning` | `ref<boolean>` | Whether workflow is actively running | `true` during execution, `false` otherwise |
| `shouldGlow` | `ref<boolean>` | UI glow effect state | `true` when ready for input, `false` during execution |

### Workflow State Variables
| Variable | Type | Purpose |
|----------|------|---------|
| `selectedFile` | `ref<string>` | Currently selected YAML file |
| `workflowYaml` | `ref<object>` | Parsed YAML content |
| `activeNodes` | `ref<string[]>` | List of currently active node IDs |
| `chatMessages` | `ref<array>` | All chat messages and notifications |

---

## WebSocket Connection Timeline

### When Disconnected:
1. **File Change:** `watch(selectedFile)` → `resetConnectionState()` → `ws.close()`
2. **Relaunch:** `handleButtonClick()` → `resetConnectionState()` → `ws.close()`
3. **Error/Close Events:** `socket.onerror` or `socket.onclose` → `resetConnectionState({ closeSocket: false })`

### When Reconnected:
1. **File Change:** `watch(selectedFile)` → `establishWebSocketConnection()` → `new WebSocket()`
2. **Relaunch:** `handleButtonClick()` → `establishWebSocketConnection()` → `new WebSocket()`

### Connection States:
```
[Completed/Cancelled] 
    ↓ (File Change or Relaunch)
[Disconnected] → resetConnectionState() closes ws
    ↓
[Connecting...] → establishWebSocketConnection() creates new ws
    ↓
[WebSocket.onopen] → socket opened
    ↓
[WebSocket.onmessage: 'connection'] → sessionId received
    ↓
[Waiting for launch...] → isConnectionReady = true
    ↓ (Launch clicked)
[Launching...] → POST /api/workflow/execute
    ↓
[Running...] → isWorkflowRunning = true
```

---

## Important Notes

1. **Double Reset Issue:** `establishWebSocketConnection()` calls `resetConnectionState()` at the start (line 809), which means when called after `resetConnectionState()` in the caller, it's resetting twice. This is safe but redundant.

2. **Stale Socket Protection:** All WebSocket event handlers check `if (ws !== socket) return` to ignore events from old sockets that were replaced.

3. **Status Transitions:** The status goes through these states:
   - `Completed/Cancelled` → `Connecting...` → `Waiting for launch...` → `Launching...` → `Running...`

4. **Connection Ready Check:** `launchWorkflow()` verifies `ws`, `isConnectionReady.value`, and `sessionId` before allowing launch.

5. **Automatic Reconnection:** Both file change and relaunch automatically establish a new WebSocket connection - no manual reconnection needed.

