# OneLight

OneLight is a small local web application for managing Kasa-compatible smart plugs (TP‑Link HS1xx series) on your local network. It provides per-user device registration, discovery/provisioning for devices in factory/AP mode, and per-device control (on/off and state) from a simple dashboard.

Target audience
- Smart home enthusiasts who want a lightweight, local-only management UI for Kasa plugs.
- Technically literate users comfortable with the CLI and Python virtual environments; some network familiarity (LAN, 2.4GHz Wi‑Fi) is helpful.

What's new in this branch
- Multi‑device support: register multiple smart plugs per user.
- Device abstraction: new `DeviceManager` module (`src/api/device_manager.py`) provides discovery, provisioning, and control using adapters (Kasa adapter included).
- In‑app provisioning: UI supports scanning for devices in factory/AP mode and registering them directly into the app.
- Per‑user device ownership: devices are stored with `owner_id` referencing `users.id`.
- New templates: `src/templates/devices.html`, `add_device.html`, and `device_detail.html` provide the dashboard and onboarding flow.

Important notes
- Legacy routes preserved for compatibility: `/on`, `/off`, `/hs100_status`, and `/hs100_state` remain unchanged to avoid merge conflicts with other branches.
- The existing `smart_device_manager.py` is intentionally left untouched; new functionality lives in `src/api/device_manager.py`.
- Discovery and provisioning use `python-kasa`. The application will log an error and return useful messages if `python-kasa` is not installed.
- This project is intended to run on the same LAN as your devices — do not expose it to the public internet without additional security measures.

Requirements
- Python 3.10 (tested)
- Virtual environment (recommended)
- Dependencies listed in `requirements.txt` (install with `pip install -r requirements.txt`)
- `python-kasa` installed for discovery/provisioning (ensure compatible version)

Quick start (fresh setup)

1. Create and activate a virtual environment (example for Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Initialize the database (this project uses SQLite). From the project root run:

```bash
sqlite3 onelight.db < src/onelight_init_schema.sql
```

4. Start the app:

```bash
python src/app.py
```

5. Open the management UI from another device on the same LAN at the hosting machine's IP. Example: `http://192.168.1.100:5000/` (the app listens on the default Quart port unless configured otherwise).

Provisioning notes
- When registering a new Kasa plug via the app's "Add Device" page, put the plug in factory/AP provisioning mode (usually by resetting the plug as per the device instructions) so it advertises itself on a temporary Wi‑Fi network. Then use the app's "Scan" button — discovery runs on the local network and should list candidates (IP, model, MAC). Select a candidate and register it to your account.
- Discovery and provisioning require the server to be on the same Wi‑Fi network (2.4GHz for many Kasa devices). Firewalls or network isolation (guest networks) may block discovery.

Security considerations
- This application does not implement production-grade CSRF or extensive session hardening. Keep it local and behind a firewall.
- If any device credentials or tokens are obtained during provisioning, avoid storing them in plaintext; consider adding encryption at rest.

Developer notes
- Files added or changed in this feature branch:
  - `src/api/device_manager.py` — new DeviceManager + KasaAdapter
  - `src/database/database.py` — added device CRUD helpers (`add_device`, `get_devices_for_user`, etc.)
  - `src/onelight_init_schema.sql` — updated schema (uses `owner_id` FK)
  - `src/app.py` — new `/devices*` routes and ownership checks (legacy routes preserved)
  - `src/templates/*.html` — new templates for device dashboard and onboarding
  - `tests/*` — test stubs for device manager and auth binding (not executed here)

Running tests
- Tests are provided as stubs and are not executed in this branch by default. To run tests (from project root) after installing dev deps:

```bash
pip install pytest pytest-asyncio
pytest tests/
```

Verification checklist
1. Initialize DB as described above.
2. Start the app and create a user via the signup page.
3. Log in and confirm you are redirected to `/home` and that the server logs show your DB `user.id` bound to the session.
4. Open "Add Device", put a Kasa plug into factory/AP mode, click "Scan" and verify the device appears in candidates.
5. Register the discovered device; verify it appears on your devices dashboard and that the `devices` table has `owner_id` set to your `users.id` and `provisioned = 1`.
6. Toggle the device on/off from the dashboard or device detail page and confirm the state change and `last_seen` updates in the DB.
7. Attempt to access or control a device from a different user account — confirm access is denied (HTTP 403).

Troubleshooting
- If discovery returns no devices:
  - Ensure the server is on the same Wi‑Fi network as the device.
  - Confirm the plug is in provisioning/factory AP mode.
  - Check firewall rules that may block UDP discovery or mDNS.
- If `python-kasa` import fails, install it in your venv and check compatibility with your platform.

Future work
- Add secure storage/encryption for any device secrets.
- Implement CSRF protection and stronger session management.
- Expand adapters for non‑Kasa devices and a plugin architecture for third‑party integrations.

License & contribution
- This project is MIT licensed. Contributions welcome via pull requests — please keep changes small and focused to simplify merges with other active branches.
