import { appState } from './state.js?v=20260717j';
import { elements } from './dom.js?v=20260717j';

export function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

export function openInspector(nodeId) {
    const node = appState.nodes.find(n => n.id === nodeId);
    if (!node) return;

    elements.selectedNodeId = nodeId;
    elements.modalName.value = node.name;
    elements.modalRole.value = node.role || '';
    elements.modalType.value = node.type;
    elements.modalModel.value = node.model || 'moonshot/kimi-k2.5';
    elements.modalBehavior.value = node.behavior || '';
    elements.modalTools.value = Array.isArray(node.tools) ? node.tools.join(', ') : (node.tools || '');
    
    // Hide error messages
    elements.nodeNameError.classList.add('hidden');

    // Compute Supervisor
    const supConn = appState.connections.find(c => c.to_node === nodeId);
    let supervisorText = "None (Root Node)";
    if (supConn) {
        const supNode = appState.nodes.find(n => n.id === supConn.from_node);
        if (supNode) {
            supervisorText = supNode.name || supNode.id;
        }
    }
    elements.modalSupervisor.value = supervisorText;

    // Compute Subordinates
    const subConns = appState.connections.filter(c => c.from_node === nodeId);
    let subordinatesText = "None";
    if (subConns.length > 0) {
        const subNames = subConns.map(c => {
            const subNode = appState.nodes.find(n => n.id === c.to_node);
            return subNode ? (subNode.name || subNode.id) : '';
        }).filter(Boolean);
        if (subNames.length > 0) {
            subordinatesText = subNames.join(", ");
        }
    }
    elements.modalSubordinates.value = subordinatesText;

    // Set conversation history
    elements.modalHistory.innerHTML = '';
    if (node.history && node.history.length > 0) {
        node.history.forEach(h => {
            const p = document.createElement('p');
            p.className = 'text-xs text-on-surface-variant font-mono mb-1';
            p.innerHTML = `<span class="text-secondary font-bold">[${h.timestamp}]</span> ${escapeHtml(h.message)}`;
            elements.modalHistory.appendChild(p);
        });
    } else {
        elements.modalHistory.innerHTML = '<p class="text-on-surface-variant/40 italic font-mono">No conversation history yet. Start Swarm Run to generate execution logs.</p>';
    }
    
    // Set compilation outputs
    elements.modalPrompt.value = node.system_prompt || 'No system prompt compiled yet. Click "Compile Swarm" to auto-generate.';
    
    // Render Modular Prompt (LLD)
    const modularPromptEl = document.getElementById('node-modular-prompt');
    modularPromptEl.innerHTML = '';
    
    if (node.modular_prompt) {
        const sections = [
            { id: 'skill', title: '🏛️ Section 1: Specialized Skill', content: node.modular_prompt.skill },
            { id: 'directory', title: '📁 Section 2: Team Directory (LLD)', content: node.modular_prompt.team_directory },
            { id: 'supervisor', title: '👔 Section 3: Supervisor Path', content: node.modular_prompt.supervisor },
            { id: 'subordinates', title: '👥 Section 4: Subordinates Chain', content: node.modular_prompt.subordinates },
            { id: 'tools', title: '⚙️ Section 5: Authorized Tools', content: node.modular_prompt.tools },
            { id: 'decision', title: '📜 Section 8: Execution Decision Rules', content: node.modular_prompt.decision_rules }
        ];
        
        sections.forEach((sec, idx) => {
            const secEl = document.createElement('div');
            secEl.className = 'modular-section';
            if (idx === 0) {
                secEl.classList.add('active');
            }
            secEl.innerHTML = `
                <div class="modular-section-header">
                    <span>${sec.title}</span>
                    <i class="fa-solid fa-chevron-right chevron"></i>
                </div>
                <div class="modular-section-body">${escapeHtml(sec.content || 'None')}</div>
            `;
            
            const header = secEl.querySelector('.modular-section-header');
            header.addEventListener('click', () => {
                const isActive = secEl.classList.contains('active');
                modularPromptEl.querySelectorAll('.modular-section').forEach(s => s.classList.remove('active'));
                if (!isActive) {
                    secEl.classList.add('active');
                }
            });
            
            modularPromptEl.appendChild(secEl);
        });
    } else {
        modularPromptEl.innerHTML = '<p class="empty">No system prompt compiled yet. Click "Compile Swarm" to auto-generate.</p>';
    }

    elements.modalSkills.innerHTML = '';
    if (node.skills && node.skills.length > 0) {
        node.skills.forEach(skill => {
            const li = document.createElement('li');
            li.textContent = skill;
            elements.modalSkills.appendChild(li);
        });
    } else {
        elements.modalSkills.innerHTML = '<li class="empty">No skills compiled yet. Click "Compile Swarm" to auto-generate.</li>';
    }

    // Default inspector tab selection
    switchInspectorTab('prompt');

    elements.inspectorModal.classList.add('active');
}

