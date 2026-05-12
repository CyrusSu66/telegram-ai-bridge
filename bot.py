import telebot
import subprocess
import time
import os
import sys
import json
import threading
import requests
import websocket
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
# RESPONSE_FILE is kept only for backward compatibility directory creation
RESPONSE_FILE = os.path.abspath(config.get("response_file", "response.txt"))
ARCHIVE_TRIGGER_FILE = os.path.join(os.path.dirname(RESPONSE_FILE), "archive_trigger.txt")

bot = telebot.TeleBot(BOT_TOKEN)

# --- CDP Global State ---
active_ws_url = None
available_targets = []
current_chat_id = None
CHAT_ID_FILE = "chat_id.txt"

def load_chat_id():
    global current_chat_id
    try:
        if os.path.exists(CHAT_ID_FILE):
            with open(CHAT_ID_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    current_chat_id = int(content)
    except:
        pass
    return current_chat_id

def save_chat_id(chat_id):
    global current_chat_id
    if current_chat_id != chat_id:
        current_chat_id = chat_id
        try:
            with open(CHAT_ID_FILE, "w") as f:
                f.write(str(chat_id))
        except:
            pass

def ensure_antigravity_running(chat_id=None):
    try:
        r = requests.get('http://localhost:7800/json', timeout=2)
        if r.status_code == 200:
            return True, False
    except Exception:
        pass
        
    if chat_id:
        try:
            bot.send_message(chat_id, "⏳ 偵測到 Antigravity 尚未啟動，正在為您執行冷啟動...")
        except:
            pass
    print("Antigravity debug port not reachable. Attempting to start...")
    subprocess.Popen(["/Applications/Antigravity.app/Contents/MacOS/Electron", "--remote-debugging-port=7800", "--remote-allow-origins=*"], start_new_session=True)
    
    for i in range(10):
        time.sleep(2)
        try:
            if requests.get('http://localhost:7800/json', timeout=2).status_code == 200:
                print("Antigravity started successfully.")
                time.sleep(2) # Give it a moment to load pages
                return True, True
        except Exception:
            pass
    print("Failed to start Antigravity.")
    return False, False

def get_active_ws_url(chat_id=None, was_just_started=False):
    global active_ws_url, available_targets
    try:
        r = requests.get('http://localhost:7800/json', timeout=2)
        targets = [t for t in r.json() if t.get('type') == 'page' and not t.get('url', '').startswith('devtools://')]
        available_targets = targets
        
        if targets and (not active_ws_url or was_just_started):
            selected_idx = 0
            target = targets[selected_idx]
            active_ws_url = target.get('webSocketDebuggerUrl')
            
            if chat_id and was_just_started:
                reply = "✅ Bot 與 Antigravity 連線成功！\n\n🖥 目前可用視窗清單：\n"
                for i, t in enumerate(targets):
                    title = t.get('title', 'Unknown')
                    reply += f"[{i}] {title}\n"
                reply += f"\n🎯 自動鎖定對象：[{selected_idx}] {target.get('title', 'Unknown')}\n(如需變更，請使用 /switch 指令)"
                bot.send_message(chat_id, reply)
                
    except Exception as e:
        print(f"Error fetching targets: {e}")
    return active_ws_url

def type_message_to_agent_cdp(message_text, chat_id, was_just_started=False):
    ws_url = get_active_ws_url(chat_id, was_just_started)
    if not ws_url:
        print("No active WebSocket URL found.")
        return False
        
    try:
        ws = websocket.create_connection(ws_url)
        
        # 0. Fetch the last block BEFORE we send the new message
        script_get_last = """
        (function() {
            let blocks = Array.from(document.querySelectorAll('.rendered-markdown, .markdown-body, .prose, .leading-relaxed.select-text'))
                              .filter(b => b.innerText.trim().length > 0 && !(b.className && typeof b.className === 'string' && b.className.includes('opacity-70')));
            if (blocks.length > 0) {
                return blocks[blocks.length - 1].innerText;
            }
            return "";
        })();
        """
        ws.send(json.dumps({
            "id": 99,
            "method": "Runtime.evaluate",
            "params": {"expression": script_get_last, "returnByValue": True}
        }))
        resp = json.loads(ws.recv())
        previous_last_text = resp.get("result", {}).get("result", {}).get("value", "")

        # 1. Focus input box
        script = """
        (function() {
            let el = document.querySelector('[contenteditable="true"].cursor-text');
            if(!el) {
                let els = document.querySelectorAll('textarea, [contenteditable="true"]');
                for(let e of els) {
                    if(e.className && typeof e.className === 'string' && !e.className.includes('ime-text-area') && !e.className.includes('xterm')) {
                        el = e; break;
                    }
                }
            }
            if(el) { el.focus(); return true; }
            return false;
        })();
        """
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": script}
        }))
        ws.recv() 
        
        # 2. Insert Text
        ws.send(json.dumps({
            "id": 2,
            "method": "Input.insertText",
            "params": {"text": message_text}
        }))
        ws.recv()
        
        # 3. Press Enter (add proper key definitions for React/Electron)
        ws.send(json.dumps({
            "id": 3,
            "method": "Input.dispatchKeyEvent",
            "params": {
                "type": "rawKeyDown",
                "windowsVirtualKeyCode": 13,
                "key": "Enter",
                "code": "Enter"
            }
        }))
        ws.recv()
        
        ws.send(json.dumps({
            "id": 4,
            "method": "Input.dispatchKeyEvent",
            "params": {
                "type": "char",
                "windowsVirtualKeyCode": 13,
                "key": "Enter",
                "code": "Enter",
                "unmodifiedText": "\r",
                "text": "\r"
            }
        }))
        ws.recv()
        
        ws.send(json.dumps({
            "id": 5,
            "method": "Input.dispatchKeyEvent",
            "params": {
                "type": "keyUp",
                "windowsVirtualKeyCode": 13,
                "key": "Enter",
                "code": "Enter"
            }
        }))
        ws.recv()
        
        ws.close()
        
        # Start response polling thread
        threading.Thread(target=poll_response_cdp, args=(chat_id, ws_url, previous_last_text)).start()
        return True
    except Exception as e:
        print(f"CDP Error: {e}")
        return False

