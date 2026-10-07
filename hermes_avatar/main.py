"""
Main application - Hermes Girl Avatar desktop companion.

Combines screen capture, chat window, and sprite animation into a unified
desktop application that stays on top and interacts with Hermes via API.
"""

import sys
import yaml
import time
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QAction

from .screen_capture import ScreenCapture
from .chat_window import ChatWindow
from .sprite_animator import SpriteAnimator
from .discord_client import HermesDiscordClient
from .api_client import HermesApiClient


class HermesAvatar(QMainWindow):
    """Main application window for Hermes Girl Avatar."""
    
    def __init__(self, config_path: str = None):
        super().__init__()
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.avatar_config = self.config.get("avatar", {})
        
        # Initialize components
        self.screen_capture = ScreenCapture(config_path)
        self.sprite_animator = SpriteAnimator(config_path)
        self.chat_window = None
        self.discord_client = None
        self.api_client = HermesApiClient(config_path)
        
        # Setup UI
        self.setup_ui()
        self.setup_tray()
        
        # Initialize Discord client (non-blocking)
        self.init_discord()
        
        # Start periodic screen capture
        if self.config.get("screen_capture", {}).get("enabled", True):
            self.start_screen_capture()
        
    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def setup_ui(self):
        """Set up the main application UI."""
        # Window properties
        width = self.avatar_config.get("width", 200)
        height = self.avatar_config.get("height", 200)
        
        self.setWindowTitle("Hermes Girl Avatar")
        self.setFixedSize(width, height)
        
        # Always on top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Close button (top-right corner of avatar)
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(231, 76, 60, 0.8);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(192, 57, 43, 1);
            }
        """)
        self.close_button.clicked.connect(self._on_close_click)
        
        # Avatar display
        self.avatar_label = self.sprite_animator.create_avatar_widget(width - 30, height - 30)
        self.avatar_label.mousePressEvent = self._on_avatar_click
        
        # Create a container layout for avatar + close button
        avatar_layout = QVBoxLayout()
        avatar_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        avatar_layout.addWidget(self.avatar_label)
        layout.addLayout(avatar_layout)
        
        # Position window
        self._position_window()
        
        # Show window
        self.show()
    
    def _position_window(self):
        """Position window based on config."""
        position = self.avatar_config.get("position", "top-right")
        screen = QApplication.primaryScreen().geometry()
        
        if position == "top-right":
            x = screen.width() - self.width() - 20
            y = 20
        elif position == "top-left":
            x = 20
            y = 20
        elif position == "bottom-left":
            x = 20
            y = screen.height() - self.height() - 20
        elif position == "bottom-right":
            x = screen.width() - self.width() - 20
            y = screen.height() - self.height() - 20
        else:
            x, y = 100, 100
        
        self.move(x, y)
    
    def _on_avatar_click(self, event):
        """Handle avatar click - open chat window."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_chat_window()
    
    def open_chat_window(self):
        """Open or focus the chat window."""
        if self.chat_window is None:
            self.chat_window = ChatWindow()
            self.chat_window.message_sent.connect(self._handle_user_message)
        
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()
    
    def init_discord(self):
        """Initialize Discord client in background thread."""
        try:
            import threading
            import os
            
            # Check if Discord token is set
            if not os.getenv("DISCORD_BOT_TOKEN"):
                print("⚠️  DISCORD_BOT_TOKEN not set. Run 'python setup.py' to configure.")
                return
            
            print("🤖 Initializing Discord client...")
            
            def start_discord():
                try:
                    self.discord_client = HermesDiscordClient()

                    # Register callbacks - wrap in QTimer.singleShot to ensure GUI updates happen in main thread
                    def show_hermes_wrapper(text):
                        QTimer.singleShot(0, lambda: self._show_hermes_response(text))
                    self.discord_client.register_response_callback(show_hermes_wrapper)

                    # Start bot (blocking call in background thread)
                    print("🤖 Starting Discord bot...")
                    self.discord_client.start()
                    
                except Exception as e:
                    print(f"❌ Discord initialization failed: {e}")
            
            # Start in background thread to avoid blocking UI
            thread = threading.Thread(target=start_discord, daemon=True)
            thread.start()
            
        except Exception as e:
            print(f"❌ Failed to initialize Discord: {e}")
    
    def _handle_user_message(self, message: str):
        """Send user message to Hermes: direct API first, Discord as fallback."""
        print(f"📤 Sending to Hermes: {message}")

        # Show thinking animation
        self.sprite_animator.set_state("think")

        # Channel primario: API diretta al gateway Hermes (sincrona, contestuale)
        if self.api_client and self.api_client.enabled:
            def ask():
                try:
                    result = self.api_client.chat(message)
                    if result["success"]:
                        print(f"✅ Hermes ({result['elapsed']:.1f}s): {result['response'][:60]}")
                        answer = result["response"]
                    else:
                        print(f"❌ Hermes error: {result['error']}")
                        answer = f"⚠️ Errore Hermes: {result['error']}"
                    # GUI update sempre nel thread principale
                    QTimer.singleShot(0, lambda: self._show_hermes_response(answer))
                except Exception as e:
                    print(f"Error in API chat: {e}")

            thread = threading.Thread(target=ask, daemon=True)
            thread.start()
            return

        # Fallback: Discord (se il bot è pronto)
        if self.discord_client and self.discord_client.bot.is_ready():
            try:
                def send():
                    try:
                        # Add @Hermesso mention and Rail prefix to ensure Hermes processes this message
                        formatted_message = f"@Hermesso 🚂 [Rail Avatar]: {message}"
                        result = self.discord_client.send_message_sync(formatted_message)
                        if result:
                            print(f"✅ Message sent to Discord: {result.id}")
                        else:
                            print("❌ Failed to send message")
                    except Exception as e:
                        print(f"Error sending message: {e}")
                
                thread = threading.Thread(target=send, daemon=True)
                thread.start()
            except Exception as e:
                print(f"Failed to send message: {e}")
        else:
            print("⚠️ Nessun canale Hermes attivo (API disattivata, Discord non pronto)")
            QTimer.singleShot(0, lambda: self._show_hermes_response(
                "⚠️ Nessun canale Hermes attivo: configura HERMES_API_KEY in .env "
                "(api_server) oppure DISCORD_BOT_TOKEN per il fallback Discord."))
    
    def _show_hermes_response(self, text: str):
        """Show Hermes response in chat window."""
        if self.chat_window:
            self.chat_window.show_hermes_suggestion(text)
        
        # Change back to idle
        self.sprite_animator.set_state("idle")
    
    def start_screen_capture(self):
        """Start periodic screen capture and send to Hermes."""
        def on_capture_result(result):
            if result.get("success"):
                analysis = result.get("analysis")
                print(f"Hermes analysis: {analysis}")
                # Use QTimer.singleShot to ensure GUI update happens in main thread
                QTimer.singleShot(0, lambda: self._show_hermes_response(analysis))
            else:
                error = result.get("error")
                print(f"Capture error: {error}")

        self.screen_capture.start_periodic_capture(callback=on_capture_result)
    
    def setup_tray(self):
        """Set up system tray icon."""
        # Create tray icon with a simple icon
        tray_icon = QSystemTrayIcon(self)
        
        # Create a simple icon programmatically (avoid file dependency)
        from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
        icon_pixmap = QPixmap(32, 32)
        icon_pixmap.fill(QColor(52, 152, 219))  # Blue background
        painter = QPainter(icon_pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(icon_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "H")
        painter.end()
        tray_icon.setIcon(QIcon(icon_pixmap))
        
        # Create context menu
        tray_menu = QMenu()
        
        show_action = QAction("Mostra", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        chat_action = QAction("Chat", self)
        chat_action.triggered.connect(self.open_chat_window)
        tray_menu.addAction(chat_action)
        
        capture_action = QAction("Toggle Screen Capture", self)
        capture_action.triggered.connect(self.toggle_screen_capture)
        tray_menu.addAction(capture_action)
        
        quit_action = QAction("Esci", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        
        tray_icon.setContextMenu(tray_menu)
        tray_icon.show()
        
        # Store reference to prevent garbage collection
        self.tray_icon = tray_icon
    
    def toggle_screen_capture(self):
        """Toggle screen capture on/off."""
        if self.screen_capture.is_running:
            self.screen_capture.stop_periodic_capture()
            print("Screen capture stopped")
        else:
            self.screen_capture.start_periodic_capture()
            print("Screen capture started")
    
    def _on_close_click(self):
        """Handle close button click."""
        self.close()
    
    def closeEvent(self, event):
        """Handle window close - minimize to tray instead of quit."""
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Hermes Girl Avatar")
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = HermesAvatar()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
