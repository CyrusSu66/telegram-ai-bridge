# Telegram Bot Bridge 🌉

這個專案實現了一個「Telegram 任意門」，讓你可以透過 Telegram Bot 遠端控制你的 Antigravity Agent。

## 🌟 功能特色

*   **雙向溝通**：
    *   **手機 -> 電腦**：在 Telegram 傳送指令，Bot 會模擬剪貼簿操作，迅速將指令貼到 Antigravity 輸入框。
    *   **電腦 -> 手機**：Agent 處理完畢後將結果寫入檔案，Bot 會自動偵測並回傳到 Telegram。
*   **中文支援**：採用剪貼簿輸入模式，完美支援中文與特殊符號。
*   **安全隔離**：Bot Token 與設定獨立於 `config.json`，方便管理與備份。

## 🚀 快速開始

### 1. 安裝依賴

確保你的環境已安裝 Python 3，然後執行：

```bash
pip install -r requirements.txt
```

### 2. 設定檔 (config.json)

請確保目錄下有 `config.json` 檔案，內容如下：

```json
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "agent_app_name": "Antigravity",
    "response_file": "response.txt"
}
```

*   `bot_token`: 從 @BotFather 取得的 Token。
*   `agent_app_name`: 你的 Agent 應用程式名稱（預設為 Antigravity）。
*   `response_file`: Agent 回應寫入的目標檔案。

### 3. 啟動 Bot

在終端機執行：

```bash
python3 bot.py
```

## 📱 使用說明

1.  在 Telegram 找到你的 Bot。
2.  傳送指令，格式為：`/ag <任何指令>`
    *   例如：`/ag 幫我檢查 dice-soul 的代碼`
    *   例如：`/ag 今天天氣如何？`
3.  **注意**：當 Bot 接收到指令時，它會**強制將電腦視窗切換到 Antigravity** 並進行貼上操作。請確保電腦處於解鎖狀態且 Antigravity 已開啟。
4.  Bot 現在只會處理以 `/ag` 開頭的訊息，避免誤觸。

## ⚠️ 常見問題

*   **無法輸入 / 亂碼？**
    *   本程式使用 `pyperclip` 與 `Cmd+V` 貼上，請確保你的輸入法狀態不是處於特殊模式。
*   **權限錯誤？**
    *   MacOS 需要授予 Python (或 Terminal) **輔助使用 (Accessibility)** 與 **System Events** 的權限，才能控制視窗與鍵盤。

---
*Created by Antigravity Agent*
