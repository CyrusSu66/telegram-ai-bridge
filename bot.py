import telebot
import pyautogui
import subprocess
import time
import os
import sys
import pyperclip
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import json

# --- CONFIGURATION ---
try:
    with open("config.json", "r") as f:
        config = json.load(f)
    print("Configuration loaded successfully.")
except FileNotFoundError:
    print("Error: config.json not found!")
    sys.exit(1)

BOT_TOKEN = config.get("bot_token")
AGENT_APP_NAME = config.get("agent_app_name", "Antigravity")
RESPONSE_FILE = os.path.abspath(config.get("response_file", "response.txt"))

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)

def focus_agent_window():
    """
    Uses AppleScript to bring the Agent window to the front.
    """
    script = f'tell application "{AGENT_APP_NAME}" to activate'
    try:
        subprocess.run(['osascript', '-e', script], check=True)
        time.sleep(0.5) # Wait for window transition
        return True
    except subprocess.CalledProcessError:
        print(f"Error: Could not focus application '{AGENT_APP_NAME}'")
        return False

def type_message_to_agent(message, chat_id):
    """
    Types the message into the focused window.
    Appends an instruction to write the response to a file.
    """
    instruction = f"\n(此指令來自 Telegram User {chat_id}。請執行並將回應寫入以下檔案，不要只在對話框回應：{RESPONSE_FILE})"
    full_text = message + instruction
    
    # Safety Check: Ensure we are not typing into a random window if focus failed
    # But for simplicity in this MVP, we assume focus_agent_window worked.
    
    # Type the message
    # Use Clipboard Paste method to support Chinese and special characters correctly
    try:
        pyperclip.copy(full_text)
        time.sleep(0.3) # Wait for clipboard update
        
        # Simulate Cmd+V (Paste) on Mac using AppleScript (More robust)
        script = 'tell application "System Events" to keystroke "v" using command down'
        subprocess.run(['osascript', '-e', script])
        
        time.sleep(0.3)
        pyautogui.press('enter')
    except Exception as e:
        print(f"Error during paste: {e}")
        # Fallback if clipboard fails (unlikely)
        pyautogui.write(full_text)
        pyautogui.press('enter')

class ResponseHandler(FileSystemEventHandler):
    """
    Monitors the response file for changes.
    """
    def __init__(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
        self.last_modified = 0

    def on_modified(self, event):
        if event.src_path == RESPONSE_FILE:
            # Debounce: avoid reading multiple times for one save
            current_time = time.time()
            if current_time - self.last_modified < 1.0:
                return
            self.last_modified = current_time

            print(f"Response file modified. Reading content...")
            try:
                with open(RESPONSE_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if content.strip():
                    self.bot.send_message(self.chat_id, f"🤖 Agent 回應：\n\n{content}")
                    # Optional: Clear file after sending to avoid re-sending old data? 
                    # For now, we keep it. Agent usually overwrites.
            except Exception as e:
                print(f"Error reading response file: {e}")

# Global variable to track the last chat ID to reply to
# Limitation: Simple version supports only one active user conversation at a time for the response loop
current_chat_id = None
observer = None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 嗨！我是 Antigravity Bridge Bot。\n傳送任何訊息給我，我會轉交給電腦前的 Agent。\n\n請確保你的電腦上 Antigravity 視窗已開啟。")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_chat_id, observer
    
    chat_id = message.chat.id
    current_chat_id = chat_id
    user_text = message.text
    
    print(f"Received from {chat_id}: {user_text}")
    

    # Direct forwarding mode: Accept all messages
    clean_text = user_text.strip()
    if not clean_text:
        return


    # 1. Acknowledge
    bot.reply_to(message, "收到指令，轉送中... 🚀")
    
    # 2. Focus Window
    if focus_agent_window():
        # 3. Type Message
        type_message_to_agent(clean_text, chat_id)
        
        # 4. Start Monitoring (if not already running)
        if not observer:
            event_handler = ResponseHandler(bot, chat_id)
            observer = Observer()
            observer.schedule(event_handler, path=os.path.dirname(RESPONSE_FILE), recursive=False)
            observer.start()
            print("Started file observer.")
        else:
            # Update the chat_id in the existing handler? 
            # For simplicity, we just update the global variable or assume single user.
            pass 
            
    else:
        bot.reply_to(message, "❌ 無法切換到 Agent 視窗。請檢查 Antigravity 應用程式是否開啟。")

if __name__ == "__main__":
    # Create empty response file if not exists
    if not os.path.exists(RESPONSE_FILE):
        with open(RESPONSE_FILE, "w") as f:
            f.write("")

    print("Bot is running...")
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        if observer:
            observer.stop()
            observer.join()
