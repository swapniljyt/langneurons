import { appState } from './state.js?v=20260717l';
import { elements } from './dom.js?v=20260717l';
import { showConsoleLayout, handleLogout } from './auth.js?v=20260717l';
import { loadDocs } from './api.js?v=20260717l';
import { initSandboxIDE, loadSandboxExplorerTree } from './sandbox.js?v=20260717l';
import { createNode, drawConnections, setSelectedNode, updateNodeCardCompiled } from './canvas.js?v=20260717l';
import { saveNodeSettings, closeInspectorModal, switchInspectorTab, openInspector } from './inspector.js?v=20260717l';
import { renderNeuronTree, resetNeuronLayout } from './neurons.js?v=20260717l';
import { startSwarmRun, sendTerminalInput, clearTerminal, toggleTerminalDrawer, appendTerminalLine } from './terminal.js?v=20260717l';
import { Viewport } from './viewport.js?v=20260717l';
import { initChatWorkspace, toggleChatPanel, triggerSwarmExecution, processChatStreamLog } from './chat.js?v=20260717o';
import { appendTelemetryLog } from './telemetry.js?v=20260717o';

// Expose createNode to window scope for Playwright testing
window.createNode = createNode;

export function selectTab(tabId) {
    elements.navItems.forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    elements.tabContents.forEach(tc => {
        if (tc.id === `tab-${tabId}`) {
            tc.classList.add('active');
        } else {
            tc.classList.remove('active');
        }
    });

    // Toggle sidebar visibility depending on active tab
    if (elements.consoleLayout) {
        if (tabId === 'tryout') {
            elements.consoleLayout.classList.add('show-sidebar');
        } else {
            elements.consoleLayout.classList.remove('show-sidebar');
        }
    }

    if (tabId === 'docs') loadDocs();
    if (tabId === 'sandbox') loadSandboxExplorerTree();
    if (tabId === 'code') generateSwarmCode();

    if (tabId === 'settings') {
        if (elements.formationBriefText) {
            elements.formationBriefText.value = appState.formationBrief || '';
        }
        if (elements.sessionIdInput) {
            elements.sessionIdInput.value = appState.sessionId || 'ecommerce_build_session';
        }
        const profileSession = document.getElementById('settings-profile-session');
        if (profileSession) profileSession.textContent = appState.sessionId || 'ecommerce_build_session';

        updateThinkingModeUI();
        fetchCostTelemetry(appState.sessionId);
        fetchApiKeysStatus();
    }
}

function initViewports() {
    // Workspace Canvas Viewport
    if (elements.canvas && elements.workspaceViewport) {
        appState.workspaceViewport = new Viewport(elements.canvas, elements.workspaceViewport, {
            initialScale: 1.0,
            minScale: 0.2,
            maxScale: 3.0
        });

        if (elements.workspaceZoomIn) {
            elements.workspaceZoomIn.addEventListener('click', () => {
                const newScale = Math.min(3.0, appState.workspaceViewport.scale * 1.25);
                appState.workspaceViewport.scale = newScale;
                appState.workspaceViewport.updateTransform();
            });
        }
        if (elements.workspaceZoomOut) {
            elements.workspaceZoomOut.addEventListener('click', () => {
                const newScale = Math.max(0.2, appState.workspaceViewport.scale / 1.25);
                appState.workspaceViewport.scale = newScale;
                appState.workspaceViewport.updateTransform();
            });
        }
        if (elements.workspaceZoomReset) {
            elements.workspaceZoomReset.addEventListener('click', () => {
                appState.workspaceViewport.reset();
            });
        }
    }

    // Neuron Console Viewport — the container clips, the viewport transforms
    if (elements.neuronConsoleCanvas && elements.neuronViewport) {
        appState.neuronViewport = new Viewport(elements.neuronConsoleCanvas, elements.neuronViewport, {
            // Start zoomed in so the graph (centered at ~2000,2000) is visible
            // We'll auto-fitToScreen after first nodes load; this is just a safe default
            initialScale: 1.0,
            initialPanX: 0,
            initialPanY: 0,
            minScale: 0.08,
            maxScale: 3.0
        });

        if (elements.neuronZoomIn) {
            elements.neuronZoomIn.addEventListener('click', () => {
                const newScale = Math.min(3.0, appState.neuronViewport.scale * 1.25);
                appState.neuronViewport.scale = newScale;
                appState.neuronViewport.updateTransform();
            });
        }
        if (elements.neuronZoomOut) {
            elements.neuronZoomOut.addEventListener('click', () => {
                const newScale = Math.max(0.08, appState.neuronViewport.scale / 1.25);
                appState.neuronViewport.scale = newScale;
                appState.neuronViewport.updateTransform();
            });
        }
        if (elements.neuronZoomReset) {
            elements.neuronZoomReset.addEventListener('click', () => {
                appState.neuronViewport.reset();
            });
        }
        if (elements.neuronZoomFit) {
            elements.neuronZoomFit.addEventListener('click', () => {
                fitGraphToNodes();
            });
        }
    }
}

function initApp() {
    try {
        if (appState.token) {
            showConsoleLayout();
        } else {
            showConsoleLayout();
        }
    } catch(e) {
        console.error("Layout init warning:", e);
    }

    try {
        initViewports();
    } catch(e) {
        console.error("Viewport init warning:", e);
    }

    try {
        setupEventListeners();
    } catch(e) {
        console.error("Event listeners init warning:", e);
    }

    try {
        initChatWorkspace();
    } catch(e) {
        console.error("Chat workspace init warning:", e);
    }

    try {
        initSandboxIDE();
    } catch(e) {
        console.error("Sandbox IDE init warning:", e);
    }

    // Default route: Land directly on Neuron Console
    try {
        selectTab('neurons');
    } catch(e) {
        console.error("SelectTab init warning:", e);
    }
}

