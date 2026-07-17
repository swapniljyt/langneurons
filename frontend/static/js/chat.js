import { elements } from './dom.js?v=20260717l';
import { appState } from './state.js?v=20260717l';
import { sendWebSocketCommand } from './terminal.js?v=20260717l';
import { triggerSandboxNotification } from './api.js?v=20260717l';
import { setNeuronThinking, showAgentBubble } from './neurons.js?v=20260717l';

let isResizing = false;
let startX = 0;
let startWidth = 460;
let currentAssistantBubble = null;
let lastMessageTime = Date.now();
let executionTimeoutCheck = null;
let currentWaitMessageEl = null;

let isAgentThinking = false;
let currentThinkingContentEl = null;

let isResponseActive = false;
let responseAgentName = "";
let responseTextAccumulator = "";

// Track active agent speaking state and accumulative text buffers for canvas chat bubbles
let lastActiveNeuron = null;
const agentSpeechBuffers = {};

function startExecutionMonitoring() {
    stopExecutionMonitoring();
    lastMessageTime = Date.now();
    
    executionTimeoutCheck = setInterval(() => {
        const inactiveDuration = Date.now() - lastMessageTime;
        // If inactive for >= 8 seconds and we don't have a wait notice already
        if (inactiveDuration >= 8000 && !currentWaitMessageEl && currentAssistantBubble) {
            currentWaitMessageEl = document.createElement('div');
            currentWaitMessageEl.className = 'api-wait-notice my-2 p-2 bg-[#101b29]/60 border border-blue-500/20 rounded-lg text-[10.5px] font-sans text-blue-300 flex items-center gap-2 animate-pulse';
            currentWaitMessageEl.innerHTML = `
                <span class="material-symbols-outlined !text-sm animate-spin text-blue-400">sync</span>
                <span>Swarm API call is running. This may take a minute, please wait...</span>
            `;
            currentAssistantBubble.appendChild(currentWaitMessageEl);
            const list = elements.chatMessagesList;
            if (list) list.scrollTop = list.scrollHeight;
        }
    }, 2000);
}

function stopExecutionMonitoring() {
    if (executionTimeoutCheck) {
        clearInterval(executionTimeoutCheck);
        executionTimeoutCheck = null;
    }
    if (currentWaitMessageEl) {
        if (currentWaitMessageEl.parentNode) {
            currentWaitMessageEl.parentNode.removeChild(currentWaitMessageEl);
        }
        currentWaitMessageEl = null;
    }
    finalizeThinkingBlock();
}

function finalizeThinkingBlock() {
    if (currentThinkingContentEl) {
        const block = currentThinkingContentEl.closest('.chat-thinking-block');
        if (block) {
            const icon = block.querySelector('.thinking-icon');
            if (icon) {
                icon.innerText = 'cloud_done';
                icon.classList.remove('animate-pulse');
                icon.className = 'thinking-icon material-symbols-outlined !text-xs text-gray-500';
            }
            const headerText = block.querySelector('.thinking-agent-name');
            if (headerText) {
                headerText.innerText = headerText.innerText.replace('thinking...', 'thought process');
                headerText.className = 'thinking-agent-name text-gray-500';
            }
            // Auto collapse when done thinking to keep chat neat
            const content = block.querySelector('.chat-thinking-content');
            const toggleBtn = block.querySelector('.thinking-toggle');
            if (content && toggleBtn) {
                content.classList.add('hidden');
                toggleBtn.innerText = 'show';
            }
        }
        currentThinkingContentEl = null;
    }
}

/**
 * Initializes the Interactive Swarm Chat Workspace panel & resizer.
 */
