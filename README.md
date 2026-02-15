# Polymarket 5m BTC Bot

Bot to trade Polymarket's 5-minute BTC up/down prediction markets.

## How it works
- Each market: will BTC be >= starting price after 5 minutes?
- Binary outcome: UP (>=) or DOWN (<)
- Settlement: Chainlink oracle, automated

## Strategy
1. Get real-time BTC price from Binance (faster than Chainlink)
2. Calculate momentum/trend over last 1-3 minutes
3. Compare to Polymarket implied odds
4. If edge > threshold, bet

## Setup
```bash
pip install py-clob-client websockets python-dotenv
cp .env.example .env
# Edit .env with your keys
python bot.py
```

## Files
- `bot.py` - Main bot loop
- `price_feed.py` - Binance websocket price feed
- `polymarket.py` - Polymarket API wrapper
- `strategy.py` - Edge detection logic
- `config.py` - Configuration
