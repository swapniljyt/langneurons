import { appState } from './state.js?v=20260717j';
import { elements } from './dom.js?v=20260717j';
import { appendTelemetryLog } from './telemetry.js?v=20260717j';

export function startSwarmRun() {
    // Clear terminal screen
    elements.terminalOutput.innerHTML = '<div class="system-line">🔌 Socket initialized. Starting swarm run...</div>';
    
    if (elements.neuronStatusBadge) {
        elements.neuronStatusBadge.textContent = 'RUNNING';
        elements.neuronStatusBadge.className = 'px-3 py-1 bg-emerald-950 text-[#00ff9d] border border-[#00ff9d]/30 rounded-full text-[10px] font-mono font-semibold tracking-wider shadow-[0_0_8px_rgba(0,255,157,0.4)]';
    }
    appendTelemetryLog('▶ Spawning Swarm Orchestration Run...', 'status');

    // Connect to WebSockets
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws/logs`;
    
    if (appState.ws) {
        try { appState.ws.close(); } catch(e) {}
    }

    appState.ws = new WebSocket(wsUrl);

    appState.ws.onopen = () => {
        // Send run instruction using compiled script path if available
        appState.ws.send(JSON.stringify({
            type: 'run',
            session_id: appState.sessionId || 'ecommerce_build_session',
            script_path: appState.activeScriptPath || null
        }));

        elements.terminalInput.disabled = false;
        elements.terminalSend.disabled = false;
        elements.terminalDrawer.classList.remove('collapsed');
        elements.terminalToggle.querySelector('span').textContent = 'keyboard_arrow_down';
    };

    appState.ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            handleIncomingWebSocketMessage(payload);
        } catch(e) { /* ignore parse errors */ }
    };

    appState.ws.onclose = () => {
        const line = document.createElement('div');
        line.className = 'system-line';
        line.textContent = '🔌 Connection closed.';
        if (elements.terminalOutput) {
            elements.terminalOutput.appendChild(line);
        }
        if (elements.terminalInput) elements.terminalInput.disabled = true;
        if (elements.terminalSend) elements.terminalSend.disabled = true;

        if (elements.neuronStatusBadge) {
            elements.neuronStatusBadge.textContent = appState.compiled ? 'READY TO RUN' : 'IDLE';
            elements.neuronStatusBadge.className = appState.compiled
                ? 'px-3 py-1 bg-emerald-950 text-[#00ff9d] border border-[#00ff9d]/30 rounded-full text-[10px] font-mono font-semibold tracking-wider shadow-[0_0_8px_rgba(0,255,157,0.2)]'
                : 'px-3 py-1 bg-zinc-900 text-zinc-400 border border-zinc-500/20 rounded-full text-[10px] font-mono font-semibold tracking-wider';
        }
        appendTelemetryLog('🔌 Swarm run execution closed.', 'status');
    };
}


export function sendTerminalInput() {
    const text = elements.terminalInput.value.trim();
    if (!text || !appState.ws) return;

    // Log the user's input line
    const lineEl = document.createElement('div');
    lineEl.className = 'stdout-line';
    lineEl.innerHTML = `<span style="color:#06b6d4; font-weight:bold;">&gt; ${text}</span>`;
    if (elements.terminalOutput) {
        elements.terminalOutput.appendChild(lineEl);
        elements.terminalOutput.scrollTop = elements.terminalOutput.scrollHeight;
    }

    // Send payload
    appState.ws.send(JSON.stringify({
        type: 'input',
        text: text
    }));

    elements.terminalInput.value = '';
}

/**
 * Send a raw JSON command payload over the active WebSocket connection.
 * Used by chat.js to trigger swarm run modes and send chat input to the backend.
 */
export function sendWebSocketCommand(payload) {
    if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
        // If no open WebSocket, open one first then send
        const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProto}//${window.location.host}/ws/logs`;
        appState.ws = new WebSocket(wsUrl);
        appState.ws.onopen = () => {
            appState.ws.send(JSON.stringify(payload));
        };
        appState.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleIncomingWebSocketMessage(data);
            } catch(e) {}
        };
        return;
    }
    appState.ws.send(JSON.stringify(payload));
}

