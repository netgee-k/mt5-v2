# app/mt5_client.py - COMPLETE FIXED VERSION (NO WIN FIELD)
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz
from typing import Optional, List
import os
from dotenv import load_dotenv
from . import schemas

load_dotenv()

class MT5Client:
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN", 0))
        self.password = os.getenv("MT5_PASSWORD", "")
        self.server = os.getenv("MT5_SERVER", "")
        self.connected = False
    
    def connect(self):
        if not mt5.initialize():
            print(f"MT5 initialize() failed, error code = {mt5.last_error()}")
            return False
        
        authorized = mt5.login(
            login=self.login,
            password=self.password,
            server=self.server
        )
        
        if not authorized:
            print(f"MT5 login failed, error code = {mt5.last_error()}")
            mt5.shutdown()
            return False
        
        self.connected = True
        print("Connected to MT5")
        return True
    
    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False
    
    def sync_trades(self, days: int = 30) -> List[schemas.TradeCreate]:
        """Sync CLOSED trades from MT5 - NO win field in TradeCreate"""
        if not self.connected:
            if not self.connect():
                return []
        
        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            print(f"Looking for trades from {from_date.date()} to {to_date.date()}")
            
            # Get deals from date range
            all_deals = mt5.history_deals_get(from_date, to_date)
            
            if all_deals is None:
                print(f"No deals found. MT5 Error: {mt5.last_error()}")
                return []
            
            print(f"Found {len(all_deals)} total deals in date range")
            
            # Debug: Show what types of deals we have
            entry_counts = {}
            for deal in all_deals[:10]:  # Check first 10
                entry_counts[deal.entry] = entry_counts.get(deal.entry, 0) + 1
                if deal.entry == 1:  # Closing deals
                    print(f"  Closing Deal {deal.ticket}: Profit=${deal.profit:.2f}, "
                          f"Position={deal.position_id}, Symbol={deal.symbol}")
            
            print(f"Deal entry types found: {entry_counts}")
            print("(Entry 0=Open, 1=Close, 2=Reverse, 3=Close by)")
            
            trades = []
            # Group deals by position_id to match opens with closes
            positions = {}
            
            for deal in all_deals:
                position_id = deal.position_id
                if position_id not in positions:
                    positions[position_id] = {'open': None, 'close': None}
                
                if deal.entry == 0:  # Opening deal
                    positions[position_id]['open'] = deal
                elif deal.entry == 1:  # Closing deal
                    positions[position_id]['close'] = deal
            
            # Process complete trades (both open and close exist)
            for position_id, deals in positions.items():
                if deals['open'] is not None and deals['close'] is not None:
                    open_deal = deals['open']
                    close_deal = deals['close']
                    
                    # Calculate time in UTC
                    time_open = datetime.fromtimestamp(open_deal.time, tz=pytz.UTC)
                    time_close = datetime.fromtimestamp(close_deal.time, tz=pytz.UTC)
                    
                    # Determine trade type from opening deal
                    trade_type = 'BUY' if open_deal.type == 0 else 'SELL'
                    
                    # Safe attribute access - MT5 TradeDeal objects don't have sl/tp!
                    sl_value = self._get_deal_attribute(open_deal, 'sl', 0.0)
                    tp_value = self._get_deal_attribute(open_deal, 'tp', 0.0)
                    open_commission = self._get_deal_attribute(open_deal, 'commission', 0.0)
                    close_commission = self._get_deal_attribute(close_deal, 'commission', 0.0)
                    swap_value = self._get_deal_attribute(close_deal, 'swap', 0.0)
                    
                    # Get comments safely
                    open_comment = self._get_deal_attribute(open_deal, 'comment', '')
                    close_comment = self._get_deal_attribute(close_deal, 'comment', '')
                    comment = close_comment or open_comment or ''
                    
                    # Create TradeCreate WITHOUT win field (will be calculated by crud.py)
                    trade = schemas.TradeCreate(
                        ticket=close_deal.ticket,  # Use closing ticket
                        position_id=position_id,
                        time=time_open,
                        type=trade_type,
                        symbol=open_deal.symbol,
                        volume=open_deal.volume,
                        price=open_deal.price,  # Opening price
                        sl=sl_value,
                        tp=tp_value,
                        time_close=time_close,
                        price_close=close_deal.price,  # Closing price
                        commission=open_commission + close_commission,
                        swap=swap_value,
                        profit=close_deal.profit,
                        comment=comment
                        # NO win field here - crud.py will calculate it from profit
                    )
                    trades.append(trade)
                    print(f"  Processed: {open_deal.symbol} {trade_type} Profit=${close_deal.profit:.2f}")
            
            print(f"Successfully processed {len(trades)} completed trades")
            
            # Also process unmatched closing deals
            unmatched_closes = 0
            for position_id, deals in positions.items():
                if deals['close'] is not None and deals['open'] is None:
                    close_deal = deals['close']
                    unmatched_closes += 1
                    
                    # Create trade from closing deal only
                    time_close = datetime.fromtimestamp(close_deal.time, tz=pytz.UTC)
                    trade_type = 'BUY' if close_deal.type == 0 else 'SELL'
                    
                    # Safe attribute access
                    sl_value = self._get_deal_attribute(close_deal, 'sl', 0.0)
                    tp_value = self._get_deal_attribute(close_deal, 'tp', 0.0)
                    commission = self._get_deal_attribute(close_deal, 'commission', 0.0)
                    swap_value = self._get_deal_attribute(close_deal, 'swap', 0.0)
                    comment = self._get_deal_attribute(close_deal, 'comment', '')
                    
                    # Create TradeCreate WITHOUT win field
                    trade = schemas.TradeCreate(
                        ticket=close_deal.ticket,
                        position_id=position_id,
                        time=time_close,  # Use close time since no open
                        type=trade_type,
                        symbol=close_deal.symbol,
                        volume=close_deal.volume,
                        price=close_deal.price,
                        sl=sl_value,
                        tp=tp_value,
                        time_close=time_close,
                        price_close=close_deal.price,
                        commission=commission,
                        swap=swap_value,
                        profit=close_deal.profit,
                        comment=comment
                        # NO win field here
                    )
                    trades.append(trade)
                    print(f"  Added unmatched: {close_deal.symbol} Profit=${close_deal.profit:.2f}")
            
            if unmatched_closes > 0:
                print(f"Added {unmatched_closes} trades from unmatched closing deals")
            
            print(f"Total trades ready for database: {len(trades)}")
            return trades
            
        except Exception as e:
            print(f"Error in sync_trades: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_deal_attribute(self, deal, attr_name, default_value):
        """Safely get an attribute from MT5 deal with fallback"""
        try:
            return getattr(deal, attr_name, default_value)
        except AttributeError:
            return default_value
    
    def sync_all_trades(self):
        return self.sync_trades(days=365*5)  # 5 years
    
    def debug_account_info(self):
        """Debug function to check account info"""
        if not self.connected:
            if not self.connect():
                return
        
        try:
            account_info = mt5.account_info()
            if account_info:
                print(f"\n=== MT5 Account Info ===")
                print(f"Login: {account_info.login}")
                print(f"Balance: ${account_info.balance:.2f}")
                print(f"Equity: ${account_info.equity:.2f}")
                print(f"Server: {account_info.server}")
                print(f"Leverage: 1:{account_info.leverage}")
            else:
                print("No account info available")
                
            # Check terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info:
                print(f"\n=== Terminal Info ===")
                print(f"Connected: {terminal_info.connected}")
                print(f"DLL build: {terminal_info.build}")
                print(f"Max bars: {terminal_info.maxbars}")
                
        except Exception as e:
            print(f"Error getting account info: {e}")
    
    def inspect_deal_attributes(self):
        """Debug: Inspect what attributes MT5 deals actually have"""
        if not self.connected:
            if not self.connect():
                return
        
        try:
            # Get one recent deal
            deals = mt5.history_deals_get(datetime.now() - timedelta(days=1), datetime.now())
            if deals and len(deals) > 0:
                print("\n=== MT5 Deal Attribute Inspection ===")
                deal = deals[0]
                
                # List all attributes
                print(f"\nAll attributes of a TradeDeal object:")
                for attr in dir(deal):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(deal, attr)
                            print(f"  {attr}: {type(value).__name__} = {value}")
                        except:
                            print(f"  {attr}: [Error accessing]")
                
                # Show common attributes
                print(f"\nKey attributes of this deal:")
                key_attrs = ['ticket', 'position_id', 'time', 'type', 'entry', 
                           'symbol', 'volume', 'price', 'profit', 'commission', 
                           'swap', 'comment']
                for attr in key_attrs:
                    try:
                        value = getattr(deal, attr, "NOT PRESENT")
                        print(f"  {attr}: {value}")
                    except:
                        print(f"  {attr}: Error")
            else:
                print("No deals to inspect")
                
        except Exception as e:
            print(f"Error inspecting deals: {e}")