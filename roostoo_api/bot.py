import os
import sys
import time
import logging
from collections import deque
from decimal import Decimal, ROUND_DOWN

from pathlib import Path
from dotenv import load_dotenv

# Ensure module import works whether run from root or roostoo_api dir
try:
    from roostoo_api.client import RoostooClient
except ModuleNotFoundError:
    from client import RoostooClient

# Load .env from project root relative to bot.py location
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()  # fallback to current working directory

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PAIR = "BTC/USD"

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
FAST_WINDOW = int(os.getenv("FAST_WINDOW", "3"))
SLOW_WINDOW = int(os.getenv("SLOW_WINDOW", "6"))

POSITION_SIZE = float(os.getenv("POSITION_SIZE", "0.10"))  # use 10% of available USD on a BUY

# Safety: keep this True while testing.
# Set DRY_RUN=False in .env when you deliberately want live orders.
DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_quantity_precision(client: RoostooClient, pair: str) -> int:
    info = client.get_exchange_info()
    trade_pairs = info.get("TradePairs", {})
    if pair in trade_pairs:
        return int(trade_pairs[pair].get("AmountPrecision", 4))
    return 4


def floor_quantity(quantity: float, precision: int) -> float:
    """
    Round quantity DOWN according to exchange precision.
    """
    factor = Decimal("1").scaleb(-precision)
    value = Decimal(str(quantity))

    rounded = value.quantize(
        factor,
        rounding=ROUND_DOWN,
    )

    return float(rounded)


def get_last_price(client: RoostooClient, pair: str) -> float:
    response = client.get_ticker(pair)
    data = response.get("Data", {})
    if pair in data:
        return float(data[pair]["LastPrice"])
    raise KeyError(f"Pair '{pair}' not found in ticker response.")


def get_balances(client: RoostooClient):
    try:
        response = client.get_balance()
        if not response.get("Success", False):
            logger.warning(
                "Balance API failed or unauthorized: %s",
                response.get("ErrMsg", response),
            )
            return 0.0, 0.0

        wallet = response.get("Wallet") or response.get("SpotWallet", {})
        usd = float(wallet.get("USD", {}).get("Free", 0))
        coin = PAIR.split("/")[0]
        coin_balance = float(wallet.get(coin, {}).get("Free", 0))
        return usd, coin_balance
    except Exception as e:
        logger.warning("Could not fetch balance (%s). Returning 0.0 balances for test run.", e)
        return 0.0, 0.0


# ---------------------------------------------------------
# Strategy
# ---------------------------------------------------------

def calculate_signal(prices):
    if len(prices) < SLOW_WINDOW + 1:
        return "HOLD"

    previous_fast = sum(
        list(prices)[-(FAST_WINDOW + 1):-1]
    ) / FAST_WINDOW

    previous_slow = sum(
        list(prices)[-(SLOW_WINDOW + 1):-1]
    ) / SLOW_WINDOW

    current_fast = sum(
        list(prices)[-FAST_WINDOW:]
    ) / FAST_WINDOW

    current_slow = sum(
        list(prices)[-SLOW_WINDOW:]
    ) / SLOW_WINDOW

    if previous_fast <= previous_slow and current_fast > current_slow:
        return "BUY"

    if previous_fast >= previous_slow and current_fast < current_slow:
        return "SELL"

    return "HOLD"


# ---------------------------------------------------------
# Trading
# ---------------------------------------------------------

def execute_signal(
    client: RoostooClient,
    signal: str,
    price: float,
    quantity_precision: int,
):
    usd, coin_balance = get_balances(client)

    logger.info(
        "Balance: USD=%.2f | BTC=%.8f",
        usd,
        coin_balance,
    )

    # -----------------------------------------------------
    # BUY
    # -----------------------------------------------------

    if signal == "BUY":
        if coin_balance > 0:
            logger.info("Already holding BTC. Skipping BUY.")
            return

        usd_to_use = usd * POSITION_SIZE

        if usd_to_use <= 0:
            logger.info("No USD available. Skipping BUY.")
            return

        quantity = usd_to_use / price

        quantity = floor_quantity(
            quantity,
            quantity_precision,
        )

        if quantity <= 0:
            logger.info("Calculated BUY quantity is zero.")
            return

        logger.info(
            "BUY %.8f BTC at market price %.2f",
            quantity,
            price,
        )

        if DRY_RUN:
            logger.info("DRY_RUN=True -> order NOT sent")
            return

        response = client.place_order(
            pair=PAIR,
            side="BUY",
            order_type="MARKET",
            quantity=quantity,
        )

        logger.info("BUY response: %s", response)

    # -----------------------------------------------------
    # SELL
    # -----------------------------------------------------

    elif signal == "SELL":
        if coin_balance <= 0:
            logger.info("No BTC to sell. Skipping SELL.")
            return

        quantity = floor_quantity(
            coin_balance,
            quantity_precision,
        )

        if quantity <= 0:
            logger.info("Calculated SELL quantity is zero.")
            return

        logger.info(
            "SELL %.8f BTC at market price %.2f",
            quantity,
            price,
        )

        if DRY_RUN:
            logger.info("DRY_RUN=True -> order NOT sent")
            return

        response = client.place_order(
            pair=PAIR,
            side="SELL",
            order_type="MARKET",
            quantity=quantity,
        )

        logger.info("SELL response: %s", response)


# ---------------------------------------------------------
# Main loop
# ---------------------------------------------------------

def main():
    api_key = os.getenv("ROOSTOO_API_KEY") or os.getenv("ROOSTOO_TEST_API_KEY", "")
    secret_key = os.getenv("ROOSTOO_SECRET_KEY") or os.getenv("ROOSTOO_API_SECRET", os.getenv("ROOSTOO_TEST_SECRET_KEY", ""))
    base_url = os.getenv("ROOSTOO_BASE_URL", "https://mock-api.roostoo.com")

    client = RoostooClient(
        api_key=api_key,
        secret_key=secret_key,
        base_url=base_url,
    )

    quantity_precision = get_quantity_precision(
        client,
        PAIR,
    )

    logger.info("Bot started")
    logger.info("Pair: %s", PAIR)
    logger.info("Base URL: %s", base_url)
    logger.info("DRY_RUN: %s", DRY_RUN)

    # Note: maxlen must be at least SLOW_WINDOW + 1 for calculate_signal
    prices = deque(maxlen=SLOW_WINDOW + 1)

    while True:
        try:
            price = get_last_price(
                client,
                PAIR,
            )

            prices.append(price)

            logger.info(
                "Current %s price = %.2f (collected %d/%d prices)",
                PAIR,
                price,
                len(prices),
                SLOW_WINDOW + 1,
            )

            signal = calculate_signal(prices)

            logger.info("Signal = %s", signal)

            if signal != "HOLD":
                execute_signal(
                    client,
                    signal,
                    price,
                    quantity_precision,
                )

        except Exception:
            logger.exception(
                "Error during bot iteration"
            )

        logger.info(
            "Sleeping for %d seconds...",
            POLL_INTERVAL,
        )

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()