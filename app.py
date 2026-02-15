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
from collections import deque
from pathlib import Path
from flask import Flask, jsonify, render_template_string

from paper_trader import PaperTrader

app = Flask(__name__)
trader = None
trader_thread = None

# Activity log for thought process
activity_log = deque(maxlen=100)

def log_activity(msg: str, level: str = "info"):
    """Add to activity log"""
    activity_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "msg": msg,
        "level": level
    })

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Polymarket BTC</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        :root {
            --bg: #09090b;
            --surface: #18181b;
            --surface-2: #27272a;
            --border: #3f3f46;
            --text: #fafafa;
            --text-dim: #a1a1aa;
            --accent: #f97316;
            --accent-dim: rgba(249, 115, 22, 0.15);
            --up: #22c55e;
            --up-dim: rgba(34, 197, 94, 0.12);
            --down: #ef4444;
            --down-dim: rgba(239, 68, 68, 0.12);
            --pending: #eab308;
        }
        
        body {
            font-family: 'DM Sans', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            min-height: 100vh;
        }
        
        .mono { font-family: 'Space Mono', monospace; }
        
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 32px 24px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 40px;
        }
        
        .logo {
            font-family: 'Space Mono', monospace;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: var(--accent);
            text-transform: uppercase;
        }
        
        .status {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 6px 12px;
            border-radius: 4px;
        }
        
        .status.scanning { background: var(--surface-2); color: var(--text-dim); }
        .status.open { background: var(--accent-dim); color: var(--accent); }
        
        .hero {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 1px;
            background: var(--border);
            border: 1px solid var(--border);
            margin-bottom: 32px;
        }
        
        .hero-stat {
            background: var(--surface);
            padding: 24px;
        }
        
        .hero-stat .label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 8px;
        }
        
        .hero-stat .value {
            font-family: 'Space Mono', monospace;
            font-size: 28px;
            font-weight: 700;
        }
        
        .hero-stat .value.positive { color: var(--up); }
        .hero-stat .value.negative { color: var(--down); }
        
        @media (max-width: 800px) {
            .hero { grid-template-columns: 1fr 1fr; }
        }
        
        .panels {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }
        
        @media (max-width: 800px) {
            .panels { grid-template-columns: 1fr; }
        }
        
        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
        }
        
        .panel-head {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
        }
        
        .panel-body {
            padding: 20px;
        }
        
        .price-block {
            text-align: center;
            padding: 32px 20px;
        }
        
        .price-block .price {
            font-family: 'Space Mono', monospace;
            font-size: 42px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        
        .price-block .change {
            font-family: 'Space Mono', monospace;
            font-size: 14px;
            margin-top: 8px;
        }
        
        .price-block .change.up { color: var(--up); }
        .price-block .change.down { color: var(--down); }
        
        .signal-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        
        .signal-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }
        
        .signal-row:last-child { border-bottom: none; }
        .signal-row .key { color: var(--text-dim); }
        .signal-row .val { font-family: 'Space Mono', monospace; font-weight: 500; }
        
        .components {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }
        
        @media (max-width: 600px) {
            .components { grid-template-columns: 1fr 1fr; }
        }
        
        .comp {
            padding: 12px;
            background: var(--bg);
            border: 1px solid var(--border);
        }
        
        .comp .label {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 6px;
        }
        
        .comp .value {
            font-family: 'Space Mono', monospace;
            font-size: 15px;
            font-weight: 500;
        }
        
        .comp .value.up { color: var(--up); }
        .comp .value.down { color: var(--down); }
        
        .bar {
            height: 3px;
            background: var(--surface-2);
            margin-top: 8px;
            overflow: hidden;
        }
        
        .bar-fill {
            height: 100%;
            transition: width 0.3s;
        }
        
        .bar-fill.up { background: var(--up); }
        .bar-fill.down { background: var(--down); }
        
        .log-scroll {
            max-height: 280px;
            overflow-y: auto;
            font-family: 'Space Mono', monospace;
            font-size: 11px;
            line-height: 1.7;
        }
        
        .log-entry {
            padding: 6px 0;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 12px;
        }
        
        .log-entry:last-child { border-bottom: none; }
        .log-entry .time { color: var(--text-dim); flex-shrink: 0; }
        .log-entry .msg { word-break: break-word; }
        .log-entry.signal { color: var(--accent); }
        .log-entry.trade { color: var(--pending); }
        .log-entry.win { color: var(--up); }
        .log-entry.loss { color: var(--down); }
        
        .trades-list {
            max-height: 320px;
            overflow-y: auto;
        }
        
        .trade-row {
            display: grid;
            grid-template-columns: 24px 1fr auto;
            gap: 12px;
            align-items: center;
            padding: 14px 0;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }
        
        .trade-row:last-child { border-bottom: none; }
        
        .trade-row.pending-row {
            background: var(--accent-dim);
            margin: 0 -20px;
            padding: 14px 20px;
            border-left: 3px solid var(--accent);
        }
        
        .trade-icon {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 700;
        }
        
        .trade-icon.win { background: var(--up-dim); color: var(--up); }
        .trade-icon.loss { background: var(--down-dim); color: var(--down); }
        .trade-icon.open { background: var(--accent-dim); color: var(--accent); }
        
        .trade-info .dir {
            font-weight: 600;
            font-family: 'Space Mono', monospace;
        }
        
        .trade-info .meta {
            font-size: 11px;
            color: var(--text-dim);
            margin-top: 2px;
        }
        
        .trade-pnl {
            font-family: 'Space Mono', monospace;
            font-weight: 600;
            text-align: right;
        }
        
        .trade-pnl.positive { color: var(--up); }
        .trade-pnl.negative { color: var(--down); }
        .trade-pnl.pending { color: var(--accent); }
        
        .empty {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-dim);
            font-size: 13px;
        }
        
        footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            font-size: 11px;
            color: var(--text-dim);
        }
        
        .pulse {
            width: 6px;
            height: 6px;
            background: var(--up);
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">Polymarket BTC / 5m</div>
            <span class="status {{ 'open' if pending else 'scanning' }}">
                {{ "Position Open" if pending else "Scanning" }}
            </span>
        </header>
        
        <div class="hero">
            <div class="hero-stat">
                <div class="label">Bankroll</div>
                <div class="value mono">${{ "%.2f"|format(bankroll) }}</div>
            </div>
            <div class="hero-stat">
                <div class="label">Total P/L</div>
                <div class="value {{ 'positive' if total_pnl >= 0 else 'negative' }}">
                    ${{ "%+.2f"|format(total_pnl) }}
                </div>
            </div>
            <div class="hero-stat">
                <div class="label">Record</div>
                <div class="value mono">{{ wins }}-{{ losses }}</div>
            </div>
            <div class="hero-stat">
                <div class="label">Win Rate</div>
                <div class="value mono">{{ "%.0f"|format(win_rate * 100) }}%</div>
            </div>
        </div>
        
        <div class="panels">
            <div class="panel">
                <div class="panel-head">Price</div>
                <div class="price-block">
                    <div class="price">${{ "{:,.2f}".format(price) if price else "---" }}</div>
                    {% if momentum_1m %}
                    <div class="change {{ 'up' if momentum_1m >= 0 else 'down' }}">
                        {{ "%+.3f"|format(momentum_1m * 100) }}% / 1m
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-head">Signal</div>
                <div class="panel-body">
                    {% if last_signal %}
                    <div class="signal-grid">
                        <div>
                            <div class="signal-row">
                                <span class="key">Direction</span>
                                <span class="val">{{ last_signal.direction }}</span>
                            </div>
                            <div class="signal-row">
                                <span class="key">Edge</span>
                                <span class="val">{{ "%.1f"|format(last_signal.edge * 100) }}%</span>
                            </div>
                            <div class="signal-row">
                                <span class="key">Confidence</span>
                                <span class="val">{{ last_signal.confidence }}</span>
                            </div>
                        </div>
                        <div>
                            <div class="signal-row">
                                <span class="key">Our Prob</span>
                                <span class="val">{{ "%.0f"|format(last_signal.our_probability * 100) }}%</span>
                            </div>
                            <div class="signal-row">
                                <span class="key">Market</span>
                                <span class="val">{{ "%.0f"|format(last_signal.market_probability * 100) }}%</span>
                            </div>
                        </div>
                    </div>
                    {% else %}
                    <div class="empty">Awaiting signal</div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        {% if components %}
        <div class="panel" style="margin-bottom: 24px;">
            <div class="panel-head">Components</div>
            <div class="panel-body">
                <div class="components">
                    <div class="comp">
                        <div class="label">Mom 30s</div>
                        <div class="value {{ 'up' if components.mom_30s >= 0 else 'down' }}">
                            {{ "%+.4f"|format(components.mom_30s) }}
                        </div>
                        <div class="bar">
                            <div class="bar-fill {{ 'up' if components.mom_30s >= 0 else 'down' }}" 
                                 style="width: {{ (min(abs(components.mom_30s) * 10000, 100))|int }}%"></div>
                        </div>
                    </div>
                    <div class="comp">
                        <div class="label">Mom 1m</div>
                        <div class="value {{ 'up' if components.mom_1m >= 0 else 'down' }}">
                            {{ "%+.4f"|format(components.mom_1m) }}
                        </div>
                        <div class="bar">
                            <div class="bar-fill {{ 'up' if components.mom_1m >= 0 else 'down' }}" 
                                 style="width: {{ (min(abs(components.mom_1m) * 10000, 100))|int }}%"></div>
                        </div>
                    </div>
                    <div class="comp">
                        <div class="label">Mom 3m</div>
                        <div class="value {{ 'up' if components.mom_3m >= 0 else 'down' }}">
                            {{ "%+.4f"|format(components.mom_3m) }}
                        </div>
                        <div class="bar">
                            <div class="bar-fill {{ 'up' if components.mom_3m >= 0 else 'down' }}" 
                                 style="width: {{ (min(abs(components.mom_3m) * 10000, 100))|int }}%"></div>
                        </div>
                    </div>
                    <div class="comp">
                        <div class="label">Accel</div>
                        <div class="value {{ 'up' if components.mom_accel >= 0 else 'down' }}">
                            {{ "%+.4f"|format(components.mom_accel) }}
                        </div>
                    </div>
                    <div class="comp">
                        <div class="label">Volatility</div>
                        <div class="value">{{ "%.4f"|format(components.volatility) }}</div>
                    </div>
                    <div class="comp">
                        <div class="label">Trend</div>
                        <div class="value">
                            {% if components.trend_alignment == 1 %}UP
                            {% elif components.trend_alignment == -1 %}DOWN
                            {% else %}MIXED{% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="panels">
            <div class="panel">
                <div class="panel-head">Log</div>
                <div class="panel-body">
                    <div class="log-scroll">
                        {% for log in logs|reverse %}
                        <div class="log-entry {{ log.level }}">
                            <span class="time">{{ log.time }}</span>
                            <span class="msg">{{ log.msg }}</span>
                        </div>
                        {% else %}
                        <div class="empty">Waiting for activity</div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-head">Trades</div>
                <div class="panel-body">
                    <div class="trades-list">
                        {% if pending %}
                        <div class="trade-row pending-row">
                            <div class="trade-icon open">O</div>
                            <div class="trade-info">
                                <div class="dir">{{ pending.direction }} @ ${{ "{:,.2f}".format(pending.entry_price) }}</div>
                                <div class="meta">Edge {{ "%.1f"|format(pending.edge * 100) }}% / Size ${{ "%.2f"|format(pending.size) }}</div>
                            </div>
                            <div class="trade-pnl pending">OPEN</div>
                        </div>
                        {% endif %}
                        {% for trade in trades[-10:]|reverse %}
                        <div class="trade-row">
                            <div class="trade-icon {{ 'win' if trade.won else 'loss' }}">{{ "W" if trade.won else "L" }}</div>
                            <div class="trade-info">
                                <div class="dir">{{ trade.direction }} @ ${{ "{:,.2f}".format(trade.entry_price) }}</div>
                                <div class="meta">Edge {{ "%.1f"|format(trade.edge * 100) }}% / Exit ${{ "{:,.2f}".format(trade.exit_price) if trade.exit_price else "---" }}</div>
                            </div>
                            <div class="trade-pnl {{ 'positive' if trade.pnl and trade.pnl >= 0 else 'negative' }}">
                                ${{ "%+.2f"|format(trade.pnl) if trade.pnl else "---" }}
                            </div>
                        </div>
                        {% else %}
                        {% if not pending %}
                        <div class="empty">No trades yet</div>
                        {% endif %}
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <span>Started {{ start_time }}</span>
            <span><span class="pulse"></span>Auto-refresh 5s</span>
        </footer>
    </div>
    
    <script>setTimeout(() => location.reload(), 5000);</script>
</body>
</html>
"""

start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

def run_trader():
    """Run trader in background thread with logging"""
    global trader
    trader = PaperTrader(log_callback=log_activity)
    asyncio.run(trader.run())

@app.route('/')
def dashboard():
    global trader
    
    if trader is None:
        return render_template_string(DASHBOARD_HTML,
            price=None, bankroll=1000, total_pnl=0, wins=0, losses=0,
            win_rate=0, trades=[], pending=None, last_signal=None, 
            components=None, momentum_1m=None, logs=list(activity_log),
            start_time=start_time)
    
    win_rate = trader.wins / (trader.wins + trader.losses) if (trader.wins + trader.losses) > 0 else 0
    
    # Get momentum for display
    momentum_1m = trader.price_feed.get_momentum(60) if trader.price_feed else None
    
    # Get signal components
    components = None
    if hasattr(trader, 'last_signal') and trader.last_signal:
        components = trader.last_signal.components
    
    return render_template_string(DASHBOARD_HTML,
        price=trader.price_feed.current_price if trader.price_feed else None,
        bankroll=trader.bankroll,
        total_pnl=trader.total_pnl,
        wins=trader.wins,
        losses=trader.losses,
        win_rate=win_rate,
        trades=trader.trades,
        pending=trader.pending_trade,
        last_signal=getattr(trader, 'last_signal', None),
        components=components,
        momentum_1m=momentum_1m,
        logs=list(activity_log),
        start_time=start_time
    )

@app.route('/api/stats')
def api_stats():
    global trader
    if trader is None:
        return jsonify({"status": "starting"})
    
    return jsonify({
        "price": trader.price_feed.current_price if trader.price_feed else None,
        "bankroll": trader.bankroll,
        "total_pnl": trader.total_pnl,
        "daily_pnl": trader.daily_pnl,
        "wins": trader.wins,
        "losses": trader.losses,
        "trades": len(trader.trades),
        "pending": trader.pending_trade is not None,
        "logs": list(activity_log)[-20:]
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
