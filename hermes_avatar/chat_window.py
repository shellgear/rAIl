"""
Chat window module - small notepad-style window that opens on click.

Displays Hermes suggestions and allows user to send messages.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLabel, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
import yaml
from pathlib import Path


class ChatWindow(QMainWindow):
    """Notepad-style chat window for Hermes interaction."""
    
    message_sent = pyqtSignal(str)  # Signal when user sends a message
    
    def __init__(self, config_path: str = None):
        super().__init__()
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.chat_config = self.config.get("chat_window", {})
        
        self.setup_ui()
        self.setup_styles()
        
    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def setup_ui(self):
        """Set up the chat window UI."""
        # Window properties
        width = self.chat_config.get("width", 400)
        height = self.chat_config.get("height", 300)
        self.setWindowTitle("Hermes Chat")
        self.setFixedSize(width, height)
        
        # Make window stay on top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint  # Optional: frameless for cleaner look
        )
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QLabel("💬 Hermes Assistant")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("background-color: #2c3e50; color: white; padding: 8px; font-weight: bold;")
        main_layout.addWidget(header)
        
        # Chat area (scrollable)
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setPlaceholderText("I suggerimenti di Hermes appariranno qui...")
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: #ecf0f1;
                border: none;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.chat_area, stretch=1)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Scrivi un messaggio a Hermes...")
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: none;
                border-top: 1px solid #bdc3c7;
                background-color: #ffffff;
                font-family: 'Courier New', monospace;
            }
        """)
        input_layout.addWidget(self.input_field, stretch=1)
        
        send_button = QPushButton("Invia")
        send_button.clicked.connect(self._send_message)
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1e6fa5;
            }
        """)
        input_layout.addWidget(send_button)
        
        main_layout.addLayout(input_layout)
        
        # Position window
        self._position_window()
        
    def setup_styles(self):
        """Apply custom styles to the window."""
        # Optional: custom palette
        pass
    
    def _position_window(self):
        """Position window based on config."""
        position = self.chat_config.get("position", "below_avatar")
        # Will be set dynamically by main window
        self.move(100, 100)  # Default position
        
    def _send_message(self):
        """Send message from input field."""
        message = self.input_field.text().strip()
        if message:
            self.message_sent.emit(message)
            self.input_field.clear()
            
            # Add user message to chat area (add_message adds the "Tu: " prefix)
            self.add_message(message, is_user=True)
    
    def add_message(self, text: str, is_user: bool = False):
        """Add a message to the chat area."""
        # Append to QTextEdit
        current_html = self.chat_area.toHtml()
        if current_html == "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0 Transitional//EN\" \"http://www.w3.org/TR/REC-html40/loose.dtd\">\n<p></p>" or not current_html.strip():
            current_html = ""
        
        color = "#2ecc71" if is_user else "#e74c3c"
        prefix = "Tu: " if is_user else "Hermes: "
        
        new_html = f"{current_html}<p style='margin: 5px 0; color: {color};'><strong>{prefix}</strong>{text}</p>"
        self.chat_area.setHtml(new_html)
        
        # Scroll to bottom
        self.chat_area.verticalScrollBar().setValue(
            self.chat_area.verticalScrollBar().maximum()
        )
    
    def show_hermes_suggestion(self, text: str):
        """Display a suggestion from Hermes."""
        self.add_message(text, is_user=False)
        
        # Auto-open if configured
        if self.chat_config.get("auto_open_on_message", True):
            self.show()
            self.raise_()
            self.activateWindow()
    
    def toggle_visibility(self):
        """Toggle window visibility."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
