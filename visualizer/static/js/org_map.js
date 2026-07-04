$(document).ready(function() {
    // ══════════════════════════════════════════════
    //  Card Position Persistence (localStorage)
    // ══════════════════════════════════════════════
    const STORAGE_KEY = "chatdev_org_positions";

    function saveNodePositions(root) {
        const positions = {};
        root.descendants().forEach(d => {
            positions[d.data.name] = { x: d.x, y: d.y };
        });
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(positions)); } catch(e) {}
    }

    function loadNodePositions() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch(e) { return null; }
    }

    function clearNodePositions() {
        try { localStorage.removeItem(STORAGE_KEY); } catch(e) {}
    }

    // ══════════════════════════════════════════════
    //  Auto-Sort Layouts
    // ══════════════════════════════════════════════
    let _currentLayout = "tree";
    let _currentRoot = null;
    let _currentSvg = null;
    // Bumped on every loadOrgMap() call so overlapping in-flight requests
    // (e.g. rapid clicks on "초기화", or a blueprint-applied event firing
    // mid-load) can detect they've been superseded and skip rendering,
    // instead of both appending nodes into #org-canvas and producing
    // duplicate-id badges.
    let _orgMapRequestToken = 0;

    function applyLayout(root, svg, layout) {
        const width = $("#org-canvas").width() - 420;
        const height = ($("#org-canvas").height() || 600) - 150;
        const nodes = root.descendants();

        if (layout === "tree") {
            const treemap = d3.tree().size([height, width]);
            treemap(root);
        } else if (layout === "vertical") {
            const treemap = d3.tree().size([width, height]);
            treemap(root);
            // Swap x/y for vertical layout
            nodes.forEach(d => { const tmp = d.x; d.x = d.y; d.y = tmp; });
        } else if (layout === "grid") {
            const cols = Math.ceil(Math.sqrt(nodes.length));
            nodes.forEach((d, i) => {
                d.y = 60 + (i % cols) * 280;
                d.x = 40 + Math.floor(i / cols) * 160;
            });
        }

        // Animate transition
        svg.selectAll(".node")
            .data(nodes)
            .transition()
            .duration(600)
            .attr("transform", d => `translate(${d.y},${d.x})`);

        svg.selectAll(".link")
            .data(root.links())
            .transition()
            .duration(600)
            .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x));

        saveNodePositions(root);
    }

    // 1. Fetch dynamic stats, load hired employee details, and render full 3-level tree
    function loadOrgMap() {
        const requestToken = ++_orgMapRequestToken;
        $.getJSON("/api/org_stats", function(data) {
            if (requestToken !== _orgMapRequestToken) return; // superseded by a newer loadOrgMap() call
            if (data.status !== "success") {
                console.error("Failed to load org stats:", data.message);
                return;
            }

            // Update top-level dashboard overview cards
            $("#total-divisions").text(data.total_divisions + " Divisions");
            $("#active-tasks").text(data.global_active_tasks + " Active");
            $("#empire-cost").text(data.cumulative_cost);

            const teamNames = Object.keys(data.squads);
            if (teamNames.length === 0) return;

            // Load details for all squads in parallel to build 3-level hierarchy
            const promises = teamNames.map(name => $.getJSON(`/api/load_team?name=${name}`));

            $.when(...promises).done(function(...responses) {
                if (requestToken !== _orgMapRequestToken) return; // superseded by a newer loadOrgMap() call
                const children = [];
                // If only 1 squad exists, responses is [data, textStatus, jqXHR]. If multiple, it is list of arrays.
                const normalizedResponses = teamNames.length === 1 ? [responses] : responses;

                normalizedResponses.forEach((respArray, idx) => {
                    const teamName = teamNames[idx];
                    const teamData = data.squads[teamName];
                    const teamConfig = respArray[0];
                    const details = teamConfig.squad_details || {};
                    const recruitments = teamConfig.recruitments || [];

                    // Determine the leader card
                    let leaderRole = "Chief Executive Officer";
                    if (recruitments.includes("Chief Executive Officer")) {
                        leaderRole = "Chief Executive Officer";
                    } else if (recruitments.length > 0) {
                        leaderRole = recruitments[0];
                    }

                    const leaderTitle = details[leaderRole] ? details[leaderRole].title : "Squad Leader";

                    // Determine the sub-employees
                    const employeeNodes = [];
                    recruitments.forEach(role => {
                        if (role !== leaderRole) {
                            const empTitle = details[role] ? details[role].title : role;
                            employeeNodes.push({
                                name: empTitle,
                                title: role,
                                type: "employee",
                                class: teamData.class,
                                team: teamName
                            });
                        }
                    });

                    children.push({
                        name: teamName,
                        title: leaderTitle,
                        type: "leader",
                        tasks: teamData.tasks,
                        cost: teamData.cost,
                        class: teamData.class,
                        children: employeeNodes
                    });
                });

                const treeData = {
                    name: "CEO_Orchestrator",
                    title: "Global Chief Executive Officer",
                    type: "ceo",
                    children: children
                };

                // Clear previous canvas
                $("#org-canvas").empty();

                const width = $("#org-canvas").width();
                const height = $("#org-canvas").height() || 600;

                const svgElement = d3.select("#org-canvas")
                    .append("svg")
                    .attr("width", width)
                    .attr("height", height)
                    .style("cursor", "grab");

                // D3 Zoom/Pan behavior
                const zoomG = svgElement.append("g")
                    .attr("class", "zoom-layer");

                const svg = zoomG.append("g")
                    .attr("transform", "translate(60, 20)");

                const zoomBehavior = d3.zoom()
                    .scaleExtent([0.2, 4])
                    .on("zoom", function(event) {
                        zoomG.attr("transform", event.transform);
                    });

                svgElement.call(zoomBehavior)
                    .on("dblclick.zoom", null);

                // Fit-to-view on initial load
                const initialTransform = d3.zoomIdentity.translate(60, 20).scale(1);
                svgElement.call(zoomBehavior.transform, initialTransform);

                // Store zoom references for controls
                window._dashZoom = zoomBehavior;
                window._dashSvg = svgElement;

                const treemap = d3.tree().size([height - 150, width - 420]);
                const root = d3.hierarchy(treeData, d => d.children);
                treemap(root);

                // Add glowing background order line links
                svg.selectAll(".link")
                    .data(root.links())
                    .enter()
                    .append("path")
                    .attr("class", "link order-line-link")
                    .attr("d", d3.linkHorizontal()
                        .x(d => d.y)
                        .y(d => d.x)
                    );

                // Add nodes group
                const node = svg.selectAll(".node")
                    .data(root.descendants())
                    .enter()
                    .append("g")
                    .attr("class", d => "node node--" + d.data.type)
                    .attr("transform", d => `translate(${d.y},${d.x})`);

                // 2. Enable D3 Drag & Drop interaction on all nodes
                const drag = d3.drag()
                    .on("start", function(event, d) {
                        d3.select(this).raise().classed("dragging", true);
                    })
                    .on("drag", function(event, d) {
                        d.y += event.dx; // horizontal translation
                        d.x += event.dy; // vertical translation
                        d3.select(this).attr("transform", `translate(${d.y},${d.x})`);
                        
                        // Dynamic trace of links
                        svg.selectAll(".link")
                            .attr("d", d3.linkHorizontal()
                                .x(d => d.y)
                                .y(d => d.x)
                            );
                    })
                    .on("end", function(event, d) {
                        d3.select(this).classed("dragging", false);
                        // Persist positions to localStorage
                        saveNodePositions(root);
                    });

                node.call(drag);

                // Restore saved positions if available
                const savedPositions = loadNodePositions();
                if (savedPositions) {
                    root.descendants().forEach(d => {
                        const saved = savedPositions[d.data.name];
                        if (saved) {
                            d.x = saved.x;
                            d.y = saved.y;
                        }
                    });
                    node.attr("transform", d => `translate(${d.y},${d.x})`);
                    svg.selectAll(".link")
                        .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x));
                }

                // Store refs for auto-sort
                _currentRoot = root;
                _currentSvg = svg;

                // Draw Level 0: CEO Node
                const ceoNode = node.filter(d => d.data.type === "ceo");
                ceoNode.append("circle")
                    .attr("r", 28)
                    .style("fill", "#ffffff")
                    .style("stroke", "#1e293b")
                    .style("stroke-width", "2px")
                    .style("filter", "none");

                ceoNode.append("text")
                    .attr("dy", ".35em")
                    .attr("x", -10)
                    .attr("y", 45)
                    .style("text-anchor", "middle")
                    .text(d => "👑 CEO_Orchestrator")
                    .style("font-size", "13px")
                    .style("font-weight", "700")
                    .style("fill", "#1e293b");

                // Draw Level 1: Leader (Squad Card) Nodes
                const leaderNode = node.filter(d => d.data.type === "leader");
                leaderNode.append("foreignObject")
                    .attr("width", 240)
                    .attr("height", 145)
                    .attr("x", -15)
                    .attr("y", -70)
                    .html(d => `
                        <div class="d3-org-card ${d.data.class}">
                            <h4>🏢 ${d.data.name.replace('_', ' ')}</h4>
                            <p style="font-weight: 500; color: #1e293b;">👑 ${d.data.title}</p>
                            <div class="badge-container">
                                <span class="badge-item" style="color: #64748b; border: 1px solid #e2e8f0;"><i class="fa-solid fa-bolt"></i> Tasks: ${d.data.tasks}</span>
                                <span class="badge-item" style="color: #64748b; border: 1px solid #e2e8f0;"><i class="fa-solid fa-coins"></i> ${d.data.cost}</span>
                            </div>
                            <a href="/squad/${d.data.name}" class="enter-squad-btn">
                                <i class="fa-solid fa-right-to-bracket"></i> 부서 업무망 진입
                            </a>
                        </div>
                    `);

                // Draw Level 2: Sub-Employee Nodes
                const employeeNode = node.filter(d => d.data.type === "employee");
                employeeNode.append("foreignObject")
                    .attr("width", 180)
                    .attr("height", 60)
                    .attr("x", 10)
                    .attr("y", -25)
                    .html(d => `
                        <div class="badge-item employee-node-badge ${d.data.class}" id="node-badge-${d.data.team.replace(/\s+/g, '-')}-${d.data.title.replace(/\s+/g, '-')}" style="background: #ffffff; border: 1px solid #e2e8f0; padding: 8px 12px; border-radius: 8px; font-weight: 500; font-size: 0.72rem; color: #1e293b; display: flex; align-items: center; gap: 8px; width: 160px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-left: 3px solid ${d.data.class === 'marketing' ? '#64748b' : d.data.class === 'dev' ? '#94a3b8' : d.data.class === 'design' ? '#b08d29' : '#16a34a'};">
                            <i class="fa-solid fa-user-gear" style="color: #94a3b8;"></i>
                            <div style="display: flex; flex-direction: column; overflow: hidden; text-align: left;">
                                <span style="font-weight: 600; color: #1e293b; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">${d.data.name}</span>
                                <span style="font-size: 0.6rem; color: #888; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">${d.data.title}</span>
                            </div>
                        </div>
                    `);
            });
        });
    }

    // Initialize D3 Tree Map
    loadOrgMap();

    // 3. Connect Socket.IO to receive live updates
    const socket = io();

    socket.on("global_live_analytics_stream", function(data) {
        // Update top-level dashboard overview cards
        $("#total-divisions").text(data.total_divisions + " Divisions");
        $("#active-tasks").text(data.global_active_tasks + " Active");
        $("#empire-cost").text(data.cumulative_cost);

        // Dynamically update D3 squad node badges without fully reconstructing D3 tree
        for (const [teamName, teamData] of Object.entries(data.squads)) {
            const cards = $(`.d3-org-card`);
            cards.each(function() {
                const headerText = $(this).find('h4').text().trim();
                if (headerText.includes(teamName.replace('_', ' '))) {
                    $(this).find('.badge-container').html(`
                        <span class="badge-item" style="color: #64748b; border: 1px solid #e2e8f0;"><i class="fa-solid fa-bolt"></i> Tasks: ${teamData.tasks}</span>
                        <span class="badge-item" style="color: #64748b; border: 1px solid #e2e8f0;"><i class="fa-solid fa-coins"></i> ${teamData.cost}</span>
                    `);
                }
            });
        }
    });

    socket.on("blueprint_applied", function(data) {
        // Automatically re-render D3 map when a new industry blueprint is applied
        loadOrgMap();
    });

    // 4. Listen for NLU Command Processed WebSockets and shoot glowing Laser pulse!
    socket.on("command_processed", function(data) {
        const teamName = data.team_name;
        const roleKey = data.role_key;
        const assignee = data.assignee;
        const desc = data.task_description;
        
        showToast(`👑 CEO 명령 실행: 스쿼드 [${teamName.replace('_', ' ')}]의 [${assignee}] 요원에게 Task가 즉각 생성 및 자동 할당되었습니다!`, "success");
        shootLaser(teamName, roleKey);
    });

    // ⚡ Static Task Routing Indicator — No animated particles, instant highlight only
    function shootLaser(targetTeam, assigneeRoleKey) {
        // Find Leader card
        const cards = $(".d3-org-card");
        let leaderCard = null;
        cards.each(function() {
            const headerText = $(this).find('h4').text().trim();
            if (headerText.includes(targetTeam.replace('_', ' '))) {
                leaderCard = $(this);
            }
        });

        // Find Employee badge (id is keyed by team+role, matching how badges are rendered above,
        // since multiple squads can share the same class and would otherwise collide on id lookup)
        const roleId = `node-badge-${targetTeam.replace(/\s+/g, '-')}-${assigneeRoleKey.replace(/\s+/g, '-')}`;
        const empBadge = $(`#${roleId}`);

        // Instant static highlight — no animation, no particles
        if (leaderCard) {
            leaderCard.css("border-color", "#1e293b").css("box-shadow", "0 0 0 2px rgba(30,41,59,0.1)");
            setTimeout(() => {
                leaderCard.css("border-color", "").css("box-shadow", "");
            }, 1200);
        }

        if (empBadge.length) {
            empBadge.css("border-color", "#1e293b").css("box-shadow", "0 0 0 2px rgba(30,41,59,0.1)");
            setTimeout(() => {
                empBadge.css("border-color", "").css("box-shadow", "");
            }, 2000);
        }
    }


    // ══════════════════════════════════════════════
    //  Auto-Sort Controls
    // ══════════════════════════════════════════════
    $(document).on("click", "#btn-autosort-tree", function() {
        if (_currentRoot && _currentSvg) {
            clearNodePositions();
            _currentLayout = "tree";
            const height = ($("#org-canvas").height() || 600) - 150;
            const width = $("#org-canvas").width() - 420;
            const treemap = d3.tree().size([height, width]);
            treemap(_currentRoot);
            applyLayout(_currentRoot, _currentSvg, "tree");
            showToast("🌳 트리 레이아웃 자동 정렬 완료", "success");
        }
    });
    $(document).on("click", "#btn-autosort-vertical", function() {
        if (_currentRoot && _currentSvg) {
            clearNodePositions();
            applyLayout(_currentRoot, _currentSvg, "vertical");
            showToast("📐 세로 레이아웃 자동 정렬 완료", "success");
        }
    });
    $(document).on("click", "#btn-autosort-grid", function() {
        if (_currentRoot && _currentSvg) {
            clearNodePositions();
            applyLayout(_currentRoot, _currentSvg, "grid");
            showToast("⊞ 그리드 레이아웃 자동 정렬 완료", "success");
        }
    });
    $(document).on("click", "#btn-reset-positions", function() {
        clearNodePositions();
        loadOrgMap();
        showToast("🔄 카드 위치 초기화 완료", "success");
    });

    // ══════════════════════════════════════════════
    //  Zoom Controls (Dashboard Canvas)
    // ══════════════════════════════════════════════
    $(document).on("click", "#btn-zoom-in", function() {
        if (window._dashZoom && window._dashSvg) {
            window._dashSvg.transition().duration(300).call(window._dashZoom.scaleBy, 1.3);
        }
    });
    $(document).on("click", "#btn-zoom-out", function() {
        if (window._dashZoom && window._dashSvg) {
            window._dashSvg.transition().duration(300).call(window._dashZoom.scaleBy, 0.7);
        }
    });
    $(document).on("click", "#btn-zoom-fit", function() {
        if (window._dashZoom && window._dashSvg) {
            window._dashSvg.transition().duration(500)
                .call(window._dashZoom.transform, d3.zoomIdentity.translate(60, 20).scale(1));
            $("#org-zoom-level").text("100%");
        }
    });

    // Update zoom level indicator when zooming
    function _watchZoomLevel() {
        if (window._dashSvg && window._dashZoom) {
            window._dashZoom.on("zoom.indicator", function(event) {
                const pct = Math.round(event.transform.k * 100);
                $("#org-zoom-level").text(pct + "%");
            });
        }
    }
    // Retry until zoom is initialized
    const _zoomWatcher = setInterval(function() {
        if (window._dashZoom) { _watchZoomLevel(); clearInterval(_zoomWatcher); }
    }, 500);

    // ══════════════════════════════════════════════
    //  Real-time Task Monitor
    // ══════════════════════════════════════════════
    function updateTaskMonitor() {
        $.getJSON("/api/org_stats", function(data) {
            if (data.status !== "success") return;
            const panel = $("#task-monitor-body");
            if (!panel.length) return;

            let html = '';
            for (const [teamName, teamData] of Object.entries(data.squads)) {
                const statusClass = teamData.tasks > 0 ? 'active' : 'idle';
                const statusIcon = teamData.tasks > 0 ? '⚡' : '💤';
                html += `<div class="task-monitor-team">
                    <div class="task-monitor-header">
                        <span class="task-monitor-status ${statusClass}">${statusIcon}</span>
                        <span class="task-monitor-name">${teamName.replace(/_/g, ' ')}</span>
                        <span class="task-monitor-count">${teamData.tasks} tasks</span>
                    </div>
                    <div class="task-monitor-cost">💰 ${teamData.cost}</div>
                </div>`;
            }
            if (!html) html = '<div style="color:#94a3b8;font-size:11px;padding:8px;">팀 데이터 없음</div>';
            panel.html(html);
        }).fail(function() {
            // silently fail
        });
    }

    // Poll task monitor every 5 seconds
    setInterval(updateTaskMonitor, 5000);
    updateTaskMonitor();

    // (Legacy executive-command bar removed)


    // Onboarding Modal Actions
    $("#chameleon-onboarding-btn").click(function() {
        $("#chameleon-modal").fadeIn(200);
    });

    $("#close-chameleon-btn").click(function() {
        $("#chameleon-modal").fadeOut(150);
    });

    // Handle Blueprint Selection Grid clicks
    $(".blueprint-card").click(function() {
        const industryId = $(this).attr("data-blueprint");
        const industryName = $(this).find("h3").text();
        const teamName = "Marketing_Team"; // Demo targeting Marketing Squad for live transitions

        if (!industryId) return;

        const originalHtml = $(this).html();
        $(this).html(`
            <div style="text-align: center; padding: 20px;">
                <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2.5rem; color: #94a3b8;"></i>
                <p style="margin-top: 10px; font-size: 0.85rem; color: #fff;">카멜레온 변신 중 (Applying Blueprint)...</p>
            </div>
        `);

        $.ajax({
            url: "/api/blueprints/apply",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify({
                team_name: teamName,
                industry_id: industryId
            }),
            success: function(res) {
                setTimeout(function() {
                    $("#chameleon-modal").fadeOut(150);
                    showToast(`🎨 스쿼드 [${teamName}]에 [${industryName}] 블루프린트가 성공적으로 주입되었습니다!`, "success");
                    loadOrgMap();
                }, 1000);
            },
            error: function(err) {
                showToast("❌ 블루프린트 설정 적용 실패: " + (err.responseJSON ? err.responseJSON.message : "서버 오류"), "error");
                $(`[data-blueprint="${industryId}"]`).html(originalHtml);
            }
        });
    });

    // Toast Alert Helper
    function showToast(message, type = "success") {
        let toast = $("<div></div>")
            .addClass("toast-alert")
            .html(`<i class="${type === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-exclamation'}"></i> ${message}`);
        
        if (type === "error") {
            toast.css("border-left-color", "#dc2626").css("color", "#dc2626");
        }
        
        $("body").append(toast);
        toast.fadeIn(300).delay(5000).fadeOut(300, function() {
            $(this).remove();
        });
    }
});
