/**
 * api_connect.js — LangNeurons Connect API Section
 * Manages 5 provider cards: OpenAI, Google Gemini, Moonshot, OpenRouter, Amazon Bedrock.
 * Each card has: API key input, model combobox (select + free-text), per-card Save, status badge.
 * One active provider radio selection drives the swarm engine.
 */

// ── Provider model options ────────────────────────────────────────────────────
const PROVIDER_MODELS = {
    openai: {
        router: ['gpt-4o-mini', 'gpt-4o', 'o1-mini', 'o3-mini', 'gpt-4-turbo'],
        exec:   ['gpt-4o', 'gpt-4o-mini', 'o1', 'o3', 'o1-pro', 'gpt-4-turbo']
    },
    gemini: {
        router: ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'],
        exec:   ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']
    },
    moonshot: {
        router: ['kimi-k2.5', 'kimi-latest', 'moonshot-v1-8k'],
        exec:   ['kimi-k2.5', 'kimi-latest', 'moonshot-v1-128k', 'moonshot-v1-32k']
    },
    openrouter: {
        router: ['deepseek/deepseek-chat', 'anthropic/claude-3-5-sonnet', 'meta-llama/llama-3.1-70b-instruct'],
        exec:   ['deepseek/deepseek-r1', 'anthropic/claude-3-5-sonnet', 'openai/gpt-4o', 'google/gemini-2.5-pro']
    },
    bedrock: {
        router: ['amazon.nova-pro-v1:0', 'amazon.nova-lite-v1:0', 'anthropic.claude-3-5-haiku-20241022-v1:0'],
        exec:   ['anthropic.claude-3-5-sonnet-20241022-v2:0', 'anthropic.claude-3-5-haiku-20241022-v1:0', 'amazon.nova-pro-v1:0', 'amazon.titan-text-premier-v1:0']
    }
};

// ── Build a combobox (datalist + input) ───────────────────────────────────────
function buildCombobox(id, options, placeholder) {
    const listId = `${id}-list`;
    return `
        <div class="relative">
            <input type="text" id="${id}" list="${listId}" placeholder="${placeholder}"
                class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs
                       focus:outline-none focus:border-[#00ff9d]/60 focus:shadow-[0_0_8px_rgba(0,255,157,0.15)]
                       transition-all placeholder-gray-600 pr-8">
            <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none text-[10px]">▾</span>
            <datalist id="${listId}">
                ${options.map(o => `<option value="${o}">`).join('')}
            </datalist>
        </div>`;
}

