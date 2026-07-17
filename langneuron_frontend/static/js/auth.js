import { API_BASE, appState } from './state.js?v=20260717j';
import { elements } from './dom.js?v=20260717j';
import { loadDocs } from './api.js?v=20260717j';
import { loadSandboxExplorerTree } from './sandbox.js?v=20260717j';
import { setupCanvasDragAndDrop } from './canvas.js?v=20260717j';

export function showLoginLayout() {
    window.location.href = `/login.html?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
}

export function showConsoleLayout() {
    if (elements.loginContainer) elements.loginContainer.classList.remove('active');
    if (elements.consoleLayout) elements.consoleLayout.classList.remove('hide');
    if (elements.usernameDisplay) elements.usernameDisplay.textContent = appState.username || 'admin';
    
    // Load tabs initial views
    if (typeof loadDocs === 'function') loadDocs();
    if (typeof loadSandboxExplorerTree === 'function') loadSandboxExplorerTree();
    if (typeof setupCanvasDragAndDrop === 'function') setupCanvasDragAndDrop();
}

export async function handleLoginSubmit(e) {
    e.preventDefault();
    const username = elements.usernameInput.value;
    const password = elements.passwordInput.value;
    
    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            appState.token = data.token;
            appState.username = data.username;
            sessionStorage.setItem('token', data.token);
            sessionStorage.setItem('username', data.username);
            elements.loginError.classList.add('hide');
            showConsoleLayout();
        } else {
            const err = await response.json();
            elements.loginError.textContent = err.detail || 'Login failed';
            elements.loginError.classList.remove('hide');
        }
    } catch (err) {
        elements.loginError.textContent = 'Could not connect to API server';
        elements.loginError.classList.remove('hide');
    }
}

export async function handleLogout() {
    try {
        await fetch(`${API_BASE}/api/auth/logout?token=${appState.token}`, { method: 'POST' });
    } catch(e) {}
    
    appState.token = null;
    appState.username = null;
    sessionStorage.clear();
    showLoginLayout();
}
