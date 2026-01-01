import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz
from typing import Optional, List
import os
from dotenv import load_dotenv
from . import schemas

load_dotenv()

class MT5Client:
    def __init__(self, server: str = None, login: int = None, password: str = None):
        self.login = login or int(os.getenv("MT5_LOGIN", 0))
        self.password = password or os.getenv("MT5_PASSWORD", "")
        self.server = server or os.getenv("MT5_SERVER", "")
        self.connected = False
    
    def connect(self):
        """Connect to MT5"""
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
        print(f"Connected to MT5: {self.server}, Login: {self.login}")
        return True
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("Disconnected from MT5")
    
    def sync_trades(self, days: int = 30) -> List[schemas.TradeCreate]:
        """Sync trades from MT5"""
        if not self.connected:
            if not self.connect():
                return []
        
        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            print(f"Syncing trades from {from_date.date()} to {to_date.date()}")
            
            # Get deals (closed trades)
            deals = mt5.history_deals_get(from_date, to_date)
            
            if deals is None or len(deals) == 0:
                print(f"No deals found. MT5 Error: {mt5.last_error()}")
                return []
            
            print(f"Found {len(deals)} deals")
            
            # Get orders (open positions)
            orders = mt5.history_orders_get(from_date, to_date)
            if orders:
                print(f"Found {len(orders)} orders")
            
            trades = []
            processed_tickets = set()
            
            # Process deals to find closed trades
            for deal in deals:
                # Skip if we already processed this ticket
                if deal.ticket in processed_tickets:
                    continue
                
                # Only process closing deals (entry=1)
                if deal.entry != 1:  # 0=in, 1=out, 2=in/out
                    continue
                
                # Get position_id for this closing deal
                position_id = deal.position_id
                
                # Find the opening deal for this position
                opening_deal = None
                for potential_open in deals:
                    if (potential_open.entry == 0 and 
                        potential_open.position_id == position_id):
                        opening_deal = potential_open
                        break
                
                if opening_deal:
                    # Create trade from complete pair
                    trade = self._create_trade_from_pair(opening_deal, deal)
                    if trade:
                        trades.append(trade)
                        processed_tickets.add(deal.ticket)
                        processed_tickets.add(opening_deal.ticket)
                else:
                    # Single deal (might be partial close or other)
                    trade = self._create_trade_from_single_deal(deal)
                    if trade:
                        trades.append(trade)
                        processed_tickets.add(deal.ticket)
            
            print(f"Successfully created {len(trades)} trades")
            return trades
            
        except Exception as e:
            print(f"Error in sync_trades: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            self.disconnect()
    
    def _create_trade_from_pair(self, open_deal, close_deal) -> Optional[schemas.TradeCreate]:
        """Create a TradeCreate from open/close deal pair"""
        try:
            # Convert timestamps
            time_open = datetime.fromtimestamp(open_deal.time, tz=pytz.UTC)
            time_close = datetime.fromtimestamp(close_deal.time, tz=pytz.UTC)
            
            # Determine trade type
            trade_type = "BUY" if open_deal.type == 0 else "SELL"
            
            # Calculate pips if possible
            pips = 0.0
            if hasattr(open_deal, 'price') and hasattr(close_deal, 'price'):
                if trade_type == "BUY":
                    pips = (close_deal.price - open_deal.price) * 10000
                else:
                    pips = (open_deal.price - close_deal.price) * 10000
            
            # Calculate win (profit > 0)
            profit = getattr(close_deal, 'profit', 0.0)
            win = profit > 0
            
            # Get commission and swap
            commission = getattr(open_deal, 'commission', 0.0) + getattr(close_deal, 'commission', 0.0)
            swap = getattr(close_deal, 'swap', 0.0)
            
            # Create TradeCreate object using the CORRECT schema
            return schemas.TradeCreate(
                ticket=close_deal.ticket,
                symbol=open_deal.symbol,
                type=trade_type,
                volume=open_deal.volume,
                entry_price=open_deal.price,
                exit_price=close_deal.price,
                profit=profit,
                commission=commission,
                swap=swap,
                time=time_open,
                time_close=time_close,
                # These are calculated in crud.py or here:
                pips=abs(pips),
                win=win,
                win_rate=100.0 if win else 0.0,
                notes="",
                tags=""
            )
            
        except Exception as e:
            print(f"Error creating trade from pair: {e}")
            return None
    
    def _create_trade_from_single_deal(self, deal) -> Optional[schemas.TradeCreate]:
        """Create a TradeCreate from a single deal"""
        try:
            time_deal = datetime.fromtimestamp(deal.time, tz=pytz.UTC)
            trade_type = "BUY" if deal.type == 0 else "SELL"
            
            profit = getattr(deal, 'profit', 0.0)
            win = profit > 0
            
            return schemas.TradeCreate(
                ticket=deal.ticket,
                symbol=deal.symbol,
                type=trade_type,
                volume=deal.volume,
                entry_price=deal.price,
                exit_price=deal.price,
                profit=profit,
                commission=getattr(deal, 'commission', 0.0),
                swap=getattr(deal, 'swap', 0.0),
                time=time_deal,
                time_close=time_deal,
                pips=0.0,
                win=win,
                win_rate=100.0 if win else 0.0,
                notes="",
                tags=""
            )
            
        except Exception as e:
            print(f"Error creating trade from single deal: {e}")
            return None
    
    def get_open_positions(self):
        """Get current open positions"""
        if not self.connected:
            if not self.connect():
                return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                print(f"No open positions. MT5 Error: {mt5.last_error()}")
                return []
            
            print(f"Found {len(positions)} open positions")
            return positions
            
        except Exception as e:
            print(f"Error getting open positions: {e}")
            return []
        finally:
            self.disconnect()
    
    def test_connection(self):
        """Test MT5 connection"""
        try:
            if self.connect():
                print(f"✓ MT5 Connection Successful")
                print(f"  Server: {self.server}")
                print(f"  Login: {self.login}")
                
                # Get account info
                account = mt5.account_info()
                if account:
                    print(f"  Balance: ${account.balance:.2f}")
                    print(f"  Equity: ${account.equity:.2f}")
                
                self.disconnect()
                return True
            else:
                print(f"✗ MT5 Connection Failed")
                return False
                
        except Exception as e:
            print(f"✗ MT5 Test Error: {e}")
            return False