// ── Card builder ─────────────────────────────────────────────────────────────
function buildProviderCard(cfg) {
    const { id, name, icon, accentColor, accentBg, keyPlaceholder, extraFields = '', keyLabel = 'API Key' } = cfg;
    const routerModels = PROVIDER_MODELS[id]?.router || [];
    const execModels   = PROVIDER_MODELS[id]?.exec || [];

    return `
    <div class="provider-card relative rounded-2xl border border-[#1a2e22] bg-[#060d09] overflow-hidden shadow-xl transition-all duration-300 hover:border-[#00ff9d]/30 hover:shadow-[0_0_30px_rgba(0,255,157,0.05)]"
         data-provider="${id}">

        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-[#1a2e22]" style="background: linear-gradient(135deg, ${accentBg} 0%, transparent 60%)">
            <div class="flex items-center gap-3">
                <!-- Active provider radio -->
                <label class="relative flex items-center cursor-pointer" title="Set as active provider">
                    <input type="radio" name="active-provider-radio" value="${id}"
                           class="peer sr-only" id="radio-${id}">
                    <div class="w-4 h-4 rounded-full border-2 border-gray-600 peer-checked:border-[#00ff9d]
                                peer-checked:bg-[#00ff9d] transition-all flex items-center justify-center">
                        <div class="w-1.5 h-1.5 rounded-full bg-[#002114] opacity-0 peer-checked:opacity-100 transition-opacity"></div>
                    </div>
                </label>
                <div class="text-xl">${icon}</div>
                <div>
                    <div class="font-bold text-sm text-white">${name}</div>
                    <div class="text-[9px] font-mono uppercase tracking-wider" style="color:${accentColor}">LLM Provider</div>
                </div>
            </div>
            <div id="status-badge-${id}"
                 class="px-2.5 py-1 rounded-full text-[9px] font-mono font-bold border transition-all
                        bg-[#0a1a0f] border-gray-600 text-gray-500">
                ● NOT CONFIGURED
            </div>
        </div>

        <!-- Body -->
        <div class="p-5 space-y-4">
            <!-- API Key row -->
            <div class="space-y-1.5">
                <div class="flex items-center justify-between">
                    <label class="text-[10px] font-mono uppercase tracking-wider text-gray-400">${keyLabel}</label>
                    <span id="key-masked-${id}" class="text-[9px] font-mono text-gray-600"></span>
                </div>
                <div class="relative">
                    <input type="password" id="key-input-${id}" placeholder="${keyPlaceholder}"
                           class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs
                                  focus:outline-none focus:border-[#00ff9d]/60 focus:shadow-[0_0_8px_rgba(0,255,157,0.15)]
                                  transition-all placeholder-gray-600 pr-9">
                    <button type="button" onclick="toggleKeyVisibility('key-input-${id}', this)"
                            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-[#00ff9d] transition-colors text-xs">
                        <span class="material-symbols-outlined !text-sm">visibility</span>
                    </button>
                </div>
            </div>

            ${extraFields}

            <!-- Model rows -->
            <div class="grid grid-cols-2 gap-3">
                <div class="space-y-1.5">
                    <label class="text-[10px] font-mono uppercase tracking-wider text-gray-400">Router Model</label>
                    ${buildCombobox(`router-model-${id}`, routerModels, routerModels[0] || 'e.g. model-name')}
                    <p class="text-[9px] text-gray-600 font-mono">Task routing & delegation</p>
                </div>
                <div class="space-y-1.5">
                    <label class="text-[10px] font-mono uppercase tracking-wider text-gray-400">Exec / Thinking Model</label>
                    ${buildCombobox(`exec-model-${id}`, execModels, execModels[0] || 'e.g. model-name')}
                    <p class="text-[9px] text-gray-600 font-mono">Complex reasoning & code</p>
                </div>
            </div>

            <!-- Save button + feedback -->
            <div class="flex items-center justify-between pt-2 border-t border-[#1a2e22]">
                <span id="save-msg-${id}" class="text-[10px] font-mono text-[#00ff9d] opacity-0 transition-opacity duration-500"></span>
                <button id="save-btn-${id}" onclick="saveProviderCard('${id}')"
                        class="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold font-mono
                               bg-[#00ff9d]/10 border border-[#00ff9d]/30 text-[#00ff9d]
                               hover:bg-[#00ff9d] hover:text-[#002114] hover:shadow-[0_0_12px_rgba(0,255,157,0.3)]
                               active:scale-95 transition-all duration-200">
                    <span class="material-symbols-outlined !text-sm">save</span> Save
                </button>
            </div>
        </div>
    </div>`;
}

// ── Toggle password visibility ────────────────────────────────────────────────
window.toggleKeyVisibility = function(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPass = input.type === 'password';
    input.type = isPass ? 'text' : 'password';
    btn.innerHTML = `<span class="material-symbols-outlined !text-sm">${isPass ? 'visibility_off' : 'visibility'}</span>`;
};