export function initChatWorkspace() {
    const panel = elements.swarmChatPanel;
    const resizer = elements.chatResizer;
    const minimizeBtn = elements.chatMinimizeBtn;
    const sendBtn = elements.chatSendBtn;
    const textarea = elements.chatInputTextarea;

    if (!panel) return;

    // Restore saved panel width from localStorage (enforce 360–700px bounds)
    const savedWidth = localStorage.getItem('swarm_chat_panel_width');
    if (savedWidth) {
        panel.style.width = `${Math.max(360, Math.min(700, parseInt(savedWidth)))}px`;
    }

    // ── Resizer Dragging Handle Logic (VS Code Style) ──────────────────────
    if (resizer) {
        resizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(panel).width, 10);
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';

            const onMouseMove = (e) => {
                if (!isResizing) return;
                const deltaX = startX - e.clientX;
                // Enforce 360–700px width bounds
                const newWidth = Math.max(360, Math.min(700, startWidth + deltaX));
                panel.style.width = `${newWidth}px`;
                // DO NOT dispatch resize events — the graph must never re-layout due to sidebar resizing
            };

            const onMouseUp = () => {
                if (isResizing) {
                    isResizing = false;
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                    localStorage.setItem('swarm_chat_panel_width', parseInt(panel.style.width, 10));
                    window.removeEventListener('mousemove', onMouseMove);
                    window.removeEventListener('mouseup', onMouseUp);
                }
            };

            window.addEventListener('mousemove', onMouseMove);
            window.addEventListener('mouseup', onMouseUp);
        });
    }

    // ── Minimize / Expand Toggle ─────────────────────────────────────────────
    if (minimizeBtn) {
        minimizeBtn.addEventListener('click', () => {
            toggleChatPanel();
        });
    }

    // ── Input & Send Controls ───────────────────────────────────────────────
    if (sendBtn && textarea) {
        sendBtn.addEventListener('click', () => {
            submitUserChatMessage();
        });

        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitUserChatMessage();
            }
        });

        // Auto-expand textarea height
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = `${Math.min(140, textarea.scrollHeight)}px`;
        });
    }

    // ── Top Action Toolbar Handlers ──────────────────────────────────────────
    if (elements.chatToolbarRun) {
        elements.chatToolbarRun.onclick = () => {
            triggerSwarmExecution({ freeze: true });
        };
    }
    if (elements.chatToolbarCache) {
        elements.chatToolbarCache.onclick = () => {
            triggerSwarmExecution({ cache: true });
        };
    }
    if (elements.chatToolbarReset) {
        elements.chatToolbarReset.onclick = () => {
            triggerSwarmExecution({ freeze: true, clean_memory: true });
        };
    }
    // ── Toggle CHAT button in top toolbar ──────────────────────────────────
    if (elements.toggleChatBtn) {
        elements.toggleChatBtn.addEventListener('click', () => {
            toggleChatPanel();
        });
    }
}

/**
 * Opens or toggles the Chat Panel.
 * @param {boolean|null} show - true to show, false to hide, null to toggle
 */
export function toggleChatPanel(show = null) {
    const panel = elements.swarmChatPanel;
    if (!panel) return;

    if (show === true) {
        panel.classList.remove('hidden');
        panel.classList.add('flex');
    } else if (show === false) {
        panel.classList.add('hidden');
        panel.classList.remove('flex');
    } else {
        panel.classList.toggle('hidden');
        panel.classList.toggle('flex');
    }
    // NOTE: We intentionally do NOT dispatch a resize event here.
    // The neuron graph uses a fixed 4000×4000 virtual canvas that is
    // independent of the sidebar width — no re-layout should ever happen.
}

// Listen for WebSocket messages dispatched from sendWebSocketCommand
window.addEventListener('swarm-ws-message', (e) => {
    const data = e.detail;
    if (!data) return;

    // Reset wait timer on any live stdout or status activity
    lastMessageTime = Date.now();
    if (currentWaitMessageEl) {
        currentWaitMessageEl.remove();
        currentWaitMessageEl = null;
    }

    if (data.type === 'stdout' && data.text) {
        processChatStreamLog(data.text.trimEnd());
        
        // If the execution completes, stop the border spinners
        if (data.text.includes('Complete. Response:') || data.text.includes('exited with status')) {
            setNeuronThinking(null);
            lastActiveNeuron = null;
            stopExecutionMonitoring();
        }
    } else if (data.type === 'error' && data.text) {
        appendSystemMessage('⚠ ' + data.text.trim());
        setNeuronThinking(null);
        lastActiveNeuron = null;
        stopExecutionMonitoring();
    } else if (data.type === 'status' && data.text) {
        appendSystemMessage(data.text.trim());
        if (data.text.toLowerCase().includes('idle') || data.text.toLowerCase().includes('finished')) {
            setNeuronThinking(null);
            lastActiveNeuron = null;
            stopExecutionMonitoring();
        }
    }
});



/**
 * Triggers swarm execution with flags (--freeze, --cache, --clean-memory).
 */
