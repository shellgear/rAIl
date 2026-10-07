"""
Discord client module - handles communication with Hermes via Discord channel.

Sends screenshots and messages to Hermes, receives suggestions and responses.
Uses discord.py for WebSocket-based real-time communication.

Configuration:
  - .env file: DISCORD_BOT_TOKEN (required)
  - config.local.yaml: channel_id, hermes_user_id (optional, uses defaults if missing)
"""

from __future__ import annotations

import os
import asyncio
import logging
import base64
from pathlib import Path
from typing import Callable, Optional, Dict, Any

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system env vars

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    logging.warning("discord.py not installed. Discord integration disabled.")


logger = logging.getLogger(__name__)


class HermesDiscordClient:
    """
    Discord client that communicates with Hermes Agent via a dedicated channel.
    
    Features:
    - Sends screenshots as base64 or image files
    - Sends text messages to Hermes
    - Receives suggestions and responses from Hermes
    - Handles reconnection automatically
    """
    
    def __init__(self, config_path: str = None):
        """Initialize Discord client with configuration."""
        if not DISCORD_AVAILABLE:
            raise RuntimeError("discord.py is not installed. Install with: pip install discord.py")
        
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        import yaml
        
        # Load main config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load local config (overrides main config)
        config_local_path = Path(__file__).parent.parent / "config.local.yaml"
        if config_local_path.exists():
            with open(config_local_path, 'r') as f:
                local_config = yaml.safe_load(f)
                if local_config:
                    # Deep merge
                    def merge_dicts(d1, d2):
                        for k, v in d2.items():
                            if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                                merge_dicts(d1[k], v)
                            else:
                                d1[k] = v
                    merge_dicts(self.config, local_config)
        
        # Discord settings - prioritize env vars, then config files
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        discord_config = self.config.get("discord", {})
        self.channel_id = os.getenv("DISCORD_CHANNEL_ID", str(discord_config.get("channel_id", "1552636595532865587")))
        self.hermes_user_id = os.getenv("HERMES_USER_ID", str(discord_config.get("hermes_user_id", "1538998656030609509")))
        
        # Message tracking
        self.last_message_id = None
        self.pending_responses = {}  # message_id -> asyncio.Event
        
        # Setup bot
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.guilds = True
        
        self.bot = commands.Bot(command_prefix="/", intents=intents)
        self.bot.remove_command("help")  # Remove default help
        
        # Register events
        self.bot.event(self.on_ready)
        self.bot.event(self.on_message)
        
        # Store reference to event loop for async calls from other threads
        self.loop = None
        
        # Callbacks
        self.message_callbacks = []
        self.response_callbacks = []
    
    def register_message_callback(self, callback: Callable[[str], None]):
        """Register a callback for incoming messages from Hermes."""
        self.message_callbacks.append(callback)
    
    def register_response_callback(self, callback: Callable[[str], None]):
        """Alias for register_message_callback."""
        self.message_callbacks.append(callback)
    
    def register_capture_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for capture results."""
        self.message_callbacks.append(callback)
    
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Discord bot logged in as {self.bot.user}")
        logger.info(f"Bot ID: {self.bot.user.id}")
        
        # Save reference to event loop for async calls from other threads
        self.loop = asyncio.get_running_loop()
        
        # Find the channel
        try:
            self.channel = await self.bot.fetch_channel(int(self.channel_id))
            logger.info(f"Connected to channel: {self.channel.name} (ID: {self.channel.id})")
        except Exception as e:
            logger.error(f"Failed to fetch channel {self.channel_id}: {e}")
            self.channel = None
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        # Ignore bot's own messages
        if message.author == self.bot.user:
            return
        
        # Ignore messages from other users (only process Hermes responses)
        if str(message.author.id) != str(self.hermes_user_id):
            return
        
        # Process Hermes response (works in channels AND threads)
        if message.content:
            logger.info(f"Received from Hermes: {message.content}")
            
            # Call message callbacks (for Hermes responses)
            for callback in self.message_callbacks:
                try:
                    callback(message.content)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    async def send_message(self, content: str, image_path: str = None) -> Optional[discord.Message]:
        """
        Send a message to the Discord channel.
        
        Args:
            content: Text message to send
            image_path: Optional path to image file to attach
            
        Returns:
            The sent message, or None if failed
        """
        if not hasattr(self, 'channel') or self.channel is None:
            logger.error("Channel not available")
            return None
        
        try:
            if image_path and os.path.exists(image_path):
                # Send with image attachment
                with open(image_path, 'rb') as f:
                    file = discord.File(f)
                    message = await self.channel.send(content=content, file=file)
            else:
                # Send text only
                message = await self.channel.send(content=content)
            
            logger.info(f"Sent message to Discord: {content[:50]}...")
            return message
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def send_message_sync(self, content: str, image_path: str = None) -> Optional[discord.Message]:
        """
        Synchronous wrapper for send_message - can be called from other threads.
        
        Args:
            content: Text message to send
            image_path: Optional path to image file to attach
            
        Returns:
            The sent message, or None if failed
        """
        if self.loop is None:
            logger.error("Bot not ready (loop not set)")
            return None
        
        try:
            # Use run_coroutine_threadsafe to schedule the coroutine in the bot's event loop
            future = asyncio.run_coroutine_threadsafe(
                self.send_message(content, image_path),
                self.loop
            )
            # Wait for the result (with timeout)
            return future.result(timeout=10)
        except Exception as e:
            logger.error(f"Failed to send message (sync): {e}")
            return None
    
    async def send_screenshot(self, screenshot_data: bytes, description: str = "") -> Optional[discord.Message]:
        """
        Send a screenshot to Discord as an image file.
        
        Args:
            screenshot_data: Raw screenshot bytes (PNG format)
            description: Optional description/context
            
        Returns:
            The sent message, or None if failed
        """
        if not hasattr(self, 'channel') or self.channel is None:
            logger.error("Channel not available")
            return None
        
        try:
            # Create a temporary file for the screenshot
            import tempfile
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
                f.write(screenshot_data)
                temp_path = f.name
            
            # Send as image file
            with open(temp_path, 'rb') as f:
                file = discord.File(f, filename="screenshot.png")
                content = f"📸 Screen capture{': ' + description if description else ''}"
                message = await self.channel.send(content=content, file=file)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            logger.info(f"Sent screenshot to Discord: {description}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to send screenshot: {e}")
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
            return None
    
    def start(self):
        """Start the Discord bot (blocking)."""
        if not self.bot_token:
            raise RuntimeError("Discord bot token not set. Set DISCORD_BOT_TOKEN environment variable.")
        
        logger.info("Starting Discord bot...")
        self.bot.run(self.bot_token)
    
    def start_async(self):
        """Start the Discord bot asynchronously (non-blocking)."""
        if not self.bot_token:
            raise RuntimeError("Discord bot token not set. Set DISCORD_BOT_TOKEN environment variable.")
        
        logger.info("Starting Discord bot asynchronously...")
        asyncio.create_task(self._run_async())
    
    async def _run_async(self):
        """Run the bot asynchronously."""
        await self.bot.start(self.bot_token)


# Convenience function for testing
def test_connection():
    """Test Discord connection (blocking)."""
    import yaml
    
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    channel_id = config.get("discord", {}).get("channel_id", "1552636595532865587")
    
    print(f"Testing Discord connection to channel: {channel_id}")
    print("Make sure DISCORD_BOT_TOKEN is set in environment")
    
    client = HermesDiscordClient(config_path)
    
    # Test send
    async def test():
        await client.on_ready()
        if client.channel:
            msg = await client.send_message("Test message from Rail avatar")
            if msg:
                print(f"✓ Test message sent: {msg.id}")
            else:
                print("✗ Failed to send test message")
        else:
            print("✗ Channel not available")
    
    asyncio.run(test())