// ── Save one provider card ───────────────────────────────────────────────────
window.saveProviderCard = async function(providerId) {
    const btn = document.getElementById(`save-btn-${providerId}`);
    const msgEl = document.getElementById(`save-msg-${providerId}`);

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="material-symbols-outlined !text-sm animate-spin">autorenew</span> Saving...';
    }

    // Build payload — always send all per-provider model fields + the key for this card
    const payload = {
        default_provider: document.querySelector('input[name="active-provider-radio"]:checked')?.value || null,
        // Keys (only send if filled)
        openai_key:     (document.getElementById('key-input-openai')?.value || '').trim() || undefined,
        gemini_key:     (document.getElementById('key-input-gemini')?.value || '').trim() || undefined,
        moonshot_key:   (document.getElementById('key-input-moonshot')?.value || '').trim() || undefined,
        openrouter_key: (document.getElementById('key-input-openrouter')?.value || '').trim() || undefined,
        aws_access_key: (document.getElementById('aws-access-key-input')?.value || '').trim() || undefined,
        aws_secret_key: (document.getElementById('aws-secret-key-input')?.value || '').trim() || undefined,
        aws_region:     (document.getElementById('aws-region-input')?.value || '').trim() || undefined,
        // Per-provider models
        openai_router_model:     (document.getElementById('router-model-openai')?.value || '').trim() || undefined,
        openai_exec_model:       (document.getElementById('exec-model-openai')?.value || '').trim() || undefined,
        gemini_router_model:     (document.getElementById('router-model-gemini')?.value || '').trim() || undefined,
        gemini_exec_model:       (document.getElementById('exec-model-gemini')?.value || '').trim() || undefined,
        moonshot_router_model:   (document.getElementById('router-model-moonshot')?.value || '').trim() || undefined,
        moonshot_exec_model:     (document.getElementById('exec-model-moonshot')?.value || '').trim() || undefined,
        openrouter_router_model: (document.getElementById('router-model-openrouter')?.value || '').trim() || undefined,
        openrouter_exec_model:   (document.getElementById('exec-model-openrouter')?.value || '').trim() || undefined,
        bedrock_router_model:    (document.getElementById('router-model-bedrock')?.value || '').trim() || undefined,
        bedrock_exec_model:      (document.getElementById('exec-model-bedrock')?.value || '').trim() || undefined,
    };

    // Strip undefined keys
    Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

    try {
        const resp = await fetch('/api/settings/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();

        if (msgEl) {
            msgEl.textContent = data.success ? '✓ Saved!' : '✗ Error saving';
            msgEl.style.opacity = '1';
            msgEl.style.color = data.success ? '#00ff9d' : '#f87171';
            setTimeout(() => { msgEl.style.opacity = '0'; }, 3000);
        }

        // Clear the key inputs after save (security)
        const keyInput = document.getElementById(`key-input-${providerId}`);
        if (keyInput) keyInput.value = '';
        if (providerId === 'bedrock') {
            ['aws-access-key-input', 'aws-secret-key-input'].forEach(id => {
                const el = document.getElementById(id); if (el) el.value = '';
            });
        }

        // Refresh status badges
        await loadApiStatus();

    } catch (e) {
        if (msgEl) { msgEl.textContent = '✗ Network error'; msgEl.style.opacity = '1'; msgEl.style.color = '#f87171'; }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span class="material-symbols-outlined !text-sm">save</span> Save';
        }
    }
};

// ── Load & render API status ─────────────────────────────────────────────────
async function loadApiStatus() {
    try {
        const resp = await fetch('/api/settings/keys');
        const data = await resp.json();
        if (!data.success) return;
        const k = data.keys;

        const statusMap = {
            openai:     { configured: k.openai_configured,     masked: k.openai_key_masked,     router: k.openai_router_model,     exec: k.openai_exec_model },
            gemini:     { configured: k.gemini_configured,     masked: k.gemini_key_masked,     router: k.gemini_router_model,     exec: k.gemini_exec_model },
            moonshot:   { configured: k.moonshot_configured,   masked: k.moonshot_key_masked,   router: k.moonshot_router_model,   exec: k.moonshot_exec_model },
            openrouter: { configured: k.openrouter_configured, masked: k.openrouter_key_masked, router: k.openrouter_router_model, exec: k.openrouter_exec_model },
            bedrock:    { configured: k.bedrock_configured,    masked: k.aws_access_key_masked, router: k.bedrock_router_model,    exec: k.bedrock_exec_model }
        };

        for (const [pid, info] of Object.entries(statusMap)) {
            const badge = document.getElementById(`status-badge-${pid}`);
            const maskedEl = document.getElementById(`key-masked-${pid}`);

            if (badge) {
                if (info.configured) {
                    badge.className = 'px-2.5 py-1 rounded-full text-[9px] font-mono font-bold border transition-all bg-[#00ff9d]/10 border-[#00ff9d]/40 text-[#00ff9d]';
                    badge.textContent = '● CONNECTED';
                } else {
                    badge.className = 'px-2.5 py-1 rounded-full text-[9px] font-mono font-bold border transition-all bg-[#0a1a0f] border-gray-600 text-gray-500';
                    badge.textContent = '● NOT CONFIGURED';
                }
            }

            if (maskedEl && info.masked) maskedEl.textContent = info.masked;

            // Pre-fill model combos with saved values
            const routerEl = document.getElementById(`router-model-${pid}`);
            const execEl   = document.getElementById(`exec-model-${pid}`);
            if (routerEl && info.router) routerEl.value = info.router;
            if (execEl && info.exec)     execEl.value   = info.exec;
        }

        // Set active provider radio
        if (k.default_provider) {
            const radio = document.getElementById(`radio-${k.default_provider}`);
            if (radio) {
                radio.checked = true;
                highlightActiveCard(k.default_provider);
            }
        }

        // Bedrock region
        if (k.aws_region) {
            const regionEl = document.getElementById('aws-region-input');
            if (regionEl) regionEl.value = k.aws_region;
        }

    } catch (e) {
        console.warn('Failed to load API status:', e);
    }
}

