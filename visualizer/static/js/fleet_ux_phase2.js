/**
 * ═══════════════════════════════════════════════════════
 *  🏢 Fleet UX Phase 2 — P1 Core UX (17 items)
 *  #1 탭스크롤, #2 활성탭, #3 인라인부서, #7 dirty state,
 *  #10 카운터, #12 툴팁, #13 컨텍스트,
 *  #25 키보드, #31 백드롭, #32 유효성, #36 역할카드,
 *  #39 프리셋, #43 반응형, #44 다크모드, #45 스켈레톤, #50 a11y
 * ═══════════════════════════════════════════════════════
 */
(function () {
    'use strict';

    // ═══════════════════════════════════
    //  #2 — 활성 팀 탭 시각적 강조
    //  Uses CSS class (not inline styles) to avoid MutationObserver feedback loop
    // ═══════════════════════════════════
    function enhanceSquadTabs() {
        function applyTabStyles() {
            document.querySelectorAll('.squad-tab-btn').forEach(function (btn) {
                if (btn.classList.contains('active')) {
                    btn.classList.add('fleet-tab-active');
                } else {
                    btn.classList.remove('fleet-tab-active');
                }
            });
        }

        const tabContainer = document.querySelector('.squad-tabs-list');
        if (tabContainer) {
            // Only watch class changes, and use a debounce to prevent loops
            var _tabRaf = 0;
            const observer = new MutationObserver(function () {
                if (_tabRaf) return;
                _tabRaf = requestAnimationFrame(function () {
                    _tabRaf = 0;
                    applyTabStyles();
                });
            });
            observer.observe(tabContainer, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
            applyTabStyles();
        }
    }

    // ═══════════════════════════════════
    //  #7 — "Fleet 구성 저장" dirty state
    // ═══════════════════════════════════
    function enhanceSaveButton() {
        const btn = document.getElementById('btn-commit-squad');
        if (!btn || btn.dataset.p2Enhanced) return;
        btn.dataset.p2Enhanced = 'true';

        let isDirty = false;
        const origText = btn.innerHTML;

        function markDirty() {
            if (isDirty) return;
            isDirty = true;
            btn.style.background = '#1e293b';
            btn.style.color = '#fff';
            btn.style.borderColor = '#1e293b';
            btn.style.boxShadow = '0 2px 10px rgba(30,41,59,0.2)';
            // Add unsaved indicator dot
            if (!btn.querySelector('.dirty-dot')) {
                const dot = document.createElement('span');
                dot.className = 'dirty-dot';
                dot.style.cssText = 'display:inline-block;width:6px;height:6px;background:#f59e0b;border-radius:50%;margin-left:6px;animation:pulseDot 1.2s ease infinite;';
                btn.appendChild(dot);
            }
        }

        function markClean() {
            isDirty = false;
            btn.style.background = '';
            btn.style.color = '';
            btn.style.borderColor = '';
            btn.style.boxShadow = '';
            const dot = btn.querySelector('.dirty-dot');
            if (dot) dot.remove();
            // #8: Success animation
            const origHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> 저장 완료!';
            btn.style.background = '#16a34a';
            btn.style.color = '#fff';
            btn.style.borderColor = '#16a34a';
            setTimeout(function () {
                btn.innerHTML = origHtml;
                btn.style.background = '';
                btn.style.color = '';
                btn.style.borderColor = '';
            }, 1500);
        }

        // Listen for changes in the workforce area
        const canvas = document.getElementById('workforce-cards-container');
        if (canvas) {
            const canvasObs = new MutationObserver(markDirty);
            canvasObs.observe(canvas, { childList: true, subtree: true });
        }

        // Listen for HR sidebar saves as dirty
        document.addEventListener('click', function (e) {
            if (e.target.closest('#btn-save-sidebar-agent')) markDirty();
        });

        // On save click, show success
        btn.addEventListener('click', function () {
            setTimeout(markClean, 500);
        });
    }

    // ═══════════════════════════════════
    //  #10 — 요원 수 카운터 뱃지
    // ═══════════════════════════════════
    function injectAgentCounter() {
        const header = document.querySelector('#view-workforce .sidebar-card .card-header');
        if (!header || header.querySelector('.fleet-agent-counter')) return;

        const counter = document.createElement('span');
        counter.className = 'fleet-agent-counter';
        counter.id = 'fleet-agent-count';
        counter.title = '현재 배치된 요원 수';
        counter.textContent = '0';
        counter.style.cssText = 'font-size:10px;font-weight:700;color:#fff;background:#1e293b;padding:2px 8px;border-radius:10px;margin-left:8px;min-width:16px;text-align:center;display:inline-block;';
        header.appendChild(counter);

        // Update count periodically
        function updateCount() {
            const nodes = document.querySelectorAll('#workforce-cards-container svg circle, #workforce-cards-container svg .node-group');
            const count = nodes.length;
            counter.textContent = count > 0 ? count : '0';
            counter.style.background = count > 0 ? '#1e293b' : '#94a3b8';
        }

        setInterval(updateCount, 2000);
        updateCount();
    }

    // ═══════════════════════════════════
    //  #1 — 부서 탭 스크롤 개선
    // ═══════════════════════════════════
    function enhanceTabScroll() {
        const tabList = document.querySelector('.squad-tabs-list');
        if (!tabList || tabList.dataset.p2Scroll) return;
        tabList.dataset.p2Scroll = 'true';

        tabList.style.scrollbarWidth = 'none';
        tabList.style.msOverflowStyle = 'none';
        tabList.style.overflowX = 'auto';
        tabList.style.overflowY = 'hidden';

        // Scroll active tab into view
        const scrollActiveIntoView = function () {
            const active = tabList.querySelector('.squad-tab-btn.active');
            if (active) {
                active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
            }
        };

        // Scroll on wheel
        tabList.addEventListener('wheel', function (e) {
            e.preventDefault();
            tabList.scrollLeft += e.deltaY;
        }, { passive: false });

        // Auto-scroll on tab change
        tabList.addEventListener('click', function () {
            setTimeout(scrollActiveIntoView, 100);
        });
    }

    // ═══════════════════════════════════
    //  #12 — 노드 호버 툴팁
    // ═══════════════════════════════════
    function injectNodeTooltip() {
        let tooltip = document.getElementById('fleet-node-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'fleet-node-tooltip';
            tooltip.className = 'fleet-node-tooltip';
            document.body.appendChild(tooltip);
        }

        // Delegate hover events on SVG nodes
        document.addEventListener('mouseover', function (e) {
            const node = e.target.closest('circle, .node-group, [data-role]');
            if (!node) return;

            const svg = node.closest('svg');
            if (!svg || !svg.closest('#workforce-cards-container')) return;

            const role = node.getAttribute('data-role') ||
                         node.closest('[data-role]')?.getAttribute('data-role') ||
                         node.parentElement?.querySelector('text')?.textContent || '';
            if (!role) return;

            const details = (window.localAgentDetails && window.localAgentDetails[role]) || {};
            const title = details.title || role;
            const tokens = details.token_limit || 5000;

            tooltip.innerHTML = `
                <div style="font-size:11px;font-weight:700;color:#1e293b;margin-bottom:4px;">${title}</div>
                <div style="font-size:10px;color:#64748b;">역할: ${role}</div>
                <div style="font-size:10px;color:#64748b;">토큰: ${tokens.toLocaleString()}</div>
            `;
            tooltip.style.display = 'block';

            const rect = node.getBoundingClientRect();
            tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + 'px';
        });

        document.addEventListener('mouseout', function (e) {
            const node = e.target.closest('circle, .node-group, [data-role]');
            if (node) tooltip.style.display = 'none';
        });
    }

    // ═══════════════════════════════════
    //  #31 — HR 사이드바 백드롭
    // ═══════════════════════════════════
    function addHRBackdrop() {
        const sidebar = document.getElementById('hr-sidebar');
        if (!sidebar) return;

        let backdrop = document.getElementById('hr-backdrop');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = 'hr-backdrop';
            backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:1999;display:none;transition:opacity 0.3s;opacity:0;';
            document.body.appendChild(backdrop);

            backdrop.addEventListener('click', function () {
                sidebar.style.right = '-420px';
                backdrop.style.opacity = '0';
                setTimeout(function () { backdrop.style.display = 'none'; }, 300);
            });
        }

        // Watch sidebar position changes (with guard to prevent re-entrant mutation loop)
        var _hrObserverBusy = false;
        var _hrLastVisible = false;
        const observer = new MutationObserver(function () {
            if (_hrObserverBusy) return;
            var right = parseInt(sidebar.style.right);
            var isVisible = (right >= 0);
            if (isVisible === _hrLastVisible) return; // no change
            _hrLastVisible = isVisible;
            _hrObserverBusy = true;
            if (isVisible) {
                backdrop.style.display = 'block';
                requestAnimationFrame(function () {
                    backdrop.style.opacity = '1';
                    _hrObserverBusy = false;
                });
            } else {
                backdrop.style.opacity = '0';
                setTimeout(function () {
                    backdrop.style.display = 'none';
                    _hrObserverBusy = false;
                }, 300);
            }
        });
        observer.observe(sidebar, { attributes: true, attributeFilter: ['style'] });
    }

    // ═══════════════════════════════════
    //  #32 — 편집 폼 유효성 검사
    // ═══════════════════════════════════
    function enhanceFormValidation() {
        const saveBtn = document.getElementById('btn-save-sidebar-agent');
        if (!saveBtn || saveBtn.dataset.p2Validated) return;
        saveBtn.dataset.p2Validated = 'true';

        saveBtn.addEventListener('click', function (e) {
            const title = document.getElementById('hr-agent-title');
            const persona = document.getElementById('hr-agent-persona');
            let hasError = false;

            // Clear previous errors
            document.querySelectorAll('.fleet-field-error').forEach(function (el) { el.remove(); });
            [title, persona].forEach(function (el) {
                if (el) el.style.borderColor = '';
            });

            if (title && !title.value.trim()) {
                showFieldError(title, '직책을 입력해주세요');
                hasError = true;
            }
            if (persona && !persona.value.trim()) {
                showFieldError(persona, '페르소나 프롬프트를 입력해주세요');
                hasError = true;
            }

            if (hasError) {
                e.stopImmediatePropagation();
                e.preventDefault();
            }
        }, true); // capture phase to fire before jQuery handler

        function showFieldError(field, msg) {
            field.style.borderColor = '#dc2626';
            field.style.background = '#fef2f2';
            const err = document.createElement('div');
            err.className = 'fleet-field-error';
            err.style.cssText = 'font-size:10px;color:#dc2626;margin-top:2px;display:flex;align-items:center;gap:4px;';
            err.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> ' + msg;
            field.parentNode.appendChild(err);

            // Clear on input
            field.addEventListener('input', function handler() {
                field.style.borderColor = '';
                field.style.background = '';
                err.remove();
                field.removeEventListener('input', handler);
            });
        }
    }

    // ═══════════════════════════════════
    //  #39 — 역할별 프리셋 자동 채우기
    // ═══════════════════════════════════
    function addRolePresets() {
        const PRESETS = {
            'Chief Executive Officer': { title: 'CEO', persona: '전략적 사고와 리더십을 갖춘 최고 경영자. 팀 전체를 총괄하며 핵심 결정을 내립니다.', tokens: 8000 },
            'Chief Product Officer': { title: 'CPO', persona: '제품 비전을 설정하고 사용자 경험을 최적화하는 제품 책임자.', tokens: 6000 },
            'Chief Technology Officer': { title: 'CTO', persona: '기술 아키텍처를 설계하고 개발팀을 이끄는 기술 총괄 책임자. 최신 기술 트렌드를 파악합니다.', tokens: 7000 },
            'Programmer': { title: 'Software Engineer', persona: '깔끔한 코드를 작성하고 기능을 구현하는 개발자. 코드 품질과 효율성을 중시합니다.', tokens: 5000 },
            'Code Reviewer': { title: 'Code Reviewer', persona: '코드 품질을 검증하고 버그를 찾아내는 리뷰어. 꼼꼼하고 건설적인 피드백을 제공합니다.', tokens: 4000 },
            'Software Test Engineer': { title: 'QA Engineer', persona: '체계적으로 테스트 케이스를 설계하고 실행하는 테스트 엔지니어.', tokens: 4000 },
            'Counselor': { title: 'Counselor', persona: '팀 갈등을 중재하고 건설적인 대화를 이끄는 상담사. 공감 능력이 뛰어납니다.', tokens: 3000 },
            'Chief Creative Officer': { title: 'CCO', persona: '창의적 방향을 설정하고 디자인 품질을 관리하는 크리에이티브 책임자.', tokens: 6000 },
            'Security Auditor': { title: 'Security Auditor', persona: '보안 취약점을 분석하고 안전한 시스템을 설계하는 보안 전문가.', tokens: 5000 },
            'Technical Writer': { title: 'Technical Writer', persona: '복잡한 기술 내용을 명확하고 읽기 쉬운 문서로 작성하는 기술 문서 전문가.', tokens: 4000 },
            'DevOps': { title: 'DevOps Engineer', persona: 'CI/CD 파이프라인을 구축하고 인프라를 자동화하는 DevOps 엔지니어.', tokens: 5000 },
            'UX Specialist': { title: 'UX Designer', persona: '사용자 중심의 인터페이스를 설계하고 사용성 테스트를 수행하는 UX 전문가.', tokens: 5000 },
            'Chief Human Resource Officer': { title: 'CHRO', persona: '인재를 발굴하고 조직 문화를 형성하는 인사 총괄 책임자.', tokens: 5000 },
        };

        const roleSelect = document.getElementById('recruit-base-role');
        if (!roleSelect || roleSelect.dataset.p2Presets) return;
        roleSelect.dataset.p2Presets = 'true';

        roleSelect.addEventListener('change', function () {
            const preset = PRESETS[roleSelect.value];
            if (!preset) return;

            const titleField = document.getElementById('recruit-title');
            const personaField = document.getElementById('recruit-persona');
            const tokenSlider = document.getElementById('recruit-token-limit');
            const tokenVal = document.getElementById('recruit-token-val');

            if (titleField && !titleField.value) titleField.value = preset.title;
            if (personaField && !personaField.value) personaField.value = preset.persona;
            if (tokenSlider) { tokenSlider.value = preset.tokens; }
            if (tokenVal) { tokenVal.textContent = preset.tokens; }
        });
    }

    // ═══════════════════════════════════
    //  #45 — 로딩 스켈레톤
    // ═══════════════════════════════════
    function injectLoadingSkeleton() {
        const canvas = document.getElementById('workforce-cards-container');
        if (!canvas || canvas.querySelector('.fleet-skeleton')) return;

        const skeleton = document.createElement('div');
        skeleton.className = 'fleet-skeleton';
        skeleton.innerHTML = `
            <div class="fleet-skel-node" style="left:30%;top:20%;width:60px;height:60px;"></div>
            <div class="fleet-skel-node" style="left:55%;top:35%;width:50px;height:50px;animation-delay:0.15s;"></div>
            <div class="fleet-skel-node" style="left:20%;top:55%;width:50px;height:50px;animation-delay:0.3s;"></div>
            <div class="fleet-skel-node" style="left:65%;top:60%;width:45px;height:45px;animation-delay:0.45s;"></div>
            <div class="fleet-skel-line" style="left:36%;top:32%;width:80px;transform:rotate(25deg);animation-delay:0.1s;"></div>
            <div class="fleet-skel-line" style="left:30%;top:45%;width:60px;transform:rotate(85deg);animation-delay:0.25s;"></div>
        `;
        canvas.appendChild(skeleton);

        // Remove skeleton when SVG loads
        const skelObs = new MutationObserver(function () {
            const svg = canvas.querySelector('svg');
            if (svg && svg.querySelectorAll('circle, rect').length > 0) {
                const skel = canvas.querySelector('.fleet-skeleton');
                if (skel) {
                    skel.style.opacity = '0';
                    setTimeout(function () { skel.remove(); }, 300);
                }
                skelObs.disconnect();
            }
        });
        skelObs.observe(canvas, { childList: true, subtree: true });
    }

    // ═══════════════════════════════════
    //  #50 — 접근성(a11y) 기본
    // ═══════════════════════════════════
    function enhanceA11y() {
        // Add ARIA labels to key interactive elements
        const ariaMap = [
            ['#btn-commit-squad', 'Fleet 구성 저장', 'button'],
            ['#btn-new-squad', '새 부서 신설', 'button'],
            ['#btn-hire-agent-btn', '직원 채용', 'button'],
            ['#workforce-cards-container', '조직도 캔버스', 'region'],
            ['#recruits-drag-pool', '채용 대기 요원 풀', 'list'],
            ['#hr-sidebar', '요원 HR 관리 패널', 'complementary'],
            ['#recruitment-modal', '직원 채용 대화상자', 'dialog'],
        ];

        ariaMap.forEach(function (item) {
            var el = document.querySelector(item[0]);
            if (el && !el.getAttribute('aria-label')) {
                el.setAttribute('aria-label', item[1]);
                if (item[2] === 'dialog') {
                    el.setAttribute('role', 'dialog');
                    el.setAttribute('aria-modal', 'true');
                } else if (item[2] !== 'button') {
                    el.setAttribute('role', item[2]);
                }
            }
        });

        // Add ARIA to drag candidates
        document.querySelectorAll('.drag-candidate-badge').forEach(function (badge) {
            badge.setAttribute('role', 'listitem');
            badge.setAttribute('aria-label', '드래그 가능: ' + (badge.dataset.role || badge.textContent.trim()));
            badge.setAttribute('tabindex', '0');
        });

        // Focus visible styles for keyboard navigation
        document.querySelectorAll('#view-workforce button, #view-workforce select, #view-workforce input').forEach(function (el) {
            if (!el.dataset.a11y) {
                el.dataset.a11y = 'true';
                el.addEventListener('focus', function () {
                    el.style.outline = '2px solid #3b82f6';
                    el.style.outlineOffset = '2px';
                });
                el.addEventListener('blur', function () {
                    el.style.outline = '';
                    el.style.outlineOffset = '';
                });
            }
        });
    }

    // ═══════════════════════════════════
    //  #43 — 반응형 레이아웃
    // ═══════════════════════════════════
    // Handled via CSS in the style injection below

    // ═══════════════════════════════════
    //  CSS Injection
    // ═══════════════════════════════════
    function injectStyles() {
        if (document.getElementById('fleet-ux-phase2-css')) return;
        var style = document.createElement('style');
        style.id = 'fleet-ux-phase2-css';
        style.textContent = `
/* ═══ #2 Active tab highlight (CSS class, not inline) ═══ */
.squad-tab-btn.fleet-tab-active {
    background: #1e293b !important;
    color: #fff !important;
    border-color: #1e293b !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(30,41,59,0.2) !important;
}

/* ═══ #7 Dirty state pulse dot ═══ */
@keyframes pulseDot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.5; transform: scale(0.8); }
}

/* ═══ #12 Node Tooltip ═══ */
.fleet-node-tooltip {
    position: fixed; z-index: 10010; display: none;
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 8px 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    font-family: 'Inter', sans-serif;
    pointer-events: none;
    animation: tooltipIn 0.15s ease;
    max-width: 200px;
}
@keyframes tooltipIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ═══ #45 Loading Skeleton ═══ */
.fleet-skeleton {
    position: absolute; inset: 0; z-index: 3;
    pointer-events: none;
    transition: opacity 0.3s;
}
.fleet-skel-node {
    position: absolute; border-radius: 50%;
    background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
    background-size: 200% 100%;
    animation: skelShimmer 1.5s ease-in-out infinite;
}
.fleet-skel-line {
    position: absolute; height: 2px;
    background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
    background-size: 200% 100%;
    animation: skelShimmer 1.5s ease-in-out infinite;
    border-radius: 1px;
}
@keyframes skelShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* ═══ #1 Tab scroll hide scrollbar ═══ */
.squad-tabs-list::-webkit-scrollbar { display: none; }

/* ═══ #43 Responsive ═══ */
@media (max-width: 1280px) {
    #view-workforce {
        flex-direction: column !important;
    }
    #view-workforce .sidebar-card {
        width: 100% !important;
        max-height: 260px;
        flex-shrink: 0 !important;
    }
    #view-workforce .glass-panel {
        min-height: 400px;
    }
}
@media (max-width: 768px) {
    #view-workforce .sidebar-card {
        max-height: 200px;
    }
    .fleet-empty-hint {
        flex-direction: column;
        gap: 6px;
    }
    .fleet-empty-arrow {
        transform: rotate(90deg);
    }
}
        `;
        document.head.appendChild(style);
    }

    // ═══════════════════════════════════
    //  Init
    // ═══════════════════════════════════
    function init() {
        injectStyles();

        var waitForEl = function (sel, cb, max) {
            max = max || 30;
            var tries = 0;
            var check = function () {
                if (document.querySelector(sel)) { cb(); return; }
                if (++tries < max) setTimeout(check, 250);
            };
            check();
        };

        waitForEl('.squad-tabs-list', function () {
            enhanceSquadTabs();
            enhanceTabScroll();
        });

        waitForEl('#btn-commit-squad', enhanceSaveButton);
        waitForEl('#view-workforce .sidebar-card .card-header', injectAgentCounter);
        waitForEl('#workforce-cards-container', function () {
            injectLoadingSkeleton();
            injectNodeTooltip();
        });
        waitForEl('#hr-sidebar', function () {
            addHRBackdrop();
            enhanceFormValidation();
        });
        waitForEl('#recruit-base-role', addRolePresets);

        // Defer a11y
        setTimeout(enhanceA11y, 2000);

        console.log('[FleetUX] Phase 2 loaded — 17 P1 improvements active');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