export function handleIncomingWebSocketMessage(payload) {
    if (!payload) return;
    if (elements.terminalOutput) {
        let lineEl = document.createElement('div');
        if (payload.type === 'stdout') {
            lineEl.className = 'stdout-line';
            lineEl.innerHTML = formatAnsiHtml(payload.text);
            appendTelemetryLog(payload.text.trimEnd(), 'info');
        } else if (payload.type === 'error') {
            lineEl.className = 'error-line';
            lineEl.style.color = '#f87171';
            lineEl.textContent = payload.text;
            appendTelemetryLog(payload.text, 'error');
        } else if (payload.type === 'status') {
            lineEl.className = 'system-line';
            lineEl.textContent = payload.text;
            appendTelemetryLog(payload.text, 'status');
        }
        elements.terminalOutput.appendChild(lineEl);
        elements.terminalOutput.scrollTop = elements.terminalOutput.scrollHeight;
    }
    window.dispatchEvent(new CustomEvent('swarm-ws-message', { detail: payload }));
}


export function clearTerminal() {
    elements.terminalOutput.innerHTML = '<div class="system-line">Console cleared.</div>';
}

export function toggleTerminalDrawer() {
    const isCollapsed = elements.terminalDrawer.classList.toggle('collapsed');
    const icon = elements.terminalToggle.querySelector('span');
    if (icon) {
        icon.textContent = isCollapsed ? 'keyboard_arrow_down' : 'keyboard_arrow_up';
    }
}

// Helper: append a line to the terminal output
export function appendTerminalLine(text, type = 'stdout') {
    if (!elements.terminalOutput) return;
    const lineEl = document.createElement('div');
    if (type === 'stdout') {
        lineEl.className = 'stdout-line';
        lineEl.innerHTML = formatAnsiHtml(text);
    } else if (type === 'error') {
        lineEl.className = 'error-line';
        lineEl.style.color = '#f87171';
        lineEl.textContent = text;
    } else if (type === 'info') {
        lineEl.className = 'system-line';
        lineEl.style.color = '#89938c';
        lineEl.style.fontStyle = 'italic';
        lineEl.textContent = text;
    } else {
        lineEl.className = 'system-line';
        lineEl.textContent = text;
    }
    elements.terminalOutput.appendChild(lineEl);
    elements.terminalOutput.scrollTop = elements.terminalOutput.scrollHeight;
}


// Ansi escapes helper to CSS formatting
export function formatAnsiHtml(text) {
    // Regex for colors and formatting
    return text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\033\[1;36m/g, '<span style="color:#06b6d4; font-weight:bold;">')
        .replace(/\033\[0m/g, '</span>')
        .replace(/\033\[0;32m/g, '<span style="color:#10b981;">')
        .replace(/\033\[1;33m/g, '<span style="color:#f97316; font-weight:bold;">')
        .replace(/\033\[0;31m/g, '<span style="color:#ef4444;">')
        .replace(/\[dim\]/g, '<span style="opacity:0.6;">')
        .replace(/\[\/dim\]/g, '</span>')
        .replace(/\[green\]/g, '<span style="color:#10b981;">')
        .replace(/\[\/green\]/g, '</span>')
        .replace(/\[cyan\]/g, '<span style="color:#06b6d4;">')
        .replace(/\[\/cyan\]/g, '</span>')
        .replace(/\[yellow\]/g, '<span style="color:#f97316;">')
        .replace(/\[\/yellow\]/g, '</span>')
        .replace(/\[red\]/g, '<span style="color:#ef4444;">')
        .replace(/\[\/red\]/g, '</span>')
        .replace(/\[bold green\]/g, '<span style="color:#10b981; font-weight:bold;">')
        .replace(/\[\/bold green\]/g, '</span>')
        .replace(/\[bold cyan\]/g, '<span style="color:#06b6d4; font-weight:bold;">')
        .replace(/\[\/bold cyan\]/g, '</span>')
        .replace(/\n/g, '<br>');
}
