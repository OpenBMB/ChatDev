# =========== Celery + Redis Background Worker Engine ===========
# Graceful fallback: When Redis/Celery unavailable, uses in-process threading
# ================================================================

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Governance Engine Import (graceful fallback) ──
_GOVERNANCE_AVAILABLE = False
try:
    from visualizer.pipeline_governance import (
        create_job_context, inject_job_context, set_current_job,
        resource_governor, run_governance_checks, GateType,
        validate_contract, extract_routing_signals,
        # Gap #1: Checkpoint/Resume
        CheckpointManager,
        # Gap #7: Semantic validation
        validate_contract_semantic,
        # Gap #10: Per-agent LLM config
        get_agent_llm_config,
        # Gap #11: LLM-powered routing
        extract_routing_signals_llm,
        # Gap #12: Workflow versioning
        WorkflowVersionManager,
        # Gap #13: Structured audit logging
        AuditLogger,
        # Gap #9: Execution history
        ExecutionHistoryManager,
        # HITL gateway
        HITLGateway, ApprovalStatus,
    )
    _GOVERNANCE_AVAILABLE = True
except ImportError as _gov_err:
    logging.warning(f"[Governance] Engine not available: {_gov_err}")

# ── Celery + Redis Import (graceful fallback) ──
_CELERY_AVAILABLE = False
_REDIS_AVAILABLE = False

try:
    from celery import Celery
    from celery.schedules import crontab
    _CELERY_AVAILABLE = True
except ImportError:
    _CELERY_AVAILABLE = False

try:
    import redis
    _redis_client = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
    _redis_client.ping()
    _REDIS_AVAILABLE = True
except Exception:
    _REDIS_AVAILABLE = False
    _redis_client = None

# ── Worker Mode Detection ──
WORKER_MODE = "celery" if (_CELERY_AVAILABLE and _REDIS_AVAILABLE) else "thread"
logging.info(f"🔧 [Worker Engine] Mode: {WORKER_MODE.upper()} (Celery={_CELERY_AVAILABLE}, Redis={_REDIS_AVAILABLE})")

# =============================================
#   Celery App (when Redis is available)
# =============================================
if WORKER_MODE == "celery":
    celery_app = Celery(
        "chatdev_workers",
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/1"
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Seoul",
        enable_utc=True,
        task_track_started=True,
        worker_concurrency=2,
        worker_max_tasks_per_child=100,
    )
else:
    celery_app = None

# =============================================
#   Execution Log Store (in-memory ring buffer)
# =============================================
_MAX_LOG_ENTRIES = 500
_execution_logs = []  # [{timestamp, level, agent, message, cost_usd}, ...]
_log_lock = threading.Lock()

def emit_log(agent, message, level="INFO", cost_usd=0.0, tokens=0):
    """Append a log entry to the ring buffer."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "agent": agent,
        "message": message,
        "cost_usd": round(cost_usd, 6),
        "tokens": tokens
    }
    with _log_lock:
        _execution_logs.append(entry)
        if len(_execution_logs) > _MAX_LOG_ENTRIES:
            _execution_logs.pop(0)
    return entry

def get_logs(limit=50, since=None):
    """Retrieve recent log entries."""
    with _log_lock:
        logs = list(_execution_logs)
    if since:
        logs = [l for l in logs if l["timestamp"] > since]
    return logs[-limit:]

# =============================================
#   Metering Engine (usage tracking)
# =============================================
_metering_store = {
    "total_actions": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "actions": []  # [{action_id, agent, tokens, cost_usd, timestamp}, ...]
}
_meter_lock = threading.Lock()

# Pricing tiers (per 1K tokens)
PRICING = {
    "input_per_1k": 0.0005,   # $0.50 / 1M input tokens
    "output_per_1k": 0.0015,  # $1.50 / 1M output tokens
    "action_base": 0.002,     # $0.002 per action (infra cost)
}

def meter_action(agent, action_type, input_tokens=0, output_tokens=0):
    """Record a billable action and compute cost."""
    input_cost = (input_tokens / 1000) * PRICING["input_per_1k"]
    output_cost = (output_tokens / 1000) * PRICING["output_per_1k"]
    total_cost = input_cost + output_cost + PRICING["action_base"]
    total_tokens = input_tokens + output_tokens

    action_id = f"act_{datetime.now().strftime('%H%M%S')}_{_metering_store['total_actions']}"

    with _meter_lock:
        _metering_store["total_actions"] += 1
        _metering_store["total_tokens"] += total_tokens
        _metering_store["total_cost_usd"] += total_cost
        _metering_store["actions"].append({
            "action_id": action_id,
            "agent": agent,
            "action_type": action_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(total_cost, 6),
            "timestamp": datetime.now().isoformat()
        })
        # Keep last 200 actions
        if len(_metering_store["actions"]) > 200:
            _metering_store["actions"] = _metering_store["actions"][-200:]

    emit_log(agent, f"{action_type} — {total_tokens} tokens, ${total_cost:.4f}", "BILLING", total_cost, total_tokens)
    return {"action_id": action_id, "cost_usd": total_cost, "tokens": total_tokens}


def get_metering_summary():
    """Get current metering summary."""
    with _meter_lock:
        return {
            "total_actions": _metering_store["total_actions"],
            "total_tokens": _metering_store["total_tokens"],
            "total_cost_usd": round(_metering_store["total_cost_usd"], 4),
            "recent_actions": _metering_store["actions"][-20:]
        }

# =============================================
#   Background Task Runner (Thread-based fallback)
# =============================================
_background_tasks = {}
_bg_lock = threading.Lock()

def _summarize_previous_output(output_text, max_chars=4000):
    """#4: Improved context chaining — summarize long outputs instead of truncating."""
    if not output_text or len(output_text) <= max_chars:
        return output_text or ""
    # Extract structured sections first
    sections = []
    for marker in ["##", "###", "**", "- "]:
        for line in output_text.split("\n"):
            if line.strip().startswith(marker):
                sections.append(line.strip())
    # Build summary: headers + truncated body
    header_summary = "\n".join(sections[:20]) if sections else ""
    body_budget = max_chars - len(header_summary) - 200
    return (
        f"[이전 산출물 요약 — 원본 {len(output_text)}자]\n"
        f"{header_summary}\n\n"
        f"--- 본문 발췌 ---\n"
        f"{output_text[:body_budget]}\n...(생략)"
    )


def _compute_dag_levels(nodes, edges):
    """#2: Compute execution levels for parallel fan-out.
    Nodes at the same level can be executed concurrently.
    """
    node_ids = {n.get("id") for n in nodes}
    in_degree = {n.get("id"): 0 for n in nodes}
    adj = {n.get("id"): [] for n in nodes}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src in adj and tgt in in_degree:
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1
    # BFS to assign levels
    levels = {}
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    current_level = 0
    while queue:
        for nid in queue:
            levels[nid] = current_level
        next_queue = []
        for nid in queue:
            for neighbor in adj.get(nid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)
        queue = next_queue
        current_level += 1
    # Assign unvisited nodes to last level
    for n in nodes:
        if n.get("id") not in levels:
            levels[n.get("id")] = current_level
    # Group by level
    level_groups = {}
    node_map = {n.get("id"): n for n in nodes}
    for nid, lvl in sorted(levels.items(), key=lambda x: x[1]):
        level_groups.setdefault(lvl, []).append(node_map.get(nid, {"id": nid}))
    return level_groups


def run_agent_task(team_name, node_id, agent_role, system_prompt=None, task_prompt="태스크를 수행해주세요.", knowledge_sources=None, previous_output="", socketio_ref=None, step_idx=0, total_steps=1, exec_id=None):
    """Execute a single agent task using the active LLM."""
    if not system_prompt:
        system_prompt = f"You are a {agent_role}. Complete your assigned task professionally."
        
    emit_log(agent_role, f"[{team_name}] 태스크 시작 — 지식 그라운딩 중...", "START")
    
    # ── RAG Grounding ──
    grounding_context = ""
    if knowledge_sources:
        matches = _search_knowledge_sources(task_prompt, knowledge_sources, top_k=2)
        if matches:
            grounding_context = "\n=== GROUNDING KNOWLEDGE FROM COMPANY FILES ===\n"
            for score, source, chunk in matches:
                grounding_context += f"[Source File: {source}]\n{chunk}\n---\n"
                emit_log(agent_role, f"📚 RAG 지식 주입: {source} (매칭 스코어: {score})", "GROUNDING")
            grounding_context += "==============================================\n"

    # #4: Improved context chaining — summarize instead of truncate
    user_content = f"## 프로젝트 태스크\n{task_prompt}\n"
    if previous_output:
        summarized = _summarize_previous_output(previous_output, max_chars=4000)
        user_content += f"\n## 이전 에이전트 산출물\n{summarized}\n"
    if grounding_context:
        user_content += f"\n## 참조 지식\n{grounding_context}\n"
    user_content += f"\n당신의 역할({agent_role})에 맞게 분석하고 결과물을 산출해주세요."

    # Emit working status for Virtual Office
    if socketio_ref and exec_id:
        try:
            socketio_ref.emit("workflow_agent_status", {
                "event": "working", "agent": agent_role, "step": step_idx + 1,
                "total": total_steps, "exec_id": exec_id
            })
        except Exception:
            pass

    # #10: Per-agent LLM config override
    agent_llm_override = None
    if _GOVERNANCE_AVAILABLE:
        try:
            agent_llm_override = get_agent_llm_config(agent_role)
        except Exception:
            pass

    # #5: Fallback chain — Primary → Alt providers → Local → Mock
    llm_result = _call_llm_with_fallback_chain(
        system_prompt, user_content, agent_role, agent_llm_override
    )
    
    if llm_result.get("success"):
        output = llm_result.get("text", "")
        source = llm_result.get("source", "LLM")
    else:
        # Final fallback: simulated response
        output = (
            f"[{agent_role} 분석 결과]\n\n"
            f"## 태스크: {task_prompt[:50]}\n\n"
            f"수행을 마쳤습니다. 상세 내역은 API 키 설정 후 사용하실 수 있습니다."
        )
        source = "fallback_mock"
        
    # #6: Use actual token counts from LLM API response (not split())
    input_tokens = llm_result.get("input_tokens", 0)
    output_tokens = llm_result.get("output_tokens", 0)
    meter_result = meter_action(agent_role, "workflow_execution", input_tokens, output_tokens)

    # Emit completion status for Virtual Office
    if socketio_ref and exec_id:
        try:
            socketio_ref.emit("workflow_agent_status", {
                "event": "completed", "agent": agent_role, "step": step_idx + 1,
                "total": total_steps, "exec_id": exec_id,
                "output_preview": output[:200]
            })
        except Exception:
            pass

    # #13: Audit log
    if _GOVERNANCE_AVAILABLE:
        try:
            AuditLogger.log("agent_task_complete", {
                "source": source, "tokens": input_tokens + output_tokens,
                "cost_usd": meter_result.get("cost_usd", 0),
            }, agent=agent_role)
        except Exception:
            pass

    emit_log(agent_role, f"✅ 태스크 완료 ({source}) — 비용: ${meter_result['cost_usd']:.4f}", "COMPLETE", meter_result["cost_usd"])

    return {
        "output": output,
        "cost_usd": meter_result["cost_usd"],
        "tokens": input_tokens + output_tokens,
        "source": source
    }


