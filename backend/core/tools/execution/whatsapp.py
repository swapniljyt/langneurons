import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.tools import tool

_DIR = Path(__file__).resolve().parent

@tool
def whatsapp_user_chat(message: str) -> str:
    """
    Sends a direct message or status notification to the user via their linked WhatsApp Web chatbot.
    Use this to notify the user of successful applications, ask questions, or report status updates.
    
    Args:
        message: The status notification or message text to send to the user (e.g. "Agent: Hii, I have successfully applied to 5 jobs!").
    """
    load_dotenv()
    phone_number = os.getenv("USER_WHATSAPP_NUMBER", "919648844873")
    
    # Clean non-digits
    clean_number = "".join(filter(str.isdigit, phone_number))
    if not clean_number:
        clean_number = "919648844873"
        
    script_path = _DIR / "whatsapp_send.js"
    try:
        res = subprocess.run(
            ["node", str(script_path), clean_number, message],
            capture_output=True,
            text=True,
            check=True
        )
        return f"✅ Notification successfully sent to user: {res.stdout.strip()}"
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        return f"❌ Failed to notify user via WhatsApp: {err_msg}"

@tool
def send_whatsapp_web_message(phone_number: str, message: str) -> str:
    """
    Sends a direct message alert to a WhatsApp phone number using your authenticated WhatsApp Web client session.
    
    Args:
        phone_number: The target WhatsApp phone number with no symbols, including country code (e.g. "919876543210").
        message: The textual alert message to deliver.
    """
    script_path = _DIR / "whatsapp_send.js"
    try:
        res = subprocess.run(
            ["node", str(script_path), phone_number, message],
            capture_output=True,
            text=True,
            check=True
        )
        return f"✅ WhatsApp message delivered: {res.stdout.strip()}"
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        return f"❌ Failed to dispatch WhatsApp message via Web Client: {err_msg}"

