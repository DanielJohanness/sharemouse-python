"""
Mouse Sync Server - Broadcast cursor position and mouse events
Runs on source PC to track and send mouse/keyboard events to target PC(s)
"""
import asyncio
import json
import logging
from pynput import mouse, keyboard
from pynput.mouse import Button
import websockets
import pyautogui
from utils import normalize_position, get_screen_size, get_mouse_sensitivity, get_mouse_acceleration, get_clipboard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MouseServer:
    def __init__(self, host='0.0.0.0', port=8765, edge_trigger='right', edge_threshold=5):
        self.host = host
        self.port = port
        self.clients = set()
        self.screen_width, self.screen_height = get_screen_size()
        self.running = False
        self.edge_trigger = edge_trigger  # 'right', 'left', 'top', 'bottom'
        self.edge_threshold = edge_threshold  # pixels from edge to trigger
        self.control_active = False  # Track if client control is active
        self.last_x = 0
        self.last_y = 0
        self.virtual_x = 0  # Virtual X position for extended desktop
        self.virtual_y = 0  # Virtual Y position for extended desktop
        self.transition_point = 0  # Where cursor crossed to client
        self.entry_x = 0  # X position when entering client
        self.entry_y = 0  # Y position when entering client
        
        # Mouse sensitivity settings
        self.mouse_sensitivity = get_mouse_sensitivity()
        self.mouse_acceleration = get_mouse_acceleration()
        logger.info(f"Mouse sensitivity: {self.mouse_sensitivity:.2f}")
        logger.info(f"Mouse acceleration: {'Enabled' if self.mouse_acceleration else 'Disabled'}")
        
        # Clipboard monitoring
        self.last_clipboard = ""
        self.clipboard_enabled = True
        
    async def register(self, websocket):
        """Register new client connection"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
    async def unregister(self, websocket):
        """Unregister client connection"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
        
    async def broadcast(self, message):
        """Send message to all connected clients"""
        if self.clients:
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
    
    async def handle_client(self, websocket, path):
        """Handle individual client connection"""
        await self.register(websocket)
        try:
            async for message in websocket:
                # Handle messages from client (e.g., return signal)
                try:
                    data = json.loads(message)
                    if data.get('type') == 'return_control':
                        # Client is returning control to server
                        if self.control_active:
                            self.control_active = False
                            
                            # Position server cursor at the edge where client exited
                            exit_x = data.get('exit_x', 0.5)
                            exit_y = data.get('exit_y', 0.5)
                            
                            # Convert to server coordinates at the edge
                            if self.edge_trigger == 'right':
                                # Cursor returning from right, place at right edge
                                server_x = self.screen_width - 1
                                server_y = int(exit_y * self.screen_height)
                            elif self.edge_trigger == 'left':
                                # Cursor returning from left, place at left edge
                                server_x = 0
                                server_y = int(exit_y * self.screen_height)
                            elif self.edge_trigger == 'top':
                                # Cursor returning from top, place at top edge
                                server_x = int(exit_x * self.screen_width)
                                server_y = 0
                            elif self.edge_trigger == 'bottom':
                                # Cursor returning from bottom, place at bottom edge
                                server_x = int(exit_x * self.screen_width)
                                server_y = self.screen_height - 1
                            else:
                                server_x = int(exit_x * self.screen_width)
                                server_y = int(exit_y * self.screen_height)
                            
                            # Move server cursor to the edge position
                            pyautogui.moveTo(server_x, server_y)
                            
                            # Reset tracking position
                            self.last_x = server_x
                            self.last_y = server_y
                            
                            logger.info(f"✓ Control returned to server - cursor at ({server_x}, {server_y})")
                    
                    elif data.get('type') == 'clipboard':
                        # Client sent clipboard content
                        clipboard_text = data.get('text', '')
                        if clipboard_text and self.clipboard_enabled:
                            from utils import set_clipboard
                            if set_clipboard(clipboard_text):
                                self.last_clipboard = clipboard_text
                                logger.info(f"Clipboard synced from client ({len(clipboard_text)} chars)")
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
    
    def check_edge_trigger(self, x, y):
        """Check if cursor is at edge to trigger client control"""
        at_edge = False
        
        if self.edge_trigger == 'right':
            at_edge = x >= (self.screen_width - self.edge_threshold)
        elif self.edge_trigger == 'left':
            at_edge = x <= self.edge_threshold
        elif self.edge_trigger == 'top':
            at_edge = y <= self.edge_threshold
        elif self.edge_trigger == 'bottom':
            at_edge = y >= (self.screen_height - self.edge_threshold)
        
        # Activate control when reaching edge
        if at_edge and not self.control_active:
            self.control_active = True
            self.transition_point = x if self.edge_trigger in ['right', 'left'] else y
            
            # Store the position where we entered client
            self.entry_x = x
            self.entry_y = y
            
            logger.info(f"Client control ACTIVATED - cursor at edge (transition at {self.transition_point})")
            
            # Send activation signal with entry position
            data = {
                'type': 'control',
                'active': True,
                'entry_y': normalize_position(x, y, self.screen_width, self.screen_height)[1],
                'entry_x': normalize_position(x, y, self.screen_width, self.screen_height)[0],
                'server_sensitivity': self.mouse_sensitivity,
                'server_acceleration': self.mouse_acceleration
            }
            asyncio.run_coroutine_threadsafe(
                self.broadcast(json.dumps(data)),
                self.loop
            )
        
        # IMPORTANT: Don't check for "moving_back" based on server cursor position!
        # When control is active, server cursor is STUCK at edge
        # Client will send signal when cursor actually leaves client screen
        
        return self.control_active
    
    def on_move(self, x, y):
        """Mouse move event handler"""
        if self.running:
            # Calculate delta from actual mouse movement
            delta_x = x - self.last_x
            delta_y = y - self.last_y
            
            # Update last position immediately
            self.last_x = x
            self.last_y = y
            
            # Check if we should activate client control
            if not self.control_active:
                # Not active yet, check if we hit the edge
                self.check_edge_trigger(x, y)
            
            # If control is active, send delta to client
            if self.control_active:
                # Send ALL movement deltas to client
                # Client will handle boundary checking and return control if needed
                if abs(delta_x) > 0 or abs(delta_y) > 0:
                    data = {
                        'type': 'move',
                        'delta_x': delta_x,
                        'delta_y': delta_y
                    }
                    asyncio.run_coroutine_threadsafe(
                        self.broadcast(json.dumps(data)),
                        self.loop
                    )
    
    def on_click(self, x, y, button, pressed):
        """Mouse click event handler"""
        if self.running and self.control_active:
            norm_x, norm_y = normalize_position(x, y, self.screen_width, self.screen_height)
            data = {
                'type': 'click',
                'x': norm_x,
                'y': norm_y,
                'button': button.name,
                'pressed': pressed
            }
            asyncio.run_coroutine_threadsafe(
                self.broadcast(json.dumps(data)),
                self.loop
            )
    
    def on_scroll(self, x, y, dx, dy):
        """Mouse scroll event handler"""
        if self.running and self.control_active:
            data = {
                'type': 'scroll',
                'dx': dx,
                'dy': dy
            }
            asyncio.run_coroutine_threadsafe(
                self.broadcast(json.dumps(data)),
                self.loop
            )
    
    def on_press(self, key):
        """Keyboard press event handler - only when control is active"""
        if self.running and self.control_active:
            try:
                # Handle special keys
                from pynput.keyboard import Key
                
                if hasattr(key, 'char') and key.char is not None:
                    # Regular character key
                    key_data = {
                        'type': 'char',
                        'char': key.char
                    }
                else:
                    # Special key (Ctrl, Alt, Shift, etc.)
                    key_name = str(key).replace('Key.', '')
                    key_data = {
                        'type': 'special',
                        'key': key_name
                    }
                
                data = {
                    'type': 'key_press',
                    'key_data': key_data
                }
                
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(json.dumps(data)),
                    self.loop
                )
                
            except Exception as e:
                logger.error(f"Key press error: {e}")
    
    def on_release(self, key):
        """Keyboard release event handler - only when control is active"""
        if self.running and self.control_active:
            try:
                # Handle special keys
                from pynput.keyboard import Key
                
                if hasattr(key, 'char') and key.char is not None:
                    # Regular character key
                    key_data = {
                        'type': 'char',
                        'char': key.char
                    }
                else:
                    # Special key
                    key_name = str(key).replace('Key.', '')
                    key_data = {
                        'type': 'special',
                        'key': key_name
                    }
                
                data = {
                    'type': 'key_release',
                    'key_data': key_data
                }
                
                asyncio.run_coroutine_threadsafe(
                    self.broadcast(json.dumps(data)),
                    self.loop
                )
                
            except Exception as e:
                logger.error(f"Key release error: {e}")
    
    async def monitor_clipboard(self):
        """Monitor clipboard changes and sync to clients"""
        while self.running:
            try:
                if self.clipboard_enabled and self.clients:
                    current_clipboard = get_clipboard()
                    
                    if current_clipboard and current_clipboard != self.last_clipboard:
                        # Clipboard changed, sync to clients
                        self.last_clipboard = current_clipboard
                        
                        data = {
                            'type': 'clipboard',
                            'text': current_clipboard
                        }
                        
                        await self.broadcast(json.dumps(data))
                        logger.info(f"Clipboard synced to clients ({len(current_clipboard)} chars)")
                
                # Check every 500ms
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Clipboard monitoring error: {e}")
                await asyncio.sleep(1)
    
    async def start(self):
        """Start WebSocket server and input listeners"""
        self.running = True
        self.loop = asyncio.get_event_loop()
        
        # Start mouse listener
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll
        )
        self.mouse_listener.start()
        
        # Start keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.keyboard_listener.start()
        
        logger.info(f"Server starting on {self.host}:{self.port}")
        logger.info(f"Screen resolution: {self.screen_width}x{self.screen_height}")
        logger.info(f"Edge trigger: {self.edge_trigger} (threshold: {self.edge_threshold}px)")
        logger.info(f"Clipboard sync: {'Enabled' if self.clipboard_enabled else 'Disabled'}")
        logger.info("Move cursor to the RIGHT EDGE to activate client control")
        
        # Start clipboard monitoring task
        clipboard_task = asyncio.create_task(self.monitor_clipboard())
        
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever
    
    def stop(self):
        """Stop server and listeners"""
        self.running = False
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()
        logger.info("Server stopped")


if __name__ == '__main__':
    server = MouseServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        server.stop()
        logger.info("Server shutdown")
