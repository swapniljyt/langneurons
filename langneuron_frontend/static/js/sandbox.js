/**
 * LangNeurons Sandbox IDE Workspace
 * Professional VS Code-style File Explorer + Monaco Editor + AI Code Assistant
 */

import { API_BASE } from './state.js?v=20260717j';

let monacoEditor = null;
let activeFileNode = null;
let openTabs = []; // Array of { path, name, relative_path, isDirty: false }
let activeTabPath = null;
let sandboxTreeData = null;
let expandedFolders = new Set(); // Stores expanded folder paths

/**
 * Initializes the Monaco Editor and Sandbox IDE Workspace listeners.
 */
export function initSandboxIDE() {
    const container = document.getElementById('monaco-editor-container');
    if (!container) return;

    // Load Monaco Editor via RequireJS
    if (window.require) {
        window.require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs' } });
        window.require(['vs/editor/editor.main'], function () {
            createMonacoInstance();
        });
    }

    // Bind UI Controls
    bindSandboxControls();

    // Load Initial Explorer Tree
    loadSandboxExplorerTree();
}

/**
 * Creates the Monaco Editor Instance inside #monaco-editor-container.
 */
function createMonacoInstance() {
    const container = document.getElementById('monaco-editor-container');
    if (!container || monacoEditor) return;

    monacoEditor = window.monaco.editor.create(container, {
        value: '',
        language: 'python',
        theme: 'vs-dark',
        automaticLayout: true,
        fontSize: 13,
        fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        lineNumbers: 'on',
        renderLineHighlight: 'all',
        tabSize: 4,
        insertSpaces: true,
        smoothScrolling: true,
        cursorBlinking: 'smooth',
    });

    // Listen for cursor position changes to update Status Bar
    monacoEditor.onDidChangeCursorPosition((e) => {
        const cursorEl = document.getElementById('sandbox-status-cursor');
        if (cursorEl) {
            cursorEl.innerText = `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
        }
    });

    // Listen for model content changes to mark tabs dirty
    monacoEditor.onDidChangeModelContent(() => {
        if (activeTabPath) {
            const tab = openTabs.find(t => t.path === activeTabPath);
            if (tab && !tab.isDirty) {
                tab.isDirty = true;
                renderSandboxTabs();
            }
        }
    });
}

/**
 * Binds Sandbox UI Action buttons.
 */
function bindSandboxControls() {
    // Refresh Explorer
    const refreshBtn = document.getElementById('sandbox-refresh-btn');
    if (refreshBtn) {
        refreshBtn.onclick = () => loadSandboxExplorerTree();
    }

    // Save File
    const saveBtn = document.getElementById('sandbox-save-file-btn');
    if (saveBtn) {
        saveBtn.onclick = () => saveActiveSandboxFile();
    }

    // File Search Filter
    const searchInput = document.getElementById('sandbox-file-search');
    if (searchInput) {
        searchInput.oninput = (e) => filterSandboxTree(e.target.value.trim().toLowerCase());
    }

    // New File
    const newFileBtn = document.getElementById('sandbox-new-file-btn');
    if (newFileBtn) {
        newFileBtn.onclick = () => createNewItem(false);
    }

    // New Folder
    const newFolderBtn = document.getElementById('sandbox-new-folder-btn');
    if (newFolderBtn) {
        newFolderBtn.onclick = () => createNewItem(true);
    }

    // AI Assistant Quick Action Buttons
    const aiActions = {
        'ai-btn-explain': 'explain',
        'ai-btn-summarize': 'summarize',
        'ai-btn-refactor': 'refactor',
        'ai-btn-fix': 'fix'
    };

    Object.entries(aiActions).forEach(([btnId, action]) => {
        const btn = document.getElementById(btnId);
        if (btn) {
            btn.onclick = () => runAiAssistantAction(action);
        }
    });

    // AI Ask Input
    const aiInput = document.getElementById('sandbox-ai-input');
    const aiSendBtn = document.getElementById('sandbox-ai-send-btn');
    if (aiSendBtn && aiInput) {
        const sendQuestion = () => {
            const q = aiInput.value.trim();
            if (q) {
                runAiAssistantAction('ask', q);
                aiInput.value = '';
            }
        };
        aiSendBtn.onclick = sendQuestion;
        aiInput.onkeydown = (e) => {
            if (e.key === 'Enter') sendQuestion();
        };
    }

    // Toast Close Button
    const toastCloseBtn = document.getElementById('sandbox-toast-close-btn');
    if (toastCloseBtn) {
        toastCloseBtn.onclick = () => {
            const toast = document.getElementById('sandbox-code-toast');
            if (toast) toast.classList.add('hidden');
        };
    }
}

/**
 * Loads the full Explorer Tree from /api/sandbox/tree.
 */
export async function loadSandboxExplorerTree() {
    const container = document.getElementById('sandbox-tree-container');
    if (!container) return;

    try {
        const response = await fetch(`${API_BASE}/api/sandbox/tree`);
        if (!response.ok) throw new Error('Failed to load sandbox tree');

        sandboxTreeData = await response.json();
        renderSandboxTree(sandboxTreeData, container);
    } catch (e) {
        console.error('Error loading sandbox tree:', e);
        container.innerHTML = `<div class="p-4 text-center text-red-400 font-mono text-xs">Error loading file tree</div>`;
    }
}

/**
 * Renders the hierarchical tree view into the container.
 */
function renderSandboxTree(node, container) {
    container.innerHTML = '';
    if (!node || !node.children || node.children.length === 0) {
        container.innerHTML = `<div class="p-4 text-center text-gray-500 font-mono text-xs italic">Empty sandbox folder</div>`;
        return;
    }

    const ul = document.createElement('ul');
    ul.className = 'space-y-0.5';

    node.children.forEach(child => {
        ul.appendChild(createTreeNodeElement(child, 0));
    });

    container.appendChild(ul);
}

/**
 * Creates a single tree node HTML element (Folder or File).
 */
function createTreeNodeElement(itemNode, depth = 0) {
    const li = document.createElement('li');
    const isFolder = itemNode.type === 'directory';
    const isExpanded = expandedFolders.has(itemNode.path);

    const row = document.createElement('div');
    const isSelected = activeTabPath === itemNode.path;

    row.className = `group flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-colors font-mono text-xs ${
        isSelected
            ? 'bg-[#00ff9d]/20 text-[#00ff9d] font-semibold border-l-2 border-[#00ff9d]'
            : 'text-gray-300 hover:bg-[#091f15] hover:text-white'
    }`;
    row.style.paddingLeft = `${depth * 14 + 8}px`;

    // Icon & Label
    const leftGroup = document.createElement('div');
    leftGroup.className = 'flex items-center gap-1.5 truncate flex-1';

    if (isFolder) {
        const chevron = document.createElement('span');
        chevron.className = 'material-symbols-outlined text-gray-400 !text-xs transition-transform transform duration-150';
        chevron.innerText = isExpanded ? 'expand_more' : 'chevron_right';
        leftGroup.appendChild(chevron);

        const folderIcon = document.createElement('span');
        folderIcon.className = `material-symbols-outlined !text-sm ${isExpanded ? 'text-[#00ff9d]' : 'text-amber-400'}`;
        folderIcon.innerText = isExpanded ? 'folder_open' : 'folder';
        leftGroup.appendChild(folderIcon);
    } else {
        const fileIcon = document.createElement('span');
        fileIcon.className = `material-symbols-outlined !text-sm ${getFileIconColor(itemNode.name)}`;
        fileIcon.innerText = getFileIconSymbol(itemNode.name);
        leftGroup.appendChild(fileIcon);
    }

    const nameSpan = document.createElement('span');
    nameSpan.className = 'truncate text-[11.5px]';
    nameSpan.innerText = itemNode.name;
    leftGroup.appendChild(nameSpan);

    row.appendChild(leftGroup);

    // Delete item action on hover
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-red-400 transition-opacity';
    deleteBtn.title = 'Delete';
    deleteBtn.innerHTML = `<span class="material-symbols-outlined !text-xs">delete</span>`;
    deleteBtn.onclick = (e) => {
        e.stopPropagation();
        deleteItem(itemNode);
    };
    row.appendChild(deleteBtn);

    li.appendChild(row);

    // If folder is expanded, render children recursively
    if (isFolder && isExpanded && itemNode.children) {
        const childrenUl = document.createElement('ul');
        childrenUl.className = 'space-y-0.5 pl-1 border-l border-[#00ff9d]/10 ml-3.5';
        itemNode.children.forEach(child => {
            childrenUl.appendChild(createTreeNodeElement(child, depth + 1));
        });
        li.appendChild(childrenUl);
    }

    // Click handler
    row.onclick = () => {
        if (isFolder) {
            if (expandedFolders.has(itemNode.path)) {
                expandedFolders.delete(itemNode.path);
            } else {
                expandedFolders.add(itemNode.path);
            }
            if (sandboxTreeData) {
                renderSandboxTree(sandboxTreeData, document.getElementById('sandbox-tree-container'));
            }
        } else {
            openFileInMonaco(itemNode);
        }
    };

    return li;
}

/**
 * Opens a file node in Monaco Editor and manages tabs.
 */
export async function openFileInMonaco(fileNode) {
    if (!fileNode || !fileNode.path) return;

    activeFileNode = fileNode;
    activeTabPath = fileNode.path;

    // Add to open tabs if not present
    let tab = openTabs.find(t => t.path === fileNode.path);
    if (!tab) {
        tab = {
            path: fileNode.path,
            name: fileNode.name,
            relative_path: fileNode.relative_path || fileNode.name,
            isDirty: false
        };
        openTabs.push(tab);
    }

    renderSandboxTabs();
    updateBreadcrumbs(tab.relative_path);
    updateStatusBar(fileNode);

    // Hide empty state
    const emptyState = document.getElementById('sandbox-empty-state');
    if (emptyState) emptyState.classList.add('hidden');

    try {
        const res = await fetch(`${API_BASE}/api/sandbox/content?path=${encodeURIComponent(fileNode.path)}`);
        if (!res.ok) throw new Error('Failed to fetch file content');
        const data = await res.json();

        if (monacoEditor) {
            const lang = detectMonacoLanguage(fileNode.name);
            const model = window.monaco.editor.createModel(data.content, lang);
            monacoEditor.setModel(model);
        }
    } catch (e) {
        console.error('Error opening file in Monaco:', e);
    }

    // Re-render tree to highlight selected file
    if (sandboxTreeData) {
        renderSandboxTree(sandboxTreeData, document.getElementById('sandbox-tree-container'));
    }
}

/**
 * Renders the Tab strip at top of editor.
 */
function renderSandboxTabs() {
    const tabsBar = document.getElementById('sandbox-tabs-bar');
    if (!tabsBar) return;

    tabsBar.innerHTML = '';
    if (openTabs.length === 0) {
        tabsBar.innerHTML = `<div class="px-3 text-[11px] font-mono text-gray-500 italic">No files open</div>`;
        const emptyState = document.getElementById('sandbox-empty-state');
        if (emptyState) emptyState.classList.remove('hidden');
        return;
    }

    openTabs.forEach(tab => {
        const tabEl = document.createElement('div');
        const isActive = tab.path === activeTabPath;

        tabEl.className = `group flex items-center gap-2 px-3 py-1.5 border-r border-[#00ff9d]/15 cursor-pointer text-xs font-mono transition-all ${
            isActive
                ? 'bg-[#040c08] text-[#00ff9d] border-t-2 border-t-[#00ff9d] font-bold'
                : 'bg-[#081710] text-gray-400 hover:text-gray-200 hover:bg-[#0a1e14]'
        }`;

        const icon = document.createElement('span');
        icon.className = `material-symbols-outlined !text-xs ${getFileIconColor(tab.name)}`;
        icon.innerText = getFileIconSymbol(tab.name);
        tabEl.appendChild(icon);

        const title = document.createElement('span');
        title.className = 'truncate max-w-[120px]';
        title.innerText = tab.name;
        tabEl.appendChild(title);

        if (tab.isDirty) {
            const dot = document.createElement('span');
            dot.className = 'w-2 h-2 rounded-full bg-[#00ff9d] inline-block';
            tabEl.appendChild(dot);
        }

        const closeBtn = document.createElement('button');
        closeBtn.className = 'text-gray-500 hover:text-red-400 rounded p-0.5 opacity-60 hover:opacity-100 transition-all';
        closeBtn.innerHTML = `<span class="material-symbols-outlined !text-xs">close</span>`;
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            closeTab(tab.path);
        };
        tabEl.appendChild(closeBtn);

        tabEl.onclick = () => {
            openFileInMonaco(tab);
        };

        tabsBar.appendChild(tabEl);
    });
}

/**
 * Closes an open tab.
 */
function closeTab(path) {
    openTabs = openTabs.filter(t => t.path !== path);
    if (activeTabPath === path) {
        if (openTabs.length > 0) {
            openFileInMonaco(openTabs[openTabs.length - 1]);
        } else {
            activeTabPath = null;
            renderSandboxTabs();
            if (monacoEditor) monacoEditor.setValue('');
        }
    } else {
        renderSandboxTabs();
    }
}

/**
 * Updates top Breadcrumb navigation.
 */
function updateBreadcrumbs(relativePath) {
    const bar = document.getElementById('sandbox-breadcrumbs-bar');
    if (!bar) return;

    const parts = ['sandbox', ...relativePath.split(/[/\\]/).filter(Boolean)];
    bar.innerHTML = parts.map((part, index) => {
        const isLast = index === parts.length - 1;
        return `
            <span class="${isLast ? 'text-white font-bold' : 'text-gray-400'}">${part}</span>
            ${!isLast ? '<span class="text-gray-600">/</span>' : ''}
        `;
    }).join('');
}

/**
 * Updates Bottom Status Bar info.
 */
function updateStatusBar(fileNode) {
    const langEl = document.getElementById('sandbox-status-lang');
    const fileEl = document.getElementById('sandbox-status-file');

    if (langEl) langEl.innerText = detectMonacoLanguage(fileNode.name).toUpperCase();
    if (fileEl) fileEl.innerText = fileNode.relative_path || fileNode.name;
}

/**
 * Saves active file content via POST /api/sandbox/save.
 */
async function saveActiveSandboxFile() {
    if (!activeTabPath || !monacoEditor) return;

    const content = monacoEditor.getValue();
    try {
        const res = await fetch(`${API_BASE}/api/sandbox/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: activeTabPath, content })
        });

        if (!res.ok) throw new Error('Failed to save file');

        const tab = openTabs.find(t => t.path === activeTabPath);
        if (tab) {
            tab.isDirty = false;
            renderSandboxTabs();
        }

        showToastNotification('File saved successfully.');
    } catch (e) {
        console.error('Error saving file:', e);
    }
}

