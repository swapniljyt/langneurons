/* ==========================================================================
   LangNeurons — Unified Client Authentication Helper
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inject Modal HTML into the DOM
    injectAuthModal();

    // 2. Initialize Navigation elements based on Auth State
    updateAuthUI();

    // 3. Intercept direct console/dashboard links
    bindLaunchConsoleLinks();
});

let destinationUrl = '/console.html';

/**
 * Checks if the user is currently logged in.
 */
function isUserLoggedIn() {
    return !!sessionStorage.getItem('token');
}

/**
 * Injects a premium glassmorphic authentication modal into the document body.
 */
function injectAuthModal() {
    // Auth is now managed via the dedicated /login.html page
}

/**
 * Redirects to the login page with the destination URL as query param.
 */
function openAuthModal(dest = '/console.html') {
    window.location.href = `/login.html?redirect=${encodeURIComponent(dest)}`;
}

/**
 * Scans page and intercepts clicks on links or buttons targeting console.html.
 */
function bindLaunchConsoleLinks() {
    // Intercept buttons or links referencing /console.html
    const elements = document.querySelectorAll('[onclick*="/console.html"], [href*="console.html"]');
    elements.forEach(el => {
        // Remove direct onclick redirect if not signed in
        if (el.hasAttribute('onclick') && el.getAttribute('onclick').includes('/console.html')) {
            el.removeAttribute('onclick');
            el.addEventListener('click', (e) => {
                e.preventDefault();
                if (isUserLoggedIn()) {
                    window.location.href = '/console.html';
                } else {
                    openAuthModal('/console.html');
                }
            });
        }
        
        if (el.hasAttribute('href') && el.getAttribute('href').includes('console.html')) {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                if (isUserLoggedIn()) {
                    window.location.href = '/console.html';
                } else {
                    openAuthModal('/console.html');
                }
            });
        }
    });
}

/**
 * Updates UI headers, footers and navigation links dynamically depending on Auth state.
 */
function updateAuthUI() {
    const isLoggedIn = isUserLoggedIn();
    
    // Find headers/nav links where we can inject Sign In/Out button
    const headers = document.querySelectorAll('header nav');
    headers.forEach(nav => {
        // Check if we already injected the button
        let authLink = nav.querySelector('#dynamic-auth-btn');
        if (!authLink) {
            // Find division line or button to insert next to
            const consoleBtn = nav.querySelector('button');
            if (consoleBtn) {
                authLink = document.createElement('a');
                authLink.id = 'dynamic-auth-btn';
                authLink.className = 'text-body-sm font-semibold text-on-surface-variant hover:text-primary transition-colors cursor-pointer mr-2';
                nav.insertBefore(authLink, consoleBtn.previousElementSibling || consoleBtn);
            }
        }
        
        if (authLink) {
            if (isLoggedIn) {
                const username = sessionStorage.getItem('username') || 'admin';
                authLink.innerHTML = `<span class="opacity-60 text-xs font-mono mr-2">[${username}]</span>Sign Out`;
                authLink.onclick = handleSignOut;
            } else {
                authLink.innerHTML = 'Sign In';
                authLink.onclick = () => openAuthModal('/console.html');
            }
        }
    });

    // Mobile Drawer buttons
    const drawers = document.querySelectorAll('#main-drawer nav');
    drawers.forEach(nav => {
        let authBtn = nav.querySelector('#drawer-dynamic-auth-btn');
        if (!authBtn) {
            authBtn = document.createElement('a');
            authBtn.id = 'drawer-dynamic-auth-btn';
            authBtn.className = 'flex items-center gap-md p-sm text-on-surface-variant hover:bg-surface-variant transition-all duration-200 rounded-xl cursor-pointer';
            nav.appendChild(authBtn);
        }

        if (isLoggedIn) {
            authBtn.innerHTML = `
                <span class="material-symbols-outlined text-red-400">logout</span>
                <span class="font-body-md font-semibold text-red-400">Sign Out</span>
            `;
            authBtn.onclick = handleSignOut;
        } else {
            authBtn.innerHTML = `
                <span class="material-symbols-outlined text-[#94d4b4]">login</span>
                <span class="font-body-md font-semibold">Sign In</span>
            `;
            authBtn.onclick = () => {
                if (typeof toggleDrawer === 'function') toggleDrawer();
                openAuthModal('/console.html');
            };
        }
    });
}

/**
 * Handle user Sign Out
 */
async function handleSignOut(e) {
    if (e) e.preventDefault();
    const token = sessionStorage.getItem('token');
    if (token) {
        try {
            await fetch(`${window.location.origin}/api/auth/logout?token=${token}`, { method: 'POST' });
        } catch(err) {}
    }
    sessionStorage.clear();
    updateAuthUI();
    window.location.href = '/';
}
