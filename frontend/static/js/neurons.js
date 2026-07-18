import { appState } from './state.js?v=20260717j';
import { elements } from './dom.js?v=20260717j';
import { openInspector } from './inspector.js?v=20260717j';

let nodePositions = {};
let nodeDepths = {};
let childMapGlobal = {};
let parentMapGlobal = {};

/**
 * Maps specialization titles and agent types to material icon identifiers.
 */
function getSpecializationIcon(roleStr = '', typeStr = '') {
    const key = (roleStr + ' ' + typeStr).toLowerCase();
    if (key.includes('arch') || key.includes('lead') || key.includes('system') || key.includes('root')) return 'schema';
    if (key.includes('db') || key.includes('database') || key.includes('sql') || key.includes('data')) return 'database';
    if (key.includes('api') || key.includes('backend') || key.includes('rest') || key.includes('server')) return 'api';
    if (key.includes('ui') || key.includes('frontend') || key.includes('design') || key.includes('css')) return 'palette';
    if (key.includes('devops') || key.includes('docker') || key.includes('cloud') || key.includes('deploy')) return 'terminal';
    if (key.includes('qa') || key.includes('test') || key.includes('bug') || key.includes('eval')) return 'fact_check';
    if (key.includes('write') || key.includes('content') || key.includes('doc')) return 'edit_note';
    return 'smart_toy';
}

/**
 * Truncates text cleanly for small node badges.
 */
function formatShortTitle(str = '', maxLen = 16) {
    if (!str) return 'Active';
    const clean = str.trim();
    return clean.length > maxLen ? clean.substring(0, maxLen - 2) + '..' : clean;
}

/**
 * Computes tree layout coordinates dynamically on organic concentric tiers.
 */
function calculateTreeLayout(nodes, canvasWidth, canvasHeight) {
    const positions = {};
    nodeDepths = {};
    childMapGlobal = {};
    parentMapGlobal = {};

    if (!nodes || nodes.length === 0) return positions;

    // Build parent-child tree mapping
    const nodeByName = {};

    nodes.forEach(n => {
        nodeByName[n.common_name] = n;
        childMapGlobal[n.common_name] = [];
    });

    nodes.forEach(n => {
        const parent = n.parent_common_name;
        if (parent && childMapGlobal[parent]) {
            childMapGlobal[parent].push(n.common_name);
            parentMapGlobal[n.common_name] = parent;
        }
    });

    // Find root nodes
    const roots = nodes.filter(n => !n.parent_common_name || !nodeByName[n.parent_common_name]);
    if (roots.length === 0 && nodes.length > 0) {
        roots.push(nodes[0]);
    }

    const spacingY = 210; // Tier distance
    const startY = 160;   // Root Y position

    function positionSubtree(nodeName, xCenter, depth, horizontalGap) {
        const y = startY + depth * spacingY;
        positions[nodeName] = { x: xCenter, y };
        nodeDepths[nodeName] = depth;

        const children = childMapGlobal[nodeName] || [];
        const k = children.length;
        if (k > 0) {
            const gap = horizontalGap;
            const startX = xCenter - ((k - 1) * gap) / 2;
            children.forEach((child, index) => {
                const childX = startX + index * gap;
                positionSubtree(child, childX, depth + 1, gap * 0.58);
            });
        }
    }

    const rootCount = roots.length;
    const rootGap = 340;
    const startRootX = canvasWidth / 2 - ((rootCount - 1) * rootGap) / 2;
    roots.forEach((root, index) => {
        const rootX = startRootX + index * rootGap;
        positionSubtree(root.common_name, rootX, 0, 280);
    });

    // Horizontally center the layout
    const keys = Object.keys(positions);
    if (keys.length > 0) {
        let minX = Infinity;
        let maxX = -Infinity;
        keys.forEach(k => {
            const x = positions[k].x;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
        });

        const treeCenter = (minX + maxX) / 2;
        const canvasCenter = canvasWidth / 2;
        const shift = canvasCenter - treeCenter;
        keys.forEach(k => {
            positions[k].x += shift;
        });
    }

    return positions;
}

// Fixed virtual canvas dimensions — graph coordinates are always computed inside
// this space, completely independent of the visible viewport/container size.
const VIRTUAL_CANVAS_WIDTH  = 4000;
const VIRTUAL_CANVAS_HEIGHT = 4000;

