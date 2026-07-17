const { Client, LocalAuth } = require('whatsapp-web.js');
const path = require('path');

const SESSION_DIR = path.join(__dirname, '..', '..', '..', 'sandbox', 'auth', 'whatsapp_session');
const targetNumber = process.argv[2]; // Phone number (e.g. 91XXXXXXXXXX)
const message = process.argv[3];      // Alert text

const fs = require('fs');

if (!targetNumber || !message) {
    console.error('❌ Usage: node whatsapp_send.js <phone_number> "<message>"');
    process.exit(1);
}

// Self-healing: remove lingering puppeteer lock if left by crashed/killed processes
const lockPath = path.join(SESSION_DIR, 'session', 'SingletonLock');
if (fs.existsSync(lockPath)) {
    try {
        fs.unlinkSync(lockPath);
        console.log('🔓 Lingering browser lock (SingletonLock) released successfully.');
    } catch (err) {
        console.log('⚠️ Note: browser lock file detected but could not be removed (might be active):', err.message);
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

client.on('ready', async () => {
    try {
        const sender = client.info && client.info.wid ? client.info.wid._serialized : "Unknown Sender";
        console.log(`📡 Logged in as Sender: ${sender}`);

        // Resolve target JID dynamically
        console.log(`📡 Resolving recipient: ${targetNumber}...`);
        const numberId = await client.getNumberId(targetNumber);
        if (!numberId) {
            console.error(`❌ Recipient number ${targetNumber} could not be resolved!`);
            await client.destroy();
            process.exit(1);
        }

        console.log(`📡 Resolved Recipient JID: ${numberId._serialized}`);
        await client.sendMessage(numberId._serialized, message);
        console.log(`✅ Message sent! Sender: ${sender} -> Receiver: ${numberId._serialized}`);
        await client.destroy();
        process.exit(0);
    } catch (err) {
        console.error('❌ Failed to send message:', err);
        await client.destroy();
        process.exit(1);
    }
});

client.on('auth_failure', async (msg) => {
    console.error('❌ Auth failure on send:', msg);
    await client.destroy();
    process.exit(1);
});

client.initialize();