def poll_response_cdp(chat_id, ws_url, previous_last_text):
    print("Starting response polling...")
    try:
        time.sleep(2) 
        ws = websocket.create_connection(ws_url)
        
        last_text = ""
        same_count = 0
        
        script = """
        (function() {
            let blocks = Array.from(document.querySelectorAll('.rendered-markdown, .markdown-body, .prose, .leading-relaxed.select-text'))
                              .filter(b => b.innerText.trim().length > 0 && !(b.className && typeof b.className === 'string' && b.className.includes('opacity-70')));
            if (blocks.length > 0) {
                return blocks[blocks.length - 1].innerText;
            }
            return "";
        })();
        """
        
        for i in range(30): 
            ws.send(json.dumps({
                "id": 100+i,
                "method": "Runtime.evaluate",
                "params": {"expression": script, "returnByValue": True}
            }))
            resp = json.loads(ws.recv())
            current_text = resp.get("result", {}).get("result", {}).get("value", "")
            
            if current_text == previous_last_text:
                time.sleep(2)
                continue
                
            if current_text and current_text == last_text:
                same_count += 1
            elif current_text:
                last_text = current_text
                same_count = 0
                
            if same_count >= 3: 
                break
                
            time.sleep(2)
            
        ws.close()
        
        if last_text:
            bot.send_message(chat_id, f"🤖 Agent 回應：\n\n{last_text}")
        else:
            bot.send_message(chat_id, "⚠️ 無法讀取回覆，可能需要更新 UI 定位路徑。")
            
    except Exception as e:
        print(f"Polling error: {e}")

class ArchiveTriggerHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = 0

    def on_modified(self, event):
        if event.src_path != ARCHIVE_TRIGGER_FILE:
            return
        current_time = time.time()
        if current_time - self.last_modified < 2.0:
            return
        self.last_modified = current_time

        try:
            with open(ARCHIVE_TRIGGER_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return

            print(f"[ArchiveTrigger] 收到歸檔指令，透過 CDP 靜默打入 Antigravity...")
            type_message_to_agent_cdp(content, current_chat_id)

            with open(ARCHIVE_TRIGGER_FILE, "w", encoding="utf-8") as f:
                f.write("")

        except Exception as e:
            print(f"[ArchiveTrigger] Error: {e}")

class NotificationHandler(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.txt'):
            return
            
        chat_id = current_chat_id
        if not chat_id:
            print("[Notification] 推播失敗：找不到有效的 current_chat_id")
            return
            
        time.sleep(0.5)
        try:
            with open(event.src_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
            if content:
                print(f"[Notification] 收到通知，正在推播：{content[:30]}...")
                self.bot.send_message(chat_id, f"🔔 **背景推播通知**\n\n{content}", parse_mode="Markdown")
                
            os.remove(event.src_path)
            
        except Exception as e:
            print(f"[Notification] Error: {e}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 嗨！我是 Antigravity Bridge Bot。\n傳送任何訊息給我，我會轉交給電腦前的 Agent。\n可使用 /list 查詢視窗，/switch <id> 切換視窗。")

@bot.message_handler(commands=['list'])
def list_windows(message):
    try:
        r = requests.get('http://localhost:7800/json', timeout=2)
        targets = [t for t in r.json() if t.get('type') == 'page' and not t.get('url', '').startswith('devtools://')]
        global available_targets
        available_targets = targets
        
        if not targets:
            bot.reply_to(message, "沒有找到可用的視窗。")
            return
            
        reply = "🖥 **可用視窗清單**：\n"
        for i, t in enumerate(targets):
            title = t.get('title', 'Unknown')
            reply += f"[{i}] {title}\n"
        bot.reply_to(message, reply)
    except Exception as e:
        bot.reply_to(message, f"❌ 無法取得視窗清單：{e}")

@bot.message_handler(commands=['switch'])
def switch_window(message):
    global active_ws_url, available_targets
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "請提供視窗編號，例如：/switch 0")
            return
            
        idx = int(parts[1])
        target = available_targets[idx]
        active_ws_url = target.get('webSocketDebuggerUrl')
        bot.reply_to(message, f"✅ 已切換至視窗：{target.get('title')}")
    except Exception as e:
        bot.reply_to(message, f"❌ 切換失敗。請先執行 /list，再輸入有效的數字（例如：/switch 0）")

@bot.message_handler(commands=['tasks'])
def send_tasks(message):
    tasks_file = "/Users/cyrus/Workspace/AgentLite/config/tasks.json"
    if not os.path.exists(tasks_file):
        bot.reply_to(message, "目前沒建立任何任務追蹤紀錄。")
        return
        
    try:
        import fcntl
        with open(tasks_file, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
                
        tasks = data.get("tasks", {})
        if not tasks:
            bot.reply_to(message, "目前沒有正在追蹤的活動任務。")
            return
            
        status_icons = {
            "pending": "⏳",
            "running": "🏃",
            "completed": "✅",
            "error": "❌"
        }
        
        reply_lines = ["📋 **AgentLite Task List**\n"]
        sorted_tasks = sorted(tasks.items(), key=lambda item: (item[1].get('status') == 'completed', item[1].get('created_at', '')), reverse=False)
        
        for tid, tinfo in sorted_tasks:
            icon = status_icons.get(tinfo.get('status', 'pending'), '❓')
            line = f"{icon} `{tid[-4:]}` **{tinfo.get('name', 'Unknown Task')}**\n"
            line += f"   └ Status: `{tinfo.get('status', 'unknown')}` | Owner: `{tinfo.get('owner', 'main_agent')}`"
            if tinfo.get('result'):
                line += f"\n   └ Result: {tinfo['result']}"
            reply_lines.append(line)
            
        bot.reply_to(message, "\n".join(reply_lines), parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"查無任務資料庫或錯誤：{e}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global current_chat_id
    
    chat_id = message.chat.id
    save_chat_id(chat_id)
    user_text = message.text.strip()
    
    if not user_text:
        return

    bot.reply_to(message, "收到指令，轉送中... 🚀")
    
    is_running, was_just_started = ensure_antigravity_running(chat_id)
    if is_running:
        success = type_message_to_agent_cdp(user_text, chat_id, was_just_started)
        if not success:
            bot.reply_to(message, "❌ 寫入失敗，請確認 Antigravity 除錯埠與網路連線。")
    else:
        bot.reply_to(message, "❌ 無法喚醒或連線到 Antigravity 除錯伺服器。")

if __name__ == "__main__":
    for filepath in [RESPONSE_FILE, ARCHIVE_TRIGGER_FILE]:
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write("")

    watch_dir = os.path.dirname(RESPONSE_FILE)
    notify_dir = os.path.join(os.path.dirname(watch_dir), "AgentLite", "config", "notifications")
    os.makedirs(notify_dir, exist_ok=True)
    
    observer = Observer()
    observer.schedule(ArchiveTriggerHandler(), path=watch_dir, recursive=False)
    observer.schedule(NotificationHandler(bot), path=notify_dir, recursive=False)
    observer.start()
    print("Started file observers (archive_trigger, notifications).")

    print("Initializing bot state...")
    saved_chat_id = load_chat_id()
    is_running, was_just_started = ensure_antigravity_running(saved_chat_id)
    if is_running:
        get_active_ws_url(saved_chat_id, was_just_started=True)

    print("Bot is running...")
    while True:
        try:
            bot.infinity_polling(none_stop=True, interval=3, timeout=30)
        except KeyboardInterrupt:
            print("Bot stopped by user.")
            observer.stop()
            observer.join()
            break
        except Exception as e:
            print(f"Polling error: {e}. Retrying in 15 seconds...")
            time.sleep(15)