function updateCompileStrategyCards() {
    const isAuto = elements.autoTreeToggle ? elements.autoTreeToggle.checked : false;
    if (elements.modeAutoCard && elements.modeCustomCard) {
        if (isAuto) {
            elements.modeAutoCard.className = "p-4 rounded-xl bg-[#101415] border-2 border-secondary/80 flex flex-col justify-between transition-all cursor-pointer";
            elements.modeCustomCard.className = "p-4 rounded-xl bg-[#101415] border border-outline-variant/50 hover:border-secondary/40 flex flex-col justify-between transition-all cursor-pointer";
            if (elements.autoTreeParams) elements.autoTreeParams.classList.remove('hidden');
        } else {
            elements.modeAutoCard.className = "p-4 rounded-xl bg-[#101415] border border-outline-variant/50 hover:border-secondary/40 flex flex-col justify-between transition-all cursor-pointer";
            elements.modeCustomCard.className = "p-4 rounded-xl bg-[#101415] border-2 border-secondary/80 flex flex-col justify-between transition-all cursor-pointer";
            if (elements.autoTreeParams) elements.autoTreeParams.classList.add('hidden');
        }
    }
}

function setupEventListeners() {
    // Logout Button
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', handleLogout);
    }

    // Navigation Tabs
    elements.navItems.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            selectTab(tabId);
        });
    });

    const openCompileModal = () => {
        // Auto-fill empty common names for existing nodes
        appState.nodes.forEach(n => {
            if (!n.name || n.name.trim() === '') {
                n.name = n.id.replace('_', '-');
            }
        });

        // Set default auto-tree toggle state
        if (appState.nodes.length === 0) {
            if (elements.autoTreeToggle) {
                elements.autoTreeToggle.checked = true;
                elements.autoTreeToggle.disabled = true; // canvas is empty, so must auto tree
            }
        } else {
            if (elements.autoTreeToggle) {
                elements.autoTreeToggle.checked = appState.useAutoTree || false;
                elements.autoTreeToggle.disabled = false;
            }
        }
        updateCompileStrategyCards();

        // Open modal
        if (elements.compileModal) {
            elements.compileModal.classList.add('active');
        }
    };

    if (elements.compileBtn) elements.compileBtn.addEventListener('click', openCompileModal);
    if (elements.neuronCompileBtn) elements.neuronCompileBtn.addEventListener('click', openCompileModal);
    if (elements.headerCompileBtn) elements.headerCompileBtn.addEventListener('click', openCompileModal);
    if (elements.workspaceSaveCompileBtn) elements.workspaceSaveCompileBtn.addEventListener('click', () => {
        if (elements.autoTreeToggle && !elements.autoTreeToggle.disabled) {
            elements.autoTreeToggle.checked = false;
            appState.useAutoTree = false;
        }
        openCompileModal();
    });

    // Strategy Card Interactions
    if (elements.autoTreeToggle) {
        elements.autoTreeToggle.addEventListener('change', updateCompileStrategyCards);
    }
    if (elements.launchWorkspaceBtn) {
        elements.launchWorkspaceBtn.addEventListener('click', () => {
            if (elements.autoTreeToggle && !elements.autoTreeToggle.disabled) {
                elements.autoTreeToggle.checked = false;
                appState.useAutoTree = false;
            }
            closeCompileModal();
            selectTab('tryout');
        });
    }

    // ── SETTINGS SUB-NAVIGATION ─────────────────────────────────────────────
    if (elements.settingsSubnavBtns) {
        elements.settingsSubnavBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetSec = btn.getAttribute('data-sec');
                elements.settingsSubnavBtns.forEach(b => {
                    b.classList.remove('active', 'bg-secondary', 'text-on-secondary', 'shadow-sm');
                    b.classList.add('text-on-surface-variant');
                });
                btn.classList.add('active', 'bg-secondary', 'text-on-secondary', 'shadow-sm');
                btn.classList.remove('text-on-surface-variant');

                document.querySelectorAll('.settings-sec-content').forEach(sec => {
                    sec.classList.add('hidden');
                });
                const activePanel = document.getElementById(`settings-sec-${targetSec}`);
                if (activePanel) activePanel.classList.remove('hidden');
            });
        });
    }

    // ── COMPILE MODAL: Cancel buttons ────────────────────────────────────────
    const cancelBtn1 = document.getElementById('cancel-compile-btn');
    const cancelBtn2 = document.getElementById('cancel-compile-modal-btn');
    [cancelBtn1, cancelBtn2].forEach(btn => {
        if (btn) btn.addEventListener('click', closeCompileModal);
    });

    // Click outside modal closes it
    if (elements.compileModal) {
        elements.compileModal.addEventListener('click', (e) => {
            if (e.target === elements.compileModal) closeCompileModal();
        });
    }

    // ── THINKING MODE TOGGLE ─────────────────────────────────────────────────
    if (elements.thinkingModeToggle) {
        elements.thinkingModeToggle.addEventListener('click', () => {
            appState.thinkingMode = !appState.thinkingMode;
            updateThinkingModeUI();
        });
    }

    // ── START COMPILATION ────────────────────────────────────────────────────
    if (elements.startCompileBtn) {
        elements.startCompileBtn.addEventListener('click', handleStartCompile);
    }
    if (elements.startCompileBtnModal) {
        elements.startCompileBtnModal.addEventListener('click', handleStartCompile);
    }

    // Swarm execution trigger
    if (elements.runBtn) {
        elements.runBtn.addEventListener('click', () => triggerSwarmExecution({ freeze: true }));
    }
    if (elements.neuronRunBtn) {
        elements.neuronRunBtn.addEventListener('click', () => triggerSwarmExecution({ freeze: true }));
    }

    // Auto-Tree settings visibility toggle
    if (elements.autoTreeToggle) {
        elements.autoTreeToggle.addEventListener('change', () => {
            if (elements.autoTreeToggle.checked) {
                if (elements.autoTreeParams) elements.autoTreeParams.classList.remove('hidden');
            } else {
                if (elements.autoTreeParams) elements.autoTreeParams.classList.add('hidden');
            }
        });
    }

    // Terminal listeners
    if (elements.terminalSend) elements.terminalSend.addEventListener('click', sendTerminalInput);
    if (elements.terminalInput) {
        elements.terminalInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendTerminalInput();
        });
    }
    if (elements.terminalClear) elements.terminalClear.addEventListener('click', clearTerminal);
    if (elements.terminalToggle) elements.terminalToggle.addEventListener('click', toggleTerminalDrawer);

    // Inspector modal listeners
    if (elements.saveNodeBtn) elements.saveNodeBtn.addEventListener('click', saveNodeSettings);
    elements.closeModalBtns.forEach(btn => btn.addEventListener('click', closeInspectorModal));
    elements.inspectorTabs.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.inspectorTabs.forEach(i => i.classList.remove('active'));
            elements.inspectorTabContents.forEach(tc => tc.classList.remove('active'));
            btn.classList.add('active');
            const tabContentId = btn.getAttribute('data-content');
            const contentEl = document.getElementById(`inspector-${tabContentId}`);
            if (contentEl) contentEl.classList.add('active');
        });
    });

    // Copy code to clipboard
    if (elements.copyCodeBtn) {
        elements.copyCodeBtn.addEventListener('click', () => {
            const codeText = elements.swarmCodeDisplay.textContent;
            navigator.clipboard.writeText(codeText).then(() => {
                const origHTML = elements.copyCodeBtn.innerHTML;
                elements.copyCodeBtn.innerHTML = '<span class="material-symbols-outlined !text-sm">check</span> Copied!';
                setTimeout(() => { elements.copyCodeBtn.innerHTML = origHTML; }, 2000);
            }).catch(err => alert('Failed to copy code: ' + err));
        });
    }

    // Live update Swarm Code tab whenever canvas nodes/connections change
    window.addEventListener('canvas-changed', () => {
        generateSwarmCode();
    });

    // Cost Tracing & Telemetry Refresh
    if (elements.refreshCostBtn) {
        elements.refreshCostBtn.addEventListener('click', () => {
            fetchCostTelemetry(appState.sessionId);
        });
    }
    
    // Listen for custom event to trigger telemetry refresh automatically after run
    window.addEventListener('update-telemetry', () => {
        fetchCostTelemetry(appState.sessionId);
    });

    // Save API Keys & Provider Settings
    if (elements.saveApiKeysBtn) {
        elements.saveApiKeysBtn.addEventListener('click', saveApiKeys);
    }

    // Dynamic model placeholders based on selected LLM provider
    if (elements.llmProviderSelect) {
        elements.llmProviderSelect.addEventListener('change', () => {
            const provider = elements.llmProviderSelect.value;
            let defaultRouter = '';
            let defaultExec = '';
            if (provider === 'moonshot') {
                defaultRouter = 'kimi-k2.5';
                defaultExec = 'kimi-k2.5';
            } else if (provider === 'openai') {
                defaultRouter = 'gpt-4o-mini';
                defaultExec = 'gpt-4o-mini';
            } else if (provider === 'gemini') {
                defaultRouter = 'gemini-2.5-flash';
                defaultExec = 'gemini-2.5-pro';
            } else if (provider === 'openrouter') {
                defaultRouter = 'deepseek/deepseek-chat';
                defaultExec = 'deepseek/deepseek-chat';
            }
            if (elements.llmRouterModelInput) {
                elements.llmRouterModelInput.placeholder = `e.g. ${defaultRouter}`;
            }
            if (elements.llmExecModelInput) {
                elements.llmExecModelInput.placeholder = `e.g. ${defaultExec}`;
            }
        });
    }

    // Swarm Creation Mode toggle card styling
    const modeAutoCard = document.getElementById('mode-auto-card');
    const modeCustomCard = document.getElementById('mode-custom-card');
    if (elements.autoTreeToggle) {
        elements.autoTreeToggle.addEventListener('change', () => {
            appState.useAutoTree = elements.autoTreeToggle.checked;
            if (elements.autoTreeToggle.checked) {
                if (modeAutoCard) { modeAutoCard.classList.add('border-2', 'border-secondary/80'); modeAutoCard.classList.remove('border-outline-variant/50'); }
                if (modeCustomCard) { modeCustomCard.classList.remove('border-2', 'border-secondary/80'); modeCustomCard.classList.add('border-outline-variant/50'); }
            } else {
                if (modeAutoCard) { modeAutoCard.classList.remove('border-2', 'border-secondary/80'); modeAutoCard.classList.add('border-outline-variant/50'); }
                if (modeCustomCard) { modeCustomCard.classList.add('border-2', 'border-secondary/80'); modeCustomCard.classList.remove('border-outline-variant/50'); }
            }
        });
    }
}

