# APAC Quant Trading Hackathon

Quantitative trading bot implementation for the Roostoo mock exchange.

## Project Structure
- `roostoo_api/`: REST API client for market data and order management (HMAC-SHA256 signed).
- `verify_connection.py`: Connectivity test script for public and authenticated endpoints.
- `requirements.txt`: Python package dependencies.
- `.env`: Environment variables and API credentials.

## Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment credentials in `.env`:
```env
ROOSTOO_API_KEY=your_api_key
ROOSTOO_SECRET_KEY=your_secret_key
ROOSTOO_BASE_URL=https://mock-api.roostoo.com
```

3. Run verification test:
```bash
python3 verify_connection.py
```