// ── Highlight the active provider card ──────────────────────────────────────
function highlightActiveCard(activeId) {
    document.querySelectorAll('.provider-card').forEach(card => {
        const pid = card.dataset.provider;
        if (pid === activeId) {
            card.classList.add('border-[#00ff9d]/50', 'shadow-[0_0_20px_rgba(0,255,157,0.08)]');
            card.classList.remove('border-[#1a2e22]');
        } else {
            card.classList.remove('border-[#00ff9d]/50', 'shadow-[0_0_20px_rgba(0,255,157,0.08)]');
            card.classList.add('border-[#1a2e22]');
        }
    });
}

// ── Render the full Connect API section ─────────────────────────────────────
export function initConnectAPI() {
    const container = document.getElementById('settings-sec-api');
    if (!container) return;

    // Bedrock extra fields
    const bedrockExtras = `
        <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
                <label class="text-[10px] font-mono uppercase tracking-wider text-gray-400">AWS Access Key ID</label>
                <div class="relative">
                    <input type="password" id="aws-access-key-input" placeholder="AKIA..."
                           class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs
                                  focus:outline-none focus:border-[#00ff9d]/60 transition-all placeholder-gray-600 pr-9">
                    <button type="button" onclick="toggleKeyVisibility('aws-access-key-input', this)"
                            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-[#00ff9d] transition-colors">
                        <span class="material-symbols-outlined !text-sm">visibility</span>
                    </button>
                </div>
            </div>
            <div class="space-y-1.5">
                <label class="text-[10px] font-mono uppercase tracking-wider text-gray-400">AWS Secret Access Key</label>
                <div class="relative">
                    <input type="password" id="aws-secret-key-input" placeholder="wJalrXU..."
                           class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs
                                  focus:outline-none focus:border-[#00ff9d]/60 transition-all placeholder-gray-600 pr-9">
                    <button type="button" onclick="toggleKeyVisibility('aws-secret-key-input', this)"
                            class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-[#00ff9d] transition-colors">
                        <span class="material-symbols-outlined !text-sm">visibility</span>
                    </button>
                </div>
            </div>
        </div>
        <div class="space-y-1.5">
            <label class="text-[10px] font-mono uppercase tracking-wider text-gray-400">AWS Region</label>
            <input type="text" id="aws-region-input" placeholder="e.g. us-east-1"
                   class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs
                          focus:outline-none focus:border-[#00ff9d]/60 transition-all placeholder-gray-600">
        </div>`;

    const CARDS = [
        { id: 'openai',     name: 'OpenAI (ChatGPT)', icon: '🟦', accentColor: '#74c0fc', accentBg: 'rgba(116,192,252,0.04)', keyPlaceholder: 'sk-proj-...' },
        { id: 'gemini',     name: 'Google Gemini',    icon: '🔴', accentColor: '#f59e0b', accentBg: 'rgba(251,191,36,0.04)', keyPlaceholder: 'AIzaSy...' },
        { id: 'moonshot',   name: 'Moonshot (Kimi)',  icon: '🌙', accentColor: '#a78bfa', accentBg: 'rgba(167,139,250,0.04)', keyPlaceholder: 'sk-mq...' },
        { id: 'openrouter', name: 'OpenRouter',       icon: '🔀', accentColor: '#34d399', accentBg: 'rgba(52,211,153,0.04)', keyPlaceholder: 'sk-or-v1-...' },
        { id: 'bedrock',    name: 'Amazon Bedrock',   icon: '🟠', accentColor: '#fb923c', accentBg: 'rgba(251,146,60,0.04)',
          keyPlaceholder: '— uses AWS credentials below —',
          keyLabel: 'AWS Credentials (see fields below)',
          extraFields: bedrockExtras }
    ];

    container.innerHTML = `
        <div class="space-y-6">
            <!-- Section header -->
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-bold text-white flex items-center gap-2">
                        <span class="material-symbols-outlined text-[#00ff9d]">hub</span>
                        Connect LLM Providers
                    </h2>
                    <p class="text-xs text-gray-500 font-mono mt-1">
                        Select one active provider · Configure API keys &amp; models per card · Click Save on each card
                    </p>
                </div>
                <div class="px-3 py-1.5 rounded-lg bg-[#00ff9d]/8 border border-[#00ff9d]/20 text-[10px] font-mono text-[#00ff9d]">
                    <span class="material-symbols-outlined !text-xs align-middle">radio_button_checked</span>
                    Active provider = radio ●
                </div>
            </div>

            <!-- Provider cards grid -->
            <div class="grid grid-cols-1 gap-5">
                ${CARDS.map(c => buildProviderCard(c)).join('')}
            </div>

            <!-- Redis section (unchanged) -->
            <div class="rounded-2xl border border-[#1a2e22] bg-[#060d09] p-5 space-y-4">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <span class="material-symbols-outlined text-[#00ff9d] !text-base">database</span>
                    Redis Cache &amp; Memory
                </h3>
                <div class="grid grid-cols-3 gap-3">
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-mono uppercase text-gray-400">Host</label>
                        <input type="text" id="redis-host-input" placeholder="localhost"
                               class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-[#00ff9d]/60 transition-all">
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-mono uppercase text-gray-400">Port</label>
                        <input type="text" id="redis-port-input" placeholder="6379"
                               class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-[#00ff9d]/60 transition-all">
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-mono uppercase text-gray-400">Password</label>
                        <input type="password" id="redis-password-input" placeholder="No Password"
                               class="w-full bg-[#070d0a] border border-[#1a2e22] rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-[#00ff9d]/60 transition-all">
                    </div>
                </div>
                <div class="flex justify-end">
                    <button id="save-redis-btn" onclick="saveRedis()"
                            class="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold font-mono
                                   bg-[#00ff9d]/10 border border-[#00ff9d]/30 text-[#00ff9d]
                                   hover:bg-[#00ff9d] hover:text-[#002114] active:scale-95 transition-all">
                        <span class="material-symbols-outlined !text-sm">save</span> Save Redis Config
                    </button>
                </div>
            </div>
        </div>`;

    // Wire up radio buttons → highlight active card
    document.querySelectorAll('input[name="active-provider-radio"]').forEach(radio => {
        radio.addEventListener('change', () => highlightActiveCard(radio.value));
    });

    // Bedrock — hide the API key input row (uses AWS creds instead)
    const bedrockKeyRow = document.getElementById('key-input-bedrock');
    if (bedrockKeyRow) bedrockKeyRow.closest('.space-y-1\\.5, .space-y-1').style.display = 'none';

    loadApiStatus();
}

// ── Save Redis only ──────────────────────────────────────────────────────────
window.saveRedis = async function() {
    const btn = document.getElementById('save-redis-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="material-symbols-outlined !text-sm animate-spin">autorenew</span> Saving...'; }
    try {
        const payload = {
            redis_host:     (document.getElementById('redis-host-input')?.value || 'localhost').trim(),
            redis_port:     (document.getElementById('redis-port-input')?.value || '6379').trim(),
            redis_password: (document.getElementById('redis-password-input')?.value || '').trim(),
            default_provider: document.querySelector('input[name="active-provider-radio"]:checked')?.value || undefined
        };
        Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);
        await fetch('/api/settings/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<span class="material-symbols-outlined !text-sm">save</span> Save Redis Config'; }
    }
};
