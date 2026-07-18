import { API_BASE, appState } from './state.js?v=20260717j';
import { elements } from './dom.js?v=20260717j';
import { loadSandboxExplorerTree, openFileInMonaco } from './sandbox.js?v=20260717j';

let activeSandboxFile = null;

export async function loadDocs() {
    try {
        const response = await fetch(`${API_BASE}/api/docs`);
        const docs = await response.json();
        
        elements.docsList.innerHTML = '';
        if (docs.length === 0) {
            elements.docsList.innerHTML = '<p class="p-4 text-xs text-gray-500 font-mono text-center">No documentation found</p>';
            return;
        }
        
        docs.forEach(doc => {
            const btn = document.createElement('button');
            btn.className = 'w-full text-left px-3 py-2 rounded-lg hover:bg-[#00ff9d]/10 text-gray-300 hover:text-[#00ff9d] transition-all font-mono text-xs flex items-center justify-between group';
            btn.innerHTML = `
                <span class="truncate font-medium">${doc.name}</span>
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 group-hover:bg-[#00ff9d]/20 group-hover:text-[#00ff9d]">${doc.category}</span>
            `;
            btn.addEventListener('click', (event) => showDocContent(doc, event.currentTarget));
            elements.docsList.appendChild(btn);
        });
    } catch(e) {
        console.error('Error loading docs:', e);
    }
}