// Guard: after the first successful layout, node positions are frozen.
// Sidebar resizing / window resizing must NEVER trigger a re-layout.
let layoutFrozen = false;

/**
 * Main function to render the Neuron Console living neural brain.
 * The graph is always drawn on a fixed 4000×4000 virtual canvas.
 * The visible area is a clipping viewport — only pan/zoom changes what you see.
 */
export function renderNeuronTree(nodes) {
    const canvas = elements.neuronNodesContainer;
    const svg = elements.neuronConnectionSvg;
    if (!canvas || !svg) return;

    // ── Fixed virtual canvas ─────────────────────────────────────────────────
    // Always use VIRTUAL_CANVAS_WIDTH — never read the container's live width.
    const width  = VIRTUAL_CANVAS_WIDTH;
    const height = VIRTUAL_CANVAS_HEIGHT;

    // Stamp the canvas and SVG to the fixed virtual size exactly once.
    if (canvas.dataset.virtualSizeSet !== '1') {
        canvas.style.width  = `${width}px`;
        canvas.style.height = `${height}px`;
        canvas.style.position = 'absolute';
        canvas.style.top  = '0';
        canvas.style.left = '0';
        canvas.style.overflow = 'visible';
        svg.setAttribute('width',  `${width}`);
        svg.setAttribute('height', `${height}`);
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        svg.style.width  = `${width}px`;
        svg.style.height = `${height}px`;
        svg.style.position = 'absolute';
        svg.style.top  = '0';
        svg.style.left = '0';
        canvas.dataset.virtualSizeSet = '1';
    }

    // ── Freeze layout after first successful layout ──────────────────────────
    // If we already have positions for every node, do NOT re-compute layout.
    // Only update visual state (compiled/pulse colour, SVG path colours, etc.).
    const allPositioned = nodes.length > 0 && nodes.every(n => nodePositions[n.common_name]);
    if (layoutFrozen && allPositioned) {
        // Only refresh card/connection visual state without moving anything
        _refreshVisualState(nodes, canvas, svg);
        return;
    }

    // Compute node coordinates against the fixed virtual canvas
    nodePositions = calculateTreeLayout(nodes, width, height);
    if (nodes.length > 0 && nodes.every(n => nodePositions[n.common_name])) {
        layoutFrozen = true;
    }



    // ── Concentric Neural Field Rings (Centered at Root Node) ──────────────
    const rootPos = Object.values(nodePositions)[0] || { x: width / 2, y: 160 };
    let fieldRingsGroup = svg.querySelector('#neural-field-rings');
    if (!fieldRingsGroup) {
        fieldRingsGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        fieldRingsGroup.setAttribute('id', 'neural-field-rings');
        svg.prepend(fieldRingsGroup);
    }
    fieldRingsGroup.innerHTML = `
        <circle cx="${rootPos.x}" cy="${rootPos.y}" r="210" fill="none" stroke="rgba(0, 255, 157, 0.05)" stroke-width="1.5" stroke-dasharray="6 6" />
        <circle cx="${rootPos.x}" cy="${rootPos.y}" r="420" fill="none" stroke="rgba(0, 255, 157, 0.03)" stroke-width="1.5" stroke-dasharray="8 8" />
        <circle cx="${rootPos.x}" cy="${rootPos.y}" r="630" fill="none" stroke="rgba(0, 255, 157, 0.02)" stroke-width="1.5" stroke-dasharray="10 10" />
    `;

    // Map existing elements
    const existingCards = Array.from(canvas.querySelectorAll('[data-node-name]'));
    const cardMap = {};
    existingCards.forEach(c => cardMap[c.dataset.nodeName] = c);

    const existingPaths = Array.from(svg.querySelectorAll('[data-link-id]'));
    const pathMap = {};
    existingPaths.forEach(p => pathMap[p.getAttribute('data-link-id')] = p);

    // ── Render Organic Dendrite Connections ─────────────────────────────────
    nodes.forEach(node => {
        const parent = node.parent_common_name;
        if (parent && nodePositions[parent] && nodePositions[node.common_name]) {
            const start = nodePositions[parent];
            const end = nodePositions[node.common_name];
            const depth = nodeDepths[node.common_name] || 1;

            // Organic dendrite Bezier curve
            const midY = (start.y + end.y) / 2;
            const pathData = `M ${start.x} ${start.y} C ${start.x} ${midY}, ${end.x} ${midY}, ${end.x} ${end.y}`;

            const isCompiled = node.system_prompt && node.system_prompt.trim() !== '';
            const glowColor = isCompiled ? 'rgba(0, 255, 157, 0.22)' : 'rgba(245, 158, 11, 0.08)';
            const strokeColor = isCompiled ? '#00ff9d' : 'rgba(245, 158, 11, 0.4)';
            const signalColor = isCompiled ? '#ffffff' : '#f59e0b';
            const shadowColor = isCompiled ? '#00ff9d' : '#f59e0b';

            // Connection thickness decreases with depth hierarchy
            const strokeWidth = depth === 1 ? '3.2' : '2.0';
            const glowWidth = depth === 1 ? '8' : '5';
            const synapseRadius = depth === 1 ? '5' : '3.5';
            const speed = isCompiled ? 1.4 + Math.random() * 1.2 : 3.0 + Math.random() * 1.5;

            const glowPathId = `${parent}-${node.common_name}-glow`;
            const mainPathId = `${parent}-${node.common_name}-main`;
            const dotId = `${parent}-${node.common_name}-dot`;
            const synapseId = `${parent}-${node.common_name}-synapse`;

            let glowPath = pathMap[glowPathId];
            let mainPath = pathMap[mainPathId];
            let flowDot = pathMap[dotId];
            let synapseDot = pathMap[synapseId];

            if (glowPath && mainPath && flowDot && synapseDot) {
                glowPath.setAttribute('d', pathData);
                glowPath.setAttribute('stroke', glowColor);
                glowPath.setAttribute('stroke-width', glowWidth);

                mainPath.setAttribute('d', pathData);
                mainPath.setAttribute('stroke', strokeColor);
                mainPath.setAttribute('stroke-width', strokeWidth);

                synapseDot.setAttribute('cx', end.x);
                synapseDot.setAttribute('cy', end.y);
                synapseDot.setAttribute('fill', strokeColor);

                flowDot.setAttribute('fill', signalColor);
                const anim = flowDot.querySelector('animateMotion');
                if (anim) {
                    anim.setAttribute('path', pathData);
                    anim.setAttribute('dur', `${speed}s`);
                }

                delete pathMap[glowPathId];
                delete pathMap[mainPathId];
                delete pathMap[dotId];
                delete pathMap[synapseId];
            } else {
                // Background Glow
                glowPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                glowPath.setAttribute('data-link-id', glowPathId);
                glowPath.setAttribute('d', pathData);
                glowPath.setAttribute('fill', 'none');
                glowPath.setAttribute('stroke', glowColor);
                glowPath.setAttribute('stroke-width', glowWidth);
                glowPath.style.filter = 'blur(4px)';
                glowPath.style.transition = 'opacity 0.4s ease, d 0.8s ease';
                svg.appendChild(glowPath);

                // Main Dendrite Path
                mainPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                mainPath.setAttribute('data-link-id', mainPathId);
                mainPath.setAttribute('d', pathData);
                mainPath.setAttribute('fill', 'none');
                mainPath.setAttribute('stroke', strokeColor);
                mainPath.setAttribute('stroke-width', strokeWidth);
                mainPath.setAttribute('stroke-linecap', 'round');
                mainPath.style.transition = 'opacity 0.4s ease, d 0.8s ease';
                svg.appendChild(mainPath);

                // Synapse Junction Dot
                synapseDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                synapseDot.setAttribute('data-link-id', synapseId);
                synapseDot.setAttribute('cx', end.x);
                synapseDot.setAttribute('cy', end.y);
                synapseDot.setAttribute('r', synapseRadius);
                synapseDot.setAttribute('fill', strokeColor);
                synapseDot.style.filter = `drop-shadow(0 0 6px ${shadowColor})`;
                svg.appendChild(synapseDot);

                // Moving Signal Pulse Particle
                flowDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                flowDot.setAttribute('data-link-id', dotId);
                flowDot.setAttribute('r', isCompiled ? '3.5' : '2.5');
                flowDot.setAttribute('fill', signalColor);
                flowDot.style.filter = `drop-shadow(0 0 8px ${shadowColor})`;

                const animateMotion = document.createElementNS('http://www.w3.org/2000/svg', 'animateMotion');
                animateMotion.setAttribute('path', pathData);
                animateMotion.setAttribute('dur', `${speed}s`);
                animateMotion.setAttribute('repeatCount', 'indefinite');
                flowDot.appendChild(animateMotion);
                svg.appendChild(flowDot);
            }
        }
    });

    // Remove defunct connection elements
    Object.values(pathMap).forEach(p => p.remove());

    // ── Render Node Cards (Hierarchy Size & Behavioral Styling) ─────────────
    nodes.forEach(node => {
        const pos = nodePositions[node.common_name];
        if (!pos) return;

        const depth = nodeDepths[node.common_name] || 0;
        const isCompiled = node.system_prompt && node.system_prompt.trim() !== '';

        let card = cardMap[node.common_name];

        if (card) {
            card.style.left = `${pos.x}px`;
            card.style.top = `${pos.y}px`;
            delete cardMap[node.common_name];
        } else {
            card = document.createElement('div');
            card.dataset.nodeName = node.common_name;
            card.className = 'absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10 select-none transition-all duration-300';
            card.style.left = `${pos.x}px`;
            card.style.top = `${pos.y}px`;
            card.style.transition = 'left 0.8s cubic-bezier(0.25, 1, 0.5, 1), top 0.8s cubic-bezier(0.25, 1, 0.5, 1)';
            canvas.appendChild(card);
        }

        // Apply visual hierarchy sizes: Root (150px), Lead (120px), Worker (95px)
        let sizeClass = 'neuron-card-worker';
        let wrapperSizeClass = 'w-[140px] h-[140px]';
        let iconSize = 'text-xs';
        let titleSize = 'text-[13px]';
        let roleSize = 'text-[7px]';
        let isRoot = depth === 0;

        if (depth === 0) {
            sizeClass = 'neuron-card-root';
            wrapperSizeClass = 'w-[190px] h-[190px]';
            iconSize = 'text-base';
            titleSize = 'text-base';
            roleSize = 'text-[8px]';
        } else if (depth === 1) {
            sizeClass = 'neuron-card-lead';
            wrapperSizeClass = 'w-[160px] h-[160px]';
            iconSize = 'text-sm';
            titleSize = 'text-sm';
            roleSize = 'text-[7.5px]';
        }

        const roleTitle = node.agent_type || (isRoot ? 'ARCHITECT' : 'WORKER');
        const specIcon = getSpecializationIcon(roleTitle, node.dynamic_name || '');
        const dynamicLabel = node.dynamic_name && node.dynamic_name.trim()
            ? formatShortTitle(node.dynamic_name, depth === 0 ? 20 : depth === 1 ? 16 : 13)
            : (isCompiled ? 'Active' : 'Compiling..');
        const commonLabel = node.common_name;
        const activeStateClass = isCompiled ? 'active' : 'inactive';

        card.innerHTML = `
            <div class="relative flex items-center justify-center ${wrapperSizeClass}">
                ${isRoot ? '<div class="neuron-orbit-ring"></div>' : ''}

                <!-- Circular Node -->
                <div class="neuron-card ${sizeClass} ${activeStateClass}">
                    <div class="neuron-card-glow-ring"></div>

                    <!-- Specialization Icon & Role -->
                    <div class="flex items-center gap-1 text-[#00ff9d] ${roleSize} font-bold tracking-[2px] font-mono uppercase">
                        <span class="material-symbols-outlined !${iconSize} text-[#00ff9d]">${specIcon}</span>
                        <span>${roleTitle}</span>
                    </div>

                    <!-- Dynamic Name — Hero text (what the LLM assigned as this agent's role/task) -->
                    <div class="text-white ${titleSize} font-extrabold mt-0.5 max-w-[85%] truncate tracking-tight font-sans text-center leading-tight">
                        ${dynamicLabel}
                    </div>

                    <!-- Common Name — Subheading identifier tag below the hero text -->
                    <div class="mt-0.5 text-[#4ade80] text-[8px] font-mono uppercase tracking-widest opacity-80 max-w-[80%] truncate text-center">
                        ${commonLabel}
                    </div>

                    <!-- Neon Accent Line -->
                    <div class="mt-1 w-6 h-[1.5px] bg-[#00ff9d] rounded-full shadow-[0_0_6px_#00ff9d] opacity-70"></div>

                    <div class="neuron-card-center-dot"></div>
                </div>

                <!-- Thinking spinner arc (toggled by setNeuronThinking) -->
                <div class="neuron-thinking-spinner" data-spinner-for="${node.common_name}"></div>
            </div>
        `;


        // ── Ancestor & Descendant Hover Highlighting ────────────────────────
        card.onmouseenter = () => {
            const activeNodeName = node.common_name;

            // Collect ancestors
            const activeNodesSet = new Set([activeNodeName]);
            let curr = activeNodeName;
            while (curr && parentMapGlobal[curr]) {
                const parent = parentMapGlobal[curr];
                activeNodesSet.add(parent);
                curr = parent;
            }

            // Collect descendants recursively
            function collectDescendants(nName) {
                const children = childMapGlobal[nName] || [];
                children.forEach(c => {
                    activeNodesSet.add(c);
                    collectDescendants(c);
                });
            }
            collectDescendants(activeNodeName);

            // Apply dimmed / highlighted state to cards
            canvas.querySelectorAll('[data-node-name]').forEach(c => {
                if (activeNodesSet.has(c.dataset.nodeName)) {
                    c.classList.add('highlighted-active');
                    c.classList.remove('dimmed-inactive');
                } else {
                    c.classList.add('dimmed-inactive');
                    c.classList.remove('highlighted-active');
                }
            });

            // Apply dimmed / highlighted state to SVG paths
            svg.querySelectorAll('[data-link-id]').forEach(p => {
                const linkId = p.getAttribute('data-link-id') || '';
                const isConnected = Array.from(activeNodesSet).some(nName => linkId.includes(nName));
                if (isConnected) {
                    p.classList.add('highlighted-active');
                    p.classList.remove('dimmed-inactive');
                } else {
                    p.classList.add('dimmed-inactive');
                    p.classList.remove('highlighted-active');
                }
            });
        };

        card.onmouseleave = () => {
            canvas.querySelectorAll('[data-node-name]').forEach(c => {
                c.classList.remove('highlighted-active', 'dimmed-inactive');
            });
            svg.querySelectorAll('[data-link-id]').forEach(p => {
                p.classList.remove('highlighted-active', 'dimmed-inactive');
            });
        };

        // Bind single click behavior to open details inspector
        card.onclick = (e) => {
            e.stopPropagation();
            let localNode = appState.nodes.find(n => n.id === node.common_name);
            if (!localNode) {
                localNode = {
                    id: node.common_name,
                    name: node.common_name,
                    role: node.dynamic_name || '',
                    type: node.agent_type || 'writer',
                    behavior: node.subtask || '',
                    system_prompt: node.system_prompt || '',
                    skills: node.skills || [],
                    tools: node.tools || '',
                    model: node.model || 'moonshot/kimi-k2.5',
                    modular_prompt: node.modular_prompt || null
                };
                appState.nodes.push(localNode);
            } else {
                localNode.role = node.dynamic_name || localNode.role;
                localNode.system_prompt = node.system_prompt || localNode.system_prompt;
                localNode.skills = node.skills || localNode.skills;
                localNode.tools = node.tools || localNode.tools;
                localNode.model = node.model || localNode.model;
                localNode.modular_prompt = node.modular_prompt || localNode.modular_prompt;
            }
            openInspector(node.common_name);
        };
    });

    // Remove defunct card elements
    Object.values(cardMap).forEach(c => c.remove());
}

