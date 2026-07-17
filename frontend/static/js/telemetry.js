import { elements } from './dom.js?v=20260717j';

/**
 * Append a log entry to the Neuron Console telemetry panel.
 * Extracted from main.js to break the circular import cycle:
 *   main.js → terminal.js → main.js (was causing entire ES module graph failure)
 */
export function appendTelemetryLog(text, level = 'info') {
    const logsEl = elements.telemetryCommunicationLogs;
    if (!logsEl) return;

    const div = document.createElement('div');
    div.className = 'py-1 border-b border-outline-variant/10 last:border-b-0 text-[10px] font-mono leading-relaxed';

    if (level === 'error') {
        div.className += ' text-red-400';
    } else if (text.startsWith('▶') || text.startsWith('✓')) {
        div.className += ' text-[#00ff9d]';
    } else {
        div.className += ' text-on-surface-variant/80';
    }

    div.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    logsEl.appendChild(div);

    logsEl.scrollTop = logsEl.scrollHeight;
}
