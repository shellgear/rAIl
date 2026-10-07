"""
Sprite animator module - handles pixel art animations for Hermes Girl avatar.

Inspired by 1990s fighting games (Metaslug style) with frame-based animations.
Uses real sprite sheets from assets/hermes_girl/ directory.
"""

from PyQt6.QtWidgets import QLabel, QApplication
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QTimer, Qt
from pathlib import Path
import yaml

from .avatar_loader import AvatarLoader


class SpriteAnimator:
    """Manages pixel art sprite animations for the avatar."""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        self.anim_config = self.config.get("animation", {})
        self.current_state = "idle"
        self.current_frame = 0
        self.frame_timer = None
        
        # Avatar loader for real sprites
        self.loader = AvatarLoader(config_path)
        
        # Animation states
        self.states = {
            "idle": {"frames": self.anim_config.get("idle_frames", 4), "fps": self.anim_config.get("fps", 12)},
            "speak": {"frames": self.anim_config.get("speak_frames", 6), "fps": self.anim_config.get("fps", 12)},
            "think": {"frames": self.anim_config.get("think_frames", 4), "fps": self.anim_config.get("fps", 12)},
            "alert": {"frames": self.anim_config.get("alert_frames", 4), "fps": self.anim_config.get("fps", 15)},
        }
        
        # Loaded sprite frames (per state)
        self.frames_cache = {}
        
    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def load_frames(self, state: str) -> list:
        """Load all frames for an animation state from sprite sheets."""
        if state in self.frames_cache:
            return self.frames_cache[state]
        
        frames = []
        state_config = self.states.get(state, {"frames": 4})
        num_frames = state_config["frames"]
        
        # Load from assets directory
        state_dir = self.loader.assets_dir / state
        if state_dir.exists():
            for i in range(num_frames):
                frame_path = state_dir / f"{i}.png"
                if frame_path.exists():
                    frames.append(QPixmap(str(frame_path)))
                else:
                    break  # Stop if frame doesn't exist
        
        # Fallback to loader if no frames found
        if not frames:
            frames = [self.loader.get_avatar_image((64, 64))]
        
        self.frames_cache[state] = frames
        return frames
    
    def create_avatar_widget(self, width: int = 200, height: int = 200) -> QLabel:
        """Create a QLabel widget that displays animated avatar."""
        avatar = QLabel()
        avatar.setFixedSize(width, height)
        avatar.setScaledContents(True)
        
        # Load idle animation frames
        self.idle_frames = self.load_frames("idle")
        
        # Set initial frame (scaled)
        initial_pixmap = self.idle_frames[0].scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        avatar.setPixmap(initial_pixmap)
        
        # Setup animation timer
        fps = self.states["idle"]["fps"]
        interval = 1000 // fps
        
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(lambda: self._animate(avatar))
        self.frame_timer.start(interval)
        
        # Store reference to avatar for timer
        self.current_avatar = avatar
        
        return avatar
    
    def _animate(self, widget: QLabel):
        """Advance animation frame."""
        if getattr(self, "_closing", False):
            return
        try:
            frames = self.load_frames(self.current_state)
            if not frames:
                return
            
            self.current_frame = (self.current_frame + 1) % len(frames)
            # Scale to widget size
            scaled_pixmap = frames[self.current_frame].scaled(widget.width(), widget.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            widget.setPixmap(scaled_pixmap)
        except RuntimeError:
            # Widget/C++ object already torn down during shutdown
            pass
    
    def stop(self):
        """Stop the frame animation timer (safe during shutdown/Ctrl+C).

        Keeps the QTimer from firing while Qt widgets are being destroyed,
        which previously aborted the app with 'core dumped' on Ctrl+C.
        """
        self._closing = True
        if self.frame_timer is not None:
            try:
                self.frame_timer.stop()
            except RuntimeError:
                pass
    
    def set_state(self, state: str):
        """Change animation state (idle, speak, think, alert)."""
        if state not in self.states:
            print(f"Unknown state: {state}")
            return
        
        if state == self.current_state:
            return  # No change needed
        
        self.current_state = state
        self.current_frame = 0  # Reset frame when changing state
        
        # Reload frames for new state
        self.load_frames(state)
        
        # Update animation timer speed
        new_fps = self.states[state]["fps"]
        new_interval = 1000 // new_fps
        self.frame_timer.setInterval(new_interval)
    
    def set_speaking(self, is_speaking: bool = True):
        """Toggle speaking animation."""
        self.set_state("speak" if is_speaking else "idle")
    
    def set_thinking(self, is_thinking: bool = True):
        """Toggle thinking animation."""
        self.set_state("think" if is_thinking else "idle")
    
    def set_alert(self, is_alert: bool = True):
        """Toggle alert animation."""
        self.set_state("alert" if is_alert else "idle")
