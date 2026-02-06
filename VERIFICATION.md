# Verification Checklist

Follow these steps to verify the multi-device provisioning and control flow locally.

1. Initialize the database (fresh DB):

```bash
sqlite3 onelight.db < src/onelight_init_schema.sql
```

2. Start the application:

```bash
python src/app.py
```

3. Create a user using the web Signup page and log in. Confirm the server logs show your DB `user.id` in the session (login binds `AuthUser.id` to DB user id).

4. Visit `/home` or `/devices` to open your devices dashboard. Initially there should be no devices.

5. Open `/devices/add`, put a Kasa plug into factory/AP provisioning mode (follow device manual), and click `Scan`:
   - Confirm the scan returns candidate devices with IP and MAC.
   - If no devices appear, check that the server is on the same LAN and that firewalls are not blocking discovery.

6. Select a discovered candidate and register it:
   - Confirm the UI shows the device was registered and you are redirected to `/devices`.
   - Inspect the `devices` table (SQLite) and verify the new row has `owner_id` set to your `users.id` and `provisioned = 1`.

7. From `/devices` or the device detail page, toggle the device On and Off:
   - Confirm the device actually powers On/Off.
   - Check that the `status` and `last_seen` fields are updated in the `devices` table after actions.

8. Security/ownership checks:
   - Create a second user account and attempt to access the first user's device detail page or control endpoints. The server should respond with HTTP 403 (Forbidden).

9. Legacy routes sanity check:
   - The legacy routes `/on`, `/off`, `/hs100_status`, and `/hs100_state` still exist and operate as before. Use them only for compatibility testing with older branches.

10. Running tests (optional):

Install test deps and run tests locally (tests are provided as stubs and not executed in the CI here):

```bash
pip install pytest pytest-asyncio
pytest tests/
```

Troubleshooting notes:
- If discovery fails repeatedly, ensure your server is connected to the same Wi‑Fi network as the device and that the device is in provisioning mode.
- If `python-kasa` fails to import, install it into your active virtualenv and verify compatibility.
