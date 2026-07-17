const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const path = require('path');

const SESSION_DIR = path.join(__dirname, '..', '..', '..', 'sandbox', 'auth', 'whatsapp_session');

const fs = require('fs');

console.log('\n🤖 INITIALIZING WHATSAPP WEB CLIENT...');
console.log(`📂 Session cache path: ${SESSION_DIR}\n`);

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
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// Generate and display scannable QR Code in terminal
client.on('qr', (qr) => {
    console.log('\n📸 SCAN THIS QR CODE WITH YOUR WHATSAPP APP (Linked Devices):');
    qrcode.generate(qr, { small: true });
    console.log('💡 Note: Keep this terminal open until scanned. Once successfully scanned, the session is saved permanently.');
});

client.on('ready', () => {
    console.log('\n🎉 SUCCESS! WhatsApp Web client is logged in and ready!');
    process.exit(0);
});

client.on('auth_failure', (msg) => {
    console.error('\n❌ Authentication failure:', msg);
    process.exit(1);
});

client.initialize();
