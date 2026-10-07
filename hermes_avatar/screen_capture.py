"""
Screen capture module - captures screenshots and sends them directly to Hermes via API.

No disk storage - screenshots are captured in memory and transmitted as base64.
"""

import base64
import io
import time
from typing import Optional, Callable
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from PIL import Image
import requests
import yaml
import os
from pathlib import Path

from .api_client import HermesApiClient


class ScreenCapture:
    """Captures screen and sends to Hermes API without saving to disk."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize screen capture with configuration.
        
        Args:
            config_path: Path to config.yaml (default: same dir as this file)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.interval = self.config.get("screen_capture", {}).get("interval_seconds", 30)
        self.api_config = self.config.get("api", {})
        self.is_running = False
        self.capture_callback: Optional[Callable] = None
        # Canale diretto verso Hermes api_server (autenticato)
        self.api = HermesApiClient(config_path)
        self.capture_session = self.api_config.get("capture_session_id", "rail-screen")
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def capture_screenshot(self) -> bytes:
        """
        Capture current screen and return as JPEG bytes.
        
        Returns:
            JPEG-encoded screenshot bytes (no file saved)
        """
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QGuiApplication
            from PyQt6.QtCore import QBuffer, QIODevice
            from PyQt6.QtGui import QImage
            
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            screen = QGuiApplication.primaryScreen()
            pixmap = screen.grabWindow(0)  # Grab entire screen
            
            # Convert to QImage and save to QBuffer
            image = pixmap.toImage()
            buffer = QBuffer()
            buffer.open(QBuffer.OpenModeFlag.WriteOnly)
            image.save(buffer, "JPEG", 85)  # Quality 85%
            buffer.close()
            
            # Get bytes from buffer
            image_data = buffer.data()
            return bytes(image_data)
            
        except Exception as e:
            print(f"Screen capture error (PyQt6): {e}")
            # Fallback: try PIL's ImageGrab if available
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                buffer.seek(0)
                return buffer.getvalue()
            except ImportError:
                raise ImportError("PyQt6 failed and PIL ImageGrab not available. Install: pip install pillow")
    
    def send_to_hermes(self, screenshot_bytes: bytes) -> dict:
        """
        Send screenshot to Hermes API for analysis (authenticated api_server).
        
        Args:
            screenshot_bytes: JPEG image bytes
            
        Returns:
            dict with success, analysis (Hermes answer) and error keys
        """
        if not self.api.enabled:
            return {
                "success": False,
                "error": "Hermes API non configurato (HERMES_API_KEY mancante in .env)",
                "analysis": None,
            }

        # Convert to base64 and send as multimodal message (text + image)
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
        prompt = ("Analizza questo screenshot e fornisci suggerimenti utili "
                  "per l'utente su ciò che sta facendo a schermo. "
                  "Sii conciso e pratico.")

        result = self.api.chat(
            prompt,
            image_b64=base64_image,
            image_mime="image/jpeg",
            session_id=self.capture_session,
        )
        return {
            "success": result["success"],
            "analysis": result.get("response"),
            "error": result.get("error"),
            "timestamp": time.time(),
        }
    
    def capture_and_send(self) -> dict:
        """
        Full workflow: capture screenshot and send to Hermes.
        
        Returns:
            Dict with success status and analysis/result
        """
        if not self.config.get("screen_capture", {}).get("enabled", True):
            return {"success": False, "error": "Screen capture disabled in config"}
        
        try:
            # Capture screenshot in memory
            screenshot_bytes = self.capture_screenshot()
            
            # Send to Hermes
            result = self.send_to_hermes(screenshot_bytes)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Capture failed: {str(e)}",
                "analysis": None
            }
    
    def start_periodic_capture(self, callback: Callable = None):
        """
        Start periodic screen capture in background.
        
        Args:
            callback: Function to call with Hermes' analysis after each capture
        """
        import threading
        
        self.capture_callback = callback
        self.is_running = True
        
        def capture_loop():
            while self.is_running:
                time.sleep(self.interval)
                if self.is_running:
                    result = self.capture_and_send()
                    # Deliver the whole result dict; the listener (main.py)
                    # marshals it to the main thread via its Qt signal.
                    if self.is_running and callback:
                        callback(result)
        
        thread = threading.Thread(target=capture_loop, daemon=True)
        thread.start()
        return thread
    
    def stop_periodic_capture(self):
        """Stop periodic capture."""
        self.is_running = False
