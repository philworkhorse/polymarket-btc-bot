#!/usr/bin/env python3
"""
Polymarket 5m BTC Paper Trading Bot - Web Dashboard
Runs paper trading in background, shows stats via web.
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template_string

from paper_trader import PaperTrader

app = Flask(__name__)
trader = None
trader_thread = None

# Dashboard HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Polymarket 5m BTC Paper Trader</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff00; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { color: #00ff00; border-bottom: 1px solid #00ff00; padding-bottom: 10px; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }
        .stat { background: #111; padding: 15px; border: 1px solid #333; border-radius: 5px; }
        .stat-label { color: #888; font-size: 12px; }
        .stat-value { font-size: 24px; margin-top: 5px; }
        .positive { color: #00ff00; }
        .negative { color: #ff4444; }
        .trades { background: #111; padding: 15px; border: 1px solid #333; border-radius: 5px; margin-top: 20px; }
        .trade { padding: 10px; border-bottom: 1px solid #222; }
        .trade:last-child { border-bottom: none; }
        .win { border-left: 3px solid #00ff00; padding-left: 10px; }
        .loss { border-left: 3px solid #ff4444; padding-left: 10px; }
        .pending { border-left: 3px solid #ffff00; padding-left: 10px; }
        .signal { background: #1a1a1a; padding: 15px; margin-top: 20px; border: 1px solid #333; border-radius: 5px; }
        .price { font-size: 32px; color: #fff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 Polymarket 5m BTC Paper Trader</h1>
        
        <div class="signal">
            <div class="price">BTC: ${{ "%.2f"|format(price) if price else "---" }}</div>
            <div>Last signal: {{ last_signal.direction if last_signal else "---" }} 
                 | Edge: {{ "%.1f%%"|format(last_signal.edge * 100) if last_signal else "---" }}
                 | Confidence: {{ last_signal.confidence if last_signal else "---" }}</div>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-label">BANKROLL</div>
                <div class="stat-value">${{ "%.2f"|format(bankroll) }}</div>
            </div>
            <div class="stat">
                <div class="stat-label">TOTAL P&L</div>
                <div class="stat-value {{ 'positive' if total_pnl >= 0 else 'negative' }}">
                    ${{ "%+.2f"|format(total_pnl) }}
                </div>
            </div>
            <div class="stat">
                <div class="stat-label">RECORD</div>
                <div class="stat-value">{{ wins }}W-{{ losses }}L</div>
            </div>
            <div class="stat">
                <div class="stat-label">WIN RATE</div>
                <div class="stat-value">{{ "%.1f%%"|format(win_rate * 100) }}</div>
            </div>
        </div>
        
        <div class="trades">
            <h3>Recent Trades</h3>
            {% if pending %}
            <div class="trade pending">
                <strong>⏳ PENDING:</strong> {{ pending.direction }} ${{ "%.2f"|format(pending.size) }} 
                @ ${{ "%.2f"|format(pending.entry_price) }}
                | Edge: {{ "%.1f%%"|format(pending.edge * 100) }}
            </div>
            {% endif %}
            {% for trade in trades[-10:]|reverse %}
            <div class="trade {{ 'win' if trade.won else 'loss' }}">
                {{ "✅" if trade.won else "❌" }} {{ trade.direction }} ${{ "%.2f"|format(trade.size) }}
                | Entry: ${{ "%.2f"|format(trade.entry_price) }}
                | Exit: ${{ "%.2f"|format(trade.exit_price) if trade.exit_price else "---" }}
                | P&L: <span class="{{ 'positive' if trade.pnl and trade.pnl >= 0 else 'negative' }}">
                    ${{ "%+.2f"|format(trade.pnl) if trade.pnl else "---" }}</span>
            </div>
            {% endfor %}
            {% if not trades and not pending %}
            <div class="trade">No trades yet. Waiting for edge...</div>
            {% endif %}
        </div>
        
        <p style="color: #666; margin-top: 20px; font-size: 12px;">
            Auto-refreshes every 10s | Started: {{ start_time }}
        </p>
    </div>
</body>
</html>
"""

start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

def run_trader():
    """Run trader in background thread"""
    global trader
    trader = PaperTrader()
    asyncio.run(trader.run())

@app.route('/')
def dashboard():
    global trader
    
    if trader is None:
        return render_template_string(DASHBOARD_HTML,
            price=None, bankroll=1000, total_pnl=0, wins=0, losses=0,
            win_rate=0, trades=[], pending=None, last_signal=None, start_time=start_time)
    
    win_rate = trader.wins / (trader.wins + trader.losses) if (trader.wins + trader.losses) > 0 else 0
    
    return render_template_string(DASHBOARD_HTML,
        price=trader.price_feed.current_price,
        bankroll=trader.bankroll,
        total_pnl=trader.total_pnl,
        wins=trader.wins,
        losses=trader.losses,
        win_rate=win_rate,
        trades=trader.trades,
        pending=trader.pending_trade,
        last_signal=getattr(trader, 'last_signal', None),
        start_time=start_time
    )

@app.route('/api/stats')
def api_stats():
    global trader
    if trader is None:
        return jsonify({"status": "starting"})
    
    return jsonify({
        "price": trader.price_feed.current_price,
        "bankroll": trader.bankroll,
        "total_pnl": trader.total_pnl,
        "daily_pnl": trader.daily_pnl,
        "wins": trader.wins,
        "losses": trader.losses,
        "trades": len(trader.trades),
        "pending": trader.pending_trade is not None
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    import os
    
    # Start trader in background
    trader_thread = threading.Thread(target=run_trader, daemon=True)
    trader_thread.start()
    
    # Run web server
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
