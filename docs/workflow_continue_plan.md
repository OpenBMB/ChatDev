# Workflow Continue — Kaldığı Yerden Devam Ettirme

## Context

Workflow tamamlandıktan sonra aynı ekibe ek iş vermek istiyoruz. Şu an "Relaunch" butonu her şeyi sıfırdan başlatıyor: yeni WebSocket session, yeni Claude Code session, boş context. Workspace dosyaları fiziksel olarak kalsa da Claude Code önceki çalışmayı hatırlamıyor.

**Hedef**: "Continue" butonu ile aynı workspace'de, Claude Code'un önceki session'ını resume ederek, mevcut dosyaların farkında olarak devam etmek.

**Neden önemli**: Claude Code `--resume` flag'i ile önceki session'ın tüm context'ini koruyabiliyor. Dosyaları tekrar okumak yerine direkt hatırlayıp devam edebilir.

## Mevcut Durum

```
Relaunch akışı (şu an):
  Frontend: resetConnectionState() → yeni WebSocket → yeni ws_session_id
  Backend:  workspace name = "session_{ws_session_id}" → WareHouse/session_{ws_session_id}/
            Her Relaunch farklı ws_session_id → farklı workspace
            Claude Code _sessions dict'i class-level ama Relaunch farklı workspace kullanıyor
  Sonuç:    Dosyalar eski workspace'te kalıyor, yeni workspace boş başlıyor

Önemli keşif:
  - clear_all_sessions() sadece runtime/sdk.py'de (CLI mode) çağrılıyor
  - WebSocket modunda (websocket_executor.py) sessions temizlenMİyor
  - Ama Relaunch yeni ws_session_id oluşturuyor → workspace adı değişiyor
  - GraphConfig name = f"session_{ws_session_id}" → farklı dizin
```

## Tasarım

```
Continue akışı (yeni):
  Frontend: "Continue" butonuna tıkla → yeni WebSocket → yeni ws_session_id
            POST /api/workflow/execute { previous_session_id: "eski-id", mode: "continue" }
  Backend:  workspace = WareHouse/session_{previous_session_id}/code_workspace/  (REUSE)
            Claude Code sessions = workspace/.claude_sessions.json'dan yükle
            Prompt'a workspace file listing inject et
  Sonuç:    Claude Code --resume ile devam, tüm dosyalar ve context mevcut
```

## Değişiklikler

### 1. MODIFY: `claude_code_provider.py` — Session Persist/Load

Dosya: `runtime/node/agent/providers/claude_code_provider.py`

Mevcut `_sessions` dict'i sadece in-memory. Workspace'e kaydetme/yükleme ekle.

**Yeni static metodlar:**
```python
@classmethod
def save_sessions_to_workspace(cls, workspace_root: str) -> None:
    """Persist current sessions to workspace for future continuation."""
    path = Path(workspace_root) / ".claude_sessions.json"
    with cls._sessions_lock:
        if cls._sessions:
            path.write_text(json.dumps(cls._sessions))

@classmethod
def load_sessions_from_workspace(cls, workspace_root: str) -> None:
    """Load previously saved sessions from workspace."""
    path = Path(workspace_root) / ".claude_sessions.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            with cls._sessions_lock:
                cls._sessions.update(data)
        except (json.JSONDecodeError, OSError):
            pass
```

**`call_model()` değişikliği:**
- Session kaydedildikten sonra (`set_session` çağrısının ardından) `save_sessions_to_workspace(cwd)` çağır

**`_build_prompt()` değişikliği — workspace context injection:**
- Non-continuation prompt'larda, workspace'de dosya varsa listeleme ekle
- Yeni helper: `_scan_workspace_for_prompt(workspace_root) -> Optional[str]`
- `[Existing Workspace Files]:\n- main.py (2.1KB)\n- utils.py (800B)` bloğu prompt'a eklenir
- Mevcut `_snapshot_workspace` helper'ından faydalanır (zaten scan yapıyor)

### 2. MODIFY: `server/models.py` — Continue parametresi

```python
class WorkflowRequest(BaseModel):
    yaml_file: str
    task_prompt: str
    session_id: Optional[str] = None
    attachments: Optional[List[str]] = None
    log_level: Literal["INFO", "DEBUG"] = "INFO"
    previous_session_id: Optional[str] = None  # EKLENDİ: continue mode
```

### 3. MODIFY: `server/routes/execute.py` — previous_session_id iletimi

`execute_workflow()` handler'ında `start_workflow()` çağrısına `previous_session_id` ekle:
```python
manager.workflow_run_service.start_workflow(
    ...
    previous_session_id=request.previous_session_id,
)
```

### 4. MODIFY: `server/services/workflow_run_service.py` — Workspace reuse

**`start_workflow()` imzası:**
```python
async def start_workflow(self, ..., previous_session_id: Optional[str] = None):
```
`_execute_workflow_async()`'a `previous_session_id` ilet.