export function triggerSwarmExecution(options = {}) {
    toggleChatPanel(true);
    isAgentThinking = false;
    currentThinkingContentEl = null;
    isResponseActive = false;
    responseAgentName = "";
    responseTextAccumulator = "";
    currentAssistantBubble = null;

    if (elements.chatStatusIndicator) {
        elements.chatStatusIndicator.className = 'w-2 h-2 rounded-full bg-[#00ff9d] animate-ping';
    }
    if (elements.chatStatusText) {
        elements.chatStatusText.innerText = options.clean_memory ? 'Resetting Memory..' : (options.cache ? 'Building (Cache)..' : 'Running Swarm Mode');
        elements.chatStatusText.className = 'text-[#00ff9d] font-mono';
    }

    // Send WebSocket command to server
    sendWebSocketCommand({
        type: 'run',
        session_id: appState.sessionId || 'default_session',
        freeze: options.freeze ?? true,
        cache: options.cache ?? false,
        clean_memory: options.clean_memory ?? false
    });

    appendSystemMessage(
        options.clean_memory
            ? '🗑 Memory reset requested. Re-running swarm with fresh context...'
            : (options.cache ? '⚡ Re-building swarm using cached skill prompts...' : '▶ Interactive Swarm Chat mode active (--freeze).')
    );

    // Start monitoring for slow API calls
    startExecutionMonitoring();
}

/**
 * Submits the user prompt message from the textarea input.
 */
function submitUserChatMessage() {
    const textarea = elements.chatInputTextarea;
    if (!textarea) return;

    const text = textarea.value.trim();
    if (!text) return;

    textarea.value = '';
    textarea.style.height = 'auto';
    isAgentThinking = false;
    currentThinkingContentEl = null;
    isResponseActive = false;
    responseAgentName = "";
    responseTextAccumulator = "";
    currentAssistantBubble = null;

    // Append User Bubble
    appendUserMessage(text);

    // Send input stdin to active runner process over WebSocket
    sendWebSocketCommand({
        type: 'input',
        text: text
    });

    // Prepare Assistant Bubble for streaming response
    currentAssistantBubble = createAssistantMessageBubble();

    // Start monitoring for slow API calls
    startExecutionMonitoring();
}

/**
 * Appends a User Message Bubble to the chat stream.
 */
export function appendUserMessage(text) {
    const list = elements.chatMessagesList;
    if (!list) return;

    const div = document.createElement('div');
    div.className = 'flex flex-col items-end gap-1 my-2';
    div.innerHTML = `
        <div class="flex items-center gap-1.5 text-[10px] text-gray-400 font-mono">
            <span>User Instruction</span>
            <span class="w-1.5 h-1.5 rounded-full bg-[#00ff9d]"></span>
        </div>
        <div class="bg-[#00ff9d]/15 border border-[#00ff9d]/30 text-white rounded-2xl rounded-tr-none px-3.5 py-2 max-w-[85%] text-xs leading-relaxed font-sans shadow-md shadow-[#00ff9d]/5 select-text">
            ${escapeHtml(text)}
        </div>
    `;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
}

/**
 * Appends a System Message Notice to the chat stream.
 */
export function appendSystemMessage(text) {
    const list = elements.chatMessagesList;
    if (!list) return;

    const div = document.createElement('div');
    div.className = 'my-2 p-2 bg-[#0a1b14] border border-[#00ff9d]/20 rounded-lg text-[11px] font-mono text-[#00ff9d] flex items-center gap-2';
    div.innerHTML = `
        <span class="material-symbols-outlined !text-sm">info</span>
        <span>${escapeHtml(text)}</span>
    `;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
}

/**
 * Creates a new Assistant Streaming Bubble.
 */
/**
 * Creates a new Assistant Streaming Bubble.
 */
