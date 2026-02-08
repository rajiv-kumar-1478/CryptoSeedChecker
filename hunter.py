import asyncio
import aiohttp
import time
import json
from mnemonic import Mnemonic
from bip_utils import (
    Bip39MnemonicGenerator, Bip39SeedGenerator, Bip39WordsNum,
    Bip44, Bip44Coins, Bip44Changes
)

import os

# --- CONFIGURATION (Environment Variables preferred for Cloud) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

try:
    BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 10))
except (ValueError, TypeError):
    BATCH_SIZE = 10
# --- COIN MAPPING ---
# Mapping our coins to bip_utils constants
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
    addr_str = ";".join(addresses[:20]) # Limit 20
    url = f"https://api.blockcypher.com/v1/{coin_slug}/main/addrs/{addr_str}?balance_only=true"
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            # BlockCypher multi-addr returns a list of objects
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
    print(f"[*] Starting CryptoHunter Pro Python CLI...")
    print(f"[*] Batch Size: {BATCH_SIZE} | Coins: {', '.join(COINS.keys())}")
    
    checked_count = 0
    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        while True:
            batch_seeds = []
            # 1. Generate Batch
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

            # 2. Check Balances in Parallel
            tasks = []
            task_info = [] # Track which mnemonic/coin each task belongs to
            
            # BTC (Multi-address)
            btc_addrs = [s["BTC"] for s in batch_seeds]
            tasks.append(check_balance_btc(session, btc_addrs))
            task_info.append(("BTC_BATCH", None))
            
            # Legacy Multi-address (BlockCypher)
            for coin_name, slug in [("LTC", "ltc"), ("DOGE", "doge"), ("BCH", "bch"), ("DASH", "dash")]:
                addrs = [s[coin_name] for s in batch_seeds]
                tasks.append(check_balance_blockcypher(session, slug, addrs))
                task_info.append(("LEGACY_BATCH", (coin_name, addrs)))

            # EVM / Solana
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

            # Execute all
            results = await asyncio.gather(*tasks)
            
            # 3. Process Results
            for i, res in enumerate(results):
                if not res: continue
                
                type, info = task_info[i]
                msg = ""
                
                if type == "BTC_BATCH":
                    # res is the address
                    m = next((s["mnemonic"] for s in batch_seeds if s["BTC"] == res), "Unknown")
                    msg = f"🟢 SUCCESS: BTC Found!\nAddress: `{res}`\nSeed: `{m}`"
                
                elif type == "LEGACY_BATCH":
                    coin, addrs = info
                    m = next((s["mnemonic"] for s in batch_seeds if s[coin] == res), "Unknown")
                    msg = f"🟢 SUCCESS: {coin} Found!\nAddress: `{res}`\nSeed: `{m}`"
                
                elif type == "SINGLE":
                    coin, addr, mnem = info
                    msg = f"🟢 SUCCESS: {coin} Found!\nAddress: `{addr}`\nSeed: `{mnem}`"

                if msg:
                    print(f"\n[!!!] {msg}")
                    await send_telegram(msg)
                    with open("found.txt", "a") as f:
                        f.write(msg.replace("\n", " | ") + "\n")

            checked_count += BATCH_SIZE
            elapsed = time.time() - start_time
            speed = checked_count / elapsed
            print(f"[*] Checked: {checked_count} | Speed: {speed:.2f} seeds/sec", end="\r")
            
            # Respect API limits
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(hunter_loop())
