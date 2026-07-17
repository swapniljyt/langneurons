export const API_BASE = window.location.origin;

// Application State
export const appState = {
    token: sessionStorage.getItem('token') || 'demo-token',
    username: sessionStorage.getItem('username') || 'admin',
    nodes: [],
    connections: [],
    selectedNodeId: null,
    draggingNode: null,
    dragOffset: { x: 0, y: 0 },
    connectingFromNodeId: null,
    tempLine: null,
    nodeCounter: 1,
    ws: null,

    // Compile-run configuration (set from Compile Settings Modal)
    formationBrief: '',
    sessionId: 'ecommerce_build_session',
    thinkingMode: true,
    compiled: false,
    activeScriptPath: null,
    useAutoTree: false,
    autoNeuronCount: 15,
    autoBranchFactor: 2
};

// Default Agent Templates Properties
export const AGENT_DEFAULTS = {
    agent: { role: 'new_agent_neuron', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    chat: { role: 'task_coordinator', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    architect: { role: 'lead_architect', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    writer: { role: 'backend_developer', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    runner: { role: 'devops_engineer', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    researcher: { role: 'web_researcher', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    analyst: { role: 'data_analyst', provider: 'moonshot', model: 'moonshot/kimi-k2.5' },
    tester: { role: 'quality_assurance_bot', provider: 'moonshot', model: 'moonshot/kimi-k2.5' }
};
