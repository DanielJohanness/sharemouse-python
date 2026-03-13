"""
Mouse Sync Client - Receive and apply cursor position and mouse events
Runs on target PC to receive and execute mouse/keyboard events
"""
import asyncio
import json
import logging
import websockets
import pyautogui
from utils import normalize_position, denormalize_position, get_screen_size, smooth_move, get_mouse_sensitivity, scale_delta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PyAutoGUI settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01


class MouseClient:
    def __init__(self, server_uri='ws://localhost:8765', position='right'):
        self.server_uri = server_uri
        self.screen_width, self.screen_height = get_screen_size()
        self.running = False
        self.smooth_movement = False  # Disable for extended monitor feel
        self.last_x = 0
        self.last_y = 0
        self.control_active = False  # Only control when server activates
        self.position = position  # 'right', 'left', 'top', 'bottom' relative to server
        self.entry_y = 0.5  # Y position where cursor entered
        self.entry_x = 0.5  # X position where cursor entered
        self.websocket = None  # Store websocket for sending messages
        self.edge_threshold = 5  # Pixels from edge to return control
        
        # Mouse sensitivity settings
        self.client_sensitivity = get_mouse_sensitivity()
        self.server_sensitivity = 1.0  # Will be updated from server
        logger.info(f"Client mouse sensitivity: {self.client_sensitivity:.2f}")
        
        # Clipboard monitoring
        self.last_clipboard = ""
        self.clipboard_enabled = True
        self.websocket = None  # Store websocket for sending messages
        self.return_threshold = 5  # Pixels from entry edge to trigger return
        
    async def connect(self):
        """Connect to server and handle incoming messages"""
        self.running = True
        retry_delay = 1
        
        # Start clipboard monitoring task
        clipboard_task = asyncio.create_task(self.monitor_clipboard())
        
        while self.running:
            try:
                logger.info(f"Connecting to {self.server_uri}...")
                async with websockets.connect(self.server_uri) as websocket:
                    self.websocket = websocket  # Store for sending messages
                    logger.info("Connected to server")
                    logger.info(f"Screen resolution: {self.screen_width}x{self.screen_height}")
                    logger.info(f"Clipboard sync: {'Enabled' if self.clipboard_enabled else 'Disabled'}")
                    retry_delay = 1
                    
                    async for message in websocket:
                        await self.handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed")
                self.websocket = None
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self.websocket = None
            
            if self.running:
                logger.info(f"Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
    
    async def handle_message(self, message):
        """Process incoming message and execute corresponding action"""
        try:
            data = json.loads(message)
            event_type = data.get('type')
            
            if event_type == 'control':
                await self.handle_control(data)
            elif event_type == 'move':
                await self.handle_move(data)
            elif event_type == 'click':
                await self.handle_click(data)
            elif event_type == 'scroll':
                await self.handle_scroll(data)
            elif event_type == 'key_press':
                await self.handle_key_press(data)
            elif event_type == 'key_release':
                await self.handle_key_release(data)
            elif event_type == 'clipboard':
                await self.handle_clipboard(data)
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def handle_control(self, data):
        """Handle control activation/deactivation"""
        active = data.get('active', False)
        
        if active and not self.control_active:
            self.control_active = True
            self.entry_y = data.get('entry_y', 0.5)
            self.entry_x = data.get('entry_x', 0.5)
            
            # Get server sensitivity settings
            self.server_sensitivity = data.get('server_sensitivity', 1.0)
            server_accel = data.get('server_acceleration', False)
            
            logger.info(f"Server sensitivity: {self.server_sensitivity:.2f}")
            logger.info(f"Sensitivity scaling: {self.client_sensitivity / self.server_sensitivity:.2f}x")
            
            # Position cursor at entry point based on client position
            # This simulates cursor "entering" from the edge with SAME Y position
            if self.position == 'right':
                # Enter from left edge, preserve Y position from server
                x = 0
                y = int(self.entry_y * self.screen_height)
            elif self.position == 'left':
                # Enter from right edge, preserve Y position from server
                x = self.screen_width - 1
                y = int(self.entry_y * self.screen_height)
            elif self.position == 'top':
                # Enter from bottom edge, preserve X position from server
                x = int(self.entry_x * self.screen_width)
                y = self.screen_height - 1
            elif self.position == 'bottom':
                # Enter from top edge, preserve X position from server
                x = int(self.entry_x * self.screen_width)
                y = 0
            else:
                x = self.screen_width // 2
                y = self.screen_height // 2
            
            pyautogui.moveTo(x, y)
            self.last_x = x
            self.last_y = y
            logger.info(f"✓ Control ACTIVE - Cursor entered at ({x}, {y}) [Y={self.entry_y:.2f}]")
            
        elif not active and self.control_active:
            self.control_active = False
            logger.info("✗ Control INACTIVE - Cursor returned to server")
    
    async def handle_move(self, data):
        """Handle mouse move event - only when control is active"""
        if not self.control_active:
            return
        
        # Use delta movement for smooth extended monitor feel
        if 'delta_x' in data and 'delta_y' in data:
            delta_x = data['delta_x']
            delta_y = data['delta_y']
            
            # Apply sensitivity scaling
            scaled_x, scaled_y = scale_delta(delta_x, delta_y, 
                                            self.server_sensitivity,
                                            self.client_sensitivity)
            
            # Apply delta to current position
            new_x = self.last_x + scaled_x
            new_y = self.last_y + scaled_y
            
            # Check if cursor is trying to leave client screen (return to server)
            should_return = False
            exit_edge = None
            
            if self.position == 'right':
                # Client is to the right, check if cursor reaches LEFT edge
                if new_x < 0:
                    should_return = True
                    exit_edge = 'left'
                    new_x = 0  # Clamp at edge
            elif self.position == 'left':
                # Client is to the left, check if cursor reaches RIGHT edge
                if new_x >= self.screen_width:
                    should_return = True
                    exit_edge = 'right'
                    new_x = self.screen_width - 1
            elif self.position == 'top':
                # Client is above, check if cursor reaches BOTTOM edge
                if new_y >= self.screen_height:
                    should_return = True
                    exit_edge = 'bottom'
                    new_y = self.screen_height - 1
            elif self.position == 'bottom':
                # Client is below, check if cursor reaches TOP edge
                if new_y < 0:
                    should_return = True
                    exit_edge = 'top'
                    new_y = 0
            
            # Clamp to screen bounds
            new_x = max(0, min(new_x, self.screen_width - 1))
            new_y = max(0, min(new_y, self.screen_height - 1))
            
            # Move cursor
            pyautogui.moveTo(int(new_x), int(new_y))
            
            self.last_x = new_x
            self.last_y = new_y
            
            # Return control if we hit the exit edge
            if should_return:
                logger.info(f"Cursor hit {exit_edge} edge, returning control to server")
                await self.return_control()
        else:
            # Fallback to absolute positioning
            norm_x = data.get('abs_x', data.get('x', 0.5))
            norm_y = data.get('abs_y', data.get('y', 0.5))
            
            client_x = int(norm_x * self.screen_width)
            client_y = int(norm_y * self.screen_height)
            
            # Clamp to screen bounds
            client_x = max(0, min(client_x, self.screen_width - 1))
            client_y = max(0, min(client_y, self.screen_height - 1))
            
            pyautogui.moveTo(client_x, client_y)
            
            self.last_x = client_x
            self.last_y = client_y
    
    async def return_control(self):
        """Send signal to server to return control"""
        if self.websocket and self.control_active:
            try:
                # Normalize current position for server
                norm_x = self.last_x / self.screen_width
                norm_y = self.last_y / self.screen_height
                
                return_data = {
                    'type': 'return_control',
                    'position': self.position,
                    'exit_x': norm_x,
                    'exit_y': norm_y
                }
                await self.websocket.send(json.dumps(return_data))
                self.control_active = False
                logger.info(f"✓ Returned control to server (exit at {norm_x:.2f}, {norm_y:.2f})")
            except Exception as e:
                logger.error(f"Failed to send return control: {e}")
    
    async def handle_click(self, data):
        """Handle mouse click event - only when control is active"""
        if not self.control_active:
            return
        
        button = data['button']
        pressed = data['pressed']
        
        # Map button names
        button_map = {
            'left': 'left',
            'right': 'right',
            'middle': 'middle'
        }
        
        pyautogui_button = button_map.get(button, 'left')
        
        # Click at current cursor position
        if pressed:
            pyautogui.mouseDown(button=pyautogui_button)
        else:
            pyautogui.mouseUp(button=pyautogui_button)
    
    async def handle_scroll(self, data):
        """Handle mouse scroll event - only when control is active"""
        if not self.control_active:
            return
        
        dx = data['dx']
        dy = data['dy']
        
        # PyAutoGUI scroll: positive = up, negative = down
        scroll_amount = int(dy * 100)  # Scale for better feel
        if scroll_amount != 0:
            pyautogui.scroll(scroll_amount)
    
    async def handle_key_press(self, data):
        """Handle keyboard press event"""
        try:
            key_data = data.get('key_data', {})
            key_type = key_data.get('type')
            
            if key_type == 'char':
                # Regular character
                char = key_data.get('char')
                if char:
                    pyautogui.press(char)
                    
            elif key_type == 'special':
                # Special key (Ctrl, Alt, Shift, etc.)
                key_name = key_data.get('key')
                
                # Map pynput key names to pyautogui key names
                key_mapping = {
                    'ctrl_l': 'ctrlleft',
                    'ctrl_r': 'ctrlright',
                    'ctrl': 'ctrl',
                    'alt_l': 'altleft',
                    'alt_r': 'altright',
                    'alt': 'alt',
                    'alt_gr': 'altright',
                    'shift_l': 'shiftleft',
                    'shift_r': 'shiftright',
                    'shift': 'shift',
                    'cmd': 'command',
                    'cmd_l': 'command',
                    'cmd_r': 'command',
                    'enter': 'enter',
                    'return': 'enter',
                    'space': 'space',
                    'tab': 'tab',
                    'backspace': 'backspace',
                    'delete': 'delete',
                    'esc': 'esc',
                    'escape': 'esc',
                    'up': 'up',
                    'down': 'down',
                    'left': 'left',
                    'right': 'right',
                    'home': 'home',
                    'end': 'end',
                    'page_up': 'pageup',
                    'page_down': 'pagedown',
                    'caps_lock': 'capslock',
                    'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
                    'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
                    'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
                }
                
                pyautogui_key = key_mapping.get(key_name.lower(), key_name)
                pyautogui.keyDown(pyautogui_key)
                
        except Exception as e:
            logger.error(f"Key press handling error: {e}")
    
    async def handle_key_release(self, data):
        """Handle keyboard release event"""
        try:
            key_data = data.get('key_data', {})
            key_type = key_data.get('type')
            
            if key_type == 'char':
                # Regular character - already handled in press
                pass
                
            elif key_type == 'special':
                # Special key - release it
                key_name = key_data.get('key')
                
                # Map pynput key names to pyautogui key names
                key_mapping = {
                    'ctrl_l': 'ctrlleft',
                    'ctrl_r': 'ctrlright',
                    'ctrl': 'ctrl',
                    'alt_l': 'altleft',
                    'alt_r': 'altright',
                    'alt': 'alt',
                    'alt_gr': 'altright',
                    'shift_l': 'shiftleft',
                    'shift_r': 'shiftright',
                    'shift': 'shift',
                    'cmd': 'command',
                    'cmd_l': 'command',
                    'cmd_r': 'command',
                    'enter': 'enter',
                    'return': 'enter',
                    'space': 'space',
                    'tab': 'tab',
                    'backspace': 'backspace',
                    'delete': 'delete',
                    'esc': 'esc',
                    'escape': 'esc',
                    'up': 'up',
                    'down': 'down',
                    'left': 'left',
                    'right': 'right',
                    'home': 'home',
                    'end': 'end',
                    'page_up': 'pageup',
                    'page_down': 'pagedown',
                    'caps_lock': 'capslock',
                    'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
                    'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
                    'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
                }
                
                pyautogui_key = key_mapping.get(key_name.lower(), key_name)
                pyautogui.keyUp(pyautogui_key)
                
        except Exception as e:
            logger.error(f"Key release handling error: {e}")
    
    async def handle_clipboard(self, data):
        """Handle clipboard sync from server"""
        clipboard_text = data.get('text', '')
        if clipboard_text and clipboard_text != self.last_clipboard:
            from utils import set_clipboard
            if set_clipboard(clipboard_text):
                self.last_clipboard = clipboard_text
                logger.info(f"Clipboard synced from server ({len(clipboard_text)} chars)")
    
    async def monitor_clipboard(self):
        """Monitor clipboard changes and sync to server"""
        while self.running:
            try:
                if self.clipboard_enabled and self.websocket:
                    from utils import get_clipboard
                    current_clipboard = get_clipboard()
                    
                    if current_clipboard and current_clipboard != self.last_clipboard:
                        # Clipboard changed, sync to server
                        self.last_clipboard = current_clipboard
                        
                        data = {
                            'type': 'clipboard',
                            'text': current_clipboard
                        }
                        
                        await self.websocket.send(json.dumps(data))
                        logger.info(f"Clipboard synced to server ({len(current_clipboard)} chars)")
                
                # Check every 500ms
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Clipboard monitoring error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop client"""
        self.running = False
        logger.info("Client stopped")


if __name__ == '__main__':
    import sys
    
    server_uri = 'ws://localhost:8765'
    position = 'right'  # Default: client is to the right of server
    
    if len(sys.argv) > 1:
        server_uri = sys.argv[1]
    if len(sys.argv) > 2:
        position = sys.argv[2]  # 'right' or 'left'
    
    client = MouseClient(server_uri, position)
    logger.info(f"Client position: {position} of server")
    logger.info("Waiting for server to activate control...")
    
    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        client.stop()
        logger.info("Client shutdown")