/**
 * Triggers AI Assistant Actions for the open code file.
 */
async function runAiAssistantAction(action, question = '') {
    if (!activeTabPath || !monacoEditor) {
        alert('Please open a file in the editor first!');
        return;
    }

    const outputEl = document.getElementById('sandbox-ai-output');
    if (!outputEl) return;

    outputEl.innerHTML = `
        <div class="flex items-center gap-2 text-[#00ff9d] font-mono text-xs animate-pulse">
            <span class="material-symbols-outlined !text-base">psychology</span>
            <span>AI Analyzing ${action}...</span>
        </div>
    `;

    try {
        const res = await fetch(`${API_BASE}/api/sandbox/ai-assist`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action,
                file_path: activeTabPath,
                content: monacoEditor.getValue(),
                question
            })
        });

        if (!res.ok) throw new Error('AI Assistant request failed');
        const data = await res.json();

        outputEl.innerHTML = `
            <div class="bg-[#091f15] border border-[#00ff9d]/25 rounded-lg p-3 font-sans text-xs text-gray-200 space-y-2 select-text shadow-md">
                ${formatMarkdown(data.result)}
            </div>
        `;
    } catch (e) {
        console.error('Error in AI Assistant action:', e);
        outputEl.innerHTML = `<div class="text-red-400 font-mono text-xs">AI Request Failed</div>`;
    }
}

