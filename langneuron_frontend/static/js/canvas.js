import { appState, AGENT_DEFAULTS } from './state.js?v=20260717j';
import { elements } from './dom.js?v=20260717j';
import { openInspector } from './inspector.js?v=20260717j';

export function setupCanvasDragAndDrop() {
    const dragItems = document.querySelectorAll('.neuron-drag-item');
    
    dragItems.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', item.getAttribute('data-type'));
        });
    });

    elements.canvas.addEventListener('dragover', (e) => {
        e.preventDefault();
    });

    elements.canvas.addEventListener('drop', (e) => {
        e.preventDefault();
        const type = e.dataTransfer.getData('text/plain');
        if (!type) return;

        // Validation rule: Block drop of a new node if any existing node's common name is not filled (empty or blank)
        const emptyNode = appState.nodes.find(n => !n.name || n.name.trim() === "");
        if (emptyNode) {
            alert("Please configure the Common Name for all existing nodes on the canvas first.");
            openInspector(emptyNode.id);
            return;
        }

        const rect = elements.canvas.getBoundingClientRect();
        const scale = appState.workspaceViewport ? appState.workspaceViewport.scale : 1.0;
        const panX = appState.workspaceViewport ? appState.workspaceViewport.panX : 0;
        const panY = appState.workspaceViewport ? appState.workspaceViewport.panY : 0;

        const x = (e.clientX - rect.left - panX) / scale - 90; // offset width
        const y = (e.clientY - rect.top - panY) / scale - 40;  // offset height

        createNode(type, Math.max(10, x), Math.max(10, y), true);
    });

    // Panning & Clicking Canvas Resets Selection
    elements.canvas.addEventListener('mousedown', (e) => {
        if (e.target === elements.canvas || e.target.id === 'connection-svg' || e.target === elements.workspaceViewport) {
            setSelectedNode(null);
            if (appState.connectingFromNodeId) {
                cancelTempConnection();
            }
        }
    });

    elements.canvas.addEventListener('mousemove', (e) => {
        if (appState.draggingNode) {
            const rect = elements.canvas.getBoundingClientRect();
            const node = appState.nodes.find(n => n.id === appState.draggingNode);
            if (node) {
                const scale = appState.workspaceViewport ? appState.workspaceViewport.scale : 1.0;
                const panX = appState.workspaceViewport ? appState.workspaceViewport.panX : 0;
                const panY = appState.workspaceViewport ? appState.workspaceViewport.panY : 0;

                const currentMouseX = (e.clientX - rect.left - panX) / scale;
                const currentMouseY = (e.clientY - rect.top - panY) / scale;

                node.x = currentMouseX - appState.dragOffset.x;
                node.y = currentMouseY - appState.dragOffset.y;
                
                const el = document.getElementById(node.id);
                if (el) {
                    el.style.left = `${node.x}px`;
                    el.style.top = `${node.y}px`;
                }
                
                drawConnections();
            }
        } else if (appState.connectingFromNodeId && appState.tempLine) {
            const rect = elements.canvas.getBoundingClientRect();
            const parentNode = appState.nodes.find(n => n.id === appState.connectingFromNodeId);
            if (parentNode) {
                const parentEl = document.getElementById(parentNode.id);
                const nodeW = parentEl ? parentEl.offsetWidth : 150;
                const nodeH = parentEl ? parentEl.offsetHeight : 90;

                const scale = appState.workspaceViewport ? appState.workspaceViewport.scale : 1.0;
                const panX = appState.workspaceViewport ? appState.workspaceViewport.panX : 0;
                const panY = appState.workspaceViewport ? appState.workspaceViewport.panY : 0;

                // Start from bottom-center of parent
                const startX = parentNode.x + nodeW / 2;
                const startY = parentNode.y + nodeH;
                const endX = (e.clientX - rect.left - panX) / scale;
                const endY = (e.clientY - rect.top - panY) / scale;
                
                const d = `M ${startX} ${startY} C ${startX} ${startY + 60}, ${endX} ${endY - 60}, ${endX} ${endY}`;
                appState.tempLine.setAttribute('d', d);
            }
        }
    });

    window.addEventListener('mouseup', () => {
        appState.draggingNode = null;
    });

    elements.clearCanvasBtn.addEventListener('click', () => {
        elements.canvas.querySelectorAll('.canvas-node').forEach(el => el.remove());
        appState.nodes = [];
        appState.connections = [];
        appState.nodeCounter = 1;
        drawConnections();
        elements.runBtn.disabled = true;
        canvasChanged();
    });

    // Canvas-level mouseup: handles connection drop anywhere on/near a target node
    elements.canvas.addEventListener('mouseup', (e) => {
        if (!appState.connectingFromNodeId) return;

        // Walk up from the event target to find a canvas-node
        let target = e.target;
        while (target && target !== elements.canvas) {
            if (target.classList && target.classList.contains('canvas-node')) break;
            target = target.parentElement;
        }

        if (target && target.classList && target.classList.contains('canvas-node')) {
            const toId = target.id;
            if (toId && toId !== appState.connectingFromNodeId) {
                createConnection(appState.connectingFromNodeId, toId);
            }
        }

        cancelTempConnection();
    });
}

// Notify other modules that the canvas tree has changed
function canvasChanged() {
    window.dispatchEvent(new CustomEvent('canvas-changed'));
}

// Node Creation
export function createNode(type, x, y, isDrop = false) {
    const actualType = type === 'agent' ? 'chat' : type;
    const defaults = AGENT_DEFAULTS[actualType] || { role: 'worker', provider: 'moonshot', model: 'moonshot/kimi-k2.5' };
    const nodeId = `neuron_${appState.nodeCounter++}`;
    
    const node = {
        id: nodeId,
        name: isDrop ? "" : `Neuron${appState.nodeCounter - 1}`,
        role: isDrop ? "" : defaults.role,
        type: actualType,
        behavior: '',
        provider: defaults.provider,
        model: defaults.model,
        x: x,
        y: y,
        system_prompt: '',
        skills: [],
        tools: ''
    };

    appState.nodes.push(node);
    renderNode(node);
    canvasChanged();

    if (isDrop) {
        openInspector(nodeId);
    }
}

// Renders the Node DOM element on canvas
export function renderNode(node) {
    const el = document.createElement('div');
    el.id = node.id;
    el.className = 'canvas-node';
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;

    let iconClass = 'fa-solid ';
    if (node.type === 'chat') iconClass += 'fa-user-tie chat';
    else if (node.type === 'interviewer') iconClass += 'fa-users interviewer';
    else if (node.type === 'architect') iconClass += 'fa-compass-drafting architect';
    else if (node.type === 'writer') iconClass += 'fa-code writer';
    else if (node.type === 'runner') iconClass += 'fa-terminal runner';
    else if (node.type === 'researcher') iconClass += 'fa-magnifying-glass researcher';
    else if (node.type === 'analyst') iconClass += 'fa-chart-line analyst';
    else iconClass += 'fa-bug tester';

    const displayName = node.name ? node.name : '<span class="text-error font-bold animate-pulse">Configure Name</span>';
    const displayRole = node.role ? node.role : '<span class="text-on-surface-variant/40 italic">Auto Role</span>';

    el.innerHTML = `
        <div class="connection-handle handle-in" title="▲ Input (receives from supervisor)"></div>
        <div class="node-header" style="display:flex;align-items:center;gap:6px;">
            <span class="material-symbols-outlined" style="font-size:16px;color:#70ffba;">smart_toy</span>
            <h4 class="node-title">${displayName}</h4>
        </div>
        <div class="node-role" style="font-size:10px;color:#bfc9c1;margin-top:2px;">${displayRole}</div>
        <div class="node-meta" style="font-size:9px;color:#404943;text-transform:uppercase;letter-spacing:0.05em;margin-top:4px;font-family:'JetBrains Mono',monospace;">${node.type}</div>
        <div class="node-dynamic" style="display:none;"></div>
        <div class="node-compiled-badge" style="display:none;">✓ compiled</div>
        <div class="connection-handle handle-out" title="▼ Output (connects to subordinates)"></div>
    `;

    // Drag move handlers
    el.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('connection-handle')) return;
        
        setSelectedNode(node.id);
        appState.draggingNode = node.id;
        
        const rect = elements.canvas.getBoundingClientRect();
        const scale = appState.workspaceViewport ? appState.workspaceViewport.scale : 1.0;
        const panX = appState.workspaceViewport ? appState.workspaceViewport.panX : 0;
        const panY = appState.workspaceViewport ? appState.workspaceViewport.panY : 0;

        const mouseX = (e.clientX - rect.left - panX) / scale;
        const mouseY = (e.clientY - rect.top - panY) / scale;

        appState.dragOffset = {
            x: mouseX - node.x,
            y: mouseY - node.y
        };
    });

    // Connection Out Pin Drag Start
    const handleOut = el.querySelector('.handle-out');
    handleOut.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        appState.connectingFromNodeId = node.id;
        
        // Create temp SVG path line
        appState.tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        appState.tempLine.setAttribute('class', 'connection-line temp-line');
        elements.connectionSvg.appendChild(appState.tempLine);
    });

    // Node-level mouseup: accept connection drop on anywhere in this node
    el.addEventListener('mouseup', (e) => {
        if (!appState.connectingFromNodeId) return;
        // Ignore if mouseup came from handle-out of same node
        if (appState.connectingFromNodeId === node.id) {
            cancelTempConnection();
            return;
        }
        createConnection(appState.connectingFromNodeId, node.id);
        cancelTempConnection();
        e.stopPropagation(); // prevent canvas-level handler from double-firing
    });

    // Double click Inspector triggers modal
    el.addEventListener('dblclick', () => {
        openInspector(node.id);
    });

    (elements.workspaceViewport || elements.canvas).appendChild(el);
}

