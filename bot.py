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

def get_debug_port():
    try:
        active_port_file = os.path.expanduser("~/Library/Application Support/Antigravity/DevToolsActivePort")
        if os.path.exists(active_port_file):
            with open(active_port_file, "r") as f:
                lines = f.readlines()
                if lines:
                    return int(lines[0].strip())
    except Exception as e:
        print(f"Error reading active port: {e}")
    return 7800 # fallback

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
    port = get_debug_port()
    try:
        r = requests.get(f'http://localhost:{port}/json', timeout=2)
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
    subprocess.Popen(["/Applications/Antigravity.app/Contents/MacOS/Antigravity"], start_new_session=True)
    
    for i in range(10):
        time.sleep(2)
        port = get_debug_port()
        try:
            if requests.get(f'http://localhost:{port}/json', timeout=2).status_code == 200:
                print("Antigravity started successfully.")
                time.sleep(2) # Give it a moment to load pages
                return True, True
        except Exception:
            pass
    print("Failed to start Antigravity.")
    return False, False

def get_active_ws_url(chat_id=None, was_just_started=False):
    global active_ws_url, available_targets
    port = get_debug_port()
    try:
        r = requests.get(f'http://localhost:{port}/json', timeout=2)
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
        ws = websocket.create_connection(ws_url, suppress_origin=True)
        
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
        
        # 3. Click send button using JS
        click_send_script = """
        (function() {
            let btns = document.querySelectorAll('button, div[role="button"], span');
            for (let b of btns) {
                let text = (b.innerText || b.getAttribute('aria-label') || b.title || "").trim().toLowerCase();
                if (text === 'send message') {
                    b.click();
                    return true;
                }
            }
            let primaryButtons = document.querySelectorAll('.bg-primary');
            for (let pb of primaryButtons) {
                let cls = pb.className || "";
                if (pb.tagName === 'BUTTON' || pb.getAttribute('role') === 'button' || cls.includes('cursor-pointer')) {
                    pb.click();
                    return true;
                }
            }
            return false;
        })();
        """
        ws.send(json.dumps({
            "id": 3,
            "method": "Runtime.evaluate",
            "params": {"expression": click_send_script, "returnByValue": True}
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
        ws = websocket.create_connection(ws_url, suppress_origin=True)
        
        last_text = ""
        same_count = 0
        
        script = """
        (function() {
            let isGenerating = false;
            let buttons = document.querySelectorAll('button, a, [role="button"]');
            for(let b of buttons) {
                let t = (b.title || b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
                if(t === 'cancel' || t === 'stop' || t === 'stop generation') {
                    isGenerating = true;
                    break;
                }
            }
            
            let text = "";
            let blocks = Array.from(document.querySelectorAll('.rendered-markdown, .markdown-body, .prose, .leading-relaxed.select-text'))
                              .filter(b => b.innerText.trim().length > 0 && !(b.className && typeof b.className === 'string' && b.className.includes('opacity-70')));
            if (blocks.length > 0) {
                text = blocks[blocks.length - 1].innerText;
            }
            
            return {isGenerating: isGenerating, text: text};
        })();
        """
        
        for i in range(120): 
            ws.send(json.dumps({
                "id": 100+i,
                "method": "Runtime.evaluate",
                "params": {"expression": script, "returnByValue": True}
            }))
            resp = json.loads(ws.recv())
            val = resp.get("result", {}).get("result", {}).get("value", {})
            if not isinstance(val, dict):
                val = {}
                
            is_generating = val.get("isGenerating", False)
            current_text = val.get("text", "")
            
            if is_generating:
                same_count = 0
                time.sleep(2)
                continue
                
            if current_text == previous_last_text:
                time.sleep(2)
                continue
                
            if current_text and current_text == last_text:
                same_count += 1
            elif current_text:
                last_text = current_text
                same_count = 0
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

available_projects = []

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 嗨！我是 Antigravity Bridge Bot。\n傳送任何訊息給我，我會轉交給電腦前的 Agent。\n可使用 /list 查詢專案項目，/switch <id或名稱> 切換專案。")

@bot.message_handler(commands=['list'])
def list_projects(message):
    global available_projects
    try:
        ws_url = get_active_ws_url()
        if not ws_url:
            bot.reply_to(message, "❌ 未能取得 Antigravity 主網頁目標，請確認 App 是否已開啟。")
            return
            
        ws = websocket.create_connection(ws_url, suppress_origin=True)
        get_projects_script = """
        (function() {
            let projects = [];
            let divs = document.querySelectorAll('div.cursor-pointer');
            divs.forEach(d => {
                let cls = d.className || "";
                if (cls.includes('pl-1 pr-0.5 h-8 shrink-0') && cls.includes('select-none')) {
                    let text = (d.innerText || "").trim().split('\\n')[0];
                    if (text && text.length < 40 && !projects.includes(text)) {
                        projects.push(text);
                    }
                }
            });
            return projects;
        })();
        """
        ws.send(json.dumps({
            "id": 88,
            "method": "Runtime.evaluate",
            "params": {"expression": get_projects_script, "returnByValue": True}
        }))
        res = json.loads(ws.recv())
        ws.close()
        
        projects = res.get("result", {}).get("result", {}).get("value", [])
        available_projects = projects
        
        if not projects:
            bot.reply_to(message, "📂 在側邊欄中沒有找到任何 Project 項目。")
            return
            
        reply = "📁 **可用專案清單 (Projects)**：\n"
        for i, p in enumerate(projects):
            reply += f"[{i}] {p}\n"
        reply += "\n💡 可使用 `/switch <編號或名稱>` 切換至該專案。"
        bot.reply_to(message, reply)
    except Exception as e:
        bot.reply_to(message, f"❌ 無法取得專案清單：{e}")

@bot.message_handler(commands=['switch'])
def switch_project(message):
    global available_projects
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "請提供專案編號或名稱，例如：\n`/switch 0` 或 `/switch VPL`")
            return
            
        arg = parts[1]
        target_name = ""
        if arg.isdigit():
            idx = int(arg)
            if idx < 0 or idx >= len(available_projects):
                bot.reply_to(message, f"❌ 數字超出範圍，請先執行 /list 取得正確的清單。")
                return
            target_name = available_projects[idx]
        else:
            target_name = arg
            
        ws_url = get_active_ws_url()
        if not ws_url:
            bot.reply_to(message, "❌ 未能取得 Antigravity 主網頁目標。")
            return
            
        ws = websocket.create_connection(ws_url, suppress_origin=True)
        click_script = f"""
        (function() {{
            try {{
                let targetProjName = {json.dumps(target_name.lower())};
                let cards = document.querySelectorAll('[data-project-card="true"]');
                let targetCard = null;
                for (let c of cards) {{
                    let name = (c.innerText || "").trim().split('\\n')[0];
                    if (name.toLowerCase() === targetProjName) {{
                        targetCard = c;
                        break;
                    }}
                }}
                if (!targetCard) return false;
                
                let all = Array.from(document.querySelectorAll('*'));
                let cardIdx = all.indexOf(targetCard);
                if (cardIdx === -1) return false;
                
                let targetChat = null;
                for (let i = cardIdx + 1; i < all.length; i++) {{
                    let el = all[i];
                    let cls = (typeof el.className === 'string') ? el.className : (el.getAttribute('class') || "");
                    if (el.getAttribute('data-project-card') === 'true') {{
                        break;
                    }}
                    if (cls.includes('ml-[22px]') && cls.includes('cursor-pointer')) {{
                        targetChat = el;
                        break;
                    }}
                }}
                
                if (targetChat) {{
                    targetChat.click();
                    let events = ['mousedown', 'mouseup', 'click'];
                    events.forEach(eventType => {{
                        let ev = new MouseEvent(eventType, {{ bubbles: true, cancelable: true, view: window }});
                        targetChat.dispatchEvent(ev);
                    }});
                    return true;
                }} else {{
                    targetCard.click();
                    let events = ['mousedown', 'mouseup', 'click'];
                    events.forEach(eventType => {{
                        let ev = new MouseEvent(eventType, {{ bubbles: true, cancelable: true, view: window }});
                        targetCard.dispatchEvent(ev);
                    }});
                    return true;
                }}
            }} catch (err) {{
                return false;
            }}
        }})();
        """
        ws.send(json.dumps({
            "id": 89,
            "method": "Runtime.evaluate",
            "params": {"expression": click_script, "returnByValue": True}
        }))
        res = json.loads(ws.recv())
        ws.close()
        
        success = res.get("result", {}).get("result", {}).get("value", False)
        if success:
            bot.reply_to(message, f"✅ 已成功切換至專案：**{target_name}**")
        else:
            bot.reply_to(message, f"❌ 切換失敗，在側邊欄找不到專案：**{target_name}**。請確認名稱是否正確。")
    except Exception as e:
        bot.reply_to(message, f"❌ 執行切換時發生錯誤：{e}")

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
