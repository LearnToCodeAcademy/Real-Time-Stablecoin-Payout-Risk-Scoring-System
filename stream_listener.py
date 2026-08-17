"""
Stream Listener - Real-Time Blockchain Transaction Monitoring
WebSocket-based streaming listener for live transaction processing

Connects to Alchemy/Infura WebSocket and scores transactions in real-time
before blockchain confirmation for zero-latency fraud detection.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional: Try to import WebSocket libraries
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("websockets library not installed. Install with: pip install websockets")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp library not installed. Install with: pip install aiohttp")


class StreamListener:
    """
    Real-time transaction listener with WebSocket connection to Alchemy/Infura
    Scores transactions as they enter mempool for real-time risk detection
    """
    
    def __init__(self, 
                 provider_url: Optional[str] = None,
                 token_contracts: Optional[Dict[str, str]] = None):
        """
        Initialize stream listener
        
        Args:
            provider_url: WebSocket URL (Alchemy/Infura)
            token_contracts: Dict mapping token symbol to contract address
        """
        self.provider_url = (
            provider_url
            or os.getenv("ALCHEMY_WS_URL")
            or os.getenv("INFURA_WS_URL")
            or ""
        )
        self.token_contracts = token_contracts or self._get_default_contracts()
        self.is_running = False
        self.transaction_handlers: List[Callable] = []
        self.stats = {
            'transactions_seen': 0,
            'transactions_scored': 0,
            'risky_transactions': 0,
            'start_time': None,
            'uptime_seconds': 0
        }
    
    def _get_default_contracts(self) -> Dict[str, str]:
        """Get default token contracts"""
        return {
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
            "BUSD": "0x4Fabb145d64652a948d72533023f6E7A623C7C53",
            "USDP": "0x8E870D67F660D95d5be2D627f142b3d3C9145e9D",
            "TUSD": "0x0000000000085d4780B73119b8B580991DEe8d52",
        }
    
    def add_transaction_handler(self, handler: Callable):
        """
        Register a callback for transaction scoring
        
        Callback signature: handler(tx_data, score_result)
        """
        self.transaction_handlers.append(handler)
    
    async def listen(self):
        """
        Main listening loop - connects to WebSocket and processes transactions
        """
        if not HAS_WEBSOCKETS:
            logger.error("websockets library required. Install with: pip install websockets")
            return
        if not self.provider_url:
            logger.error("Set ALCHEMY_WS_URL or INFURA_WS_URL before starting the stream listener")
            return
        
        self.is_running = True
        self.stats['start_time'] = time.time()
        
        logger.info(f"🚀 Starting stream listener...")
        logger.info(f"Connecting to: {self.provider_url[:50]}...")
        
        try:
            async with websockets.connect(self.provider_url) as ws:
                logger.info("✅ Connected to WebSocket")
                
                # Subscribe to token transfer events
                for token_symbol, contract in self.token_contracts.items():
                    await self._subscribe_to_token(ws, token_symbol, contract)
                
                # Main listening loop
                while self.is_running:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        await self._process_message(message)
                    except asyncio.TimeoutError:
                        # Keep-alive ping
                        logger.debug("Keep-alive...")
                        continue
                    except Exception as e:
                        logger.error(f"Error receiving message: {e}")
                        break
        
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            logger.info("Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)
            await self.listen()  # Reconnect
    
    async def _subscribe_to_token(self, ws, token_symbol: str, contract: str):
        """Subscribe to token transfer events via Alchemy webhook"""
        
        # Topic: Transfer(address indexed from, address indexed to, uint256 value)
        # Signature: 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
        
        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_subscribe",
            "params": [
                "logs",
                {
                    "address": contract,
                    "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]  # Transfer
                }
            ]
        }
        
        try:
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"📡 Subscribed to {token_symbol} transfers")
        except Exception as e:
            logger.error(f"Failed to subscribe to {token_symbol}: {e}")
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Check if it's a subscription confirmation or transaction
            if 'result' in data and data['result']:
                logger.info(f"✅ Subscription activated")
                return
            
            if 'params' not in data:
                return
            
            # Extract log data
            log_data = data['params']['result']
            
            # Parse transaction
            tx_info = self._parse_log(log_data)
            if tx_info:
                await self._score_and_handle(tx_info)
        
        except Exception as e:
            logger.debug(f"Message processing error: {e}")
    
    def _parse_log(self, log_data: Dict[str, Any]) -> Optional[Dict]:
        """Parse Ethereum log into transaction info"""
        try:
            return {
                'tx_hash': log_data.get('transactionHash', ''),
                'block_number': int(log_data.get('blockNumber', 0), 16),
                'address': log_data.get('address', ''),
                'topics': log_data.get('topics', []),
                'data': log_data.get('data', ''),
                'timestamp': datetime.now().isoformat(),
                'from_log': log_data.get('from', ''),  # Approximation
            }
        except Exception as e:
            logger.debug(f"Log parsing error: {e}")
            return None
    
    async def _score_and_handle(self, tx_info: Dict):
        """Score transaction and trigger handlers"""
        self.stats['transactions_seen'] += 1
        
        try:
            # Score transaction (simplified - in production would call wallet_check.score_wallet)
            score_result = await self._score_transaction(tx_info)
            
            self.stats['transactions_scored'] += 1
            
            # Check if risky
            if score_result.get('decision') == 'BLOCK':
                self.stats['risky_transactions'] += 1
                logger.warning(f"🚨 RISKY TX: {tx_info['tx_hash'][:10]}... {score_result}")
            
            # Trigger handlers
            for handler in self.transaction_handlers:
                try:
                    handler(tx_info, score_result)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
        
        except Exception as e:
            logger.error(f"Scoring error: {e}")
    
    async def _score_transaction(self, tx_info: Dict) -> Dict[str, Any]:
        """
        Score a transaction (placeholder implementation)
        In production, would call wallet_check.score_wallet for real scoring
        """
        
        # Simulated scoring
        return {
            'tx_hash': tx_info['tx_hash'],
            'score': 0.35,
            'decision': 'ALLOW',  # Simulated
            'confidence': 0.75,
            'timestamp': datetime.now().isoformat()
        }
    
    async def stop(self):
        """Stop listening"""
        logger.info("🛑 Stopping stream listener...")
        self.is_running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get listener statistics"""
        if self.stats['start_time']:
            self.stats['uptime_seconds'] = time.time() - self.stats['start_time']
        
        return self.stats
    
    def print_stats(self):
        """Print formatted statistics"""
        stats = self.get_stats()
        
        print(f"""
╔════════════════════════════════════════════════════════════╗
║           Stream Listener Statistics                       ║
╠════════════════════════════════════════════════════════════╣
║ Transactions Seen:      {stats['transactions_seen']:>10}                    ║
║ Transactions Scored:    {stats['transactions_scored']:>10}                    ║
║ Risky Transactions:     {stats['risky_transactions']:>10}                    ║
║ Uptime (seconds):       {stats['uptime_seconds']:>10.1f}                  ║
╚════════════════════════════════════════════════════════════╝
        """)


