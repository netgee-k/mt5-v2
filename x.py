# test_mt5.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.mt5_client import MT5Client

def test_mt5():
    print("Testing MT5 connection and trade sync...")
    
    client = MT5Client()
    
    # Test connection
    if not client.connect():
        print("Failed to connect to MT5")
        return
    
    # Debug account info
    client.debug_account_info()
    
    # Try to sync trades
    print("\n=== Syncing Trades ===")
    trades = client.sync_trades(days=30)
    
    if trades:
        print(f"\nSuccessfully synced {len(trades)} trades!")
        for i, trade in enumerate(trades[:3]):  # Show first 3
            print(f"\nTrade {i+1}:")
            print(f"  Ticket: {trade.ticket}")
            print(f"  Symbol: {trade.symbol}")
            print(f"  Type: {trade.type}")
            print(f"  Profit: ${trade.profit:.2f}")
            print(f"  Time: {trade.time}")
    else:
        print("\nNo trades found. Possible reasons:")
        print("1. No trading history in the specified date range")
        print("2. Account has only open positions (not closed trades)")
        print("3. Check MT5 'Account History' tab to verify trades exist")
    
    client.disconnect()

if __name__ == "__main__":
    test_mt5()