/**
 * Lightweight visual-state refresh — updates card glow / connection colours
 * without recomputing or changing any node positions.
 * Called when the layout is frozen but compilation state changes (e.g. a node
 * finishes compiling and should switch from amber to green).
 */
function _refreshVisualState(nodes, canvas, svg) {
    nodes.forEach(node => {
        const card = canvas.querySelector(`[data-node-name="${node.common_name}"]`);
        if (!card) return;
        const isCompiled = node.system_prompt && node.system_prompt.trim() !== '';
        const neuronCard = card.querySelector('.neuron-card');
        if (neuronCard) {
            neuronCard.classList.toggle('active', isCompiled);
            neuronCard.classList.toggle('inactive', !isCompiled);
        }
        // Refresh task label
        const taskLabel = card.querySelector('.neuron-task-label');
        if (taskLabel) {
            const shortTask = (node.dynamic_name || (isCompiled ? 'Active' : 'Compiling..')).substring(0, 16);
            taskLabel.textContent = shortTask;
        }
    });

    // Refresh SVG connection colours only
    nodes.forEach(node => {
        const parent = node.parent_common_name;
        if (!parent || !nodePositions[parent] || !nodePositions[node.common_name]) return;
        const isCompiled = node.system_prompt && node.system_prompt.trim() !== '';
        const strokeColor = isCompiled ? '#00ff9d' : 'rgba(245, 158, 11, 0.4)';
        const glowColor   = isCompiled ? 'rgba(0, 255, 157, 0.22)' : 'rgba(245, 158, 11, 0.08)';
        const mainPathId = `${parent}-${node.common_name}-main`;
        const glowPathId = `${parent}-${node.common_name}-glow`;
        const mainPath = svg.querySelector(`[data-link-id="${mainPathId}"]`);
        const glowPath = svg.querySelector(`[data-link-id="${glowPathId}"]`);
        if (mainPath) mainPath.setAttribute('stroke', strokeColor);
        if (glowPath) glowPath.setAttribute('stroke', glowColor);
    });
}

