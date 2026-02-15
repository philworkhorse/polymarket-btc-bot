#!/usr/bin/env python3
"""Quick test of price feed and prediction"""

import asyncio
from price_feed import BTCPriceFeed

async def main():
    feed = BTCPriceFeed()
    
    print("Connecting to Binance BTC feed...")
    print("Collecting data for 30 seconds...\n")
    
    task = asyncio.create_task(feed.start())
    
    for i in range(6):
        await asyncio.sleep(5)
        
        if feed.current_price:
            mom_1m = feed.get_momentum(60)
            direction, confidence = feed.predict_direction(300)
            
            print(f"[{(i+1)*5}s] BTC: ${feed.current_price:,.2f}")
            print(f"      Momentum 1m: {mom_1m*100 if mom_1m else 0:.3f}%")
            print(f"      Prediction: {direction} ({confidence:.1%} confidence)")
            print()
    
    feed.stop()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