// ── COST TRACING & TELEMETRY HANDLERS ───────────────────────────────────────

async function fetchCostTelemetry(sessionId) {
    const sid = sessionId || elements.sessionIdInput?.value || 'ecommerce_build_session';
    try {
        const resp = await fetch(`/api/cost/metrics?session_id=${encodeURIComponent(sid)}`);
        const data = await resp.json();
        if (data.success && data.summary) {
            if (elements.costTotalSpent) elements.costTotalSpent.textContent = `$${data.summary.total_cost_usd.toFixed(5)}`;
            if (elements.costTotalCalls) elements.costTotalCalls.textContent = data.summary.total_calls;
            if (elements.costTotalInput) elements.costTotalInput.textContent = data.summary.total_input_tokens.toLocaleString();
            if (elements.costTotalOutput) elements.costTotalOutput.textContent = data.summary.total_output_tokens.toLocaleString();

            // Render Agent-wise table
            if (elements.costAgentTableBody) {
                if (data.agents.length === 0) {
                    elements.costAgentTableBody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-on-surface-variant/40">No agent execution metrics recorded yet for this session.</td></tr>';
                } else {
                    elements.costAgentTableBody.innerHTML = data.agents.map(a => `
                        <tr class="hover:bg-surface-container/40">
                            <td class="p-3 font-bold text-on-surface flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-secondary"></span> ${a.agent_name}
                            </td>
                            <td class="p-3 text-center">${a.calls}</td>
                            <td class="p-3 text-right text-[#00ff9d]">$${a.cost.toFixed(5)}</td>
                            <td class="p-3 text-right text-on-surface-variant">${a.input_tokens.toLocaleString()} / ${a.output_tokens.toLocaleString()}</td>
                        </tr>
                    `).join('');
                }
            }

            // Render recent turn ledger table
            if (elements.costLogTableBody) {
                if (data.recent_turns.length === 0) {
                    elements.costLogTableBody.innerHTML = '<tr><td colspan="5" class="p-3 text-center text-on-surface-variant/40">No turn executions recorded yet.</td></tr>';
                } else {
                    elements.costLogTableBody.innerHTML = data.recent_turns.slice().reverse().map(t => `
                        <tr class="hover:bg-surface-container/30">
                            <td class="p-2 font-semibold text-on-surface">${t.agent_name || 'unknown'}</td>
                            <td class="p-2"><span class="px-1.5 py-0.5 rounded text-[8px] uppercase ${t.purpose === 'router' ? 'bg-amber-950 text-amber-400' : 'bg-emerald-950 text-[#00ff9d]'}">${t.purpose || 'exec'}</span></td>
                            <td class="p-2 text-on-surface-variant/70">${t.model_name || 'kimi-k2.5'}</td>
                            <td class="p-2 text-right">${(t.input_tokens || 0).toLocaleString()} / ${(t.output_tokens || 0).toLocaleString()}</td>
                            <td class="p-2 text-right text-[#00ff9d]">$${(t.cost || 0).toFixed(5)}</td>
                        </tr>
                    `).join('');
                }
            }
        }
    } catch (e) {
        console.error("Failed to fetch cost telemetry:", e);
    }
}

