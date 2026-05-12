# Telegram Bot Bridge 🌉

這個專案實現了一個「Telegram 任意門」，讓你可以透過 Telegram Bot 遠端無縫控制你的 AI Agent (Antigravity)。

## 🌿 分支架構說明

本專案目前有兩個主要分支，採用完全不同的底層控制技術：

### 1. `main` 分支（UI 模擬自動化）
*   **控制原理**：依賴 macOS 的 **AppleScript (`osascript`)** 強制將視窗喚醒至前景，並透過 `pyperclip` 模擬剪貼簿 `Cmd+V` 貼上操作。
*   **優點**：架構簡單，泛用性強。
*   **缺點**：
    *   **僅支援 macOS**。
    *   容易被干擾（執行時電腦不能在做其他事，否則會搶走焦點）。
    *   必須確保游標已經停在文字輸入框。

### 2. `feature/cdp-integration` 分支（本分支：CDP 底層通訊）✨
*   **控制原理**：透過 **Chrome DevTools Protocol (CDP)** 的 WebSocket 介面，直接與底層的 Chromium / Electron 核心對話。
*   **優點**：
    *   **無干擾背景執行**：即使視窗被遮擋、最小化，指令依然能精準送達，完全不影響你當前的工作。
    *   **精準輸入**：直接針對 DOM 節點 (`.cursor-text`) 注入文字與觸發鍵盤事件，不依賴滑鼠游標。
    *   **智慧冷啟動**：支援自動偵測與背景喚醒 Antigravity 服務。
    *   **多專案支援**：可透過 Telegram 指令切換並監控不同的專案視窗。
    *   **精準回覆攔截**：能自動過濾 AI 的思考日誌 (Thought logs)，精準回傳最終的正式解答。

---

## 🌟 CDP 分支功能特色

*   **自動狀態同步**：啟動 `tgbot` 時自動推播連線狀態與可用的視窗清單。
*   **多視窗管理**：
    *   `/list`：列出所有目前開啟的專案視窗。
    *   `/switch <編號>`：切換目前要下達指令的目標視窗。
*   **自動綁定**：預設會自動鎖定你最新開啟或最後操作的 `[0]` 號活躍視窗。

## 🚀 快速開始 (CDP 版本)

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

### 3. 啟動 Bot

在終端機執行（或使用 alias）：

```bash
python3 bot.py
# 或
tgbot
```

啟動後，只要 Antigravity 處於開啟狀態，你的 Telegram 就會立刻收到連線成功與視窗鎖定通知！

## ⚠️ 常見問題

*   **無法輸入或發生錯誤？**
    *   確保 Antigravity 是以 `remote-debugging-port=7800` 模式啟動。本程式的冷啟動腳本已經預設帶有此參數。
*   **等很久沒收到回覆？**
    *   系統設定會自動過濾掉 AI 的「思考中」文字區塊，必須等到 AI 給出最終回覆後才會一併送出，請耐心等候。

---
*Created by Antigravity Agent*