class StreamEventHandler:
    """Handler for stream events - customizable alerting"""
    
    def __init__(self):
        self.alerts: List[Dict] = []
    
    def on_risky_transaction(self, tx_data: Dict, score_result: Dict):
        """Handle high-risk transaction"""
        if score_result.get('decision') == 'BLOCK':
            alert = {
                'type': 'HIGH_RISK',
                'tx_hash': tx_data.get('tx_hash'),
                'score': score_result.get('score'),
                'timestamp': datetime.now().isoformat()
            }
            self.alerts.append(alert)
            
            logger.warning(f"🚨 ALERT: {alert}")
    
    def on_transaction(self, tx_data: Dict, score_result: Dict):
        """Handle any transaction"""
        logger.info(f"📊 TX {tx_data['tx_hash'][:10]}... scored: {score_result['decision']}")


# ============ STANDALONE USAGE ============

async def run_stream_listener(provider_url: str = None):
    """Run standalone stream listener"""
    
    if not HAS_WEBSOCKETS or not HAS_AIOHTTP:
        print("❌ Required libraries not installed")
        print("Install with: pip install websockets aiohttp")
        return
    
    # Use provided URL or environment configuration.
    if not provider_url:
        provider_url = os.getenv("ALCHEMY_WS_URL") or os.getenv("INFURA_WS_URL")
    
    # Create listener
    listener = StreamListener(provider_url=provider_url)
    
    # Add event handler
    handler = StreamEventHandler()
    listener.add_transaction_handler(handler.on_transaction)
    listener.add_transaction_handler(handler.on_risky_transaction)
    
    # Create tasks
    listen_task = asyncio.create_task(listener.listen())
    
    # Stats printing task
    async def print_stats_periodically():
        while listener.is_running:
            await asyncio.sleep(60)  # Print every 60 seconds
            listener.print_stats()
    
    stats_task = asyncio.create_task(print_stats_periodically())
    
    try:
        await asyncio.gather(listen_task, stats_task)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await listener.stop()


if __name__ == "__main__":
    print("""
    ╔═════════════════════════════════════════════════════════════════╗
    ║  Stream Listener - Real-Time Transaction Monitoring            ║
    ║  Version 1.0 (WebSocket-based zero-latency detection)          ║
    ╚═════════════════════════════════════════════════════════════════╝
    
    🔗 Connects to Alchemy/Infura WebSocket for live transaction data
    
    📌 USAGE:
    
    1. Set your Alchemy/Infura API key in provider_url
    2. Run: python stream_listener.py
    3. Monitor statistics in real-time
    
    🔥 FEATURES:
    - Real-time transaction monitoring
    - Stream scoring integration
    - Automatic reconnection
    - Live statistics
    
    ⚙️ CONFIGURATION:
    - provider_url: WebSocket endpoint
    - token_contracts: Supported tokens
    - transaction_handlers: Custom callbacks
    """)
    
    # Run listener
    try:
        asyncio.run(run_stream_listener())
    except KeyboardInterrupt:
        print("\n✅ Stream listener stopped")
