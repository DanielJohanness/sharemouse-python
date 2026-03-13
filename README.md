# ShareMouse-Py - Open Source Mouse Sharing

Open-source Python implementation of ShareMouse functionality - Control multiple PCs with one mouse and keyboard.

## 🎯 Features

- ✅ **Seamless Mouse Control** - Move cursor across multiple PCs like extended monitors
- ✅ **Edge Detection** - Automatic transition when cursor reaches screen edge
- ✅ **Cross-platform** - Works on Windows and macOS
- ✅ **Keyboard Forwarding** - Full keyboard support including special keys
- ✅ **Clipboard Sync** - Copy on one PC, paste on another (text)
- ✅ **Mouse Sensitivity Sync** - Automatic DPI/sensitivity scaling
- ✅ **Click & Scroll** - Full mouse button and scroll wheel support
- ✅ **Keyboard Shortcuts** - Ctrl+C, Ctrl+V, and all shortcuts work
- ✅ **Multi-directional** - Support left, right, top, bottom positioning
- ✅ **Auto-reconnect** - Handles network interruptions gracefully
- ✅ **Low Latency** - WebSocket-based real-time communication
- ✅ **Free & Open Source** - No licensing fees, fully customizable

## 🆚 ShareMouse vs ShareMouse-Py

| Feature | ShareMouse (Commercial) | ShareMouse-Py (This) |
|---------|------------------------|----------------------|
| Mouse & Keyboard Control | ✅ | ✅ |
| Edge Detection | ✅ | ✅ |
| Cross-platform | ✅ | ✅ |
| Clipboard Sync | ✅ | ✅ |
| Mouse Sensitivity Sync | ✅ | ✅ |
| Special Keys (Ctrl/Alt/Cmd) | ✅ | ✅ |
| Keyboard Shortcuts | ✅ | ✅ |
| Drag & Drop Files | ✅ | 🚧 Planned |
| Auto-discovery | ✅ | 🚧 Planned |
| Encryption | ✅ | 🚧 Planned |
| GUI Application | ✅ | 🚧 Planned |
| Price | 💰 $24.95+ | ✅ Free |
| Open Source | ❌ | ✅ |

## 📋 Requirements

- Python 3.7+
- Windows 10+ or macOS 10.14+
- Network connection (LAN recommended for best performance)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch Application

**Easy Way (Recommended):**
```bash
python launcher.py
```

The launcher provides an interactive menu:
- Start as Controller (primary PC with mouse/keyboard)
- Start as Controlled (secondary PC to be controlled)
- Test Setup
- Show Network Info

**Manual Way:**

**Primary PC (Controller):**
```bash
python server.py
```

**Secondary PC (Controlled):**
```bash
python client.py ws://192.168.1.100:8765 right
```

### 3. Setup Layout

Configure the physical position of your secondary PC relative to primary:
- `right` - Secondary PC is to the RIGHT of primary
- `left` - Secondary PC is to the LEFT of primary
- `top` - Secondary PC is ABOVE primary
- `bottom` - Secondary PC is BELOW primary

### 4. Use It!

1. Move your mouse to the edge of primary screen
2. Cursor seamlessly appears on secondary screen
3. Control secondary PC with your primary mouse/keyboard
4. Move back to return control to primary PC

## 📁 Project Structure

```
sharemouse-py/
├── server.py              # Controller - primary PC
├── client.py              # Controlled - secondary PC
├── utils.py               # Shared utilities
├── launcher.py            # Interactive launcher
├── test_setup.py          # Installation verification
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── .gitignore            # Git ignore rules
```

## ⚙️ Configuration

### Server (Primary PC)

Edit `server.py` to customize:
```python
server = MouseServer(
    host='0.0.0.0',        # Listen on all interfaces
    port=8765,             # WebSocket port
    edge_trigger='right',  # Edge to trigger: right/left/top/bottom
    edge_threshold=5       # Pixels from edge to trigger (default: 5)
)
```

### Client (Secondary PC)

```bash
# Syntax
python client.py [SERVER_URI] [POSITION]

# Examples
python client.py ws://192.168.1.100:8765 right
python client.py ws://192.168.1.100:8765 left
python client.py ws://localhost:8765 top
```

## 🔧 Advanced Usage

### Find Your IP Address

**Windows:**
```cmd
ipconfig
```

**macOS/Linux:**
```bash
ifconfig
# or
ip addr show
```

### Test Local Setup (Single PC)

**Terminal 1:**
```bash
python server.py
```

**Terminal 2:**
```bash
python client.py ws://localhost:8765 right
```

