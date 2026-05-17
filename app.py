from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, os

app = Flask(__name__)

# Enable CORS for all routes with specific configuration
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/option-chain',
}

session = requests.Session()

def refresh_cookies():
    try:
        session.get('https://www.nseindia.com/option-chain', headers=HEADERS, timeout=10)
    except Exception as e:
        print(f"Cookie refresh error: {e}")

@app.route('/')
def home():
    return 'NSE Proxy Running'

@app.route('/option-chain', methods=['GET', 'OPTIONS'])
def option_chain():
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 200
    
    symbol = request.args.get('symbol', 'NIFTY')
    url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
    try:
        r = session.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 401:
            refresh_cookies()
            r = session.get(url, headers=HEADERS, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    refresh_cookies()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
