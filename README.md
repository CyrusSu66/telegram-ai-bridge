# Telegram Bot Bridge 🌉

> [!IMPORTANT]
> **環境限制**：本專案專為 **macOS** 環境設計。
> 如果您使用的是 **Windows**，請參閱本專案邏輯並自行請 AI Agent (如 Antigravity 或 Claude) 協助開發 Windows 版本的替代方案（如使用 PowerShell 或 AutoHotKey）。

這個專案實現了一個「Telegram 任意門」，讓你可以透過 Telegram Bot 遠端控制你的 Antigravity Agent。

### 🍎 為何僅支援 macOS？
本專案核心依賴 macOS 獨有的 **AppleScript (`osascript`)** 功能，主要用於：
1.  **視窗自動聚焦**：自動將系統焦點切換至 Antigravity 視窗。
2.  **系統指令輸入**：模擬 `Cmd+V` 貼上操作與 `Enter` 鍵，以確保中文輸入不會產生亂碼。

## 🌟 功能特色

*   **雙向溝通**：
    *   **手機 -> 電腦**：在 Telegram 傳送指令，Bot 會模擬剪貼簿操作，迅速將指令貼到 Antigravity 輸入框。
    *   **電腦 -> 手機**：Agent 處理完畢後將結果寫入檔案，Bot 會自動偵測並回傳到 Telegram。
*   **中文支援**：採用剪貼簿輸入模式，完美支援中文與特殊符號。
*   **安全隔離**：Bot Token 與設定獨立於 `config.json`，方便管理與備份。

> [!NOTE]
> **使用前提**：Antigravity 的**對話輸入框**必須保持在焦點狀態（即游標停留在文字輸入框內）。
> **原因**：本程式透過 AppleScript 將 App 視窗拉到前景後，使用 `Cmd+V` 直接模擬鍵盤貼上操作，相當於你「手動點擊輸入框後按 Ctrl+V」。由於程式本身無法感知視窗內部的 UI 元素（不知道輸入框在哪個座標），它只能單純地將剪貼簿內容貼到「當前焦點所在元素」，因此需要使用者在傳指令前，確認焦點已在輸入框上。

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
2.  **直接傳送指令**即可。
    *   例如：`幫我檢查 dice-soul 的代碼`
    *   例如：`今天天氣如何？`
3.  **注意**：當 Bot 接收到指令時，它會**強制將電腦視窗切換到 Antigravity** 並進行貼上操作。請確保電腦處於解鎖狀態且 Antigravity 已開啟。
4.  目前 Bot 會處理所有接收到的文字訊息。

## ⚠️ 常見問題

*   **無法輸入 / 亂碼？**
    *   本程式使用 `pyperclip` 與 `Cmd+V` 貼上，請確保你的輸入法狀態不是處於特殊模式。
*   **權限錯誤？**
    *   MacOS 需要授予 Python (或 Terminal) **輔助使用 (Accessibility)** 與 **System Events** 的權限，才能控制視窗與鍵盤。具體路徑：`系統設定 -> 隱私權與安全性 -> 輔助使用`。

*   **支援平台？**
    *   本專案目前僅支援 **macOS**，因為指令輸入依賴於 `osascript` 與 macOS 系統 Events。

---
*Created by Antigravity Agent*
