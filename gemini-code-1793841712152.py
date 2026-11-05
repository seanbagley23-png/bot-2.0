#!/usr/bin/env python3
"""
Method 2.0 / Deity<3Kalshi - Python Core Engine
Tracks BTC 15-min prediction windows, fetches exchange blends & Kalshi strikes,
and outputs real-time model confidence and cushion stats.
"""

import time
import math
import urllib.request
import json
from datetime import datetime, timezone

# Configuration Constants
SERIES_TICKER = "KXBTC15M"
WINDOW_DURATION = 900  # 15 minutes in seconds
EARLY_LOCK_MIN = 3
FINAL_LOCK_MIN = 7

def fetch_json(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'DeityKalshiBot/2.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return None

def get_exchange_prices():
    prices = []
    
    # Coinbase
    cb_data = fetch_json(f"https://api.exchange.coinbase.com/products/BTC-USD/ticker")
    if cb_data and 'price' in cb_data:
        prices.append(float(cb_data['price']))
        
    # Kraken
    kraken_data = fetch_json("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")
    try:
        if kraken_data and 'result' in kraken_data:
            price = float(kraken_data['result']['XXBTZUSD']['c'][0])
            prices.append(price)
    except Exception:
        pass
        
    # Bitstamp
    bitstamp_data = fetch_json("https://www.bitstamp.net/api/v2/ticker/btcusd/")
    if bitstamp_data and 'last' in bitstamp_data:
        prices.append(float(bitstamp_data['last']))
        
    if not prices:
        return None
    return sum(prices) / len(prices)

def get_kalshi_market():
    base_url = "https://api.elections.kalshi.com/trade-api/v2"
    events_data = fetch_json(f"{base_url}/events?series_ticker={SERIES_TICKER}&status=open&limit=5")
    
    if not events_data or 'events' not in events_data:
        return None
        
    now = int(time.time() * 1000)
    active_market = None
    
    for event in events_data['events']:
        t0 = event.get('event_ticker', '')
        for suffix in [t0[-2:], '00', '15', '30', '45']:
            market_data = fetch_json(f"{base_url}/markets/{t0}-{suffix}")
            if market_data:
                m = market_data.get('market', market_data)
                close_time_str = m.get('close_time')
                if close_time_str:
                    # Parse ISO timestamp
                    close_dt = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                    close_ms = int(close_dt.timestamp() * 1000)
                    if close_ms > now:
                        active_market = m
                        break
        if active_market:
            break
            
    if not active_market:
        return None
        
    strike = active_market.get('floor_strike')
    if strike is None:
        strike = active_market.get('strike_price')
        
    return {
        'ticker': active_market.get('ticker'),
        'close_time': active_market.get('close_time'),
        'strike': float(strike) if strike is not None else None,
        'yes_ask': active_market.get('yes_ask') or active_market.get('yes_ask_dollars')
    }

def normal_cdf(z):
    # Standard normal cumulative distribution function approximation
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    p = 0.3989423 * math.exp(-z * z / 2.0) * t * (
        0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))
    )
    return 1.0 - p if z > 0 else p

def run_engine():
    print("==================================================")
    print("       DEITY <3 KALSHI (METHOD 2.0) PYTHON CORE     ")
    print("==================================================")
    
    current_window_start = (int(time.time()) // WINDOW_DURATION) * WINDOW_DURATION
    strike = None
    
    while True:
        now = int(time.time())
        
        # Check for window rollover
        if now >= current_window_start + WINDOW_DURATION:
            current_window_start = (now // WINDOW_DURATION) * WINDOW_DURATION
            strike = None
            print("\n--- NEW 15-MIN WINDOW STARTED ---")
            
        btc_price = get_exchange_prices()
        if not btc_price:
            print("Warning: Failed to fetch exchange prices. Retrying...")
            time.sleep(3)
            continue
            
        # Fetch Kalshi strike if not set
        if strike is None:
            market = get_kalshi_market()
            if market and market['strike']:
                strike = market['strike']
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] Connected to Kalshi | Strike: ${strike:,.2f} ({market['ticker']})")
            else:
                strike = btc_price  # Fallback to open price
                
        elapsed_min = (now - current_window_start) / 60.0
        rem_min = max(15 - elapsed_min, 0.25)
        
        # Simple volatility and probability model
        vol_per_min = 0.0004  # Baseline volatility factor
        typical_move = vol_per_min * btc_price * math.sqrt(rem_min)
        
        lead = btc_price - strike
        z_score = lead / (typical_move if typical_move > 0 else 1)
        p_up = normal_cdf(z_score)
        conf = max(p_up, 1.0 - p_up)
        side = "UP" if p_up >= 0.5 else "DOWN"
        
        # Display live read
        print(f"\rPrice: ${btc_price:,.2f} | Gap: ${lead:+,.2f} | Model: {side} ({conf*100:.1f}%) | Elapsed: {elapsed_min:.1f}m", end="", flush=True)
        
        time.sleep(3)

if __name__ == "__main__":
    try:
        run_engine()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")