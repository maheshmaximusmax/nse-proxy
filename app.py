from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import logging
import time

app = Flask(__name__)

# Enhanced CORS configuration
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    allow_headers=["*"],
    expose_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain",
    "Cache-Control": "no-cache",
}

# Maintain session for cookie persistence
session = requests.Session()
last_cookie_refresh = 0


def refresh_cookies(force: bool = False):
    """Refresh session cookies from NSE."""
    global last_cookie_refresh
    current_time = time.time()

    # Only refresh if last refresh was > 30 seconds ago
    if not force and current_time - last_cookie_refresh < 30:
        logger.info("Skipping cookie refresh - recently done")
        return True

    try:
        logger.info("Refreshing cookies from NSE...")
        res = session.get(
            "https://www.nseindia.com/option-chain", headers=HEADERS, timeout=15
        )
        last_cookie_refresh = current_time
        logger.info(f"Cookie refresh successful: {res.status_code}")
        return True
    except Exception as e:
        logger.error(f"Cookie refresh failed: {e}")
        last_cookie_refresh = current_time
        return False


@app.route("/", methods=["GET", "HEAD", "OPTIONS"])
def home():
    # Explicitly handle OPTIONS / preflight
    if request.method == "OPTIONS":
        return "", 204

    # Return simple text for quick connectivity tests
    if request.method in ("HEAD",):
        return "", 200

    return "NSE Proxy Running", 200


@app.route("/option-chain", methods=["GET", "OPTIONS"])
def option_chain():
    """Fetch NSE option chain data with proper session management."""
    if request.method == "OPTIONS":
        return "", 204

    symbol = request.args.get("symbol", "NIFTY")
    logger.info(f"Request for {symbol}")

    # Validate symbol
    valid_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
    if symbol not in valid_symbols:
        return (
            jsonify({"error": f"Invalid symbol. Use: {', '.join(valid_symbols)}"}),
            400,
        )

    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"

    try:
        # Refresh cookies if needed
        refresh_cookies()

        # Make request with session
        logger.info(f"Fetching: {url}")
        r = session.get(url, headers=HEADERS, timeout=15)
        logger.info(f"Response status: {r.status_code}")

        # Handle 401 - refresh and retry
        if r.status_code == 401:
            logger.warning("Got 401 - refreshing cookies and retrying")
            refresh_cookies(force=True)
            time.sleep(2)
            r = session.get(url, headers=HEADERS, timeout=15)

        # Handle 429 - rate limited
        if r.status_code == 429:
            logger.warning("Rate limited by NSE")
            return jsonify({"error": "Rate limited - please wait"}), 429

        # Success
        if r.status_code == 200:
            try:
                data = r.json()
                logger.info(f"Successfully parsed data for {symbol}")
                return jsonify(data), 200
            except ValueError as e:
                logger.error(f"JSON parse error: {e}")
                return jsonify({"error": "Invalid response from NSE"}), 502

        # Other errors
        logger.error(f"NSE error {r.status_code}: {r.text[:200]}")
        return (
            jsonify({"error": f"NSE returned {r.status_code}", "message": r.text[:300]}),
            r.status_code,
        )

    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({"error": "Request timeout after 15s"}), 504
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return jsonify({"error": "Cannot connect to NSE"}), 503
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # Initial cookie refresh
    refresh_cookies(force=True)

    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
