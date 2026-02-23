# 🚀 CryptoHunter Pro v2.0

Async multi-coin wallet scanner built with Python, AsyncIO, and BIP39/BIP44 standards.

---

## 🌐 Live Demo

👉 **Live Application:**  
(https://cryptohunter-q92y.onrender.com/)

---

## 📌 Project Overview

CryptoHunter Pro generates random 12-word BIP39 mnemonics, derives wallet addresses using BIP44 for multiple cryptocurrencies, and checks blockchain APIs asynchronously for balances.

If a funded address is detected:

- ✅ Logs to console  
- 🤖 Sends Telegram alert  
- 📊 Updates live dashboard  

---

## 🪙 Supported Cryptocurrencies

- Bitcoin (BTC)  
- Litecoin (LTC)  
- Dogecoin (DOGE)  
- Bitcoin Cash (BCH)  
- Dash (DASH)  
- Ethereum (ETH)  
- Binance Smart Chain (BNB)  
- Polygon (MATIC)  
- Avalanche C-Chain (AVAX)  
- Solana (SOL)  

---

## ⚙️ Tech Stack

- Python 3.9+
- AsyncIO
- aiohttp
- mnemonic
- bip-utils
- Telegram Bot API

---

## 📊 Web Dashboard

Local:
https://localhost_link

Deployed:
https://YOUR_RENDER_LINK

Dashboard Shows:
- Status
- Total Seeds Checked
- Speed (seeds/sec)
- Last Mnemonic
- Uptime

---

## 🔑 Environment Variables

Set these before running:

Linux / Mac:
export TELEGRAM_BOT_TOKEN=your_bot_token
export TELEGRAM_CHAT_ID=your_chat_id
export BATCH_SIZE=10

Windows (PowerShell):
setx TELEGRAM_BOT_TOKEN "your_bot_token"
setx TELEGRAM_CHAT_ID "your_chat_id"
setx BATCH_SIZE 10

---

## ▶️ Run Locally

python hunter.py

---

## ⚠️ Disclaimer

This project is for educational and research purposes only.

The probability of randomly discovering a funded wallet is effectively zero.

---

## 📜 License

MIT License