/**
 * Resets the layout freeze so the next renderNeuronTree call recomputes positions.
 * Call this before a new compilation begins (i.e. when the node list changes).
 */
export function resetNeuronLayout() {
    layoutFrozen = false;
    nodePositions = {};
    nodeDepths = {};
    childMapGlobal = {};
    parentMapGlobal = {};
    // Remove the virtual-size stamp so dimensions are re-applied
    const canvas = elements.neuronNodesContainer;
    if (canvas) delete canvas.dataset.virtualSizeSet;
}

/**
 * Activates or stops the rotating border spinner on a specific neuron card.
 * @param {string|null} activeNeuronName - The common_name of the agent, or null to clear all.
 */
export function setNeuronThinking(activeNeuronName, isThinking = null) {
    const canvas = elements.neuronNodesContainer;
    if (!canvas) return;

    const spinners = canvas.querySelectorAll('.neuron-thinking-spinner');
    spinners.forEach(spin => {
        const name = spin.dataset.spinnerFor;
        if (!name) return;

        if (isThinking !== null) {
            // Target specific neuron state change
            if (name.toLowerCase() === activeNeuronName?.toLowerCase()) {
                spin.classList.toggle('thinking', isThinking);
            }
        } else {
            // Legacy/global behavior: set this one active, clear others
            const shouldSpin = activeNeuronName && name.toLowerCase() === activeNeuronName.toLowerCase();
            spin.classList.toggle('thinking', shouldSpin);
        }
    });
}