// Connection Creation
export function createConnection(fromId, toId) {
    // Avoid circular or duplicate connections
    if (appState.connections.some(c => c.from_node === fromId && c.to_node === toId)) return;
    
    // In hierarchical trees, a node can only have ONE supervisor/parent
    if (appState.connections.some(c => c.to_node === toId)) {
        appState.connections = appState.connections.filter(c => c.to_node !== toId);
    }

    appState.connections.push({ from_node: fromId, to_node: toId });
    drawConnections();
    canvasChanged();
}

export function cancelTempConnection() {
    if (appState.tempLine) {
        appState.tempLine.remove();
        appState.tempLine = null;
    }
    appState.connectingFromNodeId = null;
}

// Drawing Connections SVG bezier curves
export function drawConnections() {
    // Clear all lines except temp line
    elements.connectionSvg.querySelectorAll('path:not(.temp-line)').forEach(el => el.remove());
    
    appState.connections.forEach(conn => {
        const parent = appState.nodes.find(n => n.id === conn.from_node);
        const child = appState.nodes.find(n => n.id === conn.to_node);
        
        if (parent && child) {
            const parentEl = document.getElementById(parent.id);
            const childEl = document.getElementById(child.id);
            const pW = parentEl ? parentEl.offsetWidth : 150;
            const pH = parentEl ? parentEl.offsetHeight : 90;
            const cW = childEl ? childEl.offsetWidth : 150;

            // Start: bottom-center of parent
            const startX = parent.x + pW / 2;
            const startY = parent.y + pH;
            // End: top-center of child
            const endX = child.x + cW / 2;
            const endY = child.y;
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('class', 'connection-line');
            // Connected lines render GREEN to confirm the link is active
            path.style.stroke = '#70ffba';
            path.style.strokeWidth = '2';
            path.style.strokeDasharray = '6,4';
            path.style.animation = 'connectionFlow 12s linear infinite';
            
            const cp1Y = startY + 60;
            const cp2Y = endY - 60;
            const d = `M ${startX} ${startY} C ${startX} ${cp1Y}, ${endX} ${cp2Y}, ${endX} ${endY}`;
            path.setAttribute('d', d);
            
            // Delete connection on click (turns red on hover via CSS)
            path.addEventListener('click', () => {
                appState.connections = appState.connections.filter(c => c !== conn);
                drawConnections();
                canvasChanged();
            });

            elements.connectionSvg.appendChild(path);
        }
    });
}

// Update node card after compilation
export function updateNodeCardCompiled(nodeId) {
    const node = appState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const el = document.getElementById(nodeId);
    if (!el) return;

    el.classList.remove('compiling');
    el.classList.add('compiled');

    // Update title
    const titleEl = el.querySelector('.node-title');
    if (titleEl) {
        titleEl.textContent = node.name || node.id;
    }

    // Show dynamic name (role assigned by LLM)
    const dynamicEl = el.querySelector('.node-dynamic');
    if (dynamicEl && node.role) {
        dynamicEl.textContent = node.role;
        dynamicEl.style.display = 'block';
    }

    // Show compiled badge
    const badgeEl = el.querySelector('.node-compiled-badge');
    if (badgeEl) {
        const skillCount = (node.skills && node.skills.length) ? node.skills.length : 0;
        badgeEl.innerHTML = `<span style="font-size:10px">✓</span> ${skillCount} skill${skillCount !== 1 ? 's' : ''}`;
        badgeEl.style.display = 'inline-flex';
    }
}

export function setSelectedNode(id) {
    appState.selectedNodeId = id;
    elements.canvas.querySelectorAll('.canvas-node').forEach(el => {
        if (el.id === id) el.classList.add('selected');
        else el.classList.remove('selected');
    });
}
