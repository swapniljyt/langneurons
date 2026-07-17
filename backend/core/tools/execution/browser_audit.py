"""
core/tools/execution/browser_audit.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Visual layout and browser compatibility audit tool using Playwright and Google Gemini Vision.
"""

import os
import base64
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from ..filesystem.read_write import SANDBOX_DIR, _register_file_in_manifest


@tool
def browser_vision_audit(url: str = "http://localhost:3000", output_image_name: str = "visual_audit.png") -> str:
    """
    Performs a live browser visual audit of the rendered website using Playwright and Google Gemini Vision.
    Captures full-page screenshots, audits console logs, captures network response errors,
    analyzes visual layout/alignment discrepancies, contrast/legibility, and generates a concrete
    visual layout report with exact CSS and HTML technical fixes.

    Args:
        url: The local or remote URL of the website to audit (e.g. 'http://localhost:3000').
        output_image_name: The filename to save the screenshot inside the 'docs/' directory (e.g. 'visual_audit.png').
    """
    from rich.console import Console
    try:
        console = Console()
        console.print(f"\n[bold magenta]👁️  BROWSER VISION AUDIT:[/bold magenta] [cyan]{url}[/cyan]")
    except ImportError:
        console = None
        print(f"\n👁️  BROWSER VISION AUDIT: {url}")

    # ── 1. Create Output Paths in sandbox/docs/ ────────────────────────────────
    docs_dir = Path(SANDBOX_DIR) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    screenshot_path = docs_dir / output_image_name
    report_path = docs_dir / "visual_audit_report.md"

    # Register generated files in the workspace manifest
    try:
        _register_file_in_manifest(str(screenshot_path.relative_to(SANDBOX_DIR)))
        _register_file_in_manifest(str(report_path.relative_to(SANDBOX_DIR)))
    except Exception:
        pass

    # ── 2. Run Playwright to capture screenshot & logs ─────────────────────────
    console_logs = []
    network_errors = []

    async def run_playwright():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            
            # Listen to console errors and warnings
            page.on("console", lambda msg: console_logs.append(f"[{msg.type.upper()}] {msg.text}"))
            
            # Listen to network failures and non-2xx responses
            page.on("requestfailed", lambda req: network_errors.append(f"Request failed: {req.url} - {req.failure if req.failure else 'Unknown error'}"))
            page.on("response", lambda res: network_errors.append(f"Response error: {res.url} Status: {res.status}") if res.status >= 400 else None)
            
            if console:
                console.print(f"[dim]🌐 Navigating to {url}...[/dim]")
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                if console:
                    console.print(f"[bold red]⚠️ Navigation timeout or warning:[/bold red] [dim]{e}[/dim]")
                network_errors.append(f"Navigation warning: {str(e)}")
            
            # Allow animations/transitions to settle
            await page.wait_for_timeout(2000)
            
            # Capture full page screenshot
            await page.screenshot(path=str(screenshot_path), full_page=True)
            await browser.close()

    try:
        # Run async playwright inside synchronous LangChain tool wrapper
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If running in a Jupyter/asyncio context
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(run_playwright())
        else:
            asyncio.run(run_playwright())
    except Exception as e:
        return f"❌ Playwright failed to capture browser page: {str(e)}"

    if console:
        console.print(f"[bold green]📸 Screenshot captured successfully at sandbox/docs/{output_image_name}[/bold green]")
        console.print(f"[dim]   Console Logs: {len(console_logs)} | Network Errors: {len(network_errors)}[/dim]")

    # ── 3. Call Vision API using Unified LLMConnector ─────────────────────────
    if console:
        console.print("[dim]🤖 Invoking Unified LLMConnector Vision model for visual design audit...[/dim]")

    try:
        from ...llm.connector import LLMConnector
        llm = LLMConnector.get_llm(purpose="vision")
    except Exception as e:
        return f"❌ Failed to initialize unified vision LLM instance: {str(e)}"

    try:
        
        # Read and encode the captured screenshot to base64
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        prompt = f"""
        You are an elite, highly experienced Lead Frontend QA Auditor and Senior Visual Designer.
        Your mission is to perform a meticulous visual layout, centering, alignment, and pixel-perfection audit
        for the rendered web page at {url}.
        
        COLLECTED CONSOLE LOGS:
        {chr(10).join(console_logs) if console_logs else 'None'}
        
        COLLECTED NETWORK ERRORS:
        {chr(10).join(network_errors) if network_errors else 'None'}
        
        INSTRUCTIONS FOR YOUR REPORT:
        1. **Meticulous Section-by-Section Visual Breakdown:** 
           Identify ANY misalignment, centering errors (e.g. grids shifted to the left, margins unbalanced, off-center titles),
           flexbox/grid distribution bugs, or padding/margin inconsistencies.
        2. **Premium Design Analysis:**
           Assess contrast, text legibility, card glow effects, neon borders, and glassmorphism styling against modern UI best practices.
        3. **Functional Logs Audit:**
           Explain if any of the collected console logs or network status warnings affect the rendering or backend APIs.
        4. **Actionable CSS/HTML Technical Patches:**
           Provide exact, copy-pasteable CSS rules or HTML structure fixes to completely resolve the layout misalignments.
        
        Format your response as a professional, beautiful Markdown Audit Report. Focus on visual precision and developer-friendly code fixes.
        """
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        )
        
        response = llm.invoke([message])
        report_content = response.content

        # Write audit report to docs/visual_audit_report.md
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        if console:
            console.print("[bold green]✅ Visual layout audit completed. Report saved to sandbox/docs/visual_audit_report.md[/bold green]\n")

        return report_content
    except Exception as e:
        return f"❌ Failed to run Gemini Vision audit: {str(e)}"
