import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Setup dialog listener to automatically accept all alerts
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        
        print("🚀 Navigating to http://localhost:8000/console.html ...")
        await page.goto("http://localhost:8000/console.html")
        
        # Take screenshot of login page
        await page.screenshot(path="login_page.png")
        print("📸 Screenshot saved: login_page.png")
        
        # Fill credentials
        print("🔑 Logging in as admin / admin...")
        await page.fill("#username-input", "admin")
        await page.fill("#password-input", "admin")
        await page.click("#submit-btn")
        
        # Wait for the console layout to become visible (removing .hide class)
        print("⏳ Waiting for console dashboard to load...")
        await page.wait_for_selector("#console-layout:not(.hide)", timeout=10000)
        await page.screenshot(path="dashboard_loaded.png")
        print("📸 Screenshot saved: dashboard_loaded.png")
        
        # Click on Try It Out tab (nav item with data-tab="tryout")
        print("👉 Clicking on 'Try It Out' tab...")
        await page.click(".nav-item[data-tab='tryout']")
        await page.wait_for_selector("#tab-tryout.active")
        
        # Create a node programmatically
        print("🧠 Creating 'chat' neuron programmatically...")
        await page.evaluate("createNode('chat', 100, 100)")
        
        # Fill formation brief
        print("📝 Filling formation brief...")
        await page.fill("#formation-brief", "Find information about Westeros Kings")
        await page.screenshot(path="tryout_canvas_with_node.png")
        print("📸 Screenshot saved: tryout_canvas_with_node.png")
        
        # Click compile button
        print("⚙️ Compiling swarm tree...")
        await page.click("#compile-btn")
        
        # Wait for compilation to complete (run button enabled)
        print("⏳ Waiting for compilation completion (run button active)...")
        await page.wait_for_selector("#run-btn:not([disabled])", timeout=120000)
        await page.screenshot(path="compilation_done.png")
        print("📸 Screenshot saved: compilation_done.png")
        
        # Double-click the node to open Inspector
        print("🔍 Double-clicking the neuron to open inspector...")
        await page.dblclick("#neuron_1")
        await page.wait_for_selector("#inspector-modal.active")
        
        # Switch to Modular Prompt (LLD) tab
        print("📑 Switching to Modular Prompt (LLD) tab...")
        await page.click(".inspector-tab[data-content='modular']")
        await page.wait_for_selector("#inspector-modular.active")
        
        # Capture screenshot of inspector
        await page.screenshot(path="inspector_modular_prompt.png")
        print("📸 Screenshot saved: inspector_modular_prompt.png")
        
        # Get content of modular prompt section 1
        sec_header = await page.inner_text(".modular-section-header")
        print(f"✅ Found section: {sec_header}")
        
        # Close inspector
        await page.click(".close-modal")
        
        # Execute swarm
        print("⚡ Running swarm execution...")
        await page.click("#run-btn")
        
        # Wait 10 seconds for websocket log streams
        print("⏳ Waiting for WebSocket log streams to populate...")
        await asyncio.sleep(10)
        await page.screenshot(path="execution_logs.png")
        print("📸 Screenshot saved: execution_logs.png")
        
        # Get terminal output lines
        output_text = await page.inner_text("#terminal-output")
        print("\n=== TERMINAL OUTPUT ===")
        print(output_text[:500] + "...")
        print("=======================\n")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