// Track active bubbles to allow streaming updates
const activeBubbles = {};

/**
 * Creates or updates a floating speech bubble above an agent's card on the virtual canvas.
 * @param {string} neuronName - The common_name of the agent.
 * @param {string} text - The speech text to display.
 */
export function showAgentBubble(neuronName, text) {
    const canvas = elements.neuronNodesContainer;
    if (!canvas) return;

    // Find the wrapper element for this neuron card
    const cardEl = canvas.querySelector(`[data-node-name="${neuronName}"]`);
    if (!cardEl) return;

    const wrapper = cardEl.querySelector('.relative');
    if (!wrapper) return;

    let bubble = activeBubbles[neuronName];
    if (!bubble) {
        // Create new speech bubble
        bubble = document.createElement('div');
        bubble.className = 'neuron-agent-bubble';
        
        // Agent Role Header inside bubble
        const header = document.createElement('div');
        header.className = 'bubble-agent-label';
        header.textContent = neuronName;
        bubble.appendChild(header);

        // Message text container
        const textSpan = document.createElement('span');
        textSpan.className = 'bubble-text';
        bubble.appendChild(textSpan);

        wrapper.appendChild(bubble);
        activeBubbles[neuronName] = bubble;
    }

    const textSpan = bubble.querySelector('.bubble-text');
    if (textSpan) {
        textSpan.textContent = text;
    }

    // Auto-scroll bubble text to show latest streamed tokens
    bubble.scrollTop = bubble.scrollHeight;

    // Reset bubble auto-remove timeout
    if (bubble.dataset.timeoutId) {
        clearTimeout(parseInt(bubble.dataset.timeoutId));
    }
    const timeoutId = setTimeout(() => {
        clearAgentBubble(neuronName);
    }, 6000); // fade out after 6 seconds of silence
    bubble.dataset.timeoutId = timeoutId;
}

/**
 * Gracefully fades out and removes a speech bubble.
 */
export function clearAgentBubble(neuronName) {
    const bubble = activeBubbles[neuronName];
    if (!bubble) return;

    bubble.classList.add('fade-out');
    // Wait for fadeOut animation to finish
    setTimeout(() => {
        if (bubble.parentNode) {
            bubble.parentNode.removeChild(bubble);
        }
        delete activeBubbles[neuronName];
    }, 400);
}