function createAssistantMessageBubble() {
    const list = elements.chatMessagesList;
    if (!list) return null;

    const wrapper = document.createElement('div');
    wrapper.className = 'flex flex-col items-start gap-1 my-2 w-full';

    wrapper.innerHTML = `
        <div class="flex items-center gap-1.5 text-[10px] text-[#00ff9d] font-mono font-bold uppercase tracking-wider">
            <span class="material-symbols-outlined !text-xs animate-pulse">psychology</span>
            <span>Swarm Assistant</span>
        </div>
        <div class="chat-assistant-body w-full bg-[#091811] border border-[#00ff9d]/25 text-gray-200 rounded-2xl rounded-tl-none px-3.5 py-2.5 max-w-[92%] text-xs leading-relaxed font-sans shadow-md select-text space-y-1.5">
            <div class="thinking-placeholder flex items-center gap-2 text-gray-400 font-mono text-[11px] animate-pulse">
                <span class="w-1.5 h-1.5 rounded-full bg-[#00ff9d]"></span>
                <span>Swarm agents thinking...</span>
            </div>
            
            <!-- Collapsible Logs Drawer -->
            <div class="chat-pipeline-drawer my-1.5 rounded-lg border border-[#00ff9d]/15 bg-black/35 overflow-hidden">
                <button class="chat-pipeline-toggle w-full px-2.5 py-1.5 flex items-center justify-between text-[10px] font-mono font-semibold text-[#00ff9d]/80 hover:text-[#00ff9d] bg-[#0c1e15]/40 hover:bg-[#0c1e15]/70 transition-colors">
                    <span class="flex items-center gap-1.5 pointer-events-none">
                        <span class="material-symbols-outlined !text-xs">query_stats</span>
                        <span>Swarm Activity Pipeline</span>
                    </span>
                    <span class="pipeline-arrow material-symbols-outlined !text-xs transition-transform duration-200 pointer-events-none" style="transform: rotate(180deg);">expand_more</span>
                </button>
                <div class="chat-pipeline-logs max-h-[160px] overflow-y-auto p-2 space-y-1 text-[10px] font-mono leading-relaxed border-t border-[#00ff9d]/10">
                    <!-- Mid-execution telemetry/logs will go here -->
                </div>
            </div>
            
            <!-- Final Response Block -->
            <div class="chat-final-response space-y-1.5 text-xs text-gray-200 leading-relaxed font-sans font-normal selection:bg-[#00ff9d]/30 select-text">
                <!-- Final conversational responses will go here -->
            </div>
        </div>
    `;

    list.appendChild(wrapper);
    list.scrollTop = list.scrollHeight;

    const toggleBtn = wrapper.querySelector('.chat-pipeline-toggle');
    const logsContainer = wrapper.querySelector('.chat-pipeline-logs');
    const arrow = wrapper.querySelector('.pipeline-arrow');
    if (toggleBtn && logsContainer) {
        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isHidden = logsContainer.classList.contains('hidden');
            if (isHidden) {
                logsContainer.classList.remove('hidden');
                arrow.style.transform = 'rotate(180deg)';
            } else {
                logsContainer.classList.add('hidden');
                arrow.style.transform = 'rotate(0deg)';
            }
        });
    }

    return wrapper.querySelector('.chat-assistant-body');
}

/**
 * Utility to clean raw terminal log lines for ChatGPT-style rendering in the Chat UI.
 * Removes ANSI colors, Rich ASCII border boxes, leading/trailing pipe symbols, and prompt noise.
 */
function cleanLineForChat(rawLine) {
    if (!rawLine) return null;

    // 1. Strip ANSI escape codes and carriage returns
    let line = rawLine.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, '').replace(/\r/g, '').trim();
    if (!line) return null;

    // 2. Filter out CLI prompts and session noise
    if (
        line.startsWith('You:') ||
        line.includes('Chat — type \'exit\'') ||
        line.includes('Freeze Mode — loading tree') ||
        line.includes('Process exited with status code') ||
        line.includes('Execution history cleared')
    ) {
        return null;
    }

    // 3. Ignore pure border lines (e.g. ┌───────┐, └───────┘, ╭──────╮, ╰──────╯, +-------+)
    if (/^[┌└╭╰+─\-═│|║┃\s]+$/.test(line)) {
        return null;
    }

    // 4. Strip leading border markers (┌ └ ╭ ╰ + │ | ║ ┃ ─ -)
    line = line.replace(/^[┌└╭╰+│|║┃─\-\s]+/, '');

    // 5. Strip trailing border markers (┐ ┘ ╮ ╯ + │ | ║ ┃ ─ -)
    line = line.replace(/[┐┘╮╯+│|║┃─\-\s]+$/, '').trim();

    if (!line) return null;

    // 6. Check if remaining line is just leftover border dashes
    if (/^[─\-═+]+$/.test(line)) {
        return null;
    }

    return line;
}

/**
 * Appends streaming log tokens to active assistant bubble & highlights active neuron node.
 */