### Multiple Secondary PCs

You can connect multiple secondary PCs to one primary:

**Primary PC:**
```bash
python server.py
```

**Secondary PC 1 (Right):**
```bash
python client.py ws://192.168.1.100:8765 right
```

**Secondary PC 2 (Left):**
```bash
python client.py ws://192.168.1.100:8765 left
```

## 🐛 Troubleshooting

### macOS: "Operation not permitted"

Grant Accessibility permissions:
1. System Preferences → Security & Privacy → Privacy → Accessibility
2. Add Terminal or Python to the list
3. Restart terminal

### Windows: Firewall Blocking

- Allow Python through Windows Firewall when prompted
- Or manually: Control Panel → Windows Defender Firewall → Allow an app

### Connection Issues

- Ensure both PCs are on the same network
- Check firewall isn't blocking port 8765
- Verify IP address is correct
- Try disabling VPN if active

### Cursor Stuck at Edge

This has been fixed in the latest version with:
- Directional delta filtering
- 5px boundary protection at entry edge
- Position reset on control switch

### High Latency

- Use wired LAN instead of WiFi
- Close bandwidth-heavy applications
- Check for network congestion
- Reduce distance between PCs

## 🎨 How It Works

### Architecture

```
Primary PC (Controller)          Secondary PC (Controlled)
┌──────────────────┐             ┌──────────────────┐
│                  │             │                  │
│  Mouse/Keyboard  │             │                  │
│       ↓          │             │                  │
│   server.py      │             │   client.py      │
│       ↓          │             │       ↑          │
│  Edge Detection  │             │  Event Executor  │
│       ↓          │             │       ↑          │
│   WebSocket ─────┼─────────────┼→ WebSocket       │
│                  │   Network   │                  │
└──────────────────┘             └──────────────────┘
```

### Edge Detection Flow

```
1. Primary: Cursor reaches edge (X >= screen_width - 5)
2. Primary: Activate control, send signal to secondary
3. Secondary: Position cursor at opposite edge (X = 0)
4. Primary: Send delta movements (dx, dy)
5. Secondary: Apply delta to cursor position
6. Primary: Cursor moves back from edge
7. Primary: Deactivate control, return to primary
```

### Delta-based Movement

Unlike absolute positioning, we use delta (relative) movement:
- More accurate across different screen resolutions
- Smoother cursor motion
- Prevents "jumping" artifacts
- Mimics real extended monitor behavior

## 🔐 Security Considerations

⚠️ **Warning:** This application provides full mouse/keyboard control over connected PCs.

For production use, consider:
- Add authentication tokens
- Use WSS (WebSocket Secure) with SSL/TLS
- Implement IP whitelist
- Encrypt transmitted data
- Use VPN for remote connections

## 🛣️ Roadmap

### Planned Features

- [ ] **Clipboard Sync** - Copy/paste between PCs
- [ ] **Drag & Drop** - Transfer files by dragging
- [ ] **Auto-discovery** - Automatic PC detection on LAN
- [ ] **Encryption** - Secure communication
- [ ] **GUI Application** - Native desktop app
- [ ] **System Tray** - Background operation
- [ ] **Hotkeys** - Quick enable/disable
- [ ] **Multi-monitor** - Support for multiple monitors per PC
- [ ] **Linux Support** - Full Linux compatibility

### Future Improvements

- [ ] Better error handling
- [ ] Connection quality indicator
- [ ] Latency measurement display
- [ ] Configuration file support
- [ ] Logging system
- [ ] Performance optimizations

## 📝 Tips & Best Practices

- **Use LAN:** Wired connection provides lowest latency
- **Screen Alignment:** Physically align monitors for intuitive cursor flow
- **Edge Threshold:** Adjust `edge_threshold` if triggering too easily/hard
- **Return Distance:** Default 50px from edge to return control
- **Testing:** Test locally first before network setup
- **Firewall:** Ensure port 8765 is open on both PCs

## 🤝 Contributing

Contributions are welcome! Areas that need help:
- Clipboard synchronization implementation
- File drag & drop functionality
- Auto-discovery protocol
- GUI development
- Linux testing and support
- Documentation improvements

## 📄 License

MIT License - Free to use and modify.

## 🙏 Acknowledgments

Inspired by [ShareMouse](https://www.sharemouse.com/) - the commercial solution for mouse/keyboard sharing.

## 📧 Support

- Create an issue for bug reports
- Star the repo if you find it useful
- Share with others who might benefit

---

**ShareMouse-Py** - Because mouse sharing should be free and open source! 🐭✨
