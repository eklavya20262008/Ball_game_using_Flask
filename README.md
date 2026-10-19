# Ball Bounce — 2-player online game

## Requirements
- Python 3.10 or newer
- Internet connection for the Socket.IO browser client CDN (or download the client locally if you want offline assets)

## Setup (Windows)
1. Extract the ZIP.
2. Open the extracted folder in VS Code.
3. Open Terminal in VS Code.
4. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   ```
5. Activate it:
   - Command Prompt: `.venv\Scripts\activate`
   - PowerShell: `.\.venv\Scripts\Activate.ps1`
6. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
7. Start the Flask server:
   ```bash
   python app.py
   ```
8. On the same computer, open `http://127.0.0.1:5000`.
9. Player 1 clicks **Create game** and shares the room code. Player 2 enters that code and clicks **Join game**.

## Test on two devices on the same Wi-Fi
- Find the host computer's local IPv4 address (Windows: run `ipconfig`).
- On the second device, open `http://HOST-LAN-IP:5000` (replace with the host's actual IPv4 address).
- Allow Python through the host computer's firewall if prompted.
- Both devices must be on the same Wi-Fi for this local test.

## Online over the internet
Deploy the Flask app to a Python hosting service that supports WebSockets / Socket.IO and persistent background processes. GitHub Pages alone cannot host this Flask server. Use the hosting provider's start command `python app.py` or its documented equivalent.

## Controls
Move your mouse over the game canvas, or touch/drag on the canvas on mobile. Each player controls their own horizontal paddle. Three misses means OUT.

## Notes
- Rooms and scores are stored in memory, so restarting the server clears them.
- This is a learning/demo project. Before public deployment, replace the secret key and add stricter validation, rate limiting, and production server configuration.
