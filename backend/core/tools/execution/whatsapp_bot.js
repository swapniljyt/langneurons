const { Client, LocalAuth } = require('whatsapp-web.js');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const SESSION_DIR = path.join(__dirname, '..', '..', '..', 'sandbox', 'auth', 'whatsapp_session');
const envPath = path.join(__dirname, '..', '..', '..', '.env');

// Parse target phone number directly from .env safely without dependencies
let targetNumber = '919648844873';
if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const match = envContent.match(/USER_WHATSAPP_NUMBER=["']?(\d+)["']?/);
    if (match && match[1]) {
        targetNumber = match[1];
    }
}

console.log(`🤖 INITIALIZING WHATSAPP CHATBOT INTERFACE...`);
console.log(`📂 Session cache path: ${SESSION_DIR}`);
console.log(`🎯 Recipient Target: ${targetNumber}\n`);

// Self-healing: remove lingering puppeteer lock if left by crashed/killed processes
const lockPath = path.join(SESSION_DIR, 'session', 'SingletonLock');
if (fs.existsSync(lockPath)) {
    try {
        fs.unlinkSync(lockPath);
        console.log('🔓 Lingering browser lock (SingletonLock) released successfully.');
    } catch (err) {
        console.log('⚠️ Note: browser lock file detected but could not be removed:', err.message);
    }
}

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: SESSION_DIR
    }),
    puppeteer: {
        headless: true,
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    }
});

// Helper function to invoke the LangNeurons swarm via the python bridge
function executeAgentSwarm(query) {
    return new Promise((resolve, reject) => {
        const pythonPath = path.join(__dirname, '..', '..', '..', 'venv', 'bin', 'python');
        const scriptPath = path.join(__dirname, '..', '..', '..', 'entrypoints', 'query_naukri_broker.py');
        
        console.log(`⚙️ Executing Swarm with query: "${query}"...`);
        const pyProcess = spawn(pythonPath, [scriptPath, query]);
        
        let stdout = '';
        let stderr = '';
        
        pyProcess.stdout.on('data', (data) => {
            stdout += data.toString();
        });
        
        pyProcess.stderr.on('data', (data) => {
            stderr += data.toString();
        });
        
        pyProcess.on('close', (code) => {
            if (code !== 0) {
                console.error(`❌ Swarm process exited with code ${code}. Error: ${stderr}`);
                resolve(`❌ Swarm Execution Error:\n${stderr || 'Unknown error'}`);
            } else {
                resolve(stdout.trim());
            }
        });
    });
}

// Unified command handler
async function handleUserCommand(chatId, commandText) {
    console.log(`💬 Intercepted command in chat [${chatId}]: "${commandText}"`);
    
    // Send a subtle typing indicator/acknowledgment so the user knows the swarm is thinking
    await client.sendPresenceAvailable();
    
    const response = await executeAgentSwarm(commandText);
    const replyText = `Agent: ${response}`;
    
    await client.sendMessage(chatId, replyText);
    console.log(`✅ Sent reply back to chat [${chatId}]`);
}

client.on('ready', async () => {
    console.log('\n🎉 SUCCESS! WhatsApp Agent Chatbot is fully online and listening! 🚀\n');
    
    const targetJid = `${targetNumber}@c.us`;
    const selfJid = client.info.wid._serialized;
    
    // Greet the user to let them know the system is alive
    const greeting = 'Agent: Hii! Your LangNeurons Job Broker Swarm is now ONLINE and listening in this chat! 🤖🚀\n\nType any message or command (e.g. "status", "apply", "start") to interact with me directly!';
    
    try {
        console.log(`📡 Sending welcome greeting to self-chat...`);
        await client.sendMessage(selfJid, greeting);
    } catch (err) {
        console.log(`⚠️ Note: could not send self-chat greeting. Attempting to greet target recipient JID...`);
        try {
            await client.sendMessage(targetJid, greeting);
        } catch (targetErr) {
            console.error(`❌ Could not deliver initial greeting:`, targetErr.message);
        }
    }
});

// 1. Listen for incoming messages from the target phone number
client.on('message', async (msg) => {
    const targetJid = `${targetNumber}@c.us`;
    if (msg.from === targetJid && !msg.body.startsWith('Agent:')) {
        await handleUserCommand(msg.from, msg.body);
    }
});

// 2. Listen for messages sent by ourselves in self-chat (Message Yourself)
client.on('message_create', async (msg) => {
    const selfJid = client.info.wid._serialized;
    const isSelfChat = msg.to === selfJid && msg.fromMe;
    
    if (isSelfChat && !msg.body.startsWith('Agent:')) {
        await handleUserCommand(selfJid, msg.body);
    }
});

client.on('auth_failure', (msg) => {
    console.error('❌ Authentication failed:', msg);
    process.exit(1);
});

client.on('disconnected', (reason) => {
    console.error('❌ Client was disconnected:', reason);
    process.exit(1);
});

client.initialize();