export function switchInspectorTab(tabContentId) {
    elements.inspectorTabs.forEach(i => {
        if (i.getAttribute('data-content') === tabContentId) i.classList.add('active');
        else i.classList.remove('active');
    });
    elements.inspectorTabContents.forEach(tc => {
        if (tc.id === `inspector-${tabContentId}`) tc.classList.add('active');
        else tc.classList.remove('active');
    });
}

export function closeInspectorModal() {
    elements.inspectorModal.classList.remove('active');
}

export function saveNodeSettings() {
    const node = appState.nodes.find(n => n.id === elements.selectedNodeId);
    if (node) {
        let nameVal = elements.modalName.value.trim();
        if (!nameVal) {
            nameVal = node.id.replace('_', '-');
        }
        // Check uniqueness (exclude current node)
        const duplicate = appState.nodes.some(n => n.id !== node.id && n.name.toLowerCase() === nameVal.toLowerCase());
        if (duplicate) {
            elements.nodeNameError.textContent = "Common name must be unique.";
            elements.nodeNameError.classList.remove('hidden');
            return;
        }

        elements.nodeNameError.classList.add('hidden');

        node.name = nameVal;
        node.role = elements.modalRole.value.trim();
        node.type = elements.modalType.value;
        node.model = elements.modalModel.value;
        node.behavior = elements.modalBehavior.value;
        node.tools = elements.modalTools.value;
        
        // Update DOM node representation
        const el = document.getElementById(node.id);
        if (el) {
            const titleEl = el.querySelector('.node-title');
            if (node.name) {
                titleEl.textContent = node.name;
            } else {
                titleEl.innerHTML = '<span class="text-error font-bold animate-pulse">Configure Name</span>';
            }
            
            const roleEl = el.querySelector('.node-role');
            if (node.role) {
                roleEl.textContent = node.role;
            } else {
                roleEl.innerHTML = '<span class="text-on-surface-variant/40 italic">Auto Role</span>';
            }

            el.querySelector('.node-meta').textContent = node.type;

            // Dynamically update the icon
            const iconEl = el.querySelector('.node-header i');
            if (iconEl) {
                iconEl.className = '';
                let iconClass = 'fa-solid ';
                if (node.type === 'chat') iconClass += 'fa-user-tie chat';
                else if (node.type === 'interviewer') iconClass += 'fa-users interviewer';
                else if (node.type === 'architect') iconClass += 'fa-compass-drafting architect';
                else if (node.type === 'writer') iconClass += 'fa-code writer';
                else if (node.type === 'runner') iconClass += 'fa-terminal runner';
                else if (node.type === 'researcher') iconClass += 'fa-magnifying-glass researcher';
                else if (node.type === 'analyst') iconClass += 'fa-chart-line analyst';
                else iconClass += 'fa-bug tester';
                
                iconEl.className = iconClass;
            }
        }
    }
    closeInspectorModal();
}