export function processChatStreamLog(rawLogText) {
    if (!rawLogText) return;

    // Split by newlines so multiline buffer blocks get cleaned line-by-line
    const lines = rawLogText.split('\n');

    for (let rawLine of lines) {
        const trimmedLine = rawLine.trim();
        if (!trimmedLine && !isResponseActive) continue;

        // 1. Check for thinking start: <thinking_start agent="..." />
        const startThinkingMatch = trimmedLine.match(/<thinking_start\s+agent=["']([^"']+)["']\s*\/>/);
        if (startThinkingMatch) {
            const commonName = startThinkingMatch[1];
            isAgentThinking = true;
            finalizeThinkingBlock(); // Close any old ones

            if (!currentAssistantBubble) {
                currentAssistantBubble = createAssistantMessageBubble();
            }

            // Move/re-append placeholder to bottom of chat-assistant-body to keep it running constantly
            const assistantBody = currentAssistantBubble.querySelector('.chat-assistant-body');
            const placeholder = currentAssistantBubble.querySelector('.thinking-placeholder');
            if (placeholder && assistantBody) {
                assistantBody.appendChild(placeholder);
            }

            // Switch speaker context & start border spinner
            lastActiveNeuron = commonName;
            setNeuronThinking(commonName);
            highlightActiveThinkingNeuron(commonName);
            if (!agentSpeechBuffers[commonName]) {
                agentSpeechBuffers[commonName] = "";
            }

            // Create the glassmorphic ChatGPT-style thinking box
            const block = document.createElement('div');
            block.className = 'chat-thinking-block my-2 rounded-xl border border-[#00ff9d]/15 bg-[#0a1510]/55 overflow-hidden shadow-sm w-full';
            
            const agentLabel = commonName;
            block.innerHTML = `
                <div class="chat-thinking-header px-3 py-1.5 flex items-center justify-between text-[10px] font-sans font-medium text-gray-400 bg-white/[0.02] border-b border-[#00ff9d]/10">
                    <span class="flex items-center gap-1.5">
                        <span class="thinking-icon material-symbols-outlined !text-xs animate-pulse text-[#00ff9d]">cloud</span>
                        <span class="thinking-agent-name">${escapeHtml(agentLabel)} thinking...</span>
                    </span>
                    <button class="thinking-toggle text-[9px] font-mono text-gray-500 hover:text-gray-300 transition-colors">hide</button>
                </div>
                <div class="chat-thinking-content max-h-[140px] overflow-y-auto p-3 text-[10.5px] font-sans leading-relaxed text-gray-400 italic whitespace-pre-wrap select-text"></div>
            `;

            currentAssistantBubble.appendChild(block);
            currentThinkingContentEl = block.querySelector('.chat-thinking-content');

            const toggleBtn = block.querySelector('.thinking-toggle');
            const content = block.querySelector('.chat-thinking-content');
            if (toggleBtn && content) {
                toggleBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const isCollapsed = content.classList.contains('hidden');
                    if (isCollapsed) {
                        content.classList.remove('hidden');
                        toggleBtn.innerText = 'hide';
                    } else {
                        content.classList.add('hidden');
                        toggleBtn.innerText = 'show';
                    }
                });
            }

            const list = elements.chatMessagesList;
            if (list) list.scrollTop = list.scrollHeight;
            continue;
        }

        // 2. Check for thinking token: <thinking_token>...</thinking_token>
        const tokenMatch = trimmedLine.match(/<thinking_token>([\s\S]*?)<\/thinking_token>/);
        if (tokenMatch) {
            const token = tokenMatch[1];
            if (isAgentThinking && currentThinkingContentEl) {
                currentThinkingContentEl.innerText += token;
                currentThinkingContentEl.scrollTop = currentThinkingContentEl.scrollHeight;
            }
            continue;
        }

        // 3. Check for thinking end: <thinking_end />
        if (trimmedLine === '<thinking_end />') {
            isAgentThinking = false;
            finalizeThinkingBlock();
            continue;
        }

        // 4. Check for telemetry log: <telemetry_log>...</telemetry_log>
        const telemetryMatch = trimmedLine.match(/<telemetry_log>([\s\S]*?)<\/telemetry_log>/);
        if (telemetryMatch) {
            const cleanLine = telemetryMatch[1].trim();
            if (!cleanLine) continue;

            if (!currentAssistantBubble) {
                currentAssistantBubble = createAssistantMessageBubble();
            }

            // Move/re-append placeholder to bottom of chat-assistant-body to keep it running constantly
            const assistantBody = currentAssistantBubble.querySelector('.chat-assistant-body');
            const placeholder = currentAssistantBubble.querySelector('.thinking-placeholder');
            if (placeholder && assistantBody) {
                assistantBody.appendChild(placeholder);
            }

            // Auto-detect active agent from telemetry to keep highlights in sync
            const agentMatch = cleanLine.match(/\[([a-zA-Z0-9_-]+)[^\]]*\]/) || cleanLine.match(/(?:neuron|agent)\s+([a-zA-Z0-9_-]+)/i);
            if (agentMatch && agentMatch[1]) {
                const currentNeuron = agentMatch[1];
                highlightActiveThinkingNeuron(currentNeuron);
                if (lastActiveNeuron !== currentNeuron) {
                    lastActiveNeuron = currentNeuron;
                    setNeuronThinking(currentNeuron);
                }
            }

            // Trigger sandbox file notifications
            const sandboxMatch = cleanLine.match(/(?:saved|written|created|wrote|generated|file).*?(?:sandbox[\/\\])?([a-zA-Z0-9_.-]+\.(?:py|json|js|ts|html|css|sh|md))/i);
            if (sandboxMatch && sandboxMatch[1]) {
                triggerSandboxNotification(sandboxMatch[1], `langneurons/sandbox/${sandboxMatch[1]}`);
            }

            // Append to Activity logs container
            const logsContainer = currentAssistantBubble.querySelector('.chat-pipeline-logs');
            if (logsContainer) {
                const logItem = document.createElement('div');
                logItem.className = 'py-0.5 border-b border-[#00ff9d]/5 last:border-b-0 text-[10px] text-gray-400 flex items-center gap-1.5 font-mono';
                
                if (cleanLine.includes('Activated by') || cleanLine.includes('Activated')) {
                    logItem.className += ' text-[#00ff9d] font-semibold';
                    logItem.innerHTML = `<span class="material-symbols-outlined !text-[11px] animate-pulse">login</span> <span>${escapeHtml(cleanLine)}</span>`;
                } else if (cleanLine.includes('Decision:')) {
                    logItem.className += ' text-[#4ade80]';
                    logItem.innerHTML = `<span class="material-symbols-outlined !text-[11px]">alt_route</span> <span>${escapeHtml(cleanLine)}</span>`;
                } else if (cleanLine.includes('Complete. Response:')) {
                    logItem.className += ' text-gray-500 italic';
                    logItem.innerHTML = `<span class="material-symbols-outlined !text-[11px]">done_all</span> <span>${escapeHtml(cleanLine)}</span>`;
                } else if (cleanLine.includes('Delegating to')) {
                    logItem.className += ' text-amber-400/90';
                    logItem.innerHTML = `<span class="material-symbols-outlined !text-[11px]">forward</span> <span>${escapeHtml(cleanLine)}</span>`;
                } else {
                    logItem.innerHTML = `<span>${escapeHtml(cleanLine)}</span>`;
                }
                
                logsContainer.appendChild(logItem);
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }

            const list = elements.chatMessagesList;
            if (list) list.scrollTop = list.scrollHeight;
            continue;
        }

        // 5. Check for agent final response start: <agent_response agent="...">
        const startResponseMatch = trimmedLine.match(/<agent_response\s+agent=["']([^"']+)["']\s*>/);
        if (startResponseMatch) {
            isResponseActive = true;
            responseAgentName = startResponseMatch[1];
            responseTextAccumulator = "";
            continue;
        }

        // 6. Check for agent final response end: </agent_response>
        if (trimmedLine === '</agent_response>') {
            isResponseActive = false;

            if (!currentAssistantBubble) {
                currentAssistantBubble = createAssistantMessageBubble();
            }

            // Clear placeholder if present
            const placeholder = currentAssistantBubble.querySelector('.thinking-placeholder');
            if (placeholder) {
                placeholder.remove();
            }

            // Close pipeline drawer & render clean final response
            const logsContainer = currentAssistantBubble.querySelector('.chat-pipeline-logs');
            const drawer = currentAssistantBubble.querySelector('.chat-pipeline-drawer');
            if (logsContainer && drawer) {
                logsContainer.classList.add('hidden');
                const arrow = currentAssistantBubble.querySelector('.pipeline-arrow');
                if (arrow) arrow.style.transform = 'rotate(0deg)';
            }

            const targetEl = currentAssistantBubble.querySelector('.chat-final-response') || currentAssistantBubble;
            targetEl.innerHTML = ''; // Clear placeholder if any

            renderFinalResponseMarkdown(responseTextAccumulator, targetEl);

            // Stop border spinners
            setNeuronThinking(null);
            lastActiveNeuron = null;
            stopExecutionMonitoring();

            const list = elements.chatMessagesList;
            if (list) list.scrollTop = list.scrollHeight;
            
            // Trigger telemetry update for the frontend cost tracing section
            window.dispatchEvent(new CustomEvent('update-telemetry'));
            continue;
        }

        // 7. If response text accumulator is active, collect it!
        if (isResponseActive) {
            responseTextAccumulator += rawLine + "\n";
            continue;
        }
    }
}