// ── CUSTOM API KEYS & PROVIDER HANDLERS ─────────────────────────────────────

async function fetchApiKeysStatus() {
    try {
        const resp = await fetch('/api/settings/keys');
        const data = await resp.json();
        if (data.success && data.keys) {
            const k = data.keys;
            if (elements.openaiKeyStatus) {
                elements.openaiKeyStatus.textContent = k.openai_configured ? `Active (${k.openai_key_masked})` : 'Unconfigured';
                elements.openaiKeyStatus.className = k.openai_configured ? 'text-[9px] font-mono text-[#00ff9d] font-semibold' : 'text-[9px] font-mono text-on-surface-variant/50';
            }
            if (elements.geminiKeyStatus) {
                elements.geminiKeyStatus.textContent = k.gemini_configured ? `Active (${k.gemini_key_masked})` : 'Unconfigured';
                elements.geminiKeyStatus.className = k.gemini_configured ? 'text-[9px] font-mono text-[#00ff9d] font-semibold' : 'text-[9px] font-mono text-on-surface-variant/50';
            }
            if (elements.moonshotKeyStatus) {
                elements.moonshotKeyStatus.textContent = k.moonshot_configured ? `Active (${k.moonshot_key_masked})` : 'Unconfigured';
                elements.moonshotKeyStatus.className = k.moonshot_configured ? 'text-[9px] font-mono text-[#00ff9d] font-semibold' : 'text-[9px] font-mono text-on-surface-variant/50';
            }
            if (elements.openrouterKeyStatus) {
                elements.openrouterKeyStatus.textContent = k.openrouter_configured ? `Active (${k.openrouter_key_masked})` : 'Unconfigured';
                elements.openrouterKeyStatus.className = k.openrouter_configured ? 'text-[9px] font-mono text-[#00ff9d] font-semibold' : 'text-[9px] font-mono text-on-surface-variant/50';
            }
            if (elements.llmProviderSelect && k.default_provider) {
                elements.llmProviderSelect.value = k.default_provider;
            }
            if (elements.llmRouterModelInput && k.router_model) {
                elements.llmRouterModelInput.value = k.router_model;
            }
            if (elements.llmExecModelInput && k.exec_model) {
                elements.llmExecModelInput.value = k.exec_model;
            }
            if (elements.redisHostInput && k.redis_host) {
                elements.redisHostInput.value = k.redis_host;
            }
            if (elements.redisPortInput && k.redis_port) {
                elements.redisPortInput.value = k.redis_port;
            }
            if (elements.redisPasswordInput && k.redis_password) {
                elements.redisPasswordInput.value = k.redis_password;
            }
            // Trigger placeholder update
            if (elements.llmProviderSelect) {
                elements.llmProviderSelect.dispatchEvent(new Event('change'));
            }
        }
    } catch (e) {
        console.error("Failed to fetch API keys status:", e);
    }
}