export async function showDocContent(doc, targetBtn) {
    if (targetBtn && elements.docsList) {
        Array.from(elements.docsList.children).forEach(child => child.classList.remove('bg-[#00ff9d]/20', 'text-[#00ff9d]'));
        targetBtn.classList.add('bg-[#00ff9d]/20', 'text-[#00ff9d]');
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/docs/content?path=${encodeURIComponent(doc.path)}`);
        const data = await response.json();
        
        let html = data.content
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold text-white mb-2">$1</h1>')
            .replace(/^## (.*$)/gim, '<h2 class="text-lg font-bold text-[#00ff9d] mt-4 mb-2">$1</h2>')
            .replace(/^### (.*$)/gim, '<h3 class="text-sm font-bold text-gray-200 mt-3 mb-1">$1</h3>')
            .replace(/^\* (.*$)/gim, '<li class="ml-4 text-gray-300 text-xs">$1</li>')
            .replace(/`(.*?)`/g, '<code class="bg-[#0c231a] text-[#00ff9d] px-1 py-0.5 rounded text-xs">$1</code>')
            .replace(/\n/g, '<br>');
            
        elements.docsBody.innerHTML = `<div class="markdown-body p-4 text-xs font-sans text-gray-300 leading-relaxed">${html}</div>`;
    } catch (e) {
        elements.docsBody.innerHTML = `<p class="p-4 text-red-400 font-mono text-xs">Failed to load content.</p>`;
    }
}

/**
 * Loads and renders the list of files in langneurons/sandbox/
 */
export async function loadSandboxFiles() {
    if (!elements.sandboxList) return;

    try {
        const response = await fetch(`${API_BASE}/api/sandbox`);
        const files = await response.json();
        
        elements.sandboxList.innerHTML = '';
        if (files.length === 0) {
            elements.sandboxList.innerHTML = `
                <div class="p-6 text-center text-gray-500 font-mono text-xs space-y-2">
                    <span class="material-symbols-outlined text-3xl opacity-50">folder_off</span>
                    <p>No files in sandbox yet.</p>
                    <p class="text-[10px] text-gray-600">Agents will auto-generate code files here during swarm execution.</p>
                </div>
            `;
            return;
        }
        
        files.forEach(file => {
            const btn = document.createElement('button');
            const icon = getFileIcon(file.name);
            const sizeKb = (file.size / 1024).toFixed(1);

            btn.className = 'w-full text-left px-3 py-2.5 rounded-lg hover:bg-[#00ff9d]/10 text-gray-300 hover:text-[#00ff9d] transition-all font-mono text-xs flex items-center justify-between group border border-transparent hover:border-[#00ff9d]/20 cursor-pointer';
            btn.innerHTML = `
                <div class="flex items-center gap-2 overflow-hidden">
                    <span class="material-symbols-outlined text-[#00ff9d] group-hover:scale-110 transition-transform !text-base">${icon}</span>
                    <div class="truncate">
                        <div class="font-bold text-gray-200 group-hover:text-[#00ff9d] text-xs truncate">${file.relative_path}</div>
                    </div>
                </div>
                <span class="text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-[#0a241b] text-gray-400 border border-[#00ff9d]/20 shrink-0 ml-1">${sizeKb} KB</span>
            `;

            btn.addEventListener('click', (event) => showSandboxContent(file, event.currentTarget));
            elements.sandboxList.appendChild(btn);
        });

        // Setup refresh button
        if (elements.sandboxRefreshBtn) {
            elements.sandboxRefreshBtn.onclick = () => {
                elements.sandboxRefreshBtn.querySelector('span').classList.add('animate-spin');
                loadSandboxFiles().then(() => {
                    setTimeout(() => elements.sandboxRefreshBtn.querySelector('span').classList.remove('animate-spin'), 600);
                });
            };
        }
    } catch(e) {
        console.error('Error loading sandbox files:', e);
    }
}

/**
 * Displays the content of the selected sandbox file in the code viewer.
 */
export async function showSandboxContent(file, targetBtn) {
    activeSandboxFile = file;

    // Remove active tab highlight from list
    if (elements.sandboxList) {
        Array.from(elements.sandboxList.children).forEach(child => {
            child.classList.remove('bg-[#00ff9d]/20', 'border-[#00ff9d]/40', 'text-[#00ff9d]');
        });
        if (targetBtn) {
            targetBtn.classList.add('bg-[#00ff9d]/20', 'border-[#00ff9d]/40', 'text-[#00ff9d]');
        }
    }
    
    // Clear navbar attention badge AND blink when user inspects sandbox
    if (elements.sandboxNavBadge) {
        elements.sandboxNavBadge.classList.add('hidden');
    }
    clearSandboxNavBlink();
    
    try {
        const response = await fetch(`${API_BASE}/api/sandbox/content?path=${encodeURIComponent(file.path)}`);
        const data = await response.json();
        
        // Populate Header Toolbar
        if (elements.sandboxFileHeader) {
            elements.sandboxFileHeader.classList.remove('hidden');
        }
        if (elements.sandboxFileName) {
            elements.sandboxFileName.innerText = file.name;
        }
        if (elements.sandboxFilePath) {
            elements.sandboxFilePath.innerText = `langneurons/sandbox/${file.relative_path}`;
        }
        if (elements.sandboxFileIcon) {
            elements.sandboxFileIcon.innerText = getFileIcon(file.name);
        }

        // Setup Copy Code Button
        if (elements.sandboxCopyCodeBtn) {
            elements.sandboxCopyCodeBtn.onclick = () => {
                navigator.clipboard.writeText(data.content);
                elements.sandboxCopyCodeBtn.innerHTML = `<span class="material-symbols-outlined !text-xs">check</span> Copied!`;
                setTimeout(() => {
                    elements.sandboxCopyCodeBtn.innerHTML = `<span class="material-symbols-outlined !text-xs">content_copy</span> Copy Code`;
                }, 2000);
            };
        }

        // Render code with line numbers
        const lines = data.content.split('\n');
        const formattedCode = lines.map((line, idx) => {
            const lineNum = (idx + 1).toString().padStart(3, ' ');
            const escapedLine = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            return `<div class="flex items-start gap-3 hover:bg-[#00ff9d]/5 px-2 py-0.5 rounded"><span class="text-gray-600 select-none font-mono w-8 text-right shrink-0">${lineNum}</span><span class="font-mono text-gray-200 whitespace-pre leading-relaxed">${escapedLine || ' '}</span></div>`;
        }).join('');

        if (elements.sandboxBody) {
            elements.sandboxBody.innerHTML = `
                <div class="bg-[#05130d] border border-[#00ff9d]/20 rounded-xl p-3 shadow-inner font-mono text-xs space-y-0.5">
                    ${formattedCode}
                </div>
            `;
        }
    } catch (e) {
        if (elements.sandboxBody) {
            elements.sandboxBody.innerHTML = `<div class="p-6 text-red-400 font-mono text-xs">Failed to load file contents: ${e.message}</div>`;
        }
    }
}
/**
 * Removes the sandbox nav blink animation.
 */
function clearSandboxNavBlink() {
    const navBtn = document.getElementById('sandbox-nav-btn');
    if (navBtn) navBtn.classList.remove('sandbox-nav-blink');
}

/**
 * Triggers a real-time floating toast notification and navbar badge when an agent creates code.
 */
export function triggerSandboxNotification(fileName, filePath) {
    // 1. Show navbar attention badge + blink the nav button
    if (elements.sandboxNavBadge) {
        elements.sandboxNavBadge.classList.remove('hidden');
    }
    const navBtn = document.getElementById('sandbox-nav-btn');
    if (navBtn) {
        // Remove first to restart animation if already blinking
        navBtn.classList.remove('sandbox-nav-blink');
        // Force reflow so the animation restarts fresh
        void navBtn.offsetWidth;
        navBtn.classList.add('sandbox-nav-blink');
    }

    // 2. Refresh file list in background
    loadSandboxExplorerTree();

    // 3. Display Floating Toast Notification
    if (elements.sandboxCodeToast && elements.sandboxToastMsg) {
        elements.sandboxToastMsg.innerText = `Check the code! Agent created/modified: ${fileName}`;
        elements.sandboxCodeToast.classList.remove('hidden', '-translate-y-4');
        elements.sandboxCodeToast.classList.add('translate-y-0');

        // Handle "View Code" button click on toast
        if (elements.sandboxToastViewBtn) {
            elements.sandboxToastViewBtn.onclick = () => {
                // Switch to Sandbox tab & clear blink
                const sandboxTabBtn = document.querySelector('[data-tab="sandbox"]');
                if (sandboxTabBtn) sandboxTabBtn.click();
                clearSandboxNavBlink();

                // Open file in Monaco IDE
                openFileInMonaco({ name: fileName, path: filePath, relative_path: fileName });

                // Hide toast
                elements.sandboxCodeToast.classList.add('hidden', '-translate-y-4');
            };
        }

        if (elements.sandboxToastCloseBtn) {
            elements.sandboxToastCloseBtn.onclick = () => {
                elements.sandboxCodeToast.classList.add('hidden', '-translate-y-4');
            };
        }

        // Auto-hide toast after 8 seconds
        setTimeout(() => {
            if (elements.sandboxCodeToast) {
                elements.sandboxCodeToast.classList.add('hidden', '-translate-y-4');
            }
        }, 8000);
    }
}

function getFileIcon(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    switch (ext) {
        case 'py': return 'code';
        case 'json': return 'data_object';
        case 'js':
        case 'ts': return 'javascript';
        case 'html': return 'html';
        case 'css': return 'style';
        case 'sh': return 'terminal';
        case 'md': return 'description';
        default: return 'draft';
    }
}

export async function compileSwarm(payload) {
    const response = await fetch(`${API_BASE}/api/swarm/compile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    return await response.json();
}
