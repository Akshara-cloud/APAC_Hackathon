#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from roostoo_api.client import RoostooClient


def test_account(name: str, api_key: str, secret_key: str, base_url: str):
    print(f"\nTesting {name} credentials...")
    if not api_key or not secret_key:
        print(f"[{name}] API key or secret key missing.")
        return

    client = RoostooClient(api_key=api_key, secret_key=secret_key, base_url=base_url)

    try:
        balance_res = client.get_balance()
        if balance_res.get("Success"):
            print(f"[{name}] Balance query successful:")
            wallet = balance_res.get("Wallet", {})
            for coin, details in wallet.items():
                free_val = details.get("Free", 0)
                lock_val = details.get("Lock", 0)
                if free_val > 0 or lock_val > 0:
                    print(f"  {coin}: free={free_val}, locked={lock_val}")
        else:
            print(f"[{name}] Balance response: {balance_res.get('ErrMsg', balance_res)}")
    except Exception as e:
        print(f"[{name}] Balance request error: {e}")

    try:
        pending_res = client.get_pending_count()
        if pending_res.get("Success"):
            print(f"[{name}] Pending orders: {pending_res.get('TotalPending', 0)}")
        else:
            print(f"[{name}] Pending orders response: {pending_res.get('ErrMsg', pending_res)}")
    except Exception as e:
        print(f"[{name}] Pending request error: {e}")


def main():
    load_dotenv()

    base_url = os.getenv("ROOSTOO_BASE_URL", "https://mock-api.roostoo.com").strip()
    test_key = os.getenv("ROOSTOO_TEST_API_KEY", os.getenv("ROOSTOO_API_KEY", "")).strip()
    test_secret = os.getenv("ROOSTOO_TEST_SECRET_KEY", os.getenv("ROOSTOO_SECRET_KEY", "")).strip()
    comp_key = os.getenv("ROOSTOO_COMPETITION_API_KEY", "").strip()
    comp_secret = os.getenv("ROOSTOO_COMPETITION_SECRET_KEY", "").strip()

    print("Roostoo API Connection Test")
    print(f"Base URL: {base_url}")

    client = RoostooClient(base_url=base_url)

    # Server time
    try:
        stime = client.get_server_time()
        print(f"[ServerTime] OK -> {stime.get('ServerTime')}")
    except Exception as e:
        print(f"[ServerTime] Failed: {e}")
        sys.exit(1)

    # Exchange info & ticker
    try:
        ex_info = client.get_exchange_info()
        pairs = list(ex_info.get("TradePairs", {}).keys())
        print(f"[ExchangeInfo] OK -> {len(pairs)} pairs active")

        ticker = client.get_ticker("BTC/USD")
        btc_data = ticker.get("Data", {}).get("BTC/USD", {})
        print(f"[Ticker] BTC/USD -> price={btc_data.get('LastPrice')}, change={btc_data.get('Change')}")
    except Exception as e:
        print(f"[ExchangeInfo/Ticker] Failed: {e}")

    # Authenticated endpoints
    if test_key and test_secret:
        test_account("Test Portfolio", test_key, test_secret, base_url)
    if comp_key and comp_secret:
        test_account("Competition Portfolio", comp_key, comp_secret, base_url)


if __name__ == "__main__":
    main()

