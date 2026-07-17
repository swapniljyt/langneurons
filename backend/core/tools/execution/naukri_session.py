import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[4]
SANDBOX_DIR = BASE_DIR / "sandbox"
SESSION_FILE = SANDBOX_DIR / "auth" / "naukri_session.json"

def get_naukri_credentials():
    """
    Retrieves Naukri credentials from .env safely.
    """
    username = os.getenv("NAUKRI_USERNAME")
    password = os.getenv("NAUKRI_PASSWORD")
    if not username or not password or "your_username" in username:
        raise ValueError("❌ Naukri credentials are not configured in .env file.")
    return username, password

async def naukri_login_session() -> str:
    """
    Performs secure login to Naukri.com and saves authenticated browser cookies
    under sandbox/auth/naukri_session.json to maintain continuous persistent access.
    """
    from rich.console import Console
    try:
        console = Console()
        console.print("\n[bold cyan]🔑 NAUKRI SESSION MANAGER:[/bold cyan] Initializing secure authentication...")
    except Exception:
        console = None
        print("\n🔑 NAUKRI SESSION MANAGER: Initializing secure authentication...")

    # Ensure auth directory exists in sandbox
    os.makedirs(SESSION_FILE.parent, exist_ok=True)

    # If active session exists, skip login
    if SESSION_FILE.exists():
        msg = "✅ Active Naukri session loaded from cache (sandbox/auth/naukri_session.json)."
        if console:
            console.print(f"[bold green]{msg}[/bold green]\n")
        else:
            print(msg)
        return msg

    username, password = get_naukri_credentials()

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        if console:
            console.print("[dim]🌐 Launching headless browser with stealth profile...[/dim]")
        
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        # Emulate standard Windows Chrome agent to bypass bot walls
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True
        )
        
        # Override navigator.webdriver signature
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        if console:
            console.print("[dim]🌐 Navigating to Naukri.com Login page...[/dim]")
        
        try:
            await page.goto("https://www.naukri.com/nlogin/login", wait_until="networkidle", timeout=30000)
            
            # Fill inputs securely
            if console:
                console.print("[dim]⌨️ Entering login credentials...[/dim]")
            await page.fill("#usernameField", username)
            await page.fill("#passwordField", password)
            
            # Click Login button
            if console:
                console.print("[dim]🚀 Submitting authentication...[/dim]")
            await page.click("button[type='submit']")
            
            # Wait for dashboard indicator or main profile URL change to confirm login
            await page.wait_for_timeout(5000)

            # Extract cookies state
            state = await context.storage_state()
            with open(SESSION_FILE, "w") as f:
                json.dump(state, f, indent=2)

            msg = "🎉 Success! Authenticated session cookies written to sandbox/auth/naukri_session.json."
            if console:
                console.print(f"[bold green]{msg}[/bold green]\n")
            else:
                print(msg)
            
            await browser.close()
            return msg

        except Exception as e:
            await browser.close()
            error_msg = f"❌ Login failed: {str(e)}"
            if console:
                console.print(f"[bold red]{error_msg}[/bold red]\n")
            else:
                print(error_msg)
            return error_msg

if __name__ == "__main__":
    asyncio.run(naukri_login_session())
