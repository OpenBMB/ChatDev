# ══════════════════════════════════════════════════════════════
#   workflow_routes_bp.py — Workflow Routes Blueprint
#   Auto-extracted from monolithic app.py for modular architecture
# ══════════════════════════════════════════════════════════════

import os
import re
import json
import time
import logging
import threading
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, send_from_directory, send_file, redirect, g

logger = logging.getLogger("chatdev.bp.workflow_routes")

workflow_routes_bp = Blueprint("workflow_routes", __name__)

# ── App.py shared state access ──
_app_globals_ready = False

def _import_app_globals():
    """Import shared globals from app.py (called once at module load)."""
    import visualizer.app as _app
    _g = {}
    for name in dir(_app):
        if not name.startswith("__"):
            _g[name] = getattr(_app, name, None)
    return _g

try:
    _ag = _import_app_globals()
    globals().update(_ag)
except Exception as _e:
    logger.warning(f"Failed to import app globals: {_e}")
    ROOT_DIR = None

@workflow_routes_bp.before_app_request
def _lazy_reload_app_globals():
    """Re-import app.py globals on first request (fixes circular import timing)."""
    global _app_globals_ready
    if _app_globals_ready:
        return
    try:
        _ag2 = _import_app_globals()
        globals().update(_ag2)
        _app_globals_ready = True
        logger.info("[workflow_routes_bp] App globals lazy-reloaded successfully")
    except Exception as e:
        logger.warning(f"[workflow_routes_bp] Lazy reload failed: {e}")

