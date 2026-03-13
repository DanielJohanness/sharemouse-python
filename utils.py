"""
Utility functions for mouse synchronization
"""
import asyncio
import pyautogui
import time
import platform


def get_screen_size():
    """Get current screen resolution"""
    size = pyautogui.size()
    return size.width, size.height


def get_mouse_sensitivity():
    """
    Detect mouse sensitivity/DPI settings
    Returns a scaling factor (1.0 = normal)
    """
    system = platform.system()
    
    try:
        if system == 'Windows':
            import winreg
            # Read Windows mouse speed setting (1-20, default 10)
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r'Control Panel\Mouse')
            speed, _ = winreg.QueryValueEx(key, 'MouseSpeed')
            sensitivity, _ = winreg.QueryValueEx(key, 'MouseSensitivity')
            winreg.CloseKey(key)
            
            # Convert to scaling factor
            # Windows sensitivity: 1-20, default 10
            return int(sensitivity) / 10.0
            
        elif system == 'Darwin':  # macOS
            import subprocess
            # Read macOS mouse tracking speed
            result = subprocess.run(['defaults', 'read', '-g', 
                                   'com.apple.mouse.scaling'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                speed = float(result.stdout.strip())
                # macOS speed: -1 to 3, default 1
                return (speed + 1) / 2.0
    except Exception as e:
        print(f"Could not detect mouse sensitivity: {e}")
    
    # Default: no scaling
    return 1.0


def get_mouse_acceleration():
    """
    Detect if mouse acceleration is enabled
    Returns True if enabled, False otherwise
    """
    system = platform.system()
    
    try:
        if system == 'Windows':
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Control Panel\Mouse')
            accel, _ = winreg.QueryValueEx(key, 'MouseSpeed')
            winreg.CloseKey(key)
            return int(accel) > 0
            
        elif system == 'Darwin':  # macOS
            # macOS always has some acceleration
            return True
    except:
        pass
    
    return False


def get_clipboard():
    """
    Get clipboard content (text only for now)
    Returns clipboard text or None
    """
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception as e:
        print(f"Could not get clipboard: {e}")
        return None


def set_clipboard(text):
    """
    Set clipboard content
    """
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception as e:
        print(f"Could not set clipboard: {e}")
        return False


def scale_delta(delta_x, delta_y, source_sensitivity, target_sensitivity):
    """
    Scale mouse delta based on sensitivity difference
    
    Args:
        delta_x, delta_y: Original delta from source
        source_sensitivity: Source PC sensitivity factor
        target_sensitivity: Target PC sensitivity factor
    
    Returns:
        Scaled (delta_x, delta_y)
    """
    if source_sensitivity == 0 or target_sensitivity == 0:
        return delta_x, delta_y
    
    # Calculate scaling factor
    scale = target_sensitivity / source_sensitivity
    
    # Apply scaling
    scaled_x = int(delta_x * scale)
    scaled_y = int(delta_y * scale)
    
    return scaled_x, scaled_y


def normalize_position(x, y, screen_width, screen_height):
    """
    Normalize screen position to 0.0-1.0 range
    This allows handling different screen resolutions between source and target
    """
    norm_x = x / screen_width
    norm_y = y / screen_height
    return norm_x, norm_y


def denormalize_position(norm_x, norm_y, screen_width, screen_height):
    """
    Convert normalized position back to actual screen coordinates
    """
    x = int(norm_x * screen_width)
    y = int(norm_y * screen_height)
    
    # Clamp to screen bounds
    x = max(0, min(x, screen_width - 1))
    y = max(0, min(y, screen_height - 1))
    
    return x, y


async def smooth_move(start_x, start_y, end_x, end_y, steps=5):
    """
    Smooth cursor movement with interpolation
    Reduces jittery movement for better visual experience
    """
    if steps <= 1:
        pyautogui.moveTo(end_x, end_y)
        return
    
    for i in range(1, steps + 1):
        t = i / steps
        # Linear interpolation
        x = int(start_x + (end_x - start_x) * t)
        y = int(start_y + (end_y - start_y) * t)
        pyautogui.moveTo(x, y)
        await asyncio.sleep(0.001)  # Small delay for smoothness


def calculate_delta(prev_pos, curr_pos):
    """
    Calculate position delta for bandwidth optimization
    Returns None if delta is too small (no need to send)
    """
    threshold = 2  # pixels
    dx = curr_pos[0] - prev_pos[0]
    dy = curr_pos[1] - prev_pos[1]
    
    if abs(dx) < threshold and abs(dy) < threshold:
        return None
    
    return (dx, dy)


class LatencyMeasurement:
    """Simple latency measurement utility"""
    
    def __init__(self):
        self.samples = []
        self.max_samples = 100
    
    def add_sample(self, latency_ms):
        """Add latency sample"""
        self.samples.append(latency_ms)
        if len(self.samples) > self.max_samples:
            self.samples.pop(0)
    
    def get_average(self):
        """Get average latency"""
        if not self.samples:
            return 0
        return sum(self.samples) / len(self.samples)
    
    def get_stats(self):
        """Get latency statistics"""
        if not self.samples:
            return {'avg': 0, 'min': 0, 'max': 0}
        
        return {
            'avg': sum(self.samples) / len(self.samples),
            'min': min(self.samples),
            'max': max(self.samples)
        }


class RateLimiter:
    """Rate limiter for event throttling"""
    
    def __init__(self, max_rate=120):
        """
        max_rate: maximum events per second
        """
        self.max_rate = max_rate
        self.min_interval = 1.0 / max_rate
        self.last_time = 0
    
    def should_process(self):
        """Check if event should be processed based on rate limit"""
        current_time = time.time()
        if current_time - self.last_time >= self.min_interval:
            self.last_time = current_time
            return True
        return False
