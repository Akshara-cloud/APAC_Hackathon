import os
import time
import logging
from collections import deque
from decimal import Decimal, ROUND_DOWN

from dotenv import load_dotenv

from client import RoostooClient

load_dotenv()

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PAIR = "BTC/USD"

# POLL_INTERVAL = 5 * 60      # 5 minutes
# FAST_WINDOW = 5             # 25 minutes
# SLOW_WINDOW = 20            # 100 minutes

POLL_INTERVAL = 10
FAST_WINDOW = 3
SLOW_WINDOW = 6

POSITION_SIZE = 0.10        # use 10% of available USD on a BUY

# Safety: keep this True while testing.
# Change to False when you deliberately want live orders.
DRY_RUN = True


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

    trade_pair = info["TradePairs"][pair]
    return int(trade_pair["AmountPrecision"])


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

    return float(
        response["Data"][pair]["LastPrice"]
    )


# def get_balances(client: RoostooClient):
#     response = client.get_balance()

#     wallet = response["Wallet"]

#     usd = float(wallet.get("USD", {}).get("Free", 0))
#     coin = PAIR.split("/")[0]
#     coin_balance = float(wallet.get(coin, {}).get("Free", 0))

#     return usd, coin_balance

# def get_balances(client: RoostooClient):
#     response = client.get_balance()

#     logger.info("FULL BALANCE RESPONSE: %s", response)

#     if not response.get("Success", False):
#         raise RuntimeError(
#             f"Balance API failed: {response.get('ErrMsg', 'Unknown error')}"
#         )

#     wallet = response.get("Wallet")

#     if wallet is None:
#         raise RuntimeError(
#             f"Balance response has no 'Wallet' field: {response}"
#         )

#     usd = float(wallet.get("USD", {}).get("Free", 0))

#     coin = PAIR.split("/")[0]
#     coin_balance = float(
#         wallet.get(coin, {}).get("Free", 0)
#     )

#     return usd, coin_balance

def get_balances(client: RoostooClient):
    response = client.get_balance()

    if not response.get("Success", False):
        raise RuntimeError(
            f"Balance API failed: {response.get('ErrMsg', 'Unknown error')}"
        )

    wallet = response.get("SpotWallet", {})

    usd = float(
        wallet.get("USD", {}).get("Free", 0)
    )

    coin = PAIR.split("/")[0]

    coin_balance = float(
        wallet.get(coin, {}).get("Free", 0)
    )

    return usd, coin_balance

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

        # Don't repeatedly buy if we already hold BTC.
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

    api_key = os.environ["ROOSTOO_API_KEY"]
    secret_key = os.environ["ROOSTOO_API_SECRET"]

    client = RoostooClient(
        api_key=api_key,
        secret_key=secret_key,
    )

    exchange_info = client.get_exchange_info()
    # logger.info("EXCHANGE INFO: %s", exchange_info)

    quantity_precision = get_quantity_precision(
        client,
        PAIR,
    )

    logger.info("Bot started")
    logger.info("Pair: %s", PAIR)
    logger.info("DRY_RUN: %s", DRY_RUN)

    prices = deque(maxlen=SLOW_WINDOW)

    while True:

        try:
            price = get_last_price(
                client,
                PAIR,
            )

            prices.append(price)

            logger.info(
                "Current %s price = %.2f",
                PAIR,
                price,
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