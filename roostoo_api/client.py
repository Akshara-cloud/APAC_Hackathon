import time
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class RoostooClient:
    DEFAULT_BASE_URL = "https://mock-api.roostoo.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 10,
    ):
        self.api_key = api_key or ""
        self.secret_key = secret_key or ""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get_timestamp_ms(self) -> int:
        """Returns the current 13-digit millisecond timestamp."""
        return int(time.time() * 1000)

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generates HMAC SHA256 signature for parameters.
        Keys are sorted alphabetically and joined with '&'.
        """
        if not self.secret_key:
            raise ValueError("Secret key is missing. Please provide a valid secret_key.")

        # Filter out None values and sort by key
        sorted_items = sorted(
            [(k, str(v)) for k, v in params.items() if v is not None],
            key=lambda x: x[0],
        )
        query_string = "&".join(f"{k}={v}" for k, v in sorted_items)
        
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes HTTP requests to Roostoo API endpoints with signature headers when required.
        """
        url = f"{self.base_url}{endpoint}"
        payload = params.copy() if params else {}

        headers = {}
        if signed:
            if not self.api_key:
                raise ValueError("API key is required for signed endpoints.")
            if "timestamp" not in payload:
                payload["timestamp"] = self._get_timestamp_ms()

            sig = self._generate_signature(payload)
            headers["RST-API-KEY"] = self.api_key
            headers["MSG-SIGNATURE"] = sig

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url,
                    params=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            elif method.upper() == "POST":
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = self.session.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Roostoo API error on {method} {endpoint}: {e}")
            if hasattr(e, "response") and e.response is not None:
                try:
                    return e.response.json()
                except Exception:
                    logger.error(f"Response content: {e.response.text}")
            raise

    # -------------------------------------------------------------------------
    # Public Endpoints (No verification / Timestamp check only)
    # -------------------------------------------------------------------------

    def get_server_time(self) -> Dict[str, Any]:
        """
        GET /v3/serverTime
        Tests API connectivity and fetches current server timestamp.
        """
        return self._request("GET", "/v3/serverTime")

    def get_exchange_info(self) -> Dict[str, Any]:
        """
        GET /v3/exchangeInfo
        Fetches supported trading pairs, precision limits, and min order size.
        """
        return self._request("GET", "/v3/exchangeInfo")

    def get_ticker(self, pair: Optional[str] = None) -> Dict[str, Any]:
        """
        GET /v3/ticker
        Fetches real-time market price, 24h change, and volume for a pair or all pairs.
        """
        params = {"timestamp": self._get_timestamp_ms()}
        if pair:
            params["pair"] = pair
        return self._request("GET", "/v3/ticker", params=params)

    # -------------------------------------------------------------------------
    # Authenticated Endpoints (RCL_TopLevelCheck)
    # -------------------------------------------------------------------------

    def get_balance(self) -> Dict[str, Any]:
        """
        GET /v3/balance
        Retrieves current wallet balance (Free and Locked amounts).
        """
        return self._request("GET", "/v3/balance", signed=True)

    def get_pending_count(self) -> Dict[str, Any]:
        """
        GET /v3/pending_count
        Retrieves total pending orders and count per trading pair.
        """
        return self._request("GET", "/v3/pending_count", signed=True)

    def place_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        POST /v3/place_order
        Places a spot buy/sell order on Roostoo.

        :param pair: e.g. 'BTC/USD', 'ETH/USD'
        :param side: 'BUY' or 'SELL'
        :param order_type: 'MARKET' or 'LIMIT'
        :param quantity: quantity to trade
        :param price: required if order_type is 'LIMIT'
        """
        payload: Dict[str, Any] = {
            "pair": pair,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if price is not None:
            payload["price"] = price

        return self._request("POST", "/v3/place_order", params=payload, signed=True)

    def query_order(
        self,
        order_id: Optional[str] = None,
        pair: Optional[str] = None,
        pending_only: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        POST /v3/query_order
        Queries order status or account order history according to official python_demo.py.
        """
        payload: Dict[str, Any] = {}
        if order_id is not None:
            payload["order_id"] = order_id
        if pair is not None:
            payload["pair"] = pair
        if pending_only is not None:
            payload["pending_only"] = pending_only

        return self._request("POST", "/v3/query_order", params=payload, signed=True)

    def cancel_order(
        self,
        order_id: Optional[str] = None,
        pair: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /v3/cancel_order
        Cancels pending orders by order ID, pair, or all pending orders.
        """
        params: Dict[str, Any] = {}
        if order_id is not None:
            params["order_id"] = order_id
        if pair is not None:
            params["pair"] = pair

        return self._request("POST", "/v3/cancel_order", params=params, signed=True)
