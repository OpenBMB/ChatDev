/**
 * ═══════════════════════════════════════════════════════════════
 *  ux_enhancements.js — UX 개선 Phase 2
 *  #27 호버통일  #28 로딩버튼  #22 복사피드백  #30 스크롤기억
 *  #41 브레드크럼  #25 스켈레톤  #13 CommandPalette  #26 에러바운더리
 *  #29 후속액션  #39 온보딩투어
 * ═══════════════════════════════════════════════════════════════
 */
(function () {
    'use strict';

    // ─────────────────────────────────
    //  CSS 주입
    // ─────────────────────────────────
    const css = document.createElement('style');
    css.id = 'ux-enhancements-css';
    css.textContent = `

/* ═══ #27 호버 상태 통일 ═══ */
[data-action], .clickable, button:not([disabled]), a[href], [onclick] {
    cursor: pointer;
}
button:not([disabled]):hover, .card-interactive:hover, [data-action]:hover {
    transform: translateY(-1px);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
button:not([disabled]):active, .card-interactive:active, [data-action]:active {
    transform: translateY(0) scale(0.98);
}

/* ═══ #28 로딩 버튼 상태 ═══ */
button.ux-loading {
    position: relative; pointer-events: none; opacity: 0.7;
}
button.ux-loading::after {
    content: ''; position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
    width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff; border-radius: 50%;
    animation: uxBtnSpin 0.6s linear infinite;
}
@keyframes uxBtnSpin { to { transform: translateY(-50%) rotate(360deg); } }

/* ═══ #25 스켈레톤 로딩 ═══ */
.ux-skeleton {
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: uxShimmer 1.5s ease-in-out infinite;
    border-radius: 6px;
}
.ux-skeleton-card { width: 100%; height: 120px; margin-bottom: 12px; }
.ux-skeleton-line { height: 12px; margin-bottom: 8px; }
.ux-skeleton-line:nth-child(odd) { width: 80%; }
.ux-skeleton-line:nth-child(even) { width: 60%; }
.ux-skeleton-avatar { width: 40px; height: 40px; border-radius: 50%; }
.ux-skeleton-chart { width: 100%; height: 200px; }
@keyframes uxShimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* ═══ #41 브레드크럼 ═══ */
.ux-breadcrumb {
    display: flex; align-items: center; gap: 6px; padding: 8px 16px;
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    font-size: 12px; color: #94a3b8; border-bottom: 1px solid #f1f5f9;
    background: #fafbfc;
}
.ux-breadcrumb a {
    color: #64748b; text-decoration: none; font-weight: 500;
    transition: color 0.15s;
}
.ux-breadcrumb a:hover { color: #1e293b; }
.ux-breadcrumb .ux-bc-sep { color: #cbd5e1; font-size: 10px; }
.ux-breadcrumb .ux-bc-current { color: #1e293b; font-weight: 600; }

/* ═══ #13 Command Palette ═══ */
.ux-cmd-overlay {
    position: fixed; inset: 0; z-index: 100003;
    background: rgba(15,23,42,0.5); backdrop-filter: blur(6px);
    display: flex; align-items: flex-start; justify-content: center;
    padding-top: 15vh;
    animation: uxFadeIn 0.15s ease;
}
.ux-cmd-modal {
    background: #fff; border-radius: 14px; width: 560px; max-width: 92vw;
    box-shadow: 0 20px 60px rgba(0,0,0,0.25);
    animation: uxScaleIn 0.2s cubic-bezier(0.21,1.02,0.73,1);
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    overflow: hidden;
}
.ux-cmd-input-wrap {
    display: flex; align-items: center; gap: 10px; padding: 14px 18px;
    border-bottom: 1px solid #f1f5f9;
}
.ux-cmd-input-wrap i { color: #94a3b8; font-size: 16px; }
.ux-cmd-input {
    flex: 1; border: none; outline: none; font-size: 15px; font-weight: 500;
    color: #1e293b; font-family: inherit; background: transparent;
}
.ux-cmd-input::placeholder { color: #cbd5e1; }
.ux-cmd-results {
    max-height: 340px; overflow-y: auto; padding: 8px;
}
.ux-cmd-item {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px;
    border-radius: 8px; cursor: pointer; transition: background 0.1s;
    font-size: 13px; color: #334155;
}
.ux-cmd-item:hover, .ux-cmd-item.active { background: #f1f5f9; }
.ux-cmd-item .ux-cmd-icon {
    width: 32px; height: 32px; border-radius: 8px; background: #f8fafc;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; flex-shrink: 0; border: 1px solid #e2e8f0;
}
.ux-cmd-item .ux-cmd-label { flex: 1; font-weight: 500; }
.ux-cmd-item .ux-cmd-shortcut {
    font-size: 10px; color: #94a3b8; font-family: 'JetBrains Mono', monospace;
    background: #f1f5f9; padding: 2px 6px; border-radius: 4px;
}
.ux-cmd-footer {
    display: flex; align-items: center; gap: 12px; padding: 10px 18px;
    border-top: 1px solid #f1f5f9; font-size: 11px; color: #94a3b8;
}
.ux-cmd-footer kbd {
    background: #f1f5f9; padding: 2px 6px; border-radius: 3px;
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    border: 1px solid #e2e8f0;
}

/* ═══ #39 온보딩 투어 ═══ */
.ux-tour-overlay {
    position: fixed; inset: 0; z-index: 100004;
    background: rgba(15,23,42,0.65);
    transition: opacity 0.3s;
}
.ux-tour-spotlight {
    position: fixed; z-index: 100005;
    box-shadow: 0 0 0 9999px rgba(15,23,42,0.65);
    border-radius: 8px; border: 2px solid #3b82f6;
    transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
    pointer-events: none;
}
.ux-tour-card {
    position: fixed; z-index: 100006; width: 320px;
    background: #fff; border-radius: 12px; padding: 20px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.2);
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    animation: uxScaleIn 0.25s cubic-bezier(0.21,1.02,0.73,1);
}
.ux-tour-step-num {
    font-size: 10px; font-weight: 700; color: #3b82f6;
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;
}
.ux-tour-title { font-size: 15px; font-weight: 700; color: #1e293b; margin-bottom: 6px; }
.ux-tour-desc { font-size: 12px; color: #64748b; line-height: 1.6; margin-bottom: 16px; }
.ux-tour-actions { display: flex; justify-content: space-between; align-items: center; }
.ux-tour-skip {
    background: none; border: none; color: #94a3b8; cursor: pointer;
    font-size: 12px; font-weight: 500; font-family: inherit;
}
.ux-tour-skip:hover { color: #64748b; }
.ux-tour-nav { display: flex; gap: 6px; }
.ux-tour-btn {
    padding: 7px 16px; border-radius: 6px; font-size: 12px; font-weight: 600;
    border: none; cursor: pointer; font-family: inherit; transition: all 0.15s;
}
.ux-tour-btn.prev { background: #f1f5f9; color: #64748b; }
.ux-tour-btn.prev:hover { background: #e2e8f0; }
.ux-tour-btn.next { background: #1e293b; color: #fff; }
.ux-tour-btn.next:hover { background: #334155; transform: translateY(-1px); }
.ux-tour-dots { display: flex; gap: 4px; justify-content: center; margin-top: 12px; }
.ux-tour-dot {
    width: 6px; height: 6px; border-radius: 50%; background: #e2e8f0;
    transition: all 0.2s;
}
.ux-tour-dot.active { background: #3b82f6; width: 16px; border-radius: 3px; }

/* Animations needed from phase 1 */
@keyframes uxFadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes uxScaleIn { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }
`;
    document.head.appendChild(css);


    // ─────────────────────────────────
    //  #28 로딩 버튼
    // ─────────────────────────────────
    function setButtonLoading(btn, loading = true) {
        if (!btn) return;
        if (loading) {
            btn._origText = btn.innerHTML;
            btn.classList.add('ux-loading');
            btn.disabled = true;
        } else {
            btn.classList.remove('ux-loading');
            btn.disabled = false;
            if (btn._origText) btn.innerHTML = btn._origText;
        }
    }

    // Auto-hook: buttons calling fetch
    const _origFetch = window.fetch;
    const _activeFetchBtns = new WeakSet();
    document.addEventListener('click', (e) => {
        if (!e.target || typeof e.target.closest !== 'function') return;
        const btn = e.target.closest('button[data-loading]');
        if (!btn || _activeFetchBtns.has(btn)) return;
        _activeFetchBtns.add(btn);
        setButtonLoading(btn, true);
        // Auto-reset after 15s max as safety net
        setTimeout(() => { setButtonLoading(btn, false); _activeFetchBtns.delete(btn); }, 15000);
    }, true);


    // ─────────────────────────────────
    //  #22 인라인 복사 피드백
    // ─────────────────────────────────
    function copyWithFeedback(text, triggerEl) {
        navigator.clipboard.writeText(text).then(() => {
            if (triggerEl) {
                const orig = triggerEl.innerHTML;
                triggerEl.innerHTML = '✅';
                triggerEl.style.transition = 'all 0.2s';
                setTimeout(() => { triggerEl.innerHTML = orig; }, 1500);
            }
            if (window.UX && window.UX.toast) {
                window.UX.toast('클립보드에 복사되었습니다', 'success', { duration: 2000 });
            }
        });
    }


    // ─────────────────────────────────
    //  #30 스크롤 위치 기억
    // ─────────────────────────────────
    const _scrollPositions = {};

    function saveScrollPosition(tabId) {
        const container = document.querySelector('.tab-content-pane[style*="display: flex"], .tab-content-pane:not([style*="display: none"]), [id^="tab-content-"]');
        if (container) {
            _scrollPositions[tabId] = container.scrollTop || window.scrollY;
        }
    }

    function restoreScrollPosition(tabId) {
        if (_scrollPositions[tabId] !== undefined) {
            requestAnimationFrame(() => {
                const container = document.querySelector('.tab-content-pane[style*="display: flex"], .tab-content-pane:not([style*="display: none"])');
                if (container && container.scrollTop !== undefined) {
                    container.scrollTop = _scrollPositions[tabId];
                } else {
                    window.scrollTo(0, _scrollPositions[tabId]);
                }
            });
        }
    }

    // Hook tab switching
    document.addEventListener('click', (e) => {
        if (!e.target || typeof e.target.closest !== 'function') return;
        const tabBtn = e.target.closest('.work-tab-btn, .analytics-tab-btn, .modal-tab-btn, [data-tab]');
        if (!tabBtn) return;
        // Save current tab scroll
        const activeTab = document.querySelector('.work-tab-btn.active, .analytics-tab-btn.active, [data-tab].active');
        if (activeTab) {
            const currentTabId = activeTab.dataset.tab || activeTab.id || activeTab.textContent.trim();
            saveScrollPosition(currentTabId);
        }
        // Restore target tab scroll
        const targetTabId = tabBtn.dataset.tab || tabBtn.id || tabBtn.textContent.trim();
        setTimeout(() => restoreScrollPosition(targetTabId), 100);
    }, true);


    // ─────────────────────────────────
    //  #41 브레드크럼
    // ─────────────────────────────────
    const PAGE_LABELS = {
        '/': '🏠 홈',
        '/squad': '🏠 대시보드',
        '/agents': '👥 에이전트',
        '/tools': '🛠️ 도구',
        '/bookclub': '📚 북클럽',
        '/seminar': '🎓 세미나',
        '/integrations': '🔗 연동',
        '/workflow': '⚙️ 워크플로우',
        '/dashboard': '📊 대시보드',
        '/replay': '🔄 리플레이',
    };

    function renderBreadcrumb() {
        const path = window.location.pathname;
        // Don't render on home page
        if (path === '/' || path.startsWith('/squad')) return;

        // Build crumbs
        const crumbs = [{ label: '🏠 홈', href: '/' }];
        const segments = path.split('/').filter(Boolean);

        for (let i = 0; i < segments.length; i++) {
            const partialPath = '/' + segments.slice(0, i + 1).join('/');
            const label = PAGE_LABELS[partialPath] || segments[i].charAt(0).toUpperCase() + segments[i].slice(1);
            crumbs.push({
                label,
                href: i < segments.length - 1 ? partialPath : null // last is current, no link
            });
        }

        const el = document.createElement('nav');
        el.className = 'ux-breadcrumb';
        el.setAttribute('aria-label', '브레드크럼');
        el.innerHTML = crumbs.map((c, i) => {
            if (i === crumbs.length - 1) {
                return `<span class="ux-bc-current">${c.label}</span>`;
            }
            return `<a href="${c.href}">${c.label}</a><span class="ux-bc-sep">›</span>`;
        }).join('');

        // Insert at top of body
        const firstChild = document.body.firstElementChild;
        if (firstChild) {
            document.body.insertBefore(el, firstChild);
        }
    }


    // ─────────────────────────────────
    //  #25 스켈레톤 로딩
    // ─────────────────────────────────
    function showSkeleton(container, type = 'card', count = 3) {
        if (!container) return;
        const templates = {
            card: '<div class="ux-skeleton ux-skeleton-card"></div>',
            line: '<div class="ux-skeleton ux-skeleton-line"></div>',
            avatar: '<div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;"><div class="ux-skeleton ux-skeleton-avatar"></div><div style="flex:1"><div class="ux-skeleton ux-skeleton-line" style="width:60%;margin-bottom:6px;"></div><div class="ux-skeleton ux-skeleton-line" style="width:40%;"></div></div></div>',
            chart: '<div class="ux-skeleton ux-skeleton-chart"></div>',
        };

        const html = (templates[type] || templates.card);
        container.innerHTML = Array(count).fill(html).join('');
        container.dataset.uxSkeleton = 'true';
    }

    function hideSkeleton(container) {
        if (container && container.dataset.uxSkeleton) {
            container.innerHTML = '';
            delete container.dataset.uxSkeleton;
        }
    }


    // ─────────────────────────────────
    //  #26 글로벌 에러 바운더리
    // ─────────────────────────────────
    window.addEventListener('unhandledrejection', (e) => {
        console.error('[UX] Unhandled promise rejection:', e.reason);
        const msg = e.reason?.message || String(e.reason) || '알 수 없는 오류';
        if (window.UX && window.UX.toast) {
            window.UX.toast(msg, 'error', { title: '⚠️ 네트워크 오류', duration: 6000 });
        }
    });

    window.addEventListener('error', (e) => {
        // Don't toast for script loading errors or minor issues
        if (e.filename && !e.filename.includes('localhost')) return;
        console.error('[UX] Global error:', e.message);
    });


    // ─────────────────────────────────
    //  #29 후속 액션 제안
    // ─────────────────────────────────
    function toastWithAction(message, type, opts = {}) {
        if (!window.UX) return;
        const toastEl = window.UX.toast(message, type, {
            title: opts.title,
            duration: opts.duration || 8000
        });

        if (opts.actionText && opts.actionCallback && toastEl) {
            const actionBtn = document.createElement('button');
            actionBtn.textContent = opts.actionText;
            actionBtn.style.cssText = 'margin-top:6px;padding:4px 12px;border-radius:5px;border:1px solid rgba(255,255,255,0.3);background:rgba(255,255,255,0.15);color:#fff;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;transition:all 0.15s;';
            actionBtn.addEventListener('mouseover', () => { actionBtn.style.background = 'rgba(255,255,255,0.25)'; });
            actionBtn.addEventListener('mouseout', () => { actionBtn.style.background = 'rgba(255,255,255,0.15)'; });
            actionBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                opts.actionCallback();
            });
            const body = toastEl.querySelector('.ux-toast-body');
            if (body) body.appendChild(actionBtn);
        }

        return toastEl;
    }


    // ─────────────────────────────────
    //  #13 Command Palette (Cmd+K)
    // ─────────────────────────────────
    let _cmdPaletteOpen = false;

    const CMD_ITEMS = [
        // 페이지 이동
        { icon: '🏠', label: '홈 대시보드', shortcut: '', category: 'navigate', action: () => window.location.href = '/' },
        { icon: '👥', label: '에이전트 관리', shortcut: '', category: 'navigate', action: () => window.location.href = '/agents' },
        { icon: '🛠️', label: '도구 & 학습', shortcut: '', category: 'navigate', action: () => window.location.href = '/tools' },
        { icon: '📚', label: '북클럽 스튜디오', shortcut: '', category: 'navigate', action: () => window.location.href = '/bookclub' },
        { icon: '🎓', label: '세미나', shortcut: '', category: 'navigate', action: () => window.location.href = '/seminar' },
        { icon: '🔗', label: '연동 설정', shortcut: '', category: 'navigate', action: () => window.location.href = '/integrations' },
        { icon: '⚙️', label: '워크플로우 디자이너', shortcut: '', category: 'navigate', action: () => window.location.href = '/workflow' },

        // 기능
        { icon: '📊', label: '일일 보고서 생성', shortcut: '', category: 'action', action: () => {
            fetch('/api/quality/reports/daily', { method: 'POST' })
                .then(r => r.json())
                .then(d => window.UX?.toast('보고서가 생성되었습니다', 'success', { title: '📊 보고서' }));
        }},
        { icon: '🧠', label: 'Brain 지식 내보내기', shortcut: '', category: 'action', action: () => {
            window.open('/api/quality/brain/export', '_blank');
        }},
        { icon: '🧬', label: '자기 진화 시작', shortcut: '', category: 'action', action: () => {
            fetch('/api/quality/evolve/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
                .then(r => r.json())
                .then(d => window.UX?.toast('진화 루프가 시작되었습니다', 'success', { title: '🧬 진화' }));
        }},
        { icon: '📋', label: '코드 복사', shortcut: '⌘C', category: 'action', action: () => {
            const code = document.querySelector('pre code, .code-block');
            if (code) navigator.clipboard.writeText(code.textContent);
        }},

        // 설정
        { icon: '🌙', label: '다크 모드 전환', shortcut: '', category: 'settings', action: () => {
            document.body.classList.toggle('dark-mode');
            window.UX?.toast('테마가 전환되었습니다', 'info');
        }},
    ];

    function openCommandPalette() {
        if (_cmdPaletteOpen) return;
        _cmdPaletteOpen = true;

        const overlay = document.createElement('div');
        overlay.className = 'ux-cmd-overlay';
        overlay.innerHTML = `
            <div class="ux-cmd-modal">
                <div class="ux-cmd-input-wrap">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    <input class="ux-cmd-input" placeholder="명령, 페이지, 기능 검색..." autofocus />
                    <kbd style="font-size:10px;color:#94a3b8;background:#f1f5f9;padding:2px 6px;border-radius:3px;border:1px solid #e2e8f0;">ESC</kbd>
                </div>
                <div class="ux-cmd-results"></div>
                <div class="ux-cmd-footer">
                    <span><kbd>↑↓</kbd> 탐색</span>
                    <span><kbd>↵</kbd> 실행</span>
                    <span><kbd>ESC</kbd> 닫기</span>
                </div>
            </div>
        `;

        const input = overlay.querySelector('.ux-cmd-input');
        const results = overlay.querySelector('.ux-cmd-results');
        let activeIdx = 0;

        function renderResults(query = '') {
            const q = query.toLowerCase().trim();
            const filtered = q
                ? CMD_ITEMS.filter(i => i.label.toLowerCase().includes(q) || i.category.includes(q))
                : CMD_ITEMS;

            results.innerHTML = filtered.map((item, idx) => `
                <div class="ux-cmd-item ${idx === activeIdx ? 'active' : ''}" data-idx="${idx}">
                    <div class="ux-cmd-icon">${item.icon}</div>
                    <span class="ux-cmd-label">${highlightMatch(item.label, q)}</span>
                    ${item.shortcut ? `<span class="ux-cmd-shortcut">${item.shortcut}</span>` : ''}
                </div>
            `).join('');

            // Click handlers
            results.querySelectorAll('.ux-cmd-item').forEach((el, idx) => {
                el.addEventListener('click', () => {
                    closeCmd();
                    filtered[idx].action();
                });
            });
        }

        function highlightMatch(text, query) {
            if (!query) return text;
            const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
            return text.replace(regex, '<strong style="color:#3b82f6;">$1</strong>');
        }

        function closeCmd() {
            _cmdPaletteOpen = false;
            overlay.style.animation = 'uxFadeIn 0.15s ease reverse';
            overlay.addEventListener('animationend', () => overlay.remove(), { once: true });
            setTimeout(() => overlay.remove(), 200);
        }

        input.addEventListener('input', () => {
            activeIdx = 0;
            renderResults(input.value);
        });

        input.addEventListener('keydown', (e) => {
            const items = results.querySelectorAll('.ux-cmd-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIdx = Math.min(activeIdx + 1, items.length - 1);
                items.forEach((el, i) => el.classList.toggle('active', i === activeIdx));
                items[activeIdx]?.scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIdx = Math.max(activeIdx - 1, 0);
                items.forEach((el, i) => el.classList.toggle('active', i === activeIdx));
                items[activeIdx]?.scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'Enter') {
                e.preventDefault();
                items[activeIdx]?.click();
            } else if (e.key === 'Escape') {
                closeCmd();
            }
        });

        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeCmd(); });

        document.body.appendChild(overlay);
        renderResults();
        input.focus();
    }

    // Keyboard shortcut: Cmd+K / Ctrl+K
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            if (_cmdPaletteOpen) return;
            openCommandPalette();
        }
    });


    // ─────────────────────────────────
    //  #39 온보딩 투어
    // ─────────────────────────────────
    const TOUR_STEPS = [
        {
            target: '#ucc-input, textarea#ucc-input',
            title: '🎯 CEO 명령 센터',
            desc: '여기에 명령을 입력하면 AI 에이전트 팀이 즉시 작업을 시작합니다. "쇼핑몰 웹사이트를 만들어줘" 같은 자연어 명령을 사용하세요.',
        },
        {
            target: '.work-tab-btn, #tab-btn-workforce',
            title: '👥 에이전트 워크포스',
            desc: '활성 에이전트들의 상태, 작업 분배, 실시간 진행 상황을 모니터링할 수 있습니다.',
        },
        {
            target: '#tab-btn-workflow',
            title: '⚙️ 워크플로우',
            desc: '자동화된 작업 파이프라인을 설계하고 관리합니다. 반복 작업을 워크플로우로 만들어보세요.',
        },
        {
            target: '#tab-btn-brain',
            title: '🧠 AI Brain',
            desc: '에이전트가 학습한 지식을 탐색하고 관리합니다. 지식 그래프로 연결 관계를 시각적으로 확인하세요.',
        },
        {
            target: '.analytics-tab-btn[data-tab="overview"]',
            title: '📊 분석 & 통계',
            desc: '처리량, 토큰 사용량, 에이전트 부하도 등 시스템 성과를 한눈에 파악합니다.',
        },
    ];

    let _tourActive = false;
    let _tourStep = 0;
    let _tourElements = {}; // overlay, spotlight, card

    function startTour() {
        if (_tourActive) return;
        // Check if on main page
        if (!window.location.pathname.startsWith('/squad') && window.location.pathname !== '/') return;

        _tourActive = true;
        _tourStep = 0;
        showTourStep();
    }

    function showTourStep() {
        clearTour();
        if (_tourStep >= TOUR_STEPS.length) {
            endTour();
            return;
        }

        const step = TOUR_STEPS[_tourStep];
        const target = document.querySelector(step.target);
        if (!target) {
            _tourStep++;
            showTourStep();
            return;
        }

        const rect = target.getBoundingClientRect();

        // Spotlight
        const spotlight = document.createElement('div');
        spotlight.className = 'ux-tour-spotlight';
        spotlight.style.cssText = `top:${rect.top - 4}px;left:${rect.left - 4}px;width:${rect.width + 8}px;height:${rect.height + 8}px;`;
        document.body.appendChild(spotlight);

        // Card
        const card = document.createElement('div');
        card.className = 'ux-tour-card';

        // Position card below or above target
        let cardTop = rect.bottom + 12;
        let cardLeft = rect.left;
        if (cardTop + 200 > window.innerHeight) {
            cardTop = rect.top - 200;
        }
        if (cardLeft + 320 > window.innerWidth) {
            cardLeft = window.innerWidth - 340;
        }

        card.style.cssText = `top:${cardTop}px;left:${Math.max(16, cardLeft)}px;`;
        card.innerHTML = `
            <div class="ux-tour-step-num">Step ${_tourStep + 1} / ${TOUR_STEPS.length}</div>
            <div class="ux-tour-title">${step.title}</div>
            <div class="ux-tour-desc">${step.desc}</div>
            <div class="ux-tour-actions">
                <button class="ux-tour-skip">건너뛰기</button>
                <div class="ux-tour-nav">
                    ${_tourStep > 0 ? '<button class="ux-tour-btn prev">이전</button>' : ''}
                    <button class="ux-tour-btn next">${_tourStep === TOUR_STEPS.length - 1 ? '완료 🎉' : '다음 →'}</button>
                </div>
            </div>
            <div class="ux-tour-dots">
                ${TOUR_STEPS.map((_, i) => `<div class="ux-tour-dot ${i === _tourStep ? 'active' : ''}"></div>`).join('')}
            </div>
        `;

        card.querySelector('.ux-tour-skip').addEventListener('click', endTour);
        card.querySelector('.ux-tour-btn.next').addEventListener('click', () => { _tourStep++; showTourStep(); });
        const prevBtn = card.querySelector('.ux-tour-btn.prev');
        if (prevBtn) prevBtn.addEventListener('click', () => { _tourStep--; showTourStep(); });

        document.body.appendChild(card);

        _tourElements = { spotlight, card };
    }

    function clearTour() {
        if (_tourElements.spotlight) _tourElements.spotlight.remove();
        if (_tourElements.card) _tourElements.card.remove();
        _tourElements = {};
    }

    function endTour() {
        clearTour();
        _tourActive = false;
        localStorage.setItem('ux-tour-completed', 'true');
        if (window.UX && window.UX.toast) {
            window.UX.toast('투어를 완료했습니다! Cmd+K로 언제든 기능을 검색하세요.', 'success', { title: '🎉 온보딩 완료', duration: 6000 });
        }
    }


    // ─────────────────────────────────
    //  INIT
    // ─────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        // #41 Breadcrumb
        renderBreadcrumb();

        // #39 Onboarding tour (first visit only, main page only)
        if (!localStorage.getItem('ux-tour-completed')) {
            const path = window.location.pathname;
            if (path === '/' || path.startsWith('/squad')) {
                setTimeout(startTour, 2000);
            }
        }

        console.log('✅ [UX Enhancements] loaded — Hover · LoadingBtn · Copy · Scroll · Breadcrumb · Skeleton · CmdPalette · ErrorBoundary · ActionToast · Tour');
    });


    // ─────────────────────────────────
    //  PUBLIC API
    // ─────────────────────────────────
    const _existingUX = window.UX || {};
    window.UX = Object.assign(_existingUX, {
        setButtonLoading,
        copyWithFeedback,
        saveScrollPosition,
        restoreScrollPosition,
        showSkeleton,
        hideSkeleton,
        openCommandPalette,
        toastWithAction,
        startTour,
    });

})();