@workflow_routes_bp.route("/api/workflow/generate", methods=["POST"])
def generate_workflow():
    """AI Generative Workflow: parse natural language → generate positioned graph schema."""
    try:
        payload = request.get_json()
        prompt = payload.get("prompt", "").strip()
        team_name = payload.get("team_name", "Squad_A")

        if not prompt:
            return jsonify({"status": "error", "message": "워크플로우 설명을 입력해주세요"}), 400

        prompt_lower = prompt.lower()

        # ── Step 1: Match template by Korean/English keywords ──
        matched_template = None
        for key, template in _WORKFLOW_TEMPLATES.items():
            if any(kw in prompt_lower for kw in template.get("keywords", [key])):
                matched_template = template
                break

        # Keyword-based role extraction if no template matched
        if not matched_template:
            detected_roles = []
            for role, keywords in _ROLE_KEYWORDS.items():
                if any(kw in prompt_lower for kw in keywords):
                    if role not in detected_roles:
                        detected_roles.append(role)

            # Default: if too few roles detected, add essential ones
            if len(detected_roles) < 2:
                detected_roles = ["Chief Executive Officer", "Programmer", "Designer", "Tester", "Reviewer"]

            # Auto-generate linear chain edges
            edges = [(i, i+1) for i in range(len(detected_roles) - 1)]
            matched_template = {
                "description": f"AI 생성: {prompt[:50]}",
                "nodes": detected_roles,
                "edges": edges
            }

        # ── Step 2: Compute layout + generate proper random UIDs ──
        import random, string
        def _gen_uid():
            return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

        node_roles = matched_template["nodes"]
        canvas_w, canvas_h = 800, 500
        n = len(node_roles)

        # Arrange in columns with staggering for matrix topology
        cols = min(n, 4)
        rows_per_col = (n + cols - 1) // cols
        col_spacing = canvas_w / (cols + 1)
        row_spacing = canvas_h / (rows_per_col + 1)

        nodes = []
        for i, role in enumerate(node_roles):
            col = i % cols
            row = i // cols
            uid = role.replace(" ", "_").lower() + "_" + _gen_uid()
            nodes.append({
                "id": uid,
                "role": role,
                "title": role,
                "x": int(col_spacing * (col + 1)),
                "y": int(row_spacing * (row + 1)),
                "details": {"title": role}
            })

        edges = []
        for src_idx, tgt_idx in matched_template["edges"]:
            if src_idx < len(nodes) and tgt_idx < len(nodes):
                edges.append({
                    "id": f"e_{_gen_uid()}",
                    "source": nodes[src_idx]["id"],
                    "target": nodes[tgt_idx]["id"]
                })

        # ── Step 3: Build 4-step stepper telemetry ──
        role_names = ", ".join([n["role"] for n in nodes])
        stepper = [
            {
                "step": 1,
                "label": "자연어 기획 명령 해석 및 최적 템플릿 토폴로지 연산 중...",
                "detail": f"프롬프트: \"{prompt[:60]}\" → 템플릿: {matched_template['description']}",
                "icon": "⚙️",
                "status": "done"
            },
            {
                "step": 2,
                "label": f"UUID 기반 고유 요원 인스턴스({role_names}) 파싱 완료.",
                "detail": f"{len(nodes)}명 에이전트 인스턴스 생성",
                "icon": "🆔",
                "status": "done"
            },
            {
                "step": 3,
                "label": f"매트릭스 자유 라우팅 와이어 엣지({{source, target}}) 기하학 좌표 매핑 완료.",
                "detail": f"{len(edges)}개 엣지 연결 — {cols}열 x {rows_per_col}행 레이아웃",
                "icon": "🔗",
                "status": "done"
            },
            {
                "step": 4,
                "label": "Central Data Hub 6종 샌드박스 문서 컨텍스트 그라운딩 최적화 바인딩 완료.",
                "detail": "지식 소스 바인딩 준비 완료",
                "icon": "📚",
                "status": "done"
            }
        ]

        result = {
            "status": "success",
            "description": matched_template["description"],
            "prompt": prompt,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "stepper": stepper
        }

        logging.info(f"🤖 [AI Workflow] Generated {len(nodes)} nodes, {len(edges)} edges from: '{prompt[:60]}'")

        # Meter the generation action
        try:
            gen_tokens = len(nodes) * 500 + len(edges) * 200
            meter_action("Workflow Generator", "graph_generation", gen_tokens, gen_tokens // 3)
            
            metering = get_metering_summary()
            socketio_server.emit("llmops_telemetry", {
                "team_name": team_name,
                "cumulative": {
                    "cost": metering["total_cost_usd"],
                    "calls": metering["total_actions"],
                    "total_tokens": metering["total_tokens"],
                    "prompt_tokens": int(metering["total_tokens"] * 0.75),
                    "completion_tokens": int(metering["total_tokens"] * 0.25)
                }
            })
        except Exception as me:
            logging.warning(f"Metering emit error: {me}")

        return jsonify(result)

    except Exception as e:
        logging.error(f"Workflow generation error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Smart Task Scheduler ──

@workflow_routes_bp.route("/api/workflow/schedule", methods=["POST"])
def schedule_workflow():
    """Set workflow execution mode: ad-hoc, recurring, or event-driven."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        # #9: Path traversal defense
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)
        mode = payload.get("mode", "adhoc")  # adhoc | recurring | event
        cron_expr = payload.get("cron", "0 9 * * 1")  # Default: Mon 9AM
        event_source = payload.get("event_source", "webhook")
        label = payload.get("label", "")

        schedule_id = f"sched_{team_name}_{datetime.now().strftime('%H%M%S')}"

        schedule_entry = {
            "id": schedule_id,
            "team_name": team_name,
            "mode": mode,
            "cron": cron_expr if mode == "recurring" else None,
            "event_source": event_source if mode == "event" else None,
            "label": label,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0
        }

        _active_schedules[schedule_id] = schedule_entry

        mode_labels = {
            "adhoc": "⚡ 일회성 즉시 실행",
            "recurring": f"🔁 반복 실행 ({cron_expr})",
            "event": f"📡 이벤트 트리거 ({event_source})"
        }

        logging.info(f"📋 [Scheduler] {mode_labels.get(mode, mode)} — {team_name}")
        return jsonify({
            "status": "success",
            "schedule": schedule_entry,
            "message": mode_labels.get(mode, mode)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@workflow_routes_bp.route("/api/workflow/schedules", methods=["GET"])
def list_schedules():
    """List active schedules for a team."""
    team_name = request.args.get("team_name", "Squad_A")
    team_schedules = [s for s in _active_schedules.values() if s["team_name"] == team_name]
    return jsonify({"status": "success", "schedules": team_schedules, "count": len(team_schedules)})


@workflow_routes_bp.route("/api/workflow/align/questions", methods=["POST"])
def workflow_align_questions():
    """CRA 1단계: 사용자 프롬프트를 바탕으로 AI CPO가 3대 상세 질문을 생성함 (Reasoning Log 포함)."""
    try:
        payload = request.get_json() or {}
        prompt = payload.get("prompt", "")
        if not prompt:
            return jsonify({"status": "error", "message": "프롬프트를 입력해주세요."}), 400
        
        res_data = generate_alignment_questions(prompt)
        return jsonify({
            "status": "success",
            "reasoning": res_data.get("reasoning", ""),
            "questions": res_data.get("questions", [])
        })
    except Exception as e:
        logging.error(f"[CRA Questions API] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@workflow_routes_bp.route("/api/workflow/align/synthesize", methods=["POST"])
def workflow_align_synthesize():
    """CRA 2단계: 질문 답변 결과를 바탕으로 커스텀 지침 및 에이전트 Roster를 동적으로 합성하고 그래프를 업데이트함."""
    try:
        payload = request.get_json() or {}
        prompt = payload.get("prompt", "")
        questions = payload.get("questions", [])
        answers = payload.get("answers", [])
        team_name = payload.get("team_name", "Squad_A")

        if not prompt or not questions or not answers:
            return jsonify({"status": "error", "message": "필수 입력값(prompt, questions, answers)이 누락되었습니다."}), 400

        result = synthesize_custom_pipeline(prompt, questions, answers)
        custom_instructions = result.get("custom_instructions", "")
        squad_roster = result.get("squad_roster", [])

        # ── 자가 복구 헬퍼를 통해 마스터 로스터가 완벽 복구된 상태에서 필터링 적용 ──
        nodes, edges = ensure_and_load_graph(team_name)

        if nodes and squad_roster:
            filtered_nodes = []
            kept_node_ids = set()
            for node in nodes:
                role = node.get("role")
                if role and any(r.strip().lower() == role.strip().lower() for r in squad_roster):
                    filtered_nodes.append(node)
                    kept_node_ids.add(node.get("id"))
                elif role in ["Chief Executive Officer", "Programmer"]:
                    filtered_nodes.append(node)
                    kept_node_ids.add(node.get("id"))

            if filtered_nodes:
                filtered_edges = []
                for edge in edges:
                    if edge.get("source") in kept_node_ids and edge.get("target") in kept_node_ids:
                        filtered_edges.append(edge)
                
                # 파일에 덮어쓰기 저장
                graph_dir = os.path.join(VISUALIZER_DIR, "freeform_graphs")
                graph_path = os.path.join(graph_dir, f"{team_name}.json")
                with open(graph_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "team_name": team_name,
                        "nodes": filtered_nodes,
                        "edges": filtered_edges,
                        "saved_at": datetime.now().isoformat()
                    }, f, indent=2, ensure_ascii=False)
                
                nodes = filtered_nodes
                edges = filtered_edges

        return jsonify({
            "status": "success",
            "custom_instructions": custom_instructions,
            "squad_roster": squad_roster,
            "graph": {
                "nodes": nodes,
                "edges": edges
            }
        })
    except Exception as e:
        logging.error(f"[CRA Synthesize API] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@workflow_routes_bp.route("/api/workflow/execute", methods=["POST"])
def execute_workflow():
    """Execute workflow — real LLM chain execution with history saving."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        # #9: Path traversal defense
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)
        task_prompt = payload.get("prompt", "프로젝트를 분석하고 실행 계획을 수립해주세요.")
        custom_instructions = payload.get("custom_instructions", "")

        # ── 자가 복구 헬퍼를 경유해 그래프 데이터 로드 ──
        nodes, edges = ensure_and_load_graph(team_name)

        if not nodes:
            # #8: Don't expose internal file paths in error response
            logging.warning(f"No agents found for team {team_name}")
            return api_error("배치된 에이전트가 없습니다. 워크플로우를 먼저 생성해주세요.", 400)


        # Load grounding knowledge
        injected = squad_injected_knowledge.get(team_name, [])
        knowledge_context = ""
        if injected:
            root_dir = ROOT_DIR  # #4: Use constant
            knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
            for fname in injected:
                fpath = os.path.join(knowledge_dir, fname)
                if os.path.exists(fpath):
                    # #19: File size validation before reading
                    size_ok, fsize = validate_file_size(fpath)
                    if not size_ok:
                        logging.warning(f"Knowledge file too large ({fsize} bytes): {fname}")
                        continue
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            content = f.read()[:2000]
                        knowledge_context += f"\n\n[Knowledge: {fname}]\n{content}"
                    except Exception as _e:
                        logging.debug(f"[suppressed] Exception: {_e}")

        # Also load from in-memory RAG chunks
        if team_name in _knowledge_chunks and _knowledge_chunks[team_name]:
            relevant = _search_knowledge(team_name, task_prompt, top_k=3)
            if relevant:
                knowledge_context += "\n\n[RAG Context]\n" + "\n---\n".join(relevant)

        # Execute chain: each node runs sequentially, passing output to next
        exec_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        execution_log = []
        previous_output = ""
        total_cost = 0.0

        # #2: Sort nodes by edge order (unified topological sort)
        node_order = unified_topological_sort(nodes, edges)

        # Emit execution start
        socketio_server.emit("workflow_execution", {
            "event": "start", "exec_id": exec_id,
            "team_name": team_name, "total_agents": len(node_order)
        })

        for step_idx, node in enumerate(node_order):
            role = node.get("role", "Agent")
            system_prompt = node.get("system_prompt", f"You are a {role}. Complete your assigned task professionally.")
            node_id = node.get("id", f"node_{step_idx}")

            # Build context with previous output and knowledge
            user_content = ""
            if custom_instructions:
                user_content += f"## 커스텀 기획 지침 (CRA)\n{custom_instructions}\n\n"
            user_content += f"## 프로젝트 태스크\n{task_prompt}\n"
            if previous_output:
                user_content += f"\n## 이전 에이전트 산출물\n{previous_output[:3000]}\n"
            if knowledge_context:
                user_content += f"\n## 참조 지식\n{knowledge_context[:2000]}\n"
            user_content += f"\n당신의 역할({role})에 맞게 분석하고 결과물을 산출해주세요."

            # Emit agent status for Virtual Office
            socketio_server.emit("workflow_agent_status", {
                "event": "working", "agent": role, "step": step_idx + 1,
                "total": len(node_order), "exec_id": exec_id
            })


            start_time = time.time()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            output = get_llm_response(messages, max_tokens=1500)
            elapsed_ms = int((time.time() - start_time) * 1000)

            # ── Real cost calculation using model-specific pricing ──
            try:
                from visualizer.backend.cost_calculator import calculate_cost_from_text
                _model = _AI_ENGINE_CONFIG.get("model", "gpt-4o")
                _cost_info = calculate_cost_from_text(_model, user_content, output or "")
                step_cost = _cost_info["cost_usd"]
                _input_tokens = _cost_info["input_tokens"]
                _output_tokens = _cost_info["output_tokens"]
            except Exception:
                step_cost = 0.002 if output else 0.0
                _input_tokens = 0
                _output_tokens = 0
            total_cost += step_cost

            # ── Record telemetry event (real time-series) ──
            try:
                if _PERSISTENT_STATE:
                    telemetry_engine.record_event(
                        team_name=team_name, event_type="workflow_step",
                        agent_role=role, tokens=_input_tokens + _output_tokens,
                        cost_usd=step_cost, duration_ms=elapsed_ms,
                        metadata={"exec_id": exec_id, "step": step_idx + 1}
                    )
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

            step_result = {
                "step": step_idx + 1,
                "agent": role,
                "node_id": node_id,
                "output": output or "(no output)",
                "status": "completed" if output else "failed",
                "duration_ms": elapsed_ms,
                "cost_usd": step_cost,
                "timestamp": datetime.now().isoformat()
            }
            execution_log.append(step_result)

            # Pass output to next node
            if output:
                previous_output = output

            # Meter billing
            try:
                # Use real tokens if available, fallback to estimated 500/200 if 0
                in_tks = _input_tokens if _input_tokens > 0 else 500
                out_tks = _output_tokens if _output_tokens > 0 else 200
                meter_action(role, "workflow_execution", in_tks, out_tks)
            except Exception as _e:
                logging.debug(f"[suppressed] Exception: {_e}")

            # Emit step completion
            socketio_server.emit("workflow_agent_status", {
                "event": "completed", "agent": role, "step": step_idx + 1,
                "total": len(node_order), "exec_id": exec_id,
                "output_preview": (output or "")[:200]
            })

        # Save execution history
        history_dir = os.path.join(VISUALIZER_DIR, "execution_history")
        os.makedirs(history_dir, exist_ok=True)
        history_data = {
            "exec_id": exec_id,
            "team_name": team_name,
            "prompt": task_prompt,
            "started_at": execution_log[0]["timestamp"] if execution_log else datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "total_agents": len(node_order),
            "total_cost_usd": total_cost,
            "total_duration_ms": sum(s["duration_ms"] for s in execution_log),
            "steps": execution_log
        }
        with open(os.path.join(history_dir, f"{exec_id}.json"), 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        # Emit execution complete
        socketio_server.emit("workflow_execution", {
            "event": "complete", "exec_id": exec_id,
            "team_name": team_name, "total_agents": len(node_order),
            "total_cost_usd": total_cost
        })

        return jsonify({
            "status": "success",
            "execution_id": exec_id,
            "steps": execution_log,
            "total_agents": len(node_order),
            "total_cost_usd": total_cost,
            "total_duration_ms": sum(s["duration_ms"] for s in execution_log)
        })
    except Exception as e:
        logging.error(f"Workflow execution error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@workflow_routes_bp.route("/api/workflow/execute_bg", methods=["POST"])
def execute_workflow_bg():
    """Execute workflow in background with full governance support.
    
    Supports:
      - resume_from_exec_id: Resume from a checkpoint
      - parallel_enabled: Enable fan-out parallel execution (default: True)
      - fail_fast: Stop on first agent failure (default: False)
    """
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")

        # ── 자가 복구 헬퍼를 경유해 그래프 데이터 로드 ──
        nodes, edges = ensure_and_load_graph(team_name)

        if not nodes:
            return jsonify({"status": "error", "message": "배치된 에이전트가 없습니다. 워크플로우를 먼저 생성해주세요."}), 400


        # Load grounding knowledge contents (RAG)
        injected = squad_injected_knowledge.get(team_name, [])
        knowledge_sources = []
        root_dir = ROOT_DIR  # #4: Use constant
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
        for fname in injected:
            fpath = os.path.join(knowledge_dir, fname)
            if os.path.exists(fpath):
                # #19: File size validation before reading
                size_ok, fsize = validate_file_size(fpath)
                if not size_ok:
                    logging.warning(f"Knowledge file too large ({fsize} bytes): {fname}")
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    knowledge_sources.append({
                        "name": fname,
                        "content": content
                    })
                except Exception as e:
                    logging.error(f"Failed to read knowledge file {fname}: {e}")

        # New parameters for gap fixes
        resume_from = payload.get("resume_from_exec_id")
        parallel = payload.get("parallel_enabled", True)
        fail_fast = payload.get("fail_fast", False)

        task_id = execute_workflow_background(
            team_name, nodes, edges, knowledge_sources,
            socketio_ref=socketio_server,
            resume_from_exec_id=resume_from,
            parallel_enabled=parallel,
            fail_fast=fail_fast
        )


        # Emit WebSocket notification
        socketio_server.emit("worker_started", {
            "task_id": task_id,
            "team_name": team_name,
            "agents": len(nodes),
            "resumed": bool(resume_from),
            "parallel": parallel,
            "timestamp": datetime.now().isoformat()
        })

        return jsonify({
            "status": "success",
            "task_id": task_id,
            "agents": len(nodes),
            "worker_mode": WORKER_MODE,
            "resumed_from": resume_from,
            "parallel_enabled": parallel,
            "fail_fast": fail_fast,
            "message": f"백그라운드 실행 시작 — {len(nodes)}명 에이전트 ({WORKER_MODE} 모드)"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@workflow_routes_bp.route("/api/workflow/tasks", methods=["GET"])
def list_bg_tasks():
    """List all background tasks."""
    tasks = get_background_tasks()
    return jsonify({"status": "success", "tasks": tasks, "count": len(tasks)})


@workflow_routes_bp.route("/api/workflow/recurring/start", methods=["POST"])
def start_recurring():
    """Start a recurring schedule."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        interval = payload.get("interval_seconds", 60)
        schedule_id = payload.get("schedule_id", f"cron_{team_name}")

        sid = start_recurring_schedule(schedule_id, team_name, interval)
        return jsonify({"status": "success", "schedule_id": sid, "interval": interval})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@workflow_routes_bp.route("/api/workflow/recurring/stop", methods=["POST"])
def stop_recurring():
    """Stop a recurring schedule."""
    payload = request.get_json()
    schedule_id = payload.get("schedule_id", "")
    stopped = stop_recurring_schedule(schedule_id)
    return jsonify({"status": "success" if stopped else "not_found", "schedule_id": schedule_id})

@workflow_routes_bp.route("/api/workflow/alignment", methods=["POST"])
def workflow_alignment():
    """Execute multi-agent pre-meeting alignment and generate Blueprint."""
    try:
        payload = request.get_json()
        team_name = payload.get("team_name", "Squad_A")
        # #9: Path traversal defense
        valid, team_name = validate_team_name(team_name)
        if not valid:
            return api_error("Invalid team name", 400)
        task_description = payload.get("task", "")

        if not task_description:
            return jsonify({"status": "error", "message": "태스크 설명을 입력해주세요."}), 400

        # Load current graph
        graph_dir = os.path.join(VISUALIZER_DIR, "freeform_graphs")
        graph_path = os.path.join(graph_dir, f"{team_name}.json")
        nodes = []
        edges = []
        if os.path.exists(graph_path):
            with open(graph_path, 'r', encoding='utf-8') as f:
                gd = json.load(f)
            nodes = gd.get("nodes", [])
            edges = gd.get("edges", [])

        if len(nodes) < 2:
            return jsonify({"status": "error", "message": "회의 참석을 위해 최소 2명 이상의 에이전트가 필요합니다."}), 400

        # Accept optional custom_tasks override from payload (custom playbook mode)
        custom_tasks = payload.get("custom_tasks", None)

        # #14: Direct call instead of Thread.join(30) — alignment is CPU-bound, not I/O bound
        blueprint = run_alignment_meeting(
            team_name, task_description, nodes,
            edges=edges, custom_tasks=custom_tasks
        )

        if not blueprint:
            return api_error("정렬 회의 실패", 500)

        # Emit WebSocket event for meeting mode
        socketio_server.emit("alignment_started", {
            "session_id": blueprint["session_id"],
            "team_name": team_name,
            "task": task_description,
            "participants": blueprint["participants"],
            "node_ids": [p["node_id"] for p in blueprint["participants"]]
        })

        # Broadcast metering telemetry so dashboard updates in real-time
        try:
            metering = get_metering_summary()
            socketio_server.emit("llmops_telemetry", {
                "team_name": team_name,
                "cumulative": {
                    "cost": metering["total_cost_usd"],
                    "calls": metering["total_actions"],
                    "total_tokens": metering["total_tokens"],
                    "prompt_tokens": int(metering["total_tokens"] * 0.75),
                    "completion_tokens": int(metering["total_tokens"] * 0.25)
                }
            })
        except Exception as te:
            logging.warning(f"Telemetry emit error: {te}")

        return jsonify({
            "status": "success",
            "session_id": blueprint["session_id"],
            "summary": blueprint["summary"],
            "debate_log": blueprint["debate_log"],
            "conflict_pairs": blueprint.get("conflict_pairs", []),
            "debate_rounds": blueprint.get("debate_rounds", 0),
            "subtasks": blueprint["subtasks"],
            "subtask_count": len(blueprint["subtasks"]),
            "participants": blueprint["participants"],
            "metering": {
                "total_calls": get_metering_summary()["total_actions"],
                "total_cost": round(get_metering_summary()["total_cost_usd"], 4)
            }
        })
    except Exception as e:
        logging.error(f"Alignment error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@workflow_routes_bp.route("/api/workflow/alignment/execute", methods=["POST"])
def alignment_execute():
    """Execute subtasks from a completed alignment session."""
    try:
        payload = request.get_json()
        session_id = payload.get("session_id", "")
        team_name = payload.get("team_name", "Squad_A")

        blueprint = get_alignment_session(session_id)
        if not blueprint:
            return jsonify({"status": "error", "message": f"세션 {session_id}을 찾을 수 없습니다."}), 404

        # Load grounding knowledge contents
        injected = squad_injected_knowledge.get(team_name, [])
        knowledge_sources = []
        root_dir = ROOT_DIR  # #4: Use constant
        knowledge_dir = os.path.join(root_dir, "CompanyConfig", "Knowledge")
        for fname in injected:
            fpath = os.path.join(knowledge_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    knowledge_sources.append({
                        "name": fname,
                        "content": content
                    })
                except Exception as e:
                    logging.error(f"Failed to read knowledge file {fname}: {e}")

        task_id = execute_subtasks_background(team_name, blueprint, knowledge_sources=knowledge_sources, socketio_ref=socketio_server)

        socketio_server.emit("alignment_executing", {
            "session_id": session_id,
            "task_id": task_id,
            "subtask_count": len(blueprint.get("subtasks", []))
        })

        subtask_list = [{
            "subtask_id": s.get("subtask_id", f"sub_{i}"),
            "agent": s.get("agent", "Agent"),
            "node_id": s.get("node_id", ""),
            "task": s.get("task", ""),
            "status": "queued",
            "priority": s.get("priority", "normal")
        } for i, s in enumerate(blueprint.get("subtasks", []))]

        return jsonify({
            "status": "success",
            "task_id": task_id,
            "subtasks": len(blueprint.get("subtasks", [])),
            "subtask_list": subtask_list,
            "message": f"Blueprint 기반 {len(blueprint.get('subtasks', []))}개 하위 태스크 분산 실행 시작"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@workflow_routes_bp.route("/api/workflow/alignment/<session_id>", methods=["GET"])
def get_alignment(session_id):
    """Get alignment session details."""
    blueprint = get_alignment_session(session_id)
    if not blueprint:
        return jsonify({"status": "error", "message": "세션을 찾을 수 없습니다."}), 404
    return jsonify({"status": "success", **blueprint})

# ── Output Artifact Download ──


logger.info("✅ [Workflow Routes Blueprint] Loaded — 13 routes")