**`_execute_workflow_async()` değişiklikleri:**
```python
async def _execute_workflow_async(self, ..., previous_session_id: Optional[str] = None):
    # Workspace name: eski session_id varsa onu kullan
    workspace_name = f"session_{previous_session_id}" if previous_session_id else f"session_{session_id}"

    graph_config = GraphConfig.from_definition(
        design.graph,
        name=workspace_name,  # ← eski workspace'i reuse
        ...
    )
```
Execute başlamadan önce Claude Code session'larını yükle:
```python
if previous_session_id:
    from runtime.node.agent.providers.claude_code_provider import ClaudeCodeProvider
    code_workspace = graph_context.directory / "code_workspace"
    ClaudeCodeProvider.load_sessions_from_workspace(str(code_workspace))
```

### 5. MODIFY: `runtime/sdk.py` — Session save before cleanup (satır 124-126)

```python
# Save sessions to workspace before clearing (for future continuation)
code_workspace = graph_context.directory / "code_workspace"
if code_workspace.exists():
    ClaudeCodeProvider.save_sessions_to_workspace(str(code_workspace))
ClaudeCodeProvider.clear_all_sessions()
```

### 6. MODIFY: `frontend/src/pages/LaunchView.vue` — Continue butonu

**Yeni state (ref'ler arasına):**
```javascript
const completedSessionId = ref(null)  // son tamamlanan session'ın ID'si
```

**workflow_completed handler'ında** (WebSocket message handler):
```javascript
// Mevcut: status.value = 'Completed'
completedSessionId.value = sessionId  // ← EKLENDİ
```

**İki buton — "Continue" (yeşil/primary) + "Relaunch" (gri/secondary):**

Template'de mevcut tek buton yerine:
```html
<!-- Completed state: iki buton göster -->
<button v-if="status === 'Completed'" @click="continueWorkflow" class="launch-button glow">
  Continue
</button>
<button v-if="status === 'Completed'" @click="relaunchWorkflow" class="relaunch-button">
  Relaunch
</button>
```

**continueWorkflow():**
```javascript
const continueWorkflow = () => {
  if (!selectedFile.value || !taskPrompt.value.trim()) return

  const prevId = completedSessionId.value
  resetConnectionState()
  status.value = 'Connecting...'
  handleYAMLSelection(selectedFile.value)

  // WebSocket bağlantısı kurulduktan sonra launch yap
  // launchWorkflow'a previous_session_id geçir
  pendingContinueSessionId.value = prevId
  establishWebSocketConnection()
}
```

**launchWorkflow() değişikliği:**
```javascript
body: JSON.stringify({
  yaml_file: selectedFile.value,
  task_prompt: trimmedPrompt,
  session_id: sessionId,
  attachments: attachmentIds,
  previous_session_id: pendingContinueSessionId.value || undefined,  // ← EKLENDİ
})
// Launch sonrası temizle:
pendingContinueSessionId.value = null
```

**relaunchWorkflow():** Mevcut Relaunch logic'i — `completedSessionId` ve `pendingContinueSessionId` null.

## Dosya Özeti

| Dosya | Tür | Açıklama |
|-------|-----|----------|
| `runtime/node/agent/providers/claude_code_provider.py` | MODIFY | `save/load_sessions_to_workspace()`, workspace scan for prompt |
| `server/models.py` | MODIFY | `previous_session_id` field ekleme |
| `server/routes/execute.py` | MODIFY | `previous_session_id` iletimi |
| `server/services/workflow_run_service.py` | MODIFY | Workspace reuse logic, session loading |
| `runtime/sdk.py` | MODIFY | Save sessions before cleanup (satır 124-126) |
| `frontend/src/pages/LaunchView.vue` | MODIFY | Continue/Relaunch butonları + previous_session_id gönderimi |

## Edge Cases

| Durum | Davranış |
|-------|----------|
| Claude session expired (TTL aşıldı) | `--resume` hata verir → provider zaten retry logic'i var, fresh session başlatır. Workspace dosyaları hala mevcut, prompt'ta listelenir. |
| Workspace silinmiş | `previous_session_id` ile workspace bulunamazsa fresh start gibi davran, uyarı logla |
| Farklı workflow YAML ile continue | İzin ver — aynı workspace'de farklı ekip çalışabilir |
| Backend restart arası | Session'lar disk'te (.claude_sessions.json), workspace'de — persist |

## Doğrulama

1. Backend başlat: `uv run python server_main.py --port 6400`
2. İlk workflow: "Build a Python todo CLI app" → tamamlanır
3. "Continue" butonuna tıkla, yeni prompt: "Add unit tests with pytest"
4. Kontrol:
   - Aynı workspace dizininde çalışıyor (dosyalar mevcut)
   - Claude Code `--resume` ile başlıyor (log'da session_id aynı)
   - Prompt'ta `[Existing Workspace Files]` bloğu var
   - Yeni dosyalar eski dosyaların yanına ekleniyor
5. "Relaunch" ile test: Sıfırdan başlıyor, eski dosyalar kalıyor ama Claude Code fresh session