async function saveApiKeys() {
    const payload = {
        openai_key: elements.openaiKeyInput?.value || '',
        gemini_key: elements.geminiKeyInput?.value || '',
        moonshot_key: elements.moonshotKeyInput?.value || '',
        openrouter_key: elements.openrouterKeyInput?.value || '',
        default_provider: elements.llmProviderSelect?.value || 'moonshot',
        router_model: elements.llmRouterModelInput?.value || '',
        exec_model: elements.llmExecModelInput?.value || '',
        redis_host: elements.redisHostInput?.value || '',
        redis_port: elements.redisPortInput?.value || '',
        redis_password: elements.redisPasswordInput?.value || ''
    };

    if (elements.saveApiKeysBtn) {
        elements.saveApiKeysBtn.disabled = true;
        elements.saveApiKeysBtn.innerHTML = '<span class="material-symbols-outlined !text-sm animate-spin">autorenew</span> Saving...';
    }

    try {
        const resp = await fetch('/api/settings/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (elements.keySaveMsg) {
            elements.keySaveMsg.textContent = data.message || 'API Keys Updated!';
            setTimeout(() => { elements.keySaveMsg.textContent = ''; }, 3000);
        }
        if (elements.openaiKeyInput) elements.openaiKeyInput.value = '';
        if (elements.geminiKeyInput) elements.geminiKeyInput.value = '';
        if (elements.moonshotKeyInput) elements.moonshotKeyInput.value = '';
        if (elements.openrouterKeyInput) elements.openrouterKeyInput.value = '';

        fetchApiKeysStatus();
    } catch (e) {
        if (elements.keySaveMsg) elements.keySaveMsg.textContent = 'Error saving keys: ' + e;
    } finally {
        if (elements.saveApiKeysBtn) {
            elements.saveApiKeysBtn.disabled = false;
            elements.saveApiKeysBtn.innerHTML = '<span class="material-symbols-outlined !text-sm">key_vertical</span> Save API Keys & Provider';
        }
    }
}

// ── Compile Modal Helpers ────────────────────────────────────────────────────

function closeCompileModal() {
    if (elements.compileModal) elements.compileModal.classList.remove('active');
}

function updateThinkingModeUI() {
    const toggle = elements.thinkingModeToggle;
    const label = document.getElementById('thinking-mode-label');
    if (!toggle) return;
    if (appState.thinkingMode) {
        toggle.classList.add('on');
        if (label) { label.textContent = 'ON'; label.style.color = '#00e598'; }
    } else {
        toggle.classList.remove('on');
        if (label) { label.textContent = 'OFF'; label.style.color = '#89938c'; }
    }
}

async function handleStartCompile() {
    const brief = elements.formationBriefText ? elements.formationBriefText.value.trim() : '';
    if (!brief) {
        elements.formationBriefText.style.borderColor = '#f87171';
        elements.formationBriefText.focus();
        return;
    }
    elements.formationBriefText.style.borderColor = '';

    const sessionId = (elements.sessionIdInput ? elements.sessionIdInput.value.trim() : '') || 'ecommerce_build_session';

    // Persist to state
    appState.formationBrief = brief;
    appState.sessionId = sessionId;
    appState.useAutoTree = elements.autoTreeToggle ? elements.autoTreeToggle.checked : false;
    appState.autoNeuronCount = elements.autoNeuronCount ? parseInt(elements.autoNeuronCount.value) || 15 : 15;
    appState.autoBranchFactor = elements.autoBranchFactor ? parseInt(elements.autoBranchFactor.value) || 2 : 2;

    // Update canvas header bar status
    const badge = document.getElementById('canvas-session-badge');
    const preview = document.getElementById('canvas-brief-preview');
    if (badge) badge.textContent = `⬡ ${sessionId}`;
    if (preview) preview.textContent = brief.substring(0, 80) + (brief.length > 80 ? '…' : '');

    closeCompileModal();

    // Immediately switch tab to Neuron Console to view tree generation live
    selectTab('neurons');

    // Generate Python script from canvas/auto tree state
    const scriptContent = generatePythonScript(
        brief, 
        sessionId, 
        appState.thinkingMode, 
        appState.useAutoTree, 
        appState.autoNeuronCount, 
        appState.autoBranchFactor
    );

    // Mark nodes as compiling (if manual tree)
    if (!appState.useAutoTree) {
        appState.nodes.forEach(n => {
            const el = document.getElementById(n.id);
            if (el) el.classList.add('compiling');
        });
    }

    // Update button states
    if (elements.startCompileBtn) {
        elements.startCompileBtn.disabled = true;
        elements.startCompileBtn.innerHTML = '<span class="material-symbols-outlined !text-sm animate-spin">autorenew</span> Compiling Swarm...';
    }
    if (elements.compileBtn) {
        elements.compileBtn.disabled = true;
        elements.compileBtn.innerHTML = '<span class="material-symbols-outlined !text-[12px] animate-spin">autorenew</span> Compiling...';
    }
    if (elements.neuronCompileBtn) {
        elements.neuronCompileBtn.disabled = true;
        elements.neuronCompileBtn.innerHTML = '<span class="material-symbols-outlined !text-[12px] animate-spin">autorenew</span> Compiling...';
    }
    if (elements.runBtn) elements.runBtn.disabled = true;
    if (elements.neuronRunBtn) elements.neuronRunBtn.disabled = true;

    // Reset graph layout so the new swarm tree is positioned fresh
    resetNeuronLayout();

    // Setup telemetry panel
    if (elements.telemetryCommunicationLogs) elements.telemetryCommunicationLogs.innerHTML = '';
    startTelemetryPolling(sessionId);
    appendTelemetryLog('▶ Initializing swarm tree compilation...', 'status');

    appendTerminalLine('', 'status');
    appendTerminalLine('▶ Sending swarm tree to compiler...', 'status');
    appendTerminalLine(`  Session: ${sessionId} | Thinking: ${appState.thinkingMode ? 'ON' : 'OFF'}`, 'info');

    try {
        // POST script to server → get back script_path for WS runner
        const resp = await fetch('/api/swarm/compile-run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                script_content: scriptContent,
                session_id: sessionId,
                thinking_mode: appState.thinkingMode
            })
        });
        const data = await resp.json();

        if (!data.success) {
            appendTerminalLine(`✗ Compile-run setup failed: ${data.detail || 'Unknown error'}`, 'error');
            resetCompileBtn();
            return;
        }

        appState.activeScriptPath = data.script_path;
        appendTerminalLine(`  Script written → ${data.script_path}`, 'info');
        appendTerminalLine('▶ Spawning swarm subprocess...', 'status');

        // Connect WebSocket and run
        runViaWebSocket(data.script_path, sessionId);

    } catch (err) {
        appendTerminalLine(`✗ Network error: ${err.message}`, 'error');
        resetCompileBtn();
    }
}