/**
 * Highlights the actively thinking neuron card on the Neuron Console canvas.
 */
function highlightActiveThinkingNeuron(neuronName) {
    if (elements.chatThinkingBanner) {
        elements.chatThinkingBanner.classList.remove('hidden');
    }
    if (elements.chatThinkingNeuronName) {
        elements.chatThinkingNeuronName.innerText = `${neuronName} is executing...`;
    }

    const canvas = elements.neuronNodesContainer;
    if (!canvas) return;

    const cards = canvas.querySelectorAll('[data-node-name]');
    cards.forEach(c => {
        const isTarget = c.dataset.nodeName.toLowerCase() === neuronName.toLowerCase();
        c.classList.toggle('highlighted-active', isTarget);
        c.classList.toggle('dimmed-inactive', !isTarget);
        const innerCard = c.querySelector('.neuron-card');
        if (innerCard) {
            if (isTarget) {
                innerCard.style.boxShadow = '0 0 40px #00ff9d, inset 0 0 25px rgba(0, 255, 157, 0.5)';
            } else {
                innerCard.style.boxShadow = '';
            }
        }
    });
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-extrabold text-[#00ff9d] tracking-wide">$1</strong>');
    // Italic: *text* or _text_ (avoid breaking stars in lists/tables)
    html = html.replace(/\*(.*?)\*/g, '<em class="italic text-gray-300">$1</em>');
    html = html.replace(/_(.*?)_/g, '<em class="italic text-gray-300">$1</em>');
    // Inline code: `code`
    html = html.replace(/`(.*?)`/g, '<code class="px-1.5 py-0.5 rounded bg-black/40 border border-white/10 font-mono text-[10.5px] text-[#00ff9d]">$1</code>');
    // Task lists: [ ] and [x]
    html = html.replace(/\[\s\]/g, '<span class="inline-block w-3.5 h-3.5 border border-gray-500 rounded-sm mr-1.5 align-middle"></span>');
    html = html.replace(/\[x\]/gi, '<span class="inline-block w-3.5 h-3.5 bg-[#00ff9d]/20 border border-[#00ff9d] rounded-sm mr-1.5 text-[#00ff9d] text-[10px] leading-[10px] text-center font-bold align-middle">✓</span>');
    return html;
}

function renderFinalResponseMarkdown(rawText, targetEl) {
    targetEl.innerHTML = "";
    if (!rawText) return;

    const lines = rawText.split('\n');
    let currentTable = null;
    let currentList = null;
    let currentListType = null; // 'ul' or 'ol'
    let currentCodeBlock = null;
    let currentParagraph = null;

    // Helper to close open blocks
    function closeAllExcept(type) {
        if (type !== 'table' && currentTable) {
            targetEl.appendChild(currentTable);
            currentTable = null;
        }
        if (type !== 'list' && currentList) {
            targetEl.appendChild(currentList);
            currentList = null;
            currentListType = null;
        }
        if (type !== 'code' && currentCodeBlock) {
            targetEl.appendChild(currentCodeBlock);
            currentCodeBlock = null;
        }
        if (type !== 'paragraph' && currentParagraph) {
            targetEl.appendChild(currentParagraph);
            currentParagraph = null;
        }
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // 1. Inside a code block
        if (currentCodeBlock) {
            if (trimmed.startsWith('```')) {
                closeAllExcept(null);
            } else {
                currentCodeBlock.querySelector('code').textContent += line + '\n';
            }
            continue;
        }

        // 2. Start of a code block
        if (trimmed.startsWith('```')) {
            closeAllExcept('code');
            const lang = trimmed.substring(3).trim();
            const wrapper = document.createElement('div');
            wrapper.className = 'my-3 rounded-lg border border-white/10 bg-black/40 overflow-hidden font-mono text-[11px] w-full';
            wrapper.innerHTML = `
                <div class="flex items-center justify-between px-3 py-1.5 bg-white/[0.03] border-b border-white/5 text-gray-400 text-[10px]">
                    <span>${lang || 'code'}</span>
                    <button class="copy-code-btn text-gray-500 hover:text-gray-300 transition-colors">copy</button>
                </div>
                <pre class="p-3 overflow-x-auto text-gray-300 leading-relaxed select-text"><code class="language-${lang}"></code></pre>
            `;
            const copyBtn = wrapper.querySelector('.copy-code-btn');
            const codeEl = wrapper.querySelector('code');
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(codeEl.textContent);
                copyBtn.textContent = 'copied!';
                setTimeout(() => copyBtn.textContent = 'copy', 1500);
            });
            currentCodeBlock = wrapper;
            continue;
        }

        // 3. Table parser
        if (trimmed.startsWith('|')) {
            closeAllExcept('table');
            
            // Check if it's a separator line (e.g. |---| or |:---:|)
            const isSeparator = /^\|[\s\-\|:\+]+$/.test(trimmed);
            if (isSeparator) {
                continue;
            }

            // Split columns
            const cols = line.split('|').map(c => c.trim());
            // Remove first and last empty elements caused by leading/trailing pipes
            if (line.startsWith('|')) cols.shift();
            if (line.endsWith('|')) cols.pop();

            if (!currentTable) {
                // Start new table
                currentTable = document.createElement('div');
                currentTable.className = 'overflow-x-auto my-3 rounded-lg border border-[#00ff9d]/15 bg-black/25 w-full';
                const table = document.createElement('table');
                table.className = 'min-w-full divide-y divide-[#00ff9d]/10 text-[11px] font-sans text-gray-300';
                
                const thead = document.createElement('thead');
                thead.className = 'bg-[#0c1e15]/60 text-[#00ff9d] font-semibold text-left';
                const tr = document.createElement('tr');
                cols.forEach(col => {
                    const th = document.createElement('th');
                    th.className = 'px-3 py-2 border-b border-[#00ff9d]/10 font-bold';
                    th.innerHTML = formatMarkdown(col);
                    tr.appendChild(th);
                });
                thead.appendChild(tr);
                table.appendChild(thead);

                const tbody = document.createElement('tbody');
                tbody.className = 'divide-y divide-white/5';
                table.appendChild(tbody);
                currentTable.appendChild(table);
            } else {
                // Append data row
                const tbody = currentTable.querySelector('tbody');
                if (tbody) {
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-white/[0.02] transition-colors';
                    cols.forEach(col => {
                        const td = document.createElement('td');
                        td.className = 'px-3 py-1.5 text-gray-200 border-b border-white/5';
                        td.innerHTML = formatMarkdown(col);
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                }
            }
            continue;
        }

        // 4. Headings: #, ##, ###, ####
        const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
            closeAllExcept(null);
            const level = headingMatch[1].length;
            const textContent = headingMatch[2];
            
            const heading = document.createElement('h4');
            if (level === 1) {
                heading.className = 'text-[15px] font-bold text-white tracking-wide mt-4 mb-2 pl-3 border-l-4 border-[#00ff9d] font-sans selection:bg-[#00ff9d]/30 select-text';
            } else if (level === 2) {
                heading.className = 'text-[13.5px] font-bold text-white tracking-wide mt-3.5 mb-2 pl-2.5 border-l-2.5 border-[#00ff9d]/80 font-sans selection:bg-[#00ff9d]/30 select-text';
            } else {
                heading.className = 'text-[12px] font-bold text-[#00ff9d] tracking-wide mt-3 mb-1.5 pl-2 border-l-2 border-[#00ff9d]/60 font-sans selection:bg-[#00ff9d]/30 select-text';
            }
            heading.innerHTML = formatMarkdown(textContent);
            targetEl.appendChild(heading);
            continue;
        }

        // 5. List items
        const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ');
        const isNumbered = /^\d+\.\s+/.test(trimmed);

        if (isBullet || isNumbered) {
            const listType = isBullet ? 'ul' : 'ol';
            if (currentListType !== listType) {
                closeAllExcept('list');
                currentListType = listType;
                currentList = document.createElement(listType);
                currentList.className = listType === 'ul' 
                    ? 'list-none space-y-1 my-1.5 pl-1.5'
                    : 'list-decimal space-y-1 my-1.5 pl-4 text-gray-200';
            }

            const rawContent = isBullet 
                ? trimmed.replace(/^([-*•])\s*/, '')
                : trimmed.replace(/^\d+\.\s*/, '');

            const li = document.createElement('li');
            if (listType === 'ul') {
                li.className = 'flex items-start gap-2 text-xs text-gray-200 font-sans leading-relaxed selection:bg-[#00ff9d]/30 select-text';
                li.innerHTML = `<span class="text-[#00ff9d] text-[10px] mt-0.5">•</span><span>${formatMarkdown(rawContent)}</span>`;
            } else {
                li.className = 'text-xs text-gray-200 font-sans leading-relaxed selection:bg-[#00ff9d]/30 select-text';
                li.innerHTML = formatMarkdown(rawContent);
            }
            currentList.appendChild(li);
            continue;
        }

        // 6. Blank lines
        if (!trimmed) {
            closeAllExcept(null);
            continue;
        }

        // 7. Paragraphs
        closeAllExcept('paragraph');
        if (!currentParagraph) {
            currentParagraph = document.createElement('p');
            currentParagraph.className = 'text-xs text-gray-200 leading-relaxed font-sans font-normal selection:bg-[#00ff9d]/30 select-text my-1.5';
            currentParagraph.innerHTML = formatMarkdown(line);
        } else {
            currentParagraph.innerHTML += ' ' + formatMarkdown(line);
        }
    }

    // Flush any remaining active blocks
    closeAllExcept(null);
}