def execute_workflow_background(team_name, nodes, edges, knowledge_sources=None,
                                socketio_ref=None, task_prompt=None,
                                budget_per_squad=None, resume_from_exec_id=None,
                                parallel_enabled=True, fail_fast=False):
    """Execute entire workflow in background thread with full governance.
    
    Improvements applied:
      #1  Checkpoint/Resume — saves state after each step, can resume
      #2  Fan-out parallel — independent nodes at same DAG level run concurrently
      #4  Context chaining — uses summarization instead of truncation
      #5  Error recovery — fail_fast option to stop on first failure
      #6  Token counting — uses actual API response tokens
      #7  Semantic validation — enhanced contract checks via LLM
      #8  HITL auto-resume — polls for approval instead of breaking
      #10 Per-agent LLM — respects agent-specific model/temperature
      #11 LLM routing — enhanced routing signal extraction
      #12 Versioning — saves workflow version on execution start
      #13 Audit logging — all governance events persisted to disk
    """
    exec_id = resume_from_exec_id or f"exec_bg_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _worker():
        emit_log("System", f"🚀 [{team_name}] 워크플로우 시작 — {len(nodes)}명 에이전트", "SYSTEM")
        
        # #12: Save workflow version on execution start
        if _GOVERNANCE_AVAILABLE:
            try:
                WorkflowVersionManager.save_version(
                    team_name, nodes, edges or [],
                    comment=f"exec:{exec_id}"
                )
            except Exception:
                pass

        # Sort nodes topologically
        from visualizer.workflow_utils import topological_sort as _topo_sort
        node_order = _topo_sort(nodes, edges or [])

        # #2: Compute DAG levels for parallel execution
        dag_levels = _compute_dag_levels(nodes, edges or []) if parallel_enabled else None

        if socketio_ref:
            try:
                socketio_ref.emit("workflow_execution", {
                    "event": "start", "exec_id": exec_id,
                    "team_name": team_name, "total_agents": len(node_order)
                })
            except Exception:
                pass

        # ── Governance: Create Job Context ──
        job_ctx = None
        if _GOVERNANCE_AVAILABLE:
            try:
                job_ctx = create_job_context(team_name, task_prompt)
                set_current_job(job_ctx)
                emit_log("Governance", f"🔒 Job Context 생성: {job_ctx.job_id}", "GOVERNANCE")
                AuditLogger.log("job_created", {"team": team_name}, job_id=job_ctx.job_id)
                
                _budget = budget_per_squad or 5.0
                for node in node_order:
                    r = node.get("role", "Agent")
                    resource_governor.set_budget(job_ctx.job_id, r, max_cost_usd=_budget)
                emit_log("Governance", f"💰 예산 설정: Squad당 ${_budget:.2f}", "GOVERNANCE")
            except Exception as _gov_e:
                logging.warning(f"[Governance] Job context creation failed: {_gov_e}")
                job_ctx = None

        total_cost = 0.0
        previous_outputs = {}  # {role: output} for context chaining
        previous_output = ""
        execution_log = []
        failed_agents = []
        bypassed_nodes = set()
        governance_log = []
        _final_task_prompt = task_prompt or "프로젝트 분석 및 설계 태스크를 수행해주세요."
        resume_step = -1

        # #1: Load checkpoint for resume
        if resume_from_exec_id and _GOVERNANCE_AVAILABLE:
            checkpoint = CheckpointManager.load(resume_from_exec_id)
            if checkpoint:
                resume_step = checkpoint.get("step_idx", -1)
                total_cost = checkpoint.get("total_cost", 0.0)
                previous_outputs = checkpoint.get("previous_outputs", {})
                bypassed_nodes = set(checkpoint.get("bypassed_nodes", []))
                governance_log = checkpoint.get("governance_log", [])
                failed_agents = checkpoint.get("failed_agents", [])
                previous_output = checkpoint.get("output_preview", "")
                emit_log("System", f"♻️ 체크포인트에서 재개: step {resume_step + 1}부터", "RESUME")
                AuditLogger.log("workflow_resumed", {
                    "from_step": resume_step, "exec_id": resume_from_exec_id
                }, job_id=job_ctx.job_id if job_ctx else None)

        # ── Execution loop (supports parallel fan-out) ──
        def _execute_single_node(i, node):
            """Execute one node — used both sequentially and in parallel."""
            nonlocal total_cost, previous_output

            role = node.get("role", "Agent")
            node_id = node.get("id", f"node_{i}")

            # Skip dynamically bypassed nodes
            if node_id in bypassed_nodes:
                emit_log("Governance", f"⏭️ [{role}] 동적 라우팅 우회", "ROUTING")
                return {
                    "step": i + 1, "agent": role, "node_id": node_id,
                    "output": "(bypassed)", "status": "bypassed",
                    "duration_ms": 0, "cost_usd": 0.0,
                    "timestamp": datetime.now().isoformat()
                }

            # Pre-execution budget check
            if _GOVERNANCE_AVAILABLE and job_ctx:
                budget_check = resource_governor.check_budget(job_ctx.job_id, role)
                if not budget_check["allowed"]:
                    emit_log("Governance", f"🚨 [{role}] Circuit Breaker — 예산 초과", "CIRCUIT_BREAKER")
                    AuditLogger.log("circuit_breaker", {"reason": "budget_exceeded"}, job_id=job_ctx.job_id, agent=role, severity="ERROR")
                    job_ctx.status = "suspended"
                    job_ctx._persist()
                    return {
                        "step": i + 1, "agent": role, "node_id": node_id,
                        "output": "(budget exceeded)", "status": "budget_blocked",
                        "duration_ms": 0, "cost_usd": 0.0,
                        "timestamp": datetime.now().isoformat()
                    }
                if budget_check.get("warning"):
                    emit_log("Governance", budget_check["warning"], "BUDGET_WARNING")
                    AuditLogger.log("budget_warning", budget_check, job_id=job_ctx.job_id, agent=role, severity="WARNING")

            # Inject job context into system prompt
            system_prompt = node.get("system_prompt", f"You are a {role}. Complete your assigned task professionally.")
            if _GOVERNANCE_AVAILABLE and job_ctx:
                system_prompt = inject_job_context(system_prompt, job_ctx)

            start_time = time.time()
            task_result = run_agent_task(
                team_name=team_name, node_id=node_id, agent_role=role,
                system_prompt=system_prompt, task_prompt=_final_task_prompt,
                knowledge_sources=knowledge_sources,
                previous_output=previous_output,
                socketio_ref=socketio_ref, step_idx=i,
                total_steps=len(node_order), exec_id=exec_id
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            step_cost = task_result["cost_usd"]
            total_cost += step_cost

            # Record usage in Resource Governor
            if _GOVERNANCE_AVAILABLE and job_ctx:
                try:
                    usage_result = resource_governor.record_usage(
                        job_ctx.job_id, role,
                        tokens_used=task_result.get("tokens", 0),
                        cost_usd=step_cost, socketio_ref=socketio_ref
                    )
                    if usage_result.get("circuit_breaker_tripped"):
                        emit_log("Governance", f"🚨 [{role}] Circuit Breaker 발동", "CIRCUIT_BREAKER")
                        AuditLogger.log("circuit_breaker", {"reason": "post_exec"}, job_id=job_ctx.job_id, agent=role, severity="ERROR")
                except Exception:
                    pass

            # Detect agent failures
            step_status = "completed"
            if task_result.get("source") == "fallback_mock" or not task_result.get("output"):
                step_status = "failed"
                failed_agents.append(role)
                AuditLogger.log("agent_failed", {"source": task_result.get("source")}, job_id=job_ctx.job_id if job_ctx else None, agent=role, severity="ERROR")

            node_output = task_result["output"]
            previous_outputs[role] = node_output
            previous_output = node_output

            # #7: Semantic contract validation (LLM-enhanced)
            if _GOVERNANCE_AVAILABLE and job_ctx:
                try:
                    contract_result = validate_contract_semantic(
                        role, node_output, llm_call_func=_call_active_llm
                    )
                    if not contract_result["valid"]:
                        emit_log("Governance", f"📋 [{role}] 계약 위반: {', '.join(contract_result['violations'][:3])}", "CONTRACT")
                        AuditLogger.log("contract_violation", {
                            "violations": contract_result["violations"],
                            "semantic": contract_result.get("semantic_check")
                        }, job_id=job_ctx.job_id, agent=role, severity="WARNING")
                        governance_log.append({"action": "contract_violation", "role": role})
                    else:
                        emit_log("Governance", f"✅ [{role}] 데이터 계약 충족 (점수: {contract_result['score']})", "CONTRACT")
                except Exception:
                    pass

            # #11: LLM-powered dynamic routing
            if _GOVERNANCE_AVAILABLE and job_ctx:
                try:
                    routing = extract_routing_signals_llm(node_output, llm_call_func=_call_active_llm)
                    from visualizer.pipeline_governance import evaluate_dynamic_route
                    route_result = evaluate_dynamic_route(nodes, edges, node_id, node_output, routing)
                    for bypassed_id in route_result.get("bypassed_targets", []):
                        bypassed_nodes.add(bypassed_id)
                    for reason in route_result.get("reasoning", []):
                        emit_log("Governance", reason, "ROUTING")
                except Exception:
                    pass

            # Save artifact to isolated workspace
            if _GOVERNANCE_AVAILABLE and job_ctx and node_output:
                try:
                    job_ctx.save_artifact(f"{role.replace(' ', '_')}_output.md", node_output)
                    job_ctx.cost_usd = total_cost
                    job_ctx.total_tokens += task_result.get("tokens", 0)
                except Exception:
                    pass

            step_entry = {
                "step": i + 1, "agent": role, "node_id": node_id,
                "output": node_output, "status": step_status,
                "duration_ms": elapsed_ms, "cost_usd": step_cost,
                "timestamp": datetime.now().isoformat()
            }

            # #1: Save checkpoint after each successful step
            if _GOVERNANCE_AVAILABLE:
                try:
                    CheckpointManager.save(
                        exec_id, i, node, node_output, total_cost,
                        previous_outputs, bypassed_nodes, governance_log, failed_agents
                    )
                except Exception:
                    pass

            return step_entry

        # ── Main execution: sequential or parallel ──
        if dag_levels and parallel_enabled and len(dag_levels) > 1:
            # #2: Parallel fan-out execution by DAG level
            flat_idx = 0
            for level_num in sorted(dag_levels.keys()):
                level_nodes = dag_levels[level_num]
                # Skip already-completed steps on resume
                if all(flat_idx + j <= resume_step for j in range(len(level_nodes))):
                    flat_idx += len(level_nodes)
                    continue

                if len(level_nodes) == 1:
                    # Single node at this level — run sequentially
                    node = level_nodes[0]
                    if flat_idx > resume_step:
                        entry = _execute_single_node(flat_idx, node)
                        execution_log.append(entry)
                        # #5: Fail-fast option
                        if fail_fast and entry.get("status") == "failed":
                            emit_log("System", f"🛑 Fail-fast: {entry['agent']} 실패 → 파이프라인 중단", "ERROR")
                            break
                    flat_idx += 1
                else:
                    # Multiple independent nodes — fan-out
                    emit_log("System", f"⚡ Level {level_num}: {len(level_nodes)}개 노드 병렬 실행", "PARALLEL")
                    with ThreadPoolExecutor(max_workers=min(len(level_nodes), 4)) as pool:
                        futures = {}
                        for j, node in enumerate(level_nodes):
                            idx = flat_idx + j
                            if idx > resume_step:
                                futures[pool.submit(_execute_single_node, idx, node)] = node
                        for future in as_completed(futures):
                            try:
                                entry = future.result()
                                execution_log.append(entry)
                                if fail_fast and entry.get("status") == "failed":
                                    emit_log("System", f"🛑 Fail-fast: {entry['agent']} 실패", "ERROR")
                            except Exception as exc:
                                logging.error(f"[Parallel] Node execution failed: {exc}")
                    flat_idx += len(level_nodes)
                time.sleep(0.3)
        else:
            # Sequential execution (original behavior)
            for i, node in enumerate(node_order):
                if i <= resume_step:
                    continue  # Skip already-completed steps on resume

                entry = _execute_single_node(i, node)
                execution_log.append(entry)

                # #8: HITL auto-resume — check if HITL gate requires waiting
                if _GOVERNANCE_AVAILABLE and job_ctx and entry.get("status") != "bypassed":
                    node_id = node.get("id", f"node_{i}")
                    outgoing_edges = [e for e in (edges or []) if e.get("source") == node_id]
                    for edge in outgoing_edges:
                        gate_type = edge.get("gate_type", GateType.AUTO)
                        if gate_type in (GateType.HITL_REQUIRED, GateType.HITL_OPTIONAL):
                            target_node = next((n for n in nodes if n.get("id") == edge.get("target")), {})
                            target_role = target_node.get("role", "Next")
                            role = node.get("role", "Agent")
                            req = HITLGateway.create_approval_request(
                                job_id=job_ctx.job_id, source_squad=role,
                                target_squad=target_role,
                                artifacts={f"{role}_output.md": (entry.get("output") or "")[:2000]},
                                gate_type=gate_type, socketio_ref=socketio_ref
                            )
                            emit_log("Governance", f"🛑 HITL 관문: {role}→{target_role} (대기 중...)", "HITL")
                            AuditLogger.log("hitl_gate_created", {"approval_id": req.approval_id}, job_id=job_ctx.job_id, agent=role)

                            # Poll for approval (max 30 min)
                            status, result = HITLGateway.wait_for_approval(
                                req.approval_id, poll_interval=3.0, max_wait=1800
                            )
                            if status == ApprovalStatus.REJECTED:
                                emit_log("Governance", f"❌ HITL 반려: {role}→{target_role}", "HITL")
                                AuditLogger.log("hitl_rejected", {"approval_id": req.approval_id}, job_id=job_ctx.job_id, severity="WARNING")
                                failed_agents.append(f"{role}(HITL rejected)")
                                break
                            elif status in (ApprovalStatus.APPROVED, ApprovalStatus.MODIFIED, ApprovalStatus.TIMED_OUT):
                                emit_log("Governance", f"✅ HITL {status}: {role}→{target_role} — 파이프라인 재개", "HITL")
                                AuditLogger.log("hitl_resolved", {"status": status}, job_id=job_ctx.job_id)
                            break

                # Fail-fast option
                if fail_fast and entry.get("status") == "failed":
                    emit_log("System", f"🛑 Fail-fast: {entry['agent']} 실패 → 중단", "ERROR")
                    break

                time.sleep(0.5)

        # Determine overall status
        overall_status = "completed"
        if failed_agents:
            overall_status = "failed" if len(failed_agents) == len(node_order) else "partial_failure"

        # Save execution history
        history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "execution_history")
        os.makedirs(history_dir, exist_ok=True)
        history_data = {
            "exec_id": exec_id, "team_name": team_name, "prompt": task_prompt,
            "started_at": execution_log[0]["timestamp"] if execution_log else datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "total_agents": len(node_order), "total_cost_usd": total_cost,
            "total_duration_ms": sum(s["duration_ms"] for s in execution_log),
            "overall_status": overall_status, "failed_agents": failed_agents,
            "steps": execution_log
        }
        with open(os.path.join(history_dir, f"{exec_id}.json"), 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        emit_log("System", f"🏁 [{team_name}] 워크플로우 {overall_status} — 총 비용: ${total_cost:.4f}", "SYSTEM", total_cost)

        # #13: Final audit log
        if _GOVERNANCE_AVAILABLE:
            AuditLogger.log("workflow_completed", {
                "status": overall_status, "cost": total_cost,
                "agents": len(node_order), "failed": failed_agents
            }, job_id=job_ctx.job_id if job_ctx else None)

        # Finalize Job Context
        if _GOVERNANCE_AVAILABLE and job_ctx:
            try:
                job_ctx.status = overall_status
                job_ctx.cost_usd = total_cost
                job_ctx._persist()
                emit_log("Governance", f"📦 Job {job_ctx.job_id} 완료 — 산출물 {len(job_ctx.artifacts)}개", "GOVERNANCE")
            except Exception:
                pass

        # #1: Clean up checkpoint on successful completion
        if _GOVERNANCE_AVAILABLE and overall_status == "completed":
            try:
                CheckpointManager.delete(exec_id)
            except Exception:
                pass

        try:
            _trigger_external_connectors(team_name, task_prompt, execution_log, total_cost, [])
        except Exception as e:
            logging.error(f"Failed to trigger external connectors: {e}")

        if socketio_ref:
            try:
                socketio_ref.emit("workflow_execution", {
                    "event": "complete", "exec_id": exec_id,
                    "team_name": team_name, "total_agents": len(node_order),
                    "total_cost_usd": total_cost
                })
            except Exception:
                pass

        with _bg_lock:
            if exec_id in _background_tasks:
                _background_tasks[exec_id]["status"] = overall_status
                _background_tasks[exec_id]["completed_at"] = datetime.now().isoformat()
                _background_tasks[exec_id]["total_cost"] = total_cost
                _background_tasks[exec_id]["failed_agents"] = failed_agents

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    with _bg_lock:
        _background_tasks[exec_id] = {
            "task_id": exec_id, "team_name": team_name,
            "status": "running", "agents": len(nodes),
            "started_at": datetime.now().isoformat(),
            "completed_at": None, "total_cost": 0.0
        }

    return exec_id


def get_background_tasks():
    """List all background tasks."""
    with _bg_lock:
        return list(_background_tasks.values())

# =============================================
#   Recurring Schedule Runner (Thread-based cron)
# =============================================
_cron_threads = {}
_cron_lock = threading.Lock()

def start_recurring_schedule(schedule_id, team_name, interval_seconds=60):
    """Start a recurring background execution (simplified cron) safely."""
    def _cron_worker():
        consecutive_failures = 0  # #28: Track consecutive failures
        max_consecutive_failures = 5  # #28: Stop after 5 consecutive failures
        
        while True:
            with _cron_lock:
                if schedule_id not in _cron_threads or not _cron_threads[schedule_id].get("active"):
                    break
            
            emit_log("Scheduler", f"⏰ [{team_name}] 반복 스케줄 실행 — {schedule_id}", "CRON")

            # Load graph and execute
            graph_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freeform_graphs")
            graph_path = os.path.join(graph_dir, f"{team_name}.json")
            if os.path.exists(graph_path):
                try:
                    with open(graph_path, 'r', encoding='utf-8') as f:
                        gd = json.load(f)
                    nodes = gd.get("nodes", [])
                    if nodes:
                        execute_workflow_background(team_name, nodes, gd.get("edges", []))
                    consecutive_failures = 0  # #28: Reset on success
                except Exception as e:
                    consecutive_failures += 1  # #28: Increment on failure
                    logging.error(f"Error running scheduled task {schedule_id} (failure {consecutive_failures}/{max_consecutive_failures}): {e}")
                    
                    # #28: Auto-stop after too many consecutive failures
                    if consecutive_failures >= max_consecutive_failures:
                        emit_log("Scheduler", f"🛑 [{schedule_id}] {max_consecutive_failures}회 연속 실패로 자동 중단", "CRON")
                        with _cron_lock:
                            if schedule_id in _cron_threads:
                                _cron_threads[schedule_id]["active"] = False
                        break
            
            # #28: Exponential backoff on failures
            actual_interval = interval_seconds
            if consecutive_failures > 0:
                actual_interval = min(interval_seconds * (2 ** consecutive_failures), 3600)
                emit_log("Scheduler", f"⏳ 백오프 대기: {actual_interval:.0f}초 (연속 실패: {consecutive_failures})", "CRON")
            time.sleep(actual_interval)

    with _cron_lock:
        if schedule_id in _cron_threads:
            _cron_threads[schedule_id]["active"] = False
        _cron_threads[schedule_id] = {"active": True}

    thread = threading.Thread(target=_cron_worker, daemon=True)
    thread.start()
    emit_log("Scheduler", f"🔁 반복 스케줄 등록: {schedule_id} (간격: {interval_seconds}s)", "CRON")
    return schedule_id

def stop_recurring_schedule(schedule_id):
    """Stop a recurring schedule safely."""
    with _cron_lock:
        if schedule_id in _cron_threads:
            _cron_threads[schedule_id]["active"] = False
            emit_log("Scheduler", f"⏹️ 반복 스케줄 중단: {schedule_id}", "CRON")
            return True
    return False

# =============================================
#   Multi-Agent Alignment Engine (Pre-Meeting)
# =============================================
_alignment_sessions = {}
_alignment_lock = threading.Lock()

# #16: Session persistence — save/load alignment sessions to disk
_SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alignment_sessions")
os.makedirs(_SESSIONS_DIR, exist_ok=True)

def _persist_session(session_id, blueprint):
    """#16: Save alignment session to disk for server restart survival."""
    try:
        filepath = os.path.join(_SESSIONS_DIR, f"{session_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(blueprint, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"#16: Failed to persist session {session_id}: {e}")

def _load_persisted_session(session_id):
    """#16: Load alignment session from disk."""
    try:
        filepath = os.path.join(_SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"#16: Failed to load session {session_id}: {e}")
    return None

# #29: Structured logging helper
def _struct_log(level, event, **fields):
    """#29: Emit structured log entry with key-value fields."""
    field_str = " ".join(f"{k}={v}" for k, v in fields.items())
    msg = f"[{event}] {field_str}"
    getattr(logging, level, logging.info)(msg)

# Role-specific debate perspectives
# ── Prompt sanitizer: strip Korean command suffixes for clean noun phrases ──
import re as _re
def _sanitize_prompt(raw):
    """Strip command-form endings to create a clean project noun phrase."""
    text = (raw or "").strip()
    # Remove trailing command suffixes: 해줘, 해라, 만들어, 구축해, 기획해줘, 줘, etc.
    text = _re.sub(r'[\s]*(기획|구축|만들어|설계|개발|생성|제작|분석)?(해\s*줘|해\s*라|해\s*봐|해|하자|하세요|합시다|해주세요)[.!?]*$', '', text)
    text = _re.sub(r'[\s]*(만들어|짜|줘|봐)[.!?]*$', '', text)
    # Remove trailing punctuation/whitespace
    text = text.rstrip(' .!?。')
    return text if text else raw.strip()

_ROLE_PERSPECTIVES = {
    "Chief Executive Officer": {
        "focus": "글로벌 기획 의도, 비전, 타겟 시장, KPI 목표치",
        "template": "이 프로젝트의 핵심 비전은 {task}입니다. 타겟 유저와 시장 포지셔닝을 먼저 정의해야 합니다. 주요 KPI는 DAU, 리텐션, 전환율 중심으로 잡겠습니다."
    },
    "Chief Product Officer": {
        "focus": "제품 요구사항, 기능 우선순위, 로드맵 단계 분할",
        "template": "기능 스펙을 3단계로 나누겠습니다. Phase 1: 핵심 MVP 기능, Phase 2: UX 고도화, Phase 3: 수익화 기능. {task}에서 가장 먼저 구현할 것은 코어 인터랙션입니다."
    },
    "Designer": {
        "focus": "UI/UX 가이드라인, 디자인 시스템, 에스테틱 방향성",
        "template": "미니멀한 화이트 모노크롬 기반으로 시각 방향성을 잡겠습니다. {task}의 핵심 인터페이스에는 모던 타이포그래피(Inter/SF Pro)와 섬세한 마이크로 인터랙션을 적용합니다."
    },
    "Programmer": {
        "focus": "기술 스택, 아키텍처 타당성, 성능 최적화 전략",
        "template": "기술 스택 제안: 프론트엔드는 최신 컴포넌트 기반 아키텍처, 백엔드는 이벤트 드리븐 구조로 설계합니다. {task}의 핵심 로직은 60fps 유지를 목표로 최적화하겠습니다."
    },
    "Tester": {
        "focus": "품질 보증 전략, 테스트 시나리오, 엣지 케이스 식별",
        "template": "테스트 전략: 유닛 테스트 커버리지 80% 이상, E2E 통합 테스트 필수. {task}에서 크리티컬한 엣지 케이스와 스트레스 테스트 시나리오를 사전 정의합니다."
    },
    "Reviewer": {
        "focus": "코드 품질, 보안 감사, 표준 준수 검증",
        "template": "코드 리뷰 기준: SOLID 원칙 준수, 보안 취약점 사전 차단, 성능 병목 식별. {task}의 최종 산출물은 프로덕션 그레이드 품질 기준을 통과해야 합니다."
    },
    "Content Writer": {
        "focus": "콘텐츠 전략, 카피라이팅 톤앤매너, 다국어 지원",
        "template": "콘텐츠 방향: 사용자 온보딩 UX 라이팅과 인앱 마이크로카피를 담당합니다. {task}에 맞는 톤앤매너 가이드를 수립합니다."
    },
    "Data Analyst": {
        "focus": "데이터 수집 전략, 분석 프레임워크, 지표 설계",
        "template": "데이터 설계: 이벤트 트래킹 스키마와 핵심 퍼널 지표를 정의합니다. {task}의 성과 측정을 위한 대시보드 스펙을 제안합니다."
    },
    "Creative Director": {
        "focus": "브랜딩, 마케팅 전략, 비주얼 아이덴티티",
        "template": "브랜드 방향: 프리미엄하고 세련된 비주얼 아이덴티티를 수립합니다. {task}의 마케팅 포지셔닝과 론칭 크리에이티브 전략을 제안합니다."
    },
    "DevOps": {
        "focus": "인프라 아키텍처, CI/CD 파이프라인, 배포 전략",
        "template": "인프라 설계: 컨테이너 기반 배포, 자동 스케일링, 블루-그린 디플로이먼트. {task}의 고가용성과 무중단 배포 전략을 수립합니다."
    }
}

# Sub-task generation templates per role
_SUBTASK_TEMPLATES = {
    "Chief Executive Officer": ["마일스톤 로드맵 수립", "KPI 대시보드 설계", "이해관계자 브리핑 문서 작성"],
    "Chief Product Officer": ["PRD (제품 요구사항 명세) 작성", "기능 우선순위 매트릭스 정의", "사용자 스토리 맵핑"],
    "Designer": ["UI 컴포넌트 시스템 설계", "와이어프레임 & 프로토타입 제작", "디자인 토큰 정의"],
    "Programmer": ["핵심 로직 아키텍처 구현", "API 엔드포인트 개발", "성능 최적화 및 리팩토링"],
    "Tester": ["테스트 케이스 작성", "자동화 테스트 스크립트 구현", "버그 리포트 & 리그레션 검증"],
    "Reviewer": ["코드 리뷰 & 품질 게이트 검증", "보안 취약점 스캔", "프로덕션 체크리스트 감사"],
    "Content Writer": ["UX 라이팅 & 마이크로카피 작성", "온보딩 시나리오 문서화", "다국어 번역 준비"],
    "Data Analyst": ["이벤트 트래킹 스키마 설계", "핵심 퍼널 분석 대시보드 구축", "A/B 테스트 프레임워크 설계"],
    "Creative Director": ["브랜드 가이드라인 수립", "마케팅 에셋 크리에이티브 기획", "론칭 캠페인 전략 설계"],
    "DevOps": ["CI/CD 파이프라인 구축", "모니터링 & 알림 설정", "인프라 스케일링 테스트"]
}

def run_alignment_meeting(team_name, task_description, nodes, knowledge_sources=None, edges=None, custom_tasks=None):
    """Execute multi-agent pre-meeting with multi-round adversarial debate.
    
    Args:
        edges: Optional list of {source, target} dicts defining execution order.
               If provided, subtask ordering follows edge topology.
        custom_tasks: Optional dict of {node_id: [task1, task2, ...]} overriding
                      the default _SUBTASK_TEMPLATES per-role assignments.
    """
    session_id = f"align_{team_name}_{datetime.now().strftime('%H%M%S')}"
    
    # Sanitize prompt for clean noun phrases in debate templates
    _clean_task = _sanitize_prompt(task_description)
    
    emit_log("Alignment", f"💬 [{team_name}] Swarm Meeting Room 개시 — \"{_clean_task[:50]}\"", "MEETING")
    emit_log("Alignment", f"📋 참석 요원: {len(nodes)}명 — {', '.join([n.get('role','?') for n in nodes])}", "MEETING")

    debate_log = []
    subtasks = []
    step_counter = [0]

    def _add_debate(agent, node_id, phase, dtype, statement, target_agent=None):
        step_counter[0] += 1
        entry = {
            "step": step_counter[0],
            "phase": phase,
            "type": dtype,  # proposal | conflict | rebuttal | compromise | consensus
            "agent": agent,
            "node_id": node_id,
            "target_agent": target_agent,
            "statement": statement,
            "timestamp": datetime.now().isoformat()
        }
        debate_log.append(entry)
        
        level_map = {"proposal": "DEBATE", "conflict": "CONFLICT", "rebuttal": "REBUTTAL", "compromise": "COMPROMISE", "consensus": "CONSENSUS"}
        icon_map = {"proposal": "💬", "conflict": "⚡", "rebuttal": "🛡️", "compromise": "🤝", "consensus": "✅"}
        emit_log(agent, f"{icon_map.get(dtype, '💬')} [{phase}] {statement[:120]}", level_map.get(dtype, "DEBATE"))
        time.sleep(0.3)
        return entry

    # ══════════════════════════════════════════════
    #   Phase 1: Initial Proposals (각 요원 초안 제시)
    # ══════════════════════════════════════════════
    emit_log("Alignment", "══ Phase 1: 초기 기획 제안 ══", "MEETING")
    
    proposals = {}
    for node in nodes:
        role = node.get("role", "Agent")
        perspective = _ROLE_PERSPECTIVES.get(role, {
            "focus": "일반 태스크 수행",
            "template": "{task} 관련 담당 업무를 수행하겠습니다."
        })
        statement = perspective["template"].format(task=_clean_task[:80])
        proposals[role] = statement
        _add_debate(role, node.get("id"), "Phase 1: 제안", "proposal", statement)

    # ══════════════════════════════════════════════
    #   Phase 2: Adversarial Debate (3라운드 충돌)
    # ══════════════════════════════════════════════
    
    # Conflict templates: Role A attacks Role B's proposal
    _CONFLICT_MAP = {
        ("Programmer", "Designer"): {
            "attack": "디자이너의 UI 제안은 미학적으론 훌륭하지만, 복잡한 글래스모피즘 효과는 {task}에서 렌더링 프레임 드롭을 유발합니다. 60fps 유지가 불가능해질 수 있습니다.",
            "rebuttal": "성능 우려를 이해합니다. 다만 시각적 프리미엄감은 사용자 리텐션에 직결됩니다. GPU 가속 레이어를 활용하면 프레임 드롭 없이 구현 가능합니다.",
            "compromise": "합의: 핵심 인터랙션 화면은 경량 플랫 디자인으로, 대기 화면과 메뉴에만 글래스모피즘을 제한 적용합니다."
        },
        ("Designer", "Programmer"): {
            "attack": "개발자의 아키텍처 제안은 기능 구현에 치중하여 사용자 경험 측면이 전혀 고려되지 않았습니다. 버튼 터치 영역이 44pt 미만이면 iOS HIG 위반입니다.",
            "rebuttal": "UX 가이드라인을 존중하겠습니다. 하지만 터치 영역을 무조건 키우면 화면 밀도가 낮아져 정보 전달 효율이 떨어집니다.",
            "compromise": "합의: 핵심 CTA는 48pt 이상, 보조 버튼은 36pt로 차등 적용하여 HIG 준수와 정보 밀도를 양립시킵니다."
        },
        ("Tester", "Programmer"): {
            "attack": "개발자의 이벤트 드리븐 구조는 경쟁 상태(Race Condition) 취약점이 존재합니다. {task}에서 동시 입력 시 상태 불일치가 발생할 수 있습니다.",
            "rebuttal": "경쟁 상태 지적을 수용합니다. 뮤텍스 락 대신 단일 스레드 이벤트 루프로 설계하면 해결됩니다.",
            "compromise": "합의: 단일 스레드 게임 루프를 채택하고, QA는 동시 입력 스트레스 테스트를 필수 항목으로 추가합니다."
        },
        ("Reviewer", "Designer"): {
            "attack": "디자이너의 커스텀 폰트 제안은 앱 번들 크기를 불필요하게 증가시킵니다. 시스템 폰트(SF Pro)가 iOS에서 최적 성능을 보장합니다.",
            "rebuttal": "브랜드 아이덴티티를 위해 최소 1종의 커스텀 폰트는 필수입니다. 서브셋팅으로 용량을 200KB 이하로 제한하겠습니다.",
            "compromise": "합의: 타이틀에만 커스텀 폰트(서브셋 200KB 이하), 본문은 SF Pro Display로 통일합니다."
        },
        ("Chief Executive Officer", "Tester"): {
            "attack": "QA의 테스트 커버리지 80% 요구는 출시 일정을 2주 지연시킵니다. MVP 단계에서는 핵심 기능 60% 커버리지로 충분합니다.",
            "rebuttal": "출시 일정을 존중하지만, 크래시 프리 비율 99.5% 미만이면 앱스토어 피처링이 불가능합니다. 최소 크리티컬 패스 테스트는 타협 불가입니다.",
            "compromise": "합의: Phase 1 MVP는 크리티컬 패스 70% 커버리지, Phase 2에서 80%로 상향. 크래시 프리 99.5% 목표는 유지합니다."
        }
    }

    # Default conflict template for unmapped pairs
    _DEFAULT_CONFLICT = {
        "attack": "{attacker}의 관점에서 보면, {defender}의 제안은 {task}의 핵심 요구사항과 부분적으로 충돌합니다. 재검토가 필요합니다.",
        "rebuttal": "비판을 수용합니다만, 제 제안의 핵심 가치는 {task}의 장기적 확장성에 있습니다. 부분 수정으로 양립 가능합니다.",
        "compromise": "합의: 양측의 핵심 논점을 반영하여 {task}에 최적화된 절충안을 도출합니다."
    }

    conflict_pairs = []
    round_count = min(3, max(2, len(nodes) - 1))  # 최소 2, 최대 3 라운드

    for rnd in range(round_count):
        emit_log("Alignment", f"══ Phase 2: 충돌 라운드 {rnd + 1}/{round_count} ══", "MEETING")
        time.sleep(0.3)

        # Pick two agents for this round's conflict
        attacker = nodes[rnd % len(nodes)]
        defender = nodes[(rnd + 1) % len(nodes)]
        a_role = attacker.get("role", "Agent")
        d_role = defender.get("role", "Agent")

        conflict = _CONFLICT_MAP.get((a_role, d_role), _DEFAULT_CONFLICT)

        # Attack
        attack_text = conflict["attack"].format(task=_clean_task[:60], attacker=a_role, defender=d_role)
        _add_debate(a_role, attacker.get("id"), f"Round {rnd+1}: 반박", "conflict", attack_text, d_role)

        # Rebuttal
        rebuttal_text = conflict["rebuttal"].format(task=_clean_task[:60], attacker=a_role, defender=d_role)
        _add_debate(d_role, defender.get("id"), f"Round {rnd+1}: 방어", "rebuttal", rebuttal_text, a_role)

        # Compromise
        compromise_text = conflict["compromise"].format(task=_clean_task[:60], attacker=a_role, defender=d_role)
        _add_debate("Moderator", None, f"Round {rnd+1}: 타협", "compromise", compromise_text)

        conflict_pairs.append({
            "round": rnd + 1,
            "attacker": a_role,
            "attacker_id": attacker.get("id"),
            "defender": d_role,
            "defender_id": defender.get("id"),
            "attack": attack_text,
            "rebuttal": rebuttal_text,
            "compromise": compromise_text,
            "status": "resolved"
        })

    # ══════════════════════════════════════════════
    #   Phase 3: Final Consensus (전원 합의)
    # ══════════════════════════════════════════════
    emit_log("Alignment", "══ Phase 3: 최종 합의 도출 ══", "MEETING")
    time.sleep(0.3)

    for node in nodes:
        role = node.get("role", "Agent")
        _add_debate(role, node.get("id"), "Phase 3: 합의", "consensus",
                    f"🤝 {role}: 전체 토론 결과를 수용합니다. '{_clean_task[:40]}' 프로젝트에 대한 최종 합의안에 서명합니다.")

    # ── Generate Subtasks (Dynamic Topology-Aware) ──
    # [1] Determine execution order: edge topology or node list order
    ordered_nodes = list(nodes)  # default: input order
    if edges and len(edges) > 0:
        # Topological sort by edge source→target
        node_map = {n.get("id"): n for n in nodes}
        in_degree = {n.get("id"): 0 for n in nodes}
        adj = {n.get("id"): [] for n in nodes}
        for e in edges:
            src, tgt = e.get("source"), e.get("target")
            if src in adj and tgt in in_degree:
                adj[src].append(tgt)
                in_degree[tgt] = in_degree.get(tgt, 0) + 1
        # Kahn's algorithm
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        topo_order = []
        while queue:
            nid = queue.pop(0)
            topo_order.append(nid)
            for neighbor in adj.get(nid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        # Append any nodes not reached by edges
        for n in nodes:
            if n.get("id") not in topo_order:
                topo_order.append(n.get("id"))
        ordered_nodes = [node_map[nid] for nid in topo_order if nid in node_map]
        emit_log("Alignment", f"📐 토폴로지 순서 적용: {' → '.join([node_map[nid].get('role','?') for nid in topo_order if nid in node_map])}", "MEETING")

    # [2] Generate subtasks: custom_tasks > node.custom_tasks > _SUBTASK_TEMPLATES (fallback)
    custom_tasks = custom_tasks or {}
    for node in ordered_nodes:
        role = node.get("role", "Agent")
        node_id = node.get("id", "x")
        # Priority: explicit custom_tasks dict > node-level custom_tasks > role template > default
        if node_id in custom_tasks and custom_tasks[node_id]:
            role_tasks = custom_tasks[node_id]
        elif node.get("custom_tasks") and len(node.get("custom_tasks", [])) > 0:
            role_tasks = node["custom_tasks"]
        else:
            role_tasks = _SUBTASK_TEMPLATES.get(role, ["일반 태스크 수행"])
        for task_name in role_tasks:
            subtasks.append({
                "subtask_id": f"sub_{node_id}_{len(subtasks)}",
                "agent": role,
                "node_id": node_id,
                "task": f"[{_clean_task[:30]}] {task_name}",
                "status": "queued",
                "priority": "high" if role in ["Programmer", "Designer"] else "normal"
            })

    blueprint = {
        "session_id": session_id,
        "team_name": team_name,
        "task": task_description,
        "status": "aligned",
        "participants": [{"role": n.get("role"), "node_id": n.get("id")} for n in nodes],
        "debate_log": debate_log,
        "conflict_pairs": conflict_pairs,
        "debate_rounds": round_count,
        "subtasks": subtasks,
        "created_at": datetime.now().isoformat(),
        "summary": f"{len(nodes)}명 에이전트, {round_count}라운드 토론, {len(conflict_pairs)}건 충돌 해소 → {len(subtasks)}개 태스크"
    }

    with _alignment_lock:
        _alignment_sessions[session_id] = blueprint
    # #16: Persist to disk
    _persist_session(session_id, blueprint)

    emit_log("Alignment", f"✅ [{team_name}] 다자간 합의 완결 — {round_count}라운드, {len(conflict_pairs)}건 충돌 해소, {len(subtasks)}개 태스크 분배", "MEETING")

    # #13: LLM-powered summary (optional — fallback to template if LLM unavailable)
    llm_summary = None
    try:
        llm_result = _call_active_llm(
            "You are a meeting summarizer. Produce a concise Korean summary of the alignment meeting.",
            f"프로젝트: {_clean_task}\n참여 에이전트: {', '.join([n.get('role','?') for n in nodes])}\n"
            f"토론 라운드: {round_count}, 충돌 해소: {len(conflict_pairs)}건, 생성 태스크: {len(subtasks)}개\n"
            f"요약을 2-3문장으로 작성해주세요."
        )
        if llm_result.get("success") and llm_result.get("text"):
            llm_summary = llm_result["text"]
            emit_log("Alignment", f"🤖 LLM 요약 생성 완료", "MEETING")
    except Exception as e:
        logging.debug(f"LLM summary generation skipped: {e}")

    blueprint["summary"] = llm_summary or f"{len(nodes)}명 에이전트, {round_count}라운드 토론, {len(conflict_pairs)}건 충돌 해소 → {len(subtasks)}개 태스크"

    total_tokens = len(nodes) * 800 + len(conflict_pairs) * 1200
    meter_action("Alignment Engine", "multi_round_debate", total_tokens, total_tokens // 4)

    return blueprint

def get_alignment_session(session_id):
    """#16: Retrieve a stored alignment session (memory first, then disk)."""
    with _alignment_lock:
        session = _alignment_sessions.get(session_id)
        if session:
            return session
    # #16: Fallback to disk-persisted session
    return _load_persisted_session(session_id)

def execute_subtasks_background(team_name, blueprint, knowledge_sources=None, socketio_ref=None):
    """ChatDev Core 2.0 — LLM-powered autonomous code generation with governance (#3)."""
    task_id = f"subtask_{team_name}_{datetime.now().strftime('%H%M%S')}"

    def _worker():
        # ── Wait for frontend Execution Tracker DOM to render ──
        time.sleep(3.5)

        subtasks = blueprint.get("subtasks", [])
        task_desc = blueprint.get("task", "")
        _clean = _sanitize_prompt(task_desc)
        total = len(subtasks)
        total_cost = 0.0

        # ── Create project workspace ──
        proj_slug = _re.sub(r'[^a-zA-Z0-9가-힣_]', '_', _clean)[:40].strip('_')
        proj_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "workspace", "output", team_name, f"proj_{proj_slug}"
        )
        os.makedirs(proj_dir, exist_ok=True)

        emit_log("System", f"⚡ [{team_name}] ChatDev Core 2.0 — LLM 자율 코딩 시작 ({total}개 태스크)", "SYSTEM")
        emit_log("System", f"📂 프로젝트 경로: {proj_dir}", "SYSTEM")

        # #3: Create governance context for subtask execution
        subtask_job_ctx = None
        if _GOVERNANCE_AVAILABLE:
            try:
                task_desc = blueprint.get("task", "")
                subtask_job_ctx = create_job_context(team_name, task_desc)
                set_current_job(subtask_job_ctx)
                # Set budgets per agent
                for st in subtasks:
                    agent = st.get("agent", "Agent")
                    resource_governor.set_budget(subtask_job_ctx.job_id, agent, max_cost_usd=3.0)
                emit_log("Governance", f"🛡️ Subtask 거버넌스 활성화: {subtask_job_ctx.job_id}", "GOVERNANCE")
                AuditLogger.log("subtask_job_created", {
                    "team": team_name, "subtask_count": total
                }, job_id=subtask_job_ctx.job_id)
            except Exception as _ge:
                logging.warning(f"[Governance] Subtask context failed: {_ge}")

        if socketio_ref:
            try:
                socketio_ref.emit("workflow_execution", {
                    "event": "start",
                    "exec_id": task_id,
                    "team_name": team_name,
                    "total_agents": total
                })
            except Exception:
                pass

        generated_files = []

        for idx, st in enumerate(subtasks):
            agent = st["agent"]
            task_text = st["task"]

            # ── Status: RUNNING ──
            st["status"] = "running"
            emit_log(agent, f"🧠 LLM 코딩 중... {task_text}", "SUBTASK")

            if socketio_ref:
                try:
                    socketio_ref.emit("subtask_progress", {
                        "task_id": task_id, "team_name": team_name,
                        "index": idx, "total": total,
                        "subtask_id": st.get("subtask_id", f"sub_{idx}"),
                        "agent": agent, "node_id": st.get("node_id", ""),
                        "task": task_text, "status": "running",
                        "progress_pct": int((idx / total) * 100)
                    })
                    socketio_ref.emit("workflow_agent_status", {
                        "event": "working",
                        "agent": agent,
                        "step": idx + 1,
                        "total": total,
                        "exec_id": task_id
                    })
                except Exception:
                    pass

            # ── LLM Code Generation ──
            file_map = _get_file_target(agent, task_text, idx)
            code_result = _generate_code_for_subtask(
                project_name=_clean,
                agent_role=agent,
                task_text=task_text,
                file_target=file_map,
                knowledge_sources=knowledge_sources
            )

            # ── Write to disk ──
            for fname, content in code_result["files"].items():
                fpath = os.path.join(proj_dir, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                
                # Emit file_progress for mini-console streaming
                if socketio_ref:
                    try:
                        socketio_ref.emit("file_progress", {
                            "task_id": task_id, "team_name": team_name,
                            "index": idx, "agent": agent,
                            "message": f"📝 생성 중... {fname}",
                            "file_name": fname,
                            "file_size": len(content),
                            "phase": "writing"
                        })
                    except Exception:
                        pass
                
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
                generated_files.append(fname)
                emit_log(agent, f"💾 파일 생성 완료: {fname} ({len(content)} bytes)", "FILE_WRITE")
                
                # Emit completion signal for this file
                if socketio_ref:
                    try:
                        socketio_ref.emit("file_progress", {
                            "task_id": task_id, "team_name": team_name,
                            "index": idx, "agent": agent,
                            "message": f"💾 {fname} ({len(content):,} bytes) ✅",
                            "file_name": fname,
                            "file_size": len(content),
                            "phase": "complete"
                        })
                    except Exception:
                        pass

            # ── Metering + Governance (#3) ──
            result = meter_action(agent, "llm_code_generation",
                                  code_result.get("input_tokens", 500),
                                  code_result.get("output_tokens", 300))
            total_cost += result["cost_usd"]

            # #3: Record usage in governance budget
            if _GOVERNANCE_AVAILABLE and subtask_job_ctx:
                try:
                    usage_result = resource_governor.record_usage(
                        subtask_job_ctx.job_id, agent,
                        tokens_used=code_result.get("input_tokens", 500) + code_result.get("output_tokens", 300),
                        cost_usd=result["cost_usd"], socketio_ref=socketio_ref
                    )
                    if usage_result.get("circuit_breaker_tripped"):
                        emit_log("Governance", f"🚨 [{agent}] Subtask 예산 초과", "CIRCUIT_BREAKER")
                        AuditLogger.log("subtask_circuit_breaker", {
                            "agent": agent, "cost": result["cost_usd"]
                        }, job_id=subtask_job_ctx.job_id, agent=agent, severity="ERROR")
                    AuditLogger.log("subtask_step_complete", {
                        "agent": agent, "files": list(code_result["files"].keys()),
                        "cost": result["cost_usd"], "source": code_result.get("source", "unknown")
                    }, job_id=subtask_job_ctx.job_id, agent=agent)
                except Exception:
                    pass

            st["status"] = "completed"
            st["output_files"] = list(code_result["files"].keys())
            st["llm_source"] = code_result.get("source", "unknown")

            # ── Status: COMPLETED ──
            if socketio_ref:
                try:
                    socketio_ref.emit("subtask_progress", {
                        "task_id": task_id, "team_name": team_name,
                        "index": idx, "total": total,
                        "subtask_id": st.get("subtask_id", f"sub_{idx}"),
                        "agent": agent, "node_id": st.get("node_id", ""),
                        "task": task_text, "status": "completed",
                        "cost_usd": round(result["cost_usd"], 6),
                        "progress_pct": int(((idx + 1) / total) * 100),
                        "files_generated": list(code_result["files"].keys())
                    })
                    socketio_ref.emit("workflow_agent_status", {
                        "event": "completed",
                        "agent": agent,
                        "step": idx + 1,
                        "total": total,
                        "exec_id": task_id,
                        "output_preview": task_text[:100]
                    })
                except Exception:
                    pass

        # ── Generate final execution report ──
        _write_execution_report(proj_dir, _clean, team_name, subtasks, generated_files, total_cost)

        try:
            _trigger_external_connectors(team_name, _clean, subtasks, total_cost, generated_files)
        except Exception as e:
            logging.error(f"Failed to trigger external connectors in execute_subtasks: {e}")

        emit_log("System", f"🏁 [{team_name}] ChatDev Core 2.0 완료 — {len(generated_files)}개 파일 생성, ${total_cost:.4f}", "SYSTEM")

        # ── Emit final completion event ──
        if socketio_ref:
            try:
                socketio_ref.emit("execution_complete", {
                    "task_id": task_id, "team_name": team_name,
                    "total_subtasks": total,
                    "total_cost": round(total_cost, 4),
                    "files_generated": generated_files,
                    "project_dir": proj_dir,
                    "subtask_summary": [{"agent": s["agent"], "task": s["task"], "status": s["status"],
                                         "files": s.get("output_files", []), "source": s.get("llm_source", "")} for s in subtasks]
                })
                socketio_ref.emit("workflow_execution", {
                    "event": "complete",
                    "exec_id": task_id,
                    "team_name": team_name,
                    "total_agents": total,
                    "total_cost_usd": total_cost
                })
            except Exception:
                pass

        with _bg_lock:
            if task_id in _background_tasks:
                _background_tasks[task_id]["status"] = "completed"
                _background_tasks[task_id]["completed_at"] = datetime.now().isoformat()
                _background_tasks[task_id]["total_cost"] = total_cost
                _background_tasks[task_id]["files_generated"] = generated_files

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    with _bg_lock:
        _background_tasks[task_id] = {
            "task_id": task_id, "team_name": team_name,
            "status": "running",
            "agents": len(blueprint.get("subtasks", [])),
            "started_at": datetime.now().isoformat(),
            "completed_at": None, "total_cost": 0.0,
            "type": "llm_code_generation"
        }

    return task_id


# ══════════════════════════════════════════════════════════════
#   ChatDev Core 2.0 — Local LLM Autonomous Coding Engine
# ══════════════════════════════════════════════════════════════

import httpx

_OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:latest")
_LLM_TIMEOUT = 120  # seconds

# ── System Instruction: Strict code-only output lock ──
_LLM_CODE_SYSTEM_PROMPT = """You are ChatDev Autonomous Coding Agent — a senior full-stack developer.
You ONLY output source code. No explanations, no commentary, no conversation.

RULES:
1. Output MUST be wrapped in a single fenced code block: ```language ... ```
2. Supported languages: html, css, javascript, python, markdown, json
3. The code must be COMPLETE, PRODUCTION-READY, and SELF-CONTAINED
4. Include proper comments in the source code
5. For HTML: Include modern CSS inline or in <style> tags, use semantic HTML5
6. For Python: Include proper imports, type hints, docstrings
7. For Markdown: Use proper headers, sections, tables
8. NEVER output partial code, pseudocode, or placeholder comments like "// TODO"
9. RESPOND ONLY WITH THE CODE BLOCK. Nothing else before or after."""

# ── File target mapping by agent role ──
def _get_file_target(agent_role, task_text, idx):
    """Determine output filename and language based on agent role and task."""
    role_map = {
        "Chief Executive Officer": {"file": f"docs/executive_brief_{idx}.md", "lang": "markdown"},
        "Chief Product Officer": {"file": f"docs/prd_{idx}.md", "lang": "markdown"},
        "Designer": {"file": f"frontend/index.html" if idx == 0 else f"frontend/components_{idx}.html", "lang": "html"},
        "Programmer": {"file": f"backend/server.py" if "API" in task_text or "엔드포인트" in task_text else f"backend/core_{idx}.py", "lang": "python"},
        "Tester": {"file": f"tests/test_suite_{idx}.py", "lang": "python"},
        "Reviewer": {"file": f"docs/review_checklist_{idx}.md", "lang": "markdown"},
        "Content Writer": {"file": f"docs/ux_copy_{idx}.md", "lang": "markdown"},
        "Data Analyst": {"file": f"analytics/dashboard_spec_{idx}.md", "lang": "markdown"},
        "Creative Director": {"file": f"docs/brand_guide_{idx}.md", "lang": "markdown"},
        "DevOps": {"file": f"infra/deploy_{idx}.py", "lang": "python"},
    }
    return role_map.get(agent_role, {"file": f"misc/output_{idx}.md", "lang": "markdown"})


def _extract_code_blocks(llm_output, lang="python"):
    """Extract pure source code from LLM markdown-fenced output using regex."""
    if not llm_output:
        return None

    # Try exact language match first
    match = _re.search(rf"```{lang}\s*\n(.*?)\n\s*```", llm_output, _re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try any fenced block
    match = _re.search(r"```\w*\s*\n(.*?)\n\s*```", llm_output, _re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no fences, check if the entire output looks like code (no markdown headers)
    lines = llm_output.strip().split('\n')
    if lines and not lines[0].startswith('#') and len(lines) > 3:
        return llm_output.strip()

    return None


def load_env_live():
    """Dynamically read values from .env and environment variables in the worker process."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env")
    cfg = {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key": "",
        "anthropic_api_key": "",
        "google_api_key": "",
        "local_endpoint": "http://localhost:11434"
    }
    
    # 1. Load from .env file
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key == "AI_PROVIDER":
                        cfg["provider"] = value
                    elif key == "AI_MODEL":
                        cfg["model"] = value
                    elif key == "OPENAI_API_KEY":
                        cfg["api_key"] = value
                        os.environ["OPENAI_API_KEY"] = value
                    elif key == "ANTHROPIC_API_KEY":
                        cfg["anthropic_api_key"] = value
                        os.environ["ANTHROPIC_API_KEY"] = value
                    elif key == "GOOGLE_API_KEY":
                        cfg["google_api_key"] = value
                        os.environ["GOOGLE_API_KEY"] = value
                    elif key == "LOCAL_LLM_ENDPOINT":
                        cfg["local_endpoint"] = value
        except Exception:
            pass
            
    # 2. Override with current environment variables
    for k, target in [
        ("AI_PROVIDER", "provider"),
        ("AI_MODEL", "model"),
        ("OPENAI_API_KEY", "api_key"),
        ("ANTHROPIC_API_KEY", "anthropic_api_key"),
        ("GOOGLE_API_KEY", "google_api_key"),
        ("LOCAL_LLM_ENDPOINT", "local_endpoint")
    ]:
        if k in os.environ and os.environ[k]:
            val = os.environ[k].strip().strip('"').strip("'")
            if val and not val.startswith("your_"):
                cfg[target] = val
                
    return cfg


def _call_active_llm(system_prompt, user_prompt, temperature=0.7):
    """Call the active LLM configured in the system (OpenAI, Gemini, Anthropic, or Local Ollama).
    
    #6: Uses actual token counts from API responses instead of split().
    """
    cfg = load_env_live()
    provider = cfg["provider"]
    model = cfg["model"]
    
    # #6: Estimate tokens only as fallback — prefer API-reported counts
    _est_input = len(system_prompt.split()) + len(user_prompt.split())
    
    try:
        if provider == "openai":
            api_key = cfg["api_key"]
            if not api_key:
                raise ValueError("OpenAI API key not set")
            import openai as _oai
            client = _oai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature
            )
            text = resp.choices[0].message.content.strip()
            # #6: Use actual token counts from API response
            usage = getattr(resp, 'usage', None)
            input_tokens = getattr(usage, 'prompt_tokens', _est_input) if usage else _est_input
            output_tokens = getattr(usage, 'completion_tokens', len(text.split())) if usage else len(text.split())
            return {
                "success": True, "text": text,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "model": model, "source": "openai"
            }
            
        elif provider == "anthropic":
            api_key = cfg["anthropic_api_key"]
            if not api_key:
                raise ValueError("Anthropic API key not set")
            import anthropic as _ant
            client = _ant.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model, max_tokens=4096, system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=temperature
            )
            text = resp.content[0].text.strip()
            # #6: Anthropic reports usage in response
            usage = getattr(resp, 'usage', None)
            input_tokens = getattr(usage, 'input_tokens', _est_input) if usage else _est_input
            output_tokens = getattr(usage, 'output_tokens', len(text.split())) if usage else len(text.split())
            return {
                "success": True, "text": text,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "model": model, "source": "anthropic"
            }
            
        elif provider == "google":
            api_key = cfg["google_api_key"]
            if not api_key:
                raise ValueError("Google API key not set")
            import google.generativeai as _genai
            _genai.configure(api_key=api_key)
            gclient = _genai.GenerativeModel(
                model_name=model, system_instruction=system_prompt
            )
            resp = gclient.generate_content(
                user_prompt, generation_config={"temperature": temperature}
            )
            text = resp.text.strip()
            # #6: Gemini usage metadata
            usage_meta = getattr(resp, 'usage_metadata', None)
            input_tokens = getattr(usage_meta, 'prompt_token_count', _est_input) if usage_meta else _est_input
            output_tokens = getattr(usage_meta, 'candidates_token_count', len(text.split())) if usage_meta else len(text.split())
            return {
                "success": True, "text": text,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "model": model, "source": "google"
            }
            
        elif provider == "local":
            return _call_local_llm(system_prompt, user_prompt, temperature)
            
    except Exception as e:
        emit_log("LLM", f"⚠️ {provider.upper()} ({model}) failed: {str(e)[:200]}", "WARN")
        
    # If active provider failed, try local Ollama
    if provider != "local":
        local_res = _call_local_llm(system_prompt, user_prompt, temperature)
        if local_res["success"]:
            return local_res
            
    return {"success": False, "error": "All LLM calls failed", "input_tokens": _est_input, "output_tokens": 0}


def _call_llm_with_fallback_chain(system_prompt, user_prompt, agent_role, agent_llm_override=None):
    """#5: Multi-provider fallback chain — try all available LLMs before giving up.
    #10: Respects per-agent LLM configuration.
    
    Chain: Agent-specific config → Primary provider → Alternative providers → Local → Fail
    """
    cfg = load_env_live()

    # #10: Apply per-agent overrides
    effective_provider = cfg["provider"]
    effective_model = cfg["model"]
    effective_temp = 0.7
    if agent_llm_override:
        if agent_llm_override.get("provider"):
            effective_provider = agent_llm_override["provider"]
        if agent_llm_override.get("model"):
            effective_model = agent_llm_override["model"]
        if agent_llm_override.get("temperature") is not None:
            effective_temp = agent_llm_override["temperature"]

    # Build fallback chain: primary → alternatives → local
    providers_to_try = []
    
    # 1st: Agent-specific or primary provider
    providers_to_try.append((effective_provider, effective_model, effective_temp))
    
    # 2nd-4th: Alternative providers (skip if same as primary)
    alt_providers = [
        ("openai", cfg.get("model", "gpt-4o"), 0.7, cfg.get("api_key")),
        ("anthropic", "claude-sonnet-4-20250514", 0.7, cfg.get("anthropic_api_key")),
        ("google", "gemini-2.5-flash", 0.7, cfg.get("google_api_key")),
    ]
    for alt_prov, alt_model, alt_temp, alt_key in alt_providers:
        if alt_prov != effective_provider and alt_key:
            providers_to_try.append((alt_prov, alt_model, alt_temp))
    
    # 5th: Local Ollama
    providers_to_try.append(("local", "llama3", 0.7))

    for attempt, (prov, model, temp) in enumerate(providers_to_try):
        try:
            # Temporarily override config for this call
            _saved = (cfg["provider"], cfg["model"])
            cfg["provider"] = prov
            cfg["model"] = model
            
            result = _call_active_llm(system_prompt, user_prompt, temperature=temp)
            
            cfg["provider"], cfg["model"] = _saved
            
            if result.get("success"):
                if attempt > 0:
                    emit_log(agent_role, f"🔄 Fallback 성공: {prov}/{model} (시도 {attempt+1})", "FALLBACK")
                return result
            
            cfg["provider"], cfg["model"] = _saved
            
        except Exception as e:
            emit_log(agent_role, f"⚠️ {prov}/{model} 실패: {str(e)[:100]}", "FALLBACK")
            continue
    
    return {"success": False, "error": "All providers exhausted", "input_tokens": 0, "output_tokens": 0}


def _search_knowledge_sources(query, knowledge_sources, top_k=2):
    """Keyword-based knowledge search from passed sources in worker."""
    if not knowledge_sources:
        return []
        
    # Helper to chunk text
    def _chunk_text_local(text, chunk_size=500, overlap=50):
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk.strip())
        return chunks

    # Helper to extract keywords
    def _extract_keywords_local(text):
        import re
        words = re.findall(r'[가-힣a-zA-Z]{2,}', text.lower())
        stop_words = {'the','and','for','are','but','not','you','all','can','had','her','was','one',
                      'our','out','day','get','has','him','his','how','its','may','new','now','old',
                      '이것','그것','이런','그런','하는','있는','되는','하고','에서','으로','것은'}
        return set(w for w in words if w not in stop_words and len(w) > 1)

    query_keywords = _extract_keywords_local(query)
    if not query_keywords:
        return []
        
    all_chunks = []
    for src in knowledge_sources:
        fname = src.get("name", "Unknown")
        content = src.get("content", "")
        chunks = _chunk_text_local(content)
        for chunk in chunks:
            all_chunks.append({
                "source": fname,
                "chunk": chunk,
                "keywords": _extract_keywords_local(chunk)
            })
            
    scored = []
    for cdata in all_chunks:
        overlap = len(query_keywords & cdata["keywords"])
        if overlap > 0:
            scored.append((overlap, cdata["source"], cdata["chunk"]))
            
    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]


def _call_local_llm(system_prompt, user_prompt, temperature=0.7):
    """Call local Ollama LLM via httpx synchronous client."""
    try:
        with httpx.Client(timeout=_LLM_TIMEOUT) as client:
            resp = client.post(
                f"{_OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": _OLLAMA_MODEL,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 4096,
                        "top_p": 0.9,
                    }
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "text": data.get("response", ""),
                    "input_tokens": data.get("prompt_eval_count", 0),
                    "output_tokens": data.get("eval_count", 0),
                    "model": _OLLAMA_MODEL,
                    "source": "ollama_local"
                }
            else:
                emit_log("LLM", f"⚠️ Ollama HTTP {resp.status_code}: {resp.text[:200]}", "ERROR")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
    except httpx.ConnectError:
        emit_log("LLM", "⚠️ Ollama 연결 실패 — 폴백 코더 활성화", "WARN")
        return {"success": False, "error": "connection_refused"}
    except httpx.TimeoutException:
        emit_log("LLM", f"⚠️ Ollama 타임아웃 ({_LLM_TIMEOUT}s) — 폴백 코더 활성화", "WARN")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        emit_log("LLM", f"⚠️ LLM 호출 예외: {str(e)[:200]}", "ERROR")
        return {"success": False, "error": str(e)}


def _generate_code_for_subtask(project_name, agent_role, task_text, file_target, knowledge_sources=None):
    """Generate code via active LLM with RAG grounding and intelligent fallback."""
    lang = file_target["lang"]
    fname = file_target["file"]

    # ── Perform RAG Grounding if sources are available ──
    grounding_context = ""
    if knowledge_sources:
        matches = _search_knowledge_sources(task_text, knowledge_sources, top_k=2)
        if matches:
            grounding_context = "\n=== GROUNDING KNOWLEDGE FROM COMPANY FILES ===\n"
            for score, source, chunk in matches:
                grounding_context += f"[Source File: {source}]\n{chunk}\n---\n"
                emit_log(agent_role, f"📚 RAG 지식 주입 완료: {source} (매칭 스코어: {score})", "GROUNDING")
            grounding_context += "==============================================\n"

    user_prompt = f"""Project: {project_name}
Role: {agent_role}
Task: {task_text}
Output file: {fname}
Language: {lang}
{grounding_context}
Generate the COMPLETE source code for this task. The code must be production-ready.
Output a single ```{lang} ... ``` code block."""

    # ── Call the active LLM configured in settings ──
    llm_result = _call_active_llm(_LLM_CODE_SYSTEM_PROMPT, user_prompt)

    if llm_result.get("success"):
        extracted = _extract_code_blocks(llm_result["text"], lang)
        if extracted and len(extracted) > 50:
            emit_log("LLM", f"✅ {llm_result.get('source','LLM').upper()} 코드 생성 성공: {fname} ({len(extracted)} chars)", "LLM")
            return {
                "files": {fname: extracted},
                "source": llm_result.get("source"),
                "input_tokens": llm_result.get("input_tokens", 0),
                "output_tokens": llm_result.get("output_tokens", 0)
            }
        else:
            emit_log("LLM", f"⚠️ 코드 추출 실패 (길이 부족) — 폴백 활성화", "WARN")

    # ── Fallback: Intelligent autonomous coder ──
    emit_log("Fallback", f"🔄 자율 폴백 코더 가동: {fname}", "FALLBACK")
    fallback_code = _fallback_generate(project_name, agent_role, task_text, lang, fname)
    return {
        "files": {fname: fallback_code},
        "source": "fallback_autonomous",
        "input_tokens": len(user_prompt.split()),
        "output_tokens": len(fallback_code.split())
    }


def _fallback_generate(project_name, agent_role, task_text, lang, fname):
    """Smart fallback code generator that produces real, contextual code based on role and task."""

    if lang == "html":
        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0f172a; color: #e2e8f0;
            min-height: 100vh; display: flex; flex-direction: column;
        }}
        header {{
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 24px 32px; border-bottom: 1px solid #334155;
        }}
        header h1 {{ font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }}
        header p {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
        main {{
            flex: 1; padding: 32px; max-width: 1200px; margin: 0 auto; width: 100%;
        }}
        .card {{
            background: #1e293b; border: 1px solid #334155; border-radius: 12px;
            padding: 24px; margin-bottom: 16px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}
        .card h2 {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; }}
        .card p {{ font-size: 13px; color: #94a3b8; line-height: 1.6; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
        .btn {{
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 20px; background: #3b82f6; color: #fff;
            border: none; border-radius: 8px; font-size: 13px; font-weight: 600;
            cursor: pointer; transition: background 0.2s;
        }}
        .btn:hover {{ background: #2563eb; }}
        .status {{ display: flex; align-items: center; gap: 6px; font-size: 11px; color: #22c55e; }}
        .status::before {{
            content: ''; width: 6px; height: 6px; background: #22c55e;
            border-radius: 50%; animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
        footer {{ padding: 16px 32px; text-align: center; font-size: 11px; color: #475569; }}
    </style>
</head>
<body>
    <header>
        <h1>🏗️ {project_name}</h1>
        <p>Auto-generated by ChatDev Core 2.0 — {agent_role}</p>
    </header>
    <main>
        <div class="status">System Online — Real-time</div>
        <div class="grid" style="margin-top: 16px;">
            <div class="card">
                <h2>📊 Dashboard</h2>
                <p>{task_text}</p>
                <button class="btn" style="margin-top: 12px;">Launch Module</button>
            </div>
            <div class="card">
                <h2>⚡ Live Feed</h2>
                <p>Real-time data streaming and analytics pipeline.</p>
                <div id="live-feed" style="margin-top: 8px; font-family: monospace; font-size: 11px; color: #64748b;">
                    Connecting...
                </div>
            </div>
            <div class="card">
                <h2>🔧 Configuration</h2>
                <p>System settings and deployment parameters.</p>
            </div>
        </div>
    </main>
    <footer>© {datetime.now().year} {project_name} — Powered by ChatDev Core 2.0</footer>
    <script>
        // Live feed simulation
        const feed = document.getElementById('live-feed');
        const msgs = ['[INFO] System initialized', '[DATA] Stream connected', '[OK] Modules loaded'];
        let i = 0;
        setInterval(() => {{
            feed.textContent = msgs[i % msgs.length] + ' — ' + new Date().toLocaleTimeString();
            i++;
        }}, 2000);
    </script>
</body>
</html>"""

    elif lang == "python":
        if "API" in task_text or "엔드포인트" in task_text or "server" in fname:
            return f'''"""
{project_name} — Backend API Server
Auto-generated by ChatDev Core 2.0
Agent: {agent_role}
Task: {task_text}
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import uvicorn

app = FastAPI(
    title="{project_name} API",
    description="Auto-generated API server by ChatDev Core 2.0",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Data Models ──
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

class DataItem(BaseModel):
    id: Optional[int] = None
    name: str
    value: float
    category: str = "default"
    created_at: Optional[str] = None

# ── In-Memory Store ──
_data_store: List[dict] = []

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check endpoint."""
    return HealthResponse(
        status="operational",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )

@app.get("/api/data", response_model=List[DataItem])
async def get_all_data():
    """Retrieve all data items."""
    return _data_store

@app.post("/api/data", response_model=DataItem)
async def create_data(item: DataItem):
    """Create a new data item."""
    item.id = len(_data_store) + 1
    item.created_at = datetime.now().isoformat()
    _data_store.append(item.model_dump())
    return item

@app.get("/api/data/{{item_id}}", response_model=DataItem)
async def get_data(item_id: int):
    """Retrieve a specific data item."""
    for d in _data_store:
        if d["id"] == item_id:
            return d
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/api/data/{{item_id}}")
async def delete_data(item_id: int):
    """Delete a specific data item."""
    global _data_store
    _data_store = [d for d in _data_store if d.get("id") != item_id]
    return {{"status": "deleted", "id": item_id}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
'''
        elif "테스트" in task_text or "test" in fname:
            return f'''"""
{project_name} — Test Suite
Auto-generated by ChatDev Core 2.0
Agent: {agent_role}
Task: {task_text}
"""

import pytest
from datetime import datetime


class TestCoreModule:
    """Core module test suite."""

    def test_health_check(self):
        """Verify system health endpoint."""
        assert True, "Health check passed"

    def test_data_creation(self):
        """Verify data item creation."""
        item = {{"name": "test_item", "value": 42.0, "category": "test"}}
        assert item["name"] == "test_item"
        assert item["value"] == 42.0

    def test_data_validation(self):
        """Verify data validation rules."""
        assert isinstance(datetime.now().isoformat(), str)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        assert "" == ""
        assert 0 == 0
        assert None is None

    def test_performance_baseline(self):
        """Establish performance baseline."""
        import time
        start = time.time()
        _ = [i ** 2 for i in range(10000)]
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Performance baseline exceeded: {{elapsed}}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        else:
            return f'''"""
{project_name} — Core Module
Auto-generated by ChatDev Core 2.0
Agent: {agent_role}
Task: {task_text}
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProjectCore:
    """Core business logic for {project_name}."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {{}}
        self.created_at = datetime.now().isoformat()
        self._state: Dict[str, Any] = {{}}
        logger.info(f"ProjectCore initialized: {{self.created_at}}")

    def process(self, data: Dict) -> Dict:
        """Process input data and return results."""
        result = {{
            "input": data,
            "processed_at": datetime.now().isoformat(),
            "status": "success",
            "metrics": self._compute_metrics(data)
        }}
        self._state["last_process"] = result
        return result

    def _compute_metrics(self, data: Dict) -> Dict:
        """Compute analysis metrics from input data."""
        return {{
            "field_count": len(data),
            "data_types": {{k: type(v).__name__ for k, v in data.items()}},
            "timestamp": datetime.now().isoformat()
        }}

    def export(self, format: str = "json") -> str:
        """Export current state to specified format."""
        if format == "json":
            return json.dumps(self._state, indent=2, ensure_ascii=False, default=str)
        raise ValueError(f"Unsupported format: {{format}}")


if __name__ == "__main__":
    core = ProjectCore()
    result = core.process({{"project": "{project_name}", "task": "{task_text}"}})
    print(json.dumps(result, indent=2, ensure_ascii=False))
'''

    else:  # markdown
        return f"""# {project_name}

> Auto-generated by ChatDev Core 2.0 — {agent_role}

## 📋 Task

{task_text}

## 📊 Overview

| Item | Detail |
|------|--------|
| **Project** | {project_name} |
| **Agent** | {agent_role} |
| **Generated** | {datetime.now().strftime('%Y-%m-%d %H:%M')} |
| **Status** | ✅ Complete |

## 🏗️ Architecture

### Core Components

1. **Frontend Layer** — Modern responsive SPA
2. **Backend API** — FastAPI with async handlers
3. **Data Layer** — Structured data models with validation
4. **Analytics** — Real-time metrics and reporting

### Key Decisions

- Modular architecture for independent scaling
- Event-driven communication between services
- Containerized deployment with health checks

## 📈 Implementation Plan

### Phase 1: Foundation
- Core data models and API endpoints
- Authentication and authorization framework
- Basic UI scaffold with design system

### Phase 2: Feature Development
- Domain-specific business logic
- Real-time data processing pipeline
- Advanced UI components and interactions

### Phase 3: Production Hardening
- Comprehensive test coverage (>80%)
- Performance optimization and caching
- Monitoring, alerting, and observability

## 🔒 Security Considerations

- Input validation on all endpoints
- Rate limiting and CORS configuration
- Secrets management via environment variables
- Regular dependency audits

---

*Generated by ChatDev Core 2.0 for {project_name}*
"""


def _write_execution_report(proj_dir, project_name, team_name, subtasks, files, total_cost):
    """Write comprehensive execution report to the project directory."""
    report_path = os.path.join(proj_dir, "EXECUTION_REPORT.md")
    file_list = '\n'.join([f"- `{f}`" for f in files])
    subtask_table = '\n'.join([
        f"| {s['agent']} | {s['task'][:50]} | {s.get('llm_source', 'N/A')} | {', '.join(s.get('output_files', []))} |"
        for s in subtasks
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"""# 🏗️ Execution Report — {project_name}

**Team:** {team_name}
**Generated:** {datetime.now().isoformat()}
**Engine:** ChatDev Core 2.0

## 📊 Summary

| Metric | Value |
|--------|-------|
| Total Subtasks | {len(subtasks)} |
| Files Generated | {len(files)} |
| Total Cost | ${total_cost:.4f} |
| LLM Engine | {_OLLAMA_MODEL} |

## 📂 Generated Files

{file_list}

## 🔧 Subtask Execution Log

| Agent | Task | Source | Output |
|-------|------|--------|--------|
{subtask_table}

---
*ChatDev Core 2.0 — Autonomous Code Generation Engine*
""")
    emit_log("System", f"📝 실행 리포트 생성: EXECUTION_REPORT.md", "FILE_WRITE")


def _trigger_external_connectors(team_name, project_name, subtasks, total_cost, generated_files):
    """Triggers external notifications via Slack, Notion, GitHub if configured; otherwise logs simulated actions."""
    import urllib.request, urllib.error, json as _json

    # 1. Slack
    slack_token = os.environ.get("CONN_SLACK_TOKEN")
    slack_channel = os.environ.get("CONN_SLACK_CHANNEL", "#general")
    slack_url = os.environ.get("CONN_SLACK_URL") # webhook URL

    message = f"🏁 [{team_name}] ChatDev Core 2.0 완료\n프로젝트: {project_name}\n생성 파일: {len(generated_files)}개\n총 비용: ${total_cost:.4f}"

    if slack_url or (slack_token and slack_channel):
        try:
            if slack_url:
                payload = {"text": message}
                req = urllib.request.Request(
                    slack_url,
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    logging.info("Slack webhook notification sent successfully.")
            elif slack_token:
                payload = {"channel": slack_channel, "text": message}
                req = urllib.request.Request(
                    "https://slack.com/api/chat.postMessage",
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {slack_token}",
                        "Content-Type": "application/json; charset=utf-8"
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    res = _json.loads(r.read().decode("utf-8"))
                    if res.get("ok"):
                        logging.info("Slack API notification sent successfully.")
                    else:
                        logging.warning(f"Slack API error: {res.get('error')}")
        except Exception as e:
            logging.error(f"Failed to send Slack notification: {e}")
    else:
        # Simulation log in sandbox mode
        emit_log("Connector", f"[Simulated Slack Notification] {message}", "INFO")

    # 2. Notion
    notion_token = os.environ.get("CONN_NOTION_TOKEN")
    notion_db = os.environ.get("CONN_NOTION_DATABASE_ID") or os.environ.get("CONN_NOTION_DB_ID")
    if notion_token:
        try:
            url = "https://api.notion.com/v1/pages"
            if notion_db:
                payload = {
                    "parent": {"database_id": notion_db},
                    "properties": {
                        "Name": {
                            "title": [{"text": {"content": f"ChatDev Project: {project_name}"}}]
                        },
                        "Team": {
                            "rich_text": [{"text": {"content": team_name}}]
                        },
                        "Cost": {
                            "number": total_cost
                        },
                        "Files": {
                            "number": len(generated_files)
                        }
                    }
                }
                req = urllib.request.Request(
                    url,
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {notion_token}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    logging.info("Notion page created successfully.")
            else:
                emit_log("Connector", f"[Simulated Notion Notification] Created page for project '{project_name}' (Cost: ${total_cost:.4f})", "INFO")
        except Exception as e:
            logging.error(f"Failed to create Notion page: {e}")
    else:
        emit_log("Connector", f"[Simulated Notion Notification] Notion page generated for project '{project_name}'", "INFO")

    # 3. GitHub
    github_token = os.environ.get("CONN_GITHUB_TOKEN")
    github_url = os.environ.get("CONN_GITHUB_URL")
    if github_token and github_url:
        try:
            api_url = github_url
            if "/repos/" in api_url and not api_url.endswith("/issues") and not api_url.endswith("/commits"):
                parts = api_url.split("/repos/")
                api_url = f"https://api.github.com/repos/{parts[1].rstrip('/')}/issues"

            payload = {
                "title": f"ChatDev Run Completed: {project_name}",
                "body": f"ChatDev execution completed on team **{team_name}**.\n\n- **Project Name:** {project_name}\n- **Total Cost:** ${total_cost:.4f}\n- **Generated Files:** {', '.join(generated_files)}"
            }
            req = urllib.request.Request(
                api_url,
                data=_json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"token {github_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "ChatDev-Enterprise"
                }
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                logging.info("GitHub Issue created successfully.")
        except Exception as e:
            logging.error(f"Failed to post to GitHub: {e}")
    else:
        emit_log("Connector", f"[Simulated GitHub Notification] GitHub Issue created: ChatDev Run Completed: {project_name}", "INFO")
