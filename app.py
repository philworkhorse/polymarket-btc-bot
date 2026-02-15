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

# Dashboard HTML - Clean, practical, modern
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>BTC 5m Paper Trader</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        :root {
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --text: #e6edf3;
            --text-muted: #8b949e;
            --green: #3fb950;
            --red: #f85149;
            --yellow: #d29922;
            --blue: #58a6ff;
        }
        
        body {
            font-family: 'IBM Plex Sans', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }
        
        header h1 {
            font-size: 18px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-badge {
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 500;
        }
        
        .status-badge.live { background: rgba(63, 185, 80, 0.15); color: var(--green); }
        .status-badge.pending { background: rgba(210, 153, 34, 0.15); color: var(--yellow); }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 16px;
        }
        
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
        }
        
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }
        
        .card-header {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        
        .price-display {
            font-family: 'JetBrains Mono', monospace;
            font-size: 32px;
            font-weight: 600;
        }
        
        .price-change {
            font-size: 14px;
            margin-top: 4px;
        }
        
        .price-change.up { color: var(--green); }
        .price-change.down { color: var(--red); }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 16px;
        }
        
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        .stat {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
        }
        
        .stat-label {
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }
        
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 600;
        }
        
        .stat-value.positive { color: var(--green); }
        .stat-value.negative { color: var(--red); }
        
        .signal-card {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        
        .signal-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }
        
        .signal-item:last-child { border-bottom: none; }
        
        .signal-label { color: var(--text-muted); }
        
        .signal-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
        }
        
        .momentum-bar {
            height: 4px;
            background: var(--border);
            border-radius: 2px;
            margin-top: 4px;
            overflow: hidden;
        }
        
        .momentum-fill {
            height: 100%;
            border-radius: 2px;
            transition: width 0.3s ease;
        }
        
        .momentum-fill.positive { background: var(--green); }
        .momentum-fill.negative { background: var(--red); }
        
        .log-container {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .log-header {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .log-entries {
            max-height: 300px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }
        
        .log-entry {
            padding: 8px 16px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 12px;
        }
        
        .log-entry:last-child { border-bottom: none; }
        
        .log-time { color: var(--text-muted); min-width: 60px; }
        .log-msg { flex: 1; word-break: break-word; }
        .log-entry.signal { color: var(--blue); }
        .log-entry.trade { color: var(--yellow); }
        .log-entry.win { color: var(--green); }
        .log-entry.loss { color: var(--red); }
        
        .trade-list {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
        }
        
        .trade-header {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .trade-item {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            display: grid;
            grid-template-columns: auto 1fr auto auto;
            gap: 16px;
            align-items: center;
            font-size: 14px;
        }
        
        .trade-item:last-child { border-bottom: none; }
        
        .trade-icon { font-size: 16px; }
        
        .trade-details {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }
        
        .trade-direction { font-weight: 600; }
        .trade-meta { color: var(--text-muted); font-size: 12px; }
        
        .trade-pnl {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        }
        
        .trade-pnl.positive { color: var(--green); }
        .trade-pnl.negative { color: var(--red); }
        
        .pending-trade {
            background: rgba(210, 153, 34, 0.1);
            border-left: 3px solid var(--yellow);
        }
        
        .no-trades {
            padding: 32px 16px;
            text-align: center;
            color: var(--text-muted);
        }
        
        footer {
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
        }
        
        .auto-refresh {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .pulse {
            width: 8px;
            height: 8px;
            background: var(--green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <span>📊</span>
                BTC 5m Paper Trader
            </h1>
            <span class="status-badge {{ 'pending' if pending else 'live' }}">
                {{ "Position Open" if pending else "Scanning" }}
            </span>
        </header>
        
        <div class="stats-grid">
            <div class="stat">
                <div class="stat-label">Bankroll</div>
                <div class="stat-value">${{ "%.2f"|format(bankroll) }}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Total P&L</div>
                <div class="stat-value {{ 'positive' if total_pnl >= 0 else 'negative' }}">
                    ${{ "%+.2f"|format(total_pnl) }}
                </div>
            </div>
            <div class="stat">
                <div class="stat-label">Record</div>
                <div class="stat-value">{{ wins }}W / {{ losses }}L</div>
            </div>
            <div class="stat">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value">{{ "%.0f"|format(win_rate * 100) }}%</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-header">Current Price</div>
                <div class="price-display">${{ "{:,.2f}".format(price) if price else "---" }}</div>
                {% if momentum_1m %}
                <div class="price-change {{ 'up' if momentum_1m >= 0 else 'down' }}">
                    {{ "%+.3f"|format(momentum_1m * 100) }}% (1m)
                </div>
                {% endif %}
            </div>
            
            <div class="card">
                <div class="card-header">Current Signal</div>
                {% if last_signal %}
                <div class="signal-card">
                    <div>
                        <div class="signal-item">
                            <span class="signal-label">Direction</span>
                            <span class="signal-value">{{ last_signal.direction }}</span>
                        </div>
                        <div class="signal-item">
                            <span class="signal-label">Edge</span>
                            <span class="signal-value">{{ "%.1f"|format(last_signal.edge * 100) }}%</span>
                        </div>
                        <div class="signal-item">
                            <span class="signal-label">Confidence</span>
                            <span class="signal-value">{{ last_signal.confidence }}</span>
                        </div>
                    </div>
                    <div>
                        <div class="signal-item">
                            <span class="signal-label">Our Prob</span>
                            <span class="signal-value">{{ "%.0f"|format(last_signal.our_probability * 100) }}%</span>
                        </div>
                        <div class="signal-item">
                            <span class="signal-label">Market Prob</span>
                            <span class="signal-value">{{ "%.0f"|format(last_signal.market_probability * 100) }}%</span>
                        </div>
                    </div>
                </div>
                {% else %}
                <div style="color: var(--text-muted);">Waiting for signal...</div>
                {% endif %}
            </div>
        </div>
        
        {% if components %}
        <div class="card" style="margin-bottom: 16px;">
            <div class="card-header">Strategy Components</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px;">
                <div>
                    <div class="signal-label">30s Momentum</div>
                    <div class="signal-value" style="color: {{ 'var(--green)' if components.mom_30s >= 0 else 'var(--red)' }}">
                        {{ "%+.4f"|format(components.mom_30s) }}
                    </div>
                    <div class="momentum-bar">
                        <div class="momentum-fill {{ 'positive' if components.mom_30s >= 0 else 'negative' }}" 
                             style="width: {{ (min(abs(components.mom_30s) * 10000, 100))|int }}%"></div>
                    </div>
                </div>
                <div>
                    <div class="signal-label">1m Momentum</div>
                    <div class="signal-value" style="color: {{ 'var(--green)' if components.mom_1m >= 0 else 'var(--red)' }}">
                        {{ "%+.4f"|format(components.mom_1m) }}
                    </div>
                    <div class="momentum-bar">
                        <div class="momentum-fill {{ 'positive' if components.mom_1m >= 0 else 'negative' }}" 
                             style="width: {{ (min(abs(components.mom_1m) * 10000, 100))|int }}%"></div>
                    </div>
                </div>
                <div>
                    <div class="signal-label">3m Momentum</div>
                    <div class="signal-value" style="color: {{ 'var(--green)' if components.mom_3m >= 0 else 'var(--red)' }}">
                        {{ "%+.4f"|format(components.mom_3m) }}
                    </div>
                    <div class="momentum-bar">
                        <div class="momentum-fill {{ 'positive' if components.mom_3m >= 0 else 'negative' }}" 
                             style="width: {{ (min(abs(components.mom_3m) * 10000, 100))|int }}%"></div>
                    </div>
                </div>
                <div>
                    <div class="signal-label">Acceleration</div>
                    <div class="signal-value" style="color: {{ 'var(--green)' if components.mom_accel >= 0 else 'var(--red)' }}">
                        {{ "%+.4f"|format(components.mom_accel) }}
                    </div>
                </div>
                <div>
                    <div class="signal-label">Volatility</div>
                    <div class="signal-value">{{ "%.4f"|format(components.volatility) }}</div>
                </div>
                <div>
                    <div class="signal-label">Trend Align</div>
                    <div class="signal-value">
                        {% if components.trend_alignment == 1 %}🟢 Bullish
                        {% elif components.trend_alignment == -1 %}🔴 Bearish
                        {% else %}⚪ Mixed{% endif %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="grid">
            <div class="log-container">
                <div class="log-header">
                    <span>Activity Log</span>
                    <span>Last {{ logs|length }} events</span>
                </div>
                <div class="log-entries">
                    {% for log in logs|reverse %}
                    <div class="log-entry {{ log.level }}">
                        <span class="log-time">{{ log.time }}</span>
                        <span class="log-msg">{{ log.msg }}</span>
                    </div>
                    {% else %}
                    <div class="log-entry">
                        <span class="log-msg" style="color: var(--text-muted);">Waiting for activity...</span>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="trade-list">
                <div class="trade-header">Recent Trades</div>
                {% if pending %}
                <div class="trade-item pending-trade">
                    <span class="trade-icon">⏳</span>
                    <div class="trade-details">
                        <div><span class="trade-direction">{{ pending.direction }}</span> @ ${{ "{:,.2f}".format(pending.entry_price) }}</div>
                        <div class="trade-meta">Edge: {{ "%.1f"|format(pending.edge * 100) }}% | Size: ${{ "%.2f"|format(pending.size) }}</div>
                    </div>
                    <span></span>
                    <span class="trade-pnl" style="color: var(--yellow);">OPEN</span>
                </div>
                {% endif %}
                {% for trade in trades[-8:]|reverse %}
                <div class="trade-item">
                    <span class="trade-icon">{{ "✅" if trade.won else "❌" }}</span>
                    <div class="trade-details">
                        <div><span class="trade-direction">{{ trade.direction }}</span> @ ${{ "{:,.2f}".format(trade.entry_price) }}</div>
                        <div class="trade-meta">Edge: {{ "%.1f"|format(trade.edge * 100) }}% | Exit: ${{ "{:,.2f}".format(trade.exit_price) if trade.exit_price else "---" }}</div>
                    </div>
                    <span></span>
                    <span class="trade-pnl {{ 'positive' if trade.pnl and trade.pnl >= 0 else 'negative' }}">
                        ${{ "%+.2f"|format(trade.pnl) if trade.pnl else "---" }}
                    </span>
                </div>
                {% else %}
                {% if not pending %}
                <div class="no-trades">No trades yet. Waiting for edge...</div>
                {% endif %}
                {% endfor %}
            </div>
        </div>
        
        <footer>
            <span>Started: {{ start_time }}</span>
            <div class="auto-refresh">
                <div class="pulse"></div>
                <span>Auto-refresh 5s</span>
            </div>
        </footer>
    </div>
    
    <script>
        setTimeout(() => location.reload(), 5000);
    </script>
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