function resetCompileBtn() {
    if (elements.startCompileBtn) {
        elements.startCompileBtn.disabled = false;
        elements.startCompileBtn.innerHTML = '<span class="material-symbols-outlined !text-sm">rocket_launch</span> Compile Swarm';
    }
    if (elements.compileBtn) {
        elements.compileBtn.disabled = false;
        elements.compileBtn.innerHTML = '<span class="material-symbols-outlined !text-[12px]">build</span> COMPILE';
    }
    if (elements.neuronCompileBtn) {
        elements.neuronCompileBtn.disabled = false;
        elements.neuronCompileBtn.innerHTML = '<span class="material-symbols-outlined !text-[12px]">build</span> COMPILE';
    }
    appState.nodes.forEach(n => {
        const el = document.getElementById(n.id);
        if (el) el.classList.remove('compiling');
    });
}

function runViaWebSocket(scriptPath, sessionId) {
    const ws = new WebSocket(`ws://${window.location.host}/ws/logs`);
    appState.ws = ws;

    ws.onopen = () => {
        ws.send(JSON.stringify({
            type: 'compile',
            script_path: scriptPath,
            session_id: sessionId
        }));
    };

    ws.onmessage = (ev) => {
        try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'stdout') {
                appendTerminalLine(msg.text.trimEnd(), 'stdout');
                appendTelemetryLog(msg.text.trimEnd(), 'info');
                processChatStreamLog(msg.text);
            } else if (msg.type === 'error') {
                appendTerminalLine(msg.text, 'error');
                appendTelemetryLog(msg.text, 'error');
            } else if (msg.type === 'status') {
                appendTerminalLine(msg.text, 'status');
                appendTelemetryLog(msg.text, 'status');
                if (msg.text.includes('exited') && msg.text.includes('status code 0')) {
                    onCompileSuccess(sessionId);
                    window.dispatchEvent(new CustomEvent('update-telemetry'));
                } else if (msg.text.includes('exited')) {
                    if (msg.text.includes('status code -15') || msg.text.includes('status code -9')) {
                        appendTerminalLine('ℹ Previous process restarted for new compilation.', 'info');
                    } else {
                        appendTerminalLine('✗ Compilation ended with errors. Check logs above.', 'error');
                        appendTelemetryLog('✗ Compilation ended with errors.', 'error');
                        stopTelemetryPolling();
                        if (elements.neuronStatusBadge) {
                            elements.neuronStatusBadge.textContent = 'ERROR';
                            elements.neuronStatusBadge.className = 'px-3 py-1 bg-red-950 text-red-400 border border-red-500/30 rounded-full text-[10px] font-mono font-semibold tracking-wider';
                        }
                        resetCompileBtn();
                    }
                }
            } else if (msg.type === 'compile_done') {
                onCompileSuccess(sessionId);
            }
        } catch (e) {
            appendTerminalLine(ev.data, 'stdout');
            appendTelemetryLog(ev.data, 'info');
        }
    };

    ws.onerror = (err) => {
        appendTerminalLine('WebSocket error — check server logs.', 'error');
        appendTelemetryLog('WebSocket error — check server logs.', 'error');
        stopTelemetryPolling();
        resetCompileBtn();
    };

    ws.onclose = () => {
        stopTelemetryPolling();
        if (appState.compiled) {
            appendTerminalLine('── Session stream closed ──', 'status');
            appendTelemetryLog('── Session stream closed ──', 'status');
        }
    };
}

async function onCompileSuccess(sessionId) {
    appState.compiled = true;
    stopTelemetryPolling();
    appendTerminalLine('', 'status');
    appendTerminalLine('✓ Compilation complete! Fetching compiled agent attributes...', 'status');
    appendTelemetryLog('✓ Compilation complete! Loading swarm hierarchy...', 'status');

    // Try to fetch compiled node data from /api/swarm/compile-results
    try {
        const resp = await fetch(`/api/swarm/compile-results?session_id=${encodeURIComponent(sessionId)}`);
        const data = await resp.json();
        if (data.success && data.nodes) {
            data.nodes.forEach(compiledNode => {
                const node = appState.nodes.find(n => 
                    (n.name && n.name === compiledNode.common_name) || 
                    n.id === compiledNode.common_name
                );
                if (node) {
                    node.system_prompt = compiledNode.system_prompt || '';
                    node.skills = compiledNode.skills || [];
                    node.role = compiledNode.dynamic_name || node.role;
                    node.modular_prompt = compiledNode.modular_prompt || null;
                    node.model = compiledNode.model || node.model || 'moonshot/kimi-k2.5';
                    node.tools = Array.isArray(compiledNode.tools) ? compiledNode.tools.join(', ') : (compiledNode.tools || node.tools || '');
                    updateNodeCardCompiled(node.id);
                }
            });
            updateTelemetryUI(data.nodes);
            appendTerminalLine(`✓ ${data.nodes.length} agent node(s) loaded with compiled attributes.`, 'status');
            appendTelemetryLog(`✓ ${data.nodes.length} agent node(s) defined and mapped to brain.`, 'status');
        } else {
            updateTelemetryUI([]);
        }
    } catch (e) {
        appendTerminalLine('ℹ Could not fetch compiled attributes (non-fatal).', 'info');
        appendTelemetryLog('ℹ Could not fetch compiled attributes.', 'info');
        // Still mark nodes as compiled visually
        appState.nodes.forEach(n => updateNodeCardCompiled(n.id));
        updateTelemetryUI([]);
    }

    if (elements.runBtn) elements.runBtn.disabled = false;
    if (elements.neuronRunBtn) elements.neuronRunBtn.disabled = false;
    resetCompileBtn();
    generateSwarmCode();
    appendTerminalLine('▶ Ready to Run Swarm.', 'status');
    appendTelemetryLog('▶ Swarm brain is ready to run.', 'status');
    selectTab('neurons');
}