/**
 * Creates a new file or folder in sandbox.
 */
async function createNewItem(isDirectory) {
    const name = prompt(`Enter ${isDirectory ? 'Folder' : 'File'} name:`);
    if (!name) return;

    try {
        const res = await fetch(`${API_BASE}/api/sandbox/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                parent_path: '',
                name,
                is_directory: isDirectory
            })
        });

        if (res.ok) {
            loadSandboxExplorerTree();
        }
    } catch (e) {
        console.error('Error creating item:', e);
    }
}

/**
 * Deletes a file or folder.
 */
async function deleteItem(itemNode) {
    if (!confirm(`Are you sure you want to delete ${itemNode.name}?`)) return;

    try {
        const res = await fetch(`${API_BASE}/api/sandbox/delete`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: itemNode.path })
        });

        if (res.ok) {
            closeTab(itemNode.path);
            loadSandboxExplorerTree();
        }
    } catch (e) {
        console.error('Error deleting item:', e);
    }
}

/**
 * Displays floating notification toast.
 */
function showToastNotification(msg) {
    const toast = document.getElementById('sandbox-code-toast');
    const msgEl = document.getElementById('sandbox-toast-msg');
    if (toast && msgEl) {
        msgEl.innerText = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3000);
    }
}

/**
 * Language & Icon Helpers
 */
function detectMonacoLanguage(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const langMap = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'tsx': 'typescript',
        'jsx': 'javascript',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'md': 'markdown',
        'sh': 'shell',
        'sql': 'sql'
    };
    return langMap[ext] || 'plaintext';
}

function getFileIconSymbol(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'py': 'code',
        'html': 'html',
        'css': 'css',
        'js': 'javascript',
        'ts': 'javascript',
        'json': 'data_object',
        'md': 'description',
        'sh': 'terminal'
    };
    return iconMap[ext] || 'description';
}

function getFileIconColor(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const colorMap = {
        'py': 'text-emerald-400',
        'html': 'text-amber-400',
        'css': 'text-blue-400',
        'js': 'text-yellow-400',
        'ts': 'text-cyan-400',
        'json': 'text-purple-400',
        'md': 'text-teal-400',
        'sh': 'text-gray-300'
    };
    return colorMap[ext] || 'text-[#00ff9d]';
}

function formatMarkdown(text) {
    return text.replace(/\n/g, '<br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code class="bg-[#05140c] text-[#00ff9d] px-1 py-0.5 rounded">$1</code>');
}
