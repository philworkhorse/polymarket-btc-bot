module.exports = {
  apps: [
    {
      name: 'polymarket-web',
      script: 'venv/bin/gunicorn',
      args: 'app:app --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 300',
      cwd: '/Users/trentishee-dunn/projects/polymarket-btc-bot',
      env: {
        PORT: 8080,
        MIN_EDGE: 0.03,
        BET_SIZE_USDC: 10,
        MAX_DAILY_LOSS: 50
      }
    },
    {
      name: 'polymarket-tunnel',
      script: '/opt/homebrew/bin/cloudflared',
      args: 'tunnel --url http://localhost:8080',
      autorestart: true,
      restart_delay: 3000
    }
  ]
};