// ── Python Script Generator ──────────────────────────────────────────────────

export function generatePythonScript(brief, sessionId, thinkingMode, useAutoTree = false, autoNeuronCount = 15, autoBranchFactor = 2) {
    const escapedBrief = brief.replace(/\\/g, '\\\\').replace(/"""/g, '\\"\\"\\"');
    const escapedSession = sessionId.replace(/"/g, '\\"');
    const thinkingStr = thinkingMode ? 'True' : 'False';

    let code = `import asyncio\nimport argparse\nfrom core import run_swarm, AgentNode\n\n`;
    code += `SESSION_NAME = "${escapedSession}"\n\n`;
    code += `FORMATION_BRIEF = """\\\n${escapedBrief}"""\n\n`;

    code += `def build_swarm_tree() -> AgentNode:\n`;
    code += `    """\n    Define the agent hierarchy for your swarm.\n    """\n\n`;

    if (useAutoTree || appState.nodes.length === 0) {
        code += `    return None\n\n`;
    } else {
        const idToVar = {};
        const varNamesUsed = new Set();

        function getPythonVarName(name) {
            let base = name ? name.toLowerCase().replace(/[^a-z0-9_]/g, '_') : 'agent';
            if (!/^[a-z_]/.test(base)) base = '_' + base;
            let varName = base;
            let counter = 1;
            while (varNamesUsed.has(varName)) varName = `${base}_${counter++}`;
            varNamesUsed.add(varName);
            return varName;
        }

        code += `    # ── Node Declarations ───────────────────────────────────────────────────\n`;
        appState.nodes.forEach(node => {
            const varName = getPythonVarName(node.name || node.id);
            idToVar[node.id] = varName;
            let nodeInit = `AgentNode("${node.name || node.id}", session_id=SESSION_NAME)`;
            if (node.type) nodeInit += `.set_agent_type("${node.type}")`;
            if (node.behavior) {
                const esc = node.behavior.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
                nodeInit += `.set_behavior_hint("${esc}")`;
            }
            code += `    ${varName} = ${nodeInit}\n`;
        });

        code += `\n    # ── Node Connections ───────────────────────────────────────────────────\n`;
        appState.connections.forEach(conn => {
            const parentVar = idToVar[conn.from_node];
            const childVar = idToVar[conn.to_node];
            if (parentVar && childVar) code += `    ${parentVar}.add_child(${childVar})\n`;
        });

        const rootNodes = appState.nodes.filter(n => !appState.connections.some(c => c.to_node === n.id));
        let rootVar = rootNodes.length > 0 ? idToVar[rootNodes[0].id] : (appState.nodes.length > 0 ? idToVar[appState.nodes[0].id] : 'None');
        code += `\n    return ${rootVar}\n\n`;
    }

    code += `async def main():\n`;
    code += `    parser = argparse.ArgumentParser(description="LangNeurons — Universal Swarm Runner")\n`;
    code += `    parser.add_argument("--freeze", action="store_true", default=False)\n`;
    code += `    parser.add_argument("--clean-memory", action="store_true", default=False)\n`;
    code += `    parser.add_argument("--cache", action="store_true", default=False)\n`;
    code += `    args = parser.parse_args()\n\n`;
    code += `    custom_root = build_swarm_tree()\n\n`;
    code += `    await run_swarm(\n`;
    code += `        prompt=FORMATION_BRIEF,\n`;
    code += `        freeze_mode=args.freeze,\n`;
    code += `        custom_tree=custom_root,\n`;
    code += `        session_id=SESSION_NAME,\n`;
    code += `        clean_memory=args.clean_memory,\n`;
    code += `        thinking_mode=${thinkingStr},\n`;
    code += `        use_cache=args.cache,\n`;
    if (useAutoTree || appState.nodes.length === 0) {
        code += `        neuron_count=${autoNeuronCount},\n`;
        code += `        branching_factor=${autoBranchFactor},\n`;
    }
    code += `    )\n\n`;
    code += `if __name__ == "__main__":\n`;
    code += `    try:\n        asyncio.run(main())\n    except KeyboardInterrupt:\n        pass\n`;

    return code;
}

// ── Swarm Code Tab Live Display ──────────────────────────────────────────────

export function generateSwarmCode() {
    if (!elements.swarmCodeDisplay) return;
    // Use stored brief or a clear placeholder so code tab is always readable
    const brief = appState.formationBrief ||
        'Phase 1 — Architecture: Design the full system architecture...\n' +
        'Phase 2 — Backend: Build REST APIs...\n' +
        'Phase 3 — Frontend: Develop interactive user interface...';
    const sessionId = appState.sessionId || 'ecommerce_build_session';
    const thinkingMode = appState.thinkingMode !== false;
    elements.swarmCodeDisplay.textContent = generatePythonScript(
        brief,
        sessionId,
        thinkingMode,
        appState.useAutoTree,
        appState.autoNeuronCount,
        appState.autoBranchFactor
    );
}




export function updateTelemetryUI(nodes) {
    const statusBadge = elements.neuronStatusBadge;
    if (statusBadge) {
        statusBadge.textContent = appState.compiled ? 'READY TO RUN' : 'COMPILING...';
        statusBadge.className = appState.compiled 
            ? 'px-3 py-1 bg-emerald-950 text-[#00ff9d] border border-[#00ff9d]/30 rounded-full text-[10px] font-mono font-semibold tracking-wider animate-pulse shadow-[0_0_8px_rgba(0,255,157,0.2)]'
            : 'px-3 py-1 bg-amber-950 text-amber-400 border border-amber-500/30 rounded-full text-[10px] font-mono font-semibold tracking-wider animate-pulse';
    }

    if (elements.telemetrySessionId) elements.telemetrySessionId.textContent = appState.sessionId;
    
    const expectedCount = appState.useAutoTree ? appState.autoNeuronCount : appState.nodes.length;
    // Count how many nodes have their prompts populated (fully compiled)
    const compiledCount = nodes.filter(n => n.system_prompt && n.system_prompt.trim() !== '').length;
    
    if (elements.telemetryNeuronsCount) elements.telemetryNeuronsCount.textContent = `${compiledCount} / ${expectedCount}`;
    if (elements.telemetryBranchFactor) elements.telemetryBranchFactor.textContent = appState.useAutoTree ? appState.autoBranchFactor : 'N/A';

    const progressPercent = appState.compiled 
        ? 100 
        : Math.min(95, Math.round((compiledCount / Math.max(1, expectedCount)) * 90) + 5);
    
    if (elements.telemetryProgressBar) {
        elements.telemetryProgressBar.style.width = `${progressPercent}%`;
    }
    if (elements.telemetryProgressLabel) {
        elements.telemetryProgressLabel.textContent = appState.compiled 
            ? 'Compilation Complete' 
            : `Generating Agents (${progressPercent}%)`;
    }

    const activeNodes = nodes.filter(n => n.activate_flag === true || n.activate_flag === 'true');

    if (elements.telemetryActiveNeuronsList) {
        elements.telemetryActiveNeuronsList.innerHTML = activeNodes.map(n => {
            const isCompiled = n.system_prompt && n.system_prompt.trim() !== '';
            return `
                <div class="flex items-center justify-between p-2 bg-[#0b0f10] border border-outline-variant/30 rounded-lg text-[10px] font-mono">
                    <div class="truncate pr-2">
                        <span class="text-[#00ff9d] font-bold">${n.common_name}</span>
                        <span class="text-on-surface-variant/70"> → ${n.dynamic_name || 'Assigning...'}</span>
                    </div>
                    <div class="flex items-center gap-1.5 shrink-0">
                        <span class="px-1.5 py-0.5 bg-surface-container-high rounded text-[8px] uppercase text-[#00ff9d]">${n.agent_type || 'worker'}</span>
                        <span class="h-1.5 w-1.5 rounded-full ${isCompiled ? 'bg-[#00ff9d] animate-ping' : 'bg-amber-500 animate-pulse'}"></span>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderNeuronTree(activeNodes);
}

let compilePollInterval = null;
let hasAutoFittedGraph = false;  // True after the initial fit-to-screen on first render

export function fitGraphToNodes(targetScale = null) {
    if (!appState.neuronViewport) return;
    const canvas = elements.neuronNodesContainer;
    const cards = canvas ? canvas.querySelectorAll('[data-node-name]') : [];
    if (cards.length === 0) {
        appState.neuronViewport.fitToScreen(4000, 4000);
        return;
    }
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    cards.forEach(c => {
        const x = parseFloat(c.style.left) || 0;
        const y = parseFloat(c.style.top) || 0;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
    });
    const padding = 250;
    const treeWidth  = (maxX - minX) + padding;
    const treeHeight = (maxY - minY) + padding;
    const containerRect = elements.neuronConsoleCanvas.getBoundingClientRect();
    const containerW = containerRect.width  || 800;
    const containerH = containerRect.height || 600;
    
    let fitScale = targetScale;
    if (fitScale === null) {
        const scaleX = (containerW - 80) / Math.max(1, treeWidth);
        const scaleY = (containerH - 80) / Math.max(1, treeHeight);
        // Medium zoom clamp between 0.55 and 0.8 so first node is clearly visible
        fitScale = Math.max(0.55, Math.min(0.8, Math.min(scaleX, scaleY)));
    }
    
    appState.neuronViewport.scale  = fitScale;
    appState.neuronViewport.panX   = (containerW - treeWidth  * fitScale) / 2 - minX * fitScale;
    appState.neuronViewport.panY   = (containerH - treeHeight * fitScale) / 2 - minY * fitScale;
    appState.neuronViewport.updateTransform();
}


export function startTelemetryPolling(sessionId) {
    if (compilePollInterval) clearInterval(compilePollInterval);
    appState.compilingTelemetryActive = true;
    appState.compiled = false;
    hasAutoFittedGraph = false;  // Reset so next compilation auto-fits again
    
    // Initial display
    updateTelemetryUI([]);

    compilePollInterval = setInterval(async () => {
        if (!appState.compilingTelemetryActive) {
            clearInterval(compilePollInterval);
            return;
        }
        try {
            const resp = await fetch(`/api/swarm/compile-results?session_id=${encodeURIComponent(sessionId)}`);
            const data = await resp.json();
            if (data.success && data.nodes) {
                updateTelemetryUI(data.nodes);

                // Auto fit-to-screen exactly once when nodes first appear
                if (!hasAutoFittedGraph && data.nodes.length > 0 && appState.neuronViewport) {
                    hasAutoFittedGraph = true;
                    setTimeout(() => {
                        fitGraphToNodes();
                    }, 400);
                }
            }
        } catch (e) {
            console.error("Telemetry fetch error:", e);
        }
    }, 1200);
}

export function stopTelemetryPolling() {
    appState.compilingTelemetryActive = false;
    if (compilePollInterval) {
        clearInterval(compilePollInterval);
        compilePollInterval = null;
    }
}

// Bootstrap Application Startup
initApp();
