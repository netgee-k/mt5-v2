# app/services/ai_service.py
import openai
import json
import finnhub
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import requests
import asyncio
import httpx
from .config import settings
from . import crud

class AITradingAnalyzer:
    def __init__(self):
        # OpenAI Configuration
        self.openai_api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        # Finnhub Configuration (for market data in analysis)
        self.finnhub_api_key = getattr(settings, 'FINNHUB_API_KEY', 'd5fqc9hr01qie3lejdag')
        self.finnhub_client = None
        if self.finnhub_api_key:
            try:
                self.finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
            except Exception as e:
                print(f"Failed to initialize Finnhub client: {e}")
    
    def analyze_weekly_performance(self, trades: List[Dict], previous_week_stats: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze weekly trading performance using AI with market context"""
        
        if not self.openai_api_key:
            return self._generate_basic_analysis(trades)
        
        try:
            # Get current market conditions for context
            market_context = self._get_market_context()
            
            # Prepare trade data for analysis
            trade_summary = []
            for trade in trades:
                trade_summary.append({
                    'symbol': trade.get('symbol'),
                    'type': trade.get('type'),
                    'profit': trade.get('profit'),
                    'win': trade.get('win'),
                    'volume': trade.get('volume'),
                    'time': trade.get('time').isoformat() if trade.get('time') else None,
                    'entry_price': trade.get('entry_price'),
                    'exit_price': trade.get('exit_price')
                })
            
            # Prepare prompt for GPT with market context
            prompt = f"""
            Analyze this week's trading performance considering current market conditions:
            
            Market Context: {market_context}
            
            Trade Data: {json.dumps(trade_summary, default=str)}
            
            Previous Week Stats: {json.dumps(previous_week_stats or {}, default=str)}
            
            Please provide comprehensive analysis with:
            1. Brief summary of weekly performance
            2. Key strengths and weaknesses
            3. Risk management assessment
            4. 3 actionable recommendations for improvement
            5. Patterns identified in trading behavior
            6. Sentiment analysis (confidence level, emotional state)
            7. Outlook for next week with market conditions in mind
            
            Format response as JSON with these keys: summary, strengths, weaknesses, risk_assessment, recommendations, patterns, sentiment, outlook.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert trading analyst. Analyze performance with market context. Provide concise, actionable insights."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Calculate performance score (0-100)
            performance_score = self._calculate_performance_score(trades, analysis)
            
            # Get best and worst trades
            best_trade, worst_trade = self._identify_extreme_trades(trades)
            
            # Add market recommendations
            market_recommendations = self._generate_market_recommendations(trades)
            
            return {
                'summary': analysis.get('summary', ''),
                'performance_score': performance_score,
                'strengths': analysis.get('strengths', []),
                'weaknesses': analysis.get('weaknesses', []),
                'risk_assessment': analysis.get('risk_assessment', ''),
                'recommendations': analysis.get('recommendations', []) + market_recommendations,
                'patterns': analysis.get('patterns', []),
                'sentiment': analysis.get('sentiment', ''),
                'outlook': analysis.get('outlook', ''),
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'market_context': market_context
            }
            
        except Exception as e:
            print(f"AI analysis error: {e}")
            return self._generate_basic_analysis(trades)
    
    def _get_market_context(self) -> str:
        """Get current market conditions for analysis context"""
        if not self.finnhub_client:
            return "Market data unavailable"
        
        try:
            context = []
            
            # Get major indices
            symbols = ['SPY', 'QQQ', 'DIA']  # S&P 500, NASDAQ, Dow Jones
            for symbol in symbols:
                quote = self.finnhub_client.quote(symbol)
                if quote and 'c' in quote:
                    change = quote.get('dp', 0)
                    trend = "bullish" if change > 0 else "bearish" if change < 0 else "neutral"
                    context.append(f"{symbol}: ${quote['c']:.2f} ({change:+.2f}%) - {trend}")
            
            # Get forex market
            forex_pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY']
            for pair in forex_pairs:
                finnhub_symbol = f"OANDA:{pair.replace('/', '_')}"
                quote = self.finnhub_client.quote(finnhub_symbol)
                if quote and 'c' in quote:
                    context.append(f"{pair}: {quote['c']:.4f}")
            
            # Get crypto market
            crypto_symbols = ['BTC-USD', 'ETH-USD']
            for symbol in crypto_symbols:
                quote = self.finnhub_client.quote(symbol)
                if quote and 'c' in quote:
                    change = quote.get('dp', 0)
                    context.append(f"{symbol}: ${quote['c']:.2f} ({change:+.2f}%)")
            
            return " | ".join(context)
            
        except Exception as e:
            print(f"Market context error: {e}")
            return "Market data fetch failed"
    
    def _generate_market_recommendations(self, trades: List[Dict]) -> List[str]:
        """Generate market-specific recommendations"""
        if not trades or not self.finnhub_client:
            return []
        
        # Analyze most traded symbols
        symbol_counts = {}
        for trade in trades:
            symbol = trade.get('symbol')
            if symbol:
                symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        if not symbol_counts:
            return []
        
        # Get top 3 traded symbols
        top_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        recommendations = []
        for symbol, count in top_symbols:
            try:
                quote = self.finnhub_client.quote(symbol)
                if quote and 'dp' in quote:
                    change = quote.get('dp', 0)
                    if change < -5:
                        recommendations.append(f"Consider reducing exposure to {symbol} (down {abs(change):.1f}%)")
                    elif change > 5:
                        recommendations.append(f"{symbol} showing strong momentum (up {change:.1f}%)")
            except:
                pass
        
        return recommendations
    
    def _generate_basic_analysis(self, trades: List[Dict]) -> Dict[str, Any]:
        """Generate basic analysis without AI"""
        if not trades:
            return {
                'summary': "No trades this week.",
                'performance_score': 0,
                'recommendations': ["Start trading to generate performance data"],
                'patterns': [],
                'sentiment': "Neutral",
                'market_context': "No market data"
            }
        
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        losing_trades = [t for t in trades if t.get('profit', 0) <= 0]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        total_profit = sum(t.get('profit', 0) for t in trades)
        avg_profit = total_profit / len(trades) if trades else 0
        
        # Get market context
        market_context = self._get_market_context() if self.finnhub_client else "Market data unavailable"
        
        return {
            'summary': f"Traded {len(trades)} times with {win_rate:.1f}% win rate. Total profit: ${total_profit:.2f}",
            'performance_score': min(100, max(0, win_rate + (total_profit / 100))),
            'recommendations': [
                f"Maintain win rate above {win_rate:.1f}%",
                "Review losing trades for patterns",
                "Consider position sizing adjustments"
            ],
            'patterns': ["Basic pattern detection requires AI"],
            'sentiment': "Confident" if win_rate > 60 else "Cautious" if win_rate > 40 else "Needs improvement",
            'market_context': market_context
        }
    
    def _calculate_performance_score(self, trades: List[Dict], analysis: Dict) -> float:
        """Calculate performance score 0-100"""
        if not trades:
            return 0
        
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        win_rate = len(winning_trades) / len(trades) * 100
        
        # Calculate profit factor
        total_profit = sum(t.get('profit', 0) for t in winning_trades)
        total_loss = abs(sum(t.get('profit', 0) for t in trades if t.get('profit', 0) < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else 1
        
        # Calculate consistency (lower variance is better)
        profits = [t.get('profit', 0) for t in trades]
        avg_profit = sum(profits) / len(profits)
        variance = sum((p - avg_profit) ** 2 for p in profits) / len(profits)
        consistency_score = max(0, 100 - variance)
        
        # Sentiment bonus
        sentiment = analysis.get('sentiment', '').lower()
        sentiment_bonus = 0
        if 'confident' in sentiment or 'optimistic' in sentiment:
            sentiment_bonus = 5
        elif 'cautious' in sentiment or 'concerned' in sentiment:
            sentiment_bonus = -5
        
        # Combined score
        score = (win_rate * 0.4) + (min(100, profit_factor * 25) * 0.3) + (consistency_score * 0.25) + sentiment_bonus
        
        return min(100, max(0, score))
    
    def _identify_extreme_trades(self, trades: List[Dict]) -> tuple:
        """Identify best and worst trades"""
        if not trades:
            return None, None
        
        best_trade = max(trades, key=lambda x: x.get('profit', 0))
        worst_trade = min(trades, key=lambda x: x.get('profit', 0))
        
        # Get current prices for context
        best_current = self._get_current_price(best_trade.get('symbol'))
        worst_current = self._get_current_price(worst_trade.get('symbol'))
        
        return {
            'ticket': best_trade.get('ticket'),
            'symbol': best_trade.get('symbol'),
            'profit': best_trade.get('profit'),
            'entry_price': best_trade.get('entry_price'),
            'exit_price': best_trade.get('exit_price'),
            'current_price': best_current,
            'reason': "Highest profit trade",
            'performance': f"+{best_trade.get('profit', 0):.2f}"
        }, {
            'ticket': worst_trade.get('ticket'),
            'symbol': worst_trade.get('symbol'),
            'profit': worst_trade.get('profit'),
            'entry_price': worst_trade.get('entry_price'),
            'exit_price': worst_trade.get('exit_price'),
            'current_price': worst_current,
            'reason': "Largest loss trade",
            'performance': f"{worst_trade.get('profit', 0):.2f}"
        }
    
    def _get_current_price(self, symbol: Optional[str]) -> Optional[float]:
        """Get current price for a symbol"""
        if not symbol or not self.finnhub_client:
            return None
        
        try:
            quote = self.finnhub_client.quote(symbol)
            return quote.get('c') if quote else None
        except:
            return None
    
    def analyze_trade_patterns(self, trades: List[Dict]) -> List[str]:
        """Analyze patterns in trading behavior"""
        if not trades or len(trades) < 5:
            return ["Insufficient data for pattern analysis"]
        
        patterns = []
        
        # Analyze by day of week
        day_trades = {}
        for trade in trades:
            if trade.get('time'):
                day = trade['time'].strftime('%A')
                day_trades[day] = day_trades.get(day, 0) + 1
        
        if day_trades:
            most_active_day = max(day_trades.items(), key=lambda x: x[1])
            patterns.append(f"Most active trading day: {most_active_day[0]} ({most_active_day[1]} trades)")
        
        # Analyze by symbol
        symbol_profits = {}
        for trade in trades:
            symbol = trade.get('symbol')
            profit = trade.get('profit', 0)
            if symbol:
                symbol_profits[symbol] = symbol_profits.get(symbol, 0) + profit
        
        profitable_symbols = [s for s, p in symbol_profits.items() if p > 0]
        unprofitable_symbols = [s for s, p in symbol_profits.items() if p < 0]
        
        if profitable_symbols:
            patterns.append(f"Profitable symbols: {', '.join(profitable_symbols[:3])}")
        if unprofitable_symbols:
            patterns.append(f"Unprofitable symbols: {', '.join(unprofitable_symbols[:3])}")
        
        # Analyze win/loss streaks
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for trade in sorted(trades, key=lambda x: x.get('time', datetime.min)):
            if trade.get('profit', 0) > 0:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    max_loss_streak = max(max_loss_streak, abs(current_streak))
                    current_streak = 1
            else:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    max_win_streak = max(max_win_streak, current_streak)
                    current_streak = -1
        
        if current_streak > 0:
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, abs(current_streak))
        
        patterns.append(f"Longest win streak: {max_win_streak} trades")
        patterns.append(f"Longest loss streak: {max_loss_streak} trades")
        
        return patterns

class BadgeAwarder:
    def __init__(self):
        # Initialize Finnhub for market context in badges
        self.finnhub_api_key = getattr(settings, 'FINNHUB_API_KEY', 'd5fqc9hr01qie3lejdag')
        self.finnhub_client = None
        if self.finnhub_api_key:
            try:
                self.finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
            except Exception as e:
                print(f"Failed to initialize Finnhub for badges: {e}")
    
    @staticmethod
    def check_for_badges(db: Session, user_id: int, trades: List[Dict]) -> List[Dict]:
        """Check and award badges based on trading performance"""
        badges = []
        
        # Analyze performance metrics
        total_trades = len(trades)
        if total_trades == 0:
            return badges
        
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        win_rate = len(winning_trades) / total_trades * 100
        total_profit = sum(t.get('profit', 0) for t in trades)
        
        # Check for Best Trader badge (win rate > 70% and profitable)
        if win_rate > 70 and total_profit > 0:
            badges.append({
                'badge_type': 'best_trader',
                'name': 'Best Trader',
                'description': f'Achieved {win_rate:.1f}% win rate with ${total_profit:.2f} profit',
                'icon': 'crown',
                'color': 'yellow'
            })
        
        # Check for Consistency badge (consistent profits over time)
        if total_trades >= 20 and win_rate > 60:
            recent_trades = trades[-10:] if len(trades) >= 10 else trades
            recent_win_rate = len([t for t in recent_trades if t.get('profit', 0) > 0]) / len(recent_trades) * 100
            if recent_win_rate > 55:
                badges.append({
                    'badge_type': 'consistency',
                    'name': 'Consistency King',
                    'description': 'Consistent profitable trading over multiple sessions',
                    'icon': 'chart-line',
                    'color': 'blue'
                })
        
        # Check for Risk Manager badge (good risk-reward ratio)
        risk_reward_ratios = []
        for trade in trades:
            if trade.get('sl') and trade.get('tp'):
                risk = abs(trade.get('entry_price', 0) - trade.get('sl', 0))
                reward = abs(trade.get('tp', 0) - trade.get('entry_price', 0))
                if risk > 0:
                    risk_reward_ratios.append(reward / risk)
        
        if risk_reward_ratios and len([rr for rr in risk_reward_ratios if rr >= 1.5]) / len(risk_reward_ratios) > 0.7:
            badges.append({
                'badge_type': 'risk_manager',
                'name': 'Risk Manager',
                'description': 'Excellent risk-reward management in trades',
                'icon': 'shield-alt',
                'color': 'green'
            })
        
        # Check for High Profit badge
        if total_profit > 1000:
            badges.append({
                'badge_type': 'high_profit',
                'name': 'High Profit',
                'description': f'Generated ${total_profit:.2f} in total profit',
                'icon': 'money-bill-wave',
                'color': 'green'
            })
        
        # Check for Comeback King badge (recovery from drawdown)
        if len(trades) >= 10:
            # Calculate drawdown
            equity_curve = []
            equity = 0
            for trade in sorted(trades, key=lambda x: x.get('time', datetime.min)):
                equity += trade.get('profit', 0)
                equity_curve.append(equity)
            
            if equity_curve:
                peak = max(equity_curve)
                trough = min(equity_curve[i] for i in range(equity_curve.index(peak), len(equity_curve)))
                drawdown = (peak - trough) / peak * 100 if peak > 0 else 0
                
                # Recovery check
                if drawdown > 20 and equity_curve[-1] > peak:
                    badges.append({
                        'badge_type': 'comeback_king',
                        'name': 'Comeback King',
                        'description': 'Recovered from significant drawdown',
                        'icon': 'redo',
                        'color': 'red'
                    })
        
        # Check for Disciplined Trader badge (follows rules)
        rule_following_trades = 0
        for trade in trades:
            # Check if trade has stop loss (basic rule following)
            if trade.get('sl') and trade.get('sl') > 0:
                rule_following_trades += 1
        
        if rule_following_trades / len(trades) > 0.8:
            badges.append({
                'badge_type': 'disciplined',
                'name': 'Disciplined Trader',
                'description': 'Consistently follows trading rules',
                'icon': 'user-check',
                'color': 'blue'
            })
        
        return badges

class FinnhubNewsAggregator:
    def __init__(self):
        self.api_key = getattr(settings, 'FINNHUB_API_KEY', 'd5fqc9hr01qie3lejdag')
        self.finnhub_client = None
        
        if self.api_key:
            try:
                self.finnhub_client = finnhub.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Failed to initialize Finnhub client: {e}")
        
        # Rate limiting
        self.requests_per_minute = 0
        self.last_reset = datetime.now()
    
    def get_market_news(self, category: str = "general", limit: int = 10) -> List[Dict]:
        """Get market news from Finnhub"""
        if not self.finnhub_client:
            return self._get_mock_news()
        
        try:
            # Rate limiting check
            self._check_rate_limit()
            
            news_data = self.finnhub_client.general_news(category)
            self.requests_per_minute += 1
            
            # Process and format news
            news_items = []
            for item in news_data[:limit]:
                # Extract related symbols
                related_symbols = []
                if item.get("related"):
                    related_symbols = item["related"].split(",")
                
                # Determine impact based on sentiment
                sentiment = item.get("sentiment", 0)
                if abs(sentiment) > 0.3:
                    impact = "high"
                elif abs(sentiment) > 0.1:
                    impact = "medium"
                else:
                    impact = "low"
                
                # Format summary
                summary = item.get('summary', '')
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                
                news_items.append({
                    'title': item.get('headline', ''),
                    'summary': summary,
                    'source': item.get('source', ''),
                    'symbol': related_symbols[0] if related_symbols else None,
                    'url': item.get('url', ''),
                    'image': item.get('image', ''),
                    'sentiment': sentiment,
                    'impact': impact,
                    'published_at': datetime.fromtimestamp(item['datetime']) if 'datetime' in item else datetime.utcnow(),
                    'is_read': False
                })
            
            return news_items
            
        except Exception as e:
            print(f"Finnhub news error: {e}")
            return self._get_mock_news()
    
    def get_company_news(self, symbol: str, from_date: str = None, to_date: str = None) -> List[Dict]:
        """Get news for specific company/symbol"""
        if not self.finnhub_client:
            return []
        
        try:
            self._check_rate_limit()
            
            # Default to last 7 days
            if not from_date:
                from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            if not to_date:
                to_date = datetime.now().strftime("%Y-%m-%d")
            
            news_data = self.finnhub_client.company_news(symbol, _from=from_date, to=to_date)
            self.requests_per_minute += 1
            
            news_items = []
            for item in news_data[:10]:  # Limit to 10 articles
                summary = item.get('summary', '')
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                
                news_items.append({
                    'title': item.get('headline', ''),
                    'summary': summary,
                    'source': item.get('source', ''),
                    'symbol': symbol,
                    'url': item.get('url', ''),
                    'published_at': datetime.fromtimestamp(item['datetime']) if 'datetime' in item else datetime.utcnow()
                })
            
            return news_items
            
        except Exception as e:
            print(f"Finnhub company news error: {e}")
            return []
    
    def get_stock_quote(self, symbol: str) -> Dict:
        """Get real-time stock quote"""
        if not self.finnhub_client:
            return {}
        
        try:
            self._check_rate_limit()
            quote = self.finnhub_client.quote(symbol)
            self.requests_per_minute += 1
            
            return {
                'current': quote.get('c', 0),
                'change': quote.get('d', 0),
                'percent_change': quote.get('dp', 0),
                'high': quote.get('h', 0),
                'low': quote.get('l', 0),
                'open': quote.get('o', 0),
                'previous_close': quote.get('pc', 0),
                'timestamp': quote.get('t', 0),
                'symbol': symbol
            }
        except Exception as e:
            print(f"Finnhub quote error: {e}")
            return {}
    
    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get quotes for multiple symbols"""
        quotes = {}
        for symbol in symbols:
            quotes[symbol] = self.get_stock_quote(symbol)
        return quotes
    
    def get_crypto_quote(self, symbol: str = "BTC-USD") -> Dict:
        """Get cryptocurrency quote"""
        if not self.finnhub_client:
            return {}
        
        try:
            self._check_rate_limit()
            quote = self.finnhub_client.quote(symbol)
            self.requests_per_minute += 1
            
            return {
                'current': quote.get('c', 0),
                'change': quote.get('d', 0),
                'percent_change': quote.get('dp', 0),
                'high': quote.get('h', 0),
                'low': quote.get('l', 0),
                'open': quote.get('o', 0),
                'symbol': symbol
            }
        except Exception as e:
            print(f"Finnhub crypto quote error: {e}")
            return {}
    
    def get_forex_quote(self, pair: str = "EUR/USD") -> Dict:
        """Get forex quote"""
        if not self.finnhub_client:
            return {}
        
        try:
            self._check_rate_limit()
            # Finnhub uses format like "OANDA:EUR_USD"
            finnhub_symbol = f"OANDA:{pair.replace('/', '_')}"
            quote = self.finnhub_client.quote(finnhub_symbol)
            self.requests_per_minute += 1
            
            return {
                'current': quote.get('c', 0),
                'change': quote.get('d', 0),
                'percent_change': quote.get('dp', 0),
                'bid': quote.get('b', 0),
                'ask': quote.get('a', 0),
                'timestamp': quote.get('t', 0),
                'pair': pair
            }
        except Exception as e:
            print(f"Finnhub forex quote error: {e}")
            return {}
    
    def _check_rate_limit(self):
        """Check and enforce rate limits (60 requests/minute free tier)"""
        now = datetime.now()
        if (now - self.last_reset).seconds >= 60:
            self.requests_per_minute = 0
            self.last_reset = now
        
        if self.requests_per_minute >= 55:  # Leave buffer
            print(f"Approaching rate limit: {self.requests_per_minute}/60 requests")
            if self.requests_per_minute >= 60:
                wait_time = 60 - (now - self.last_reset).seconds
                if wait_time > 0:
                    print(f"Rate limit reached. Waiting {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                    self.requests_per_minute = 0
                    self.last_reset = datetime.now()
    
    def _get_mock_news(self) -> List[Dict]:
        """Return mock news data for development"""
        current_time = datetime.utcnow()
        return [
            {
                'title': 'Bitcoin Surges Past $90,000',
                'summary': 'Cryptocurrency markets show strong bullish momentum as Bitcoin breaks through key resistance levels...',
                'source': 'CoinDesk',
                'symbol': 'BTC-USD',
                'impact': 'high',
                'sentiment': 0.8,
                'published_at': current_time - timedelta(hours=1),
                'is_read': False,
                'url': '#'
            },
            {
                'title': 'Federal Reserve Interest Rate Decision',
                'summary': 'Federal Reserve announces interest rate decision, affecting major currency pairs and equity markets...',
                'source': 'Financial Times',
                'symbol': 'EUR/USD',
                'impact': 'high',
                'sentiment': -0.2,
                'published_at': current_time - timedelta(hours=3),
                'is_read': False,
                'url': '#'
            },
            {
                'title': 'Apple Earnings Beat Expectations',
                'summary': 'Apple reports strong quarterly earnings, driven by iPhone sales and services growth...',
                'source': 'Bloomberg',
                'symbol': 'AAPL',
                'impact': 'medium',
                'sentiment': 0.6,
                'published_at': current_time - timedelta(hours=5),
                'is_read': False,
                'url': '#'
            }
        ]
    
    async def async_get_market_news(self, category: str = "general", limit: int = 10) -> List[Dict]:
        """Async version of get_market_news"""
        # For async operations, you might want to use httpx directly
        # This is a wrapper for compatibility
        return self.get_market_news(category, limit)

# Create singleton instances for easy access
ai_analyzer = AITradingAnalyzer()
badge_awarder = BadgeAwarder()
news_aggregator = FinnhubNewsAggregator()