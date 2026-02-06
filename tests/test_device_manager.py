import pytest
import asyncio

from api.device_manager import DeviceManager


class FakeDB:
    def __init__(self):
        self._devices = {}
        self._next = 1

    def add_device(self, name, model, owner_id, ip=None, mac=None, provisioned=False):
        did = self._next
        self._next += 1
        self._devices[did] = {
            "id": did,
            "name": name,
            "model": model,
            "owner_id": owner_id,
            "ip": ip,
            "mac": mac,
            "provisioned": int(bool(provisioned)),
            "status": None,
            "last_seen": None,
        }
        return did

    def get_device_by_id(self, device_id):
        return self._devices.get(device_id)

    def update_device_status(self, device_id, status, last_seen=None):
        if device_id in self._devices:
            self._devices[device_id]["status"] = status
            self._devices[device_id]["last_seen"] = last_seen
            return True
        return False


@pytest.mark.asyncio
async def test_discover_presents_candidates(monkeypatch):
    # Patch kasa.Discover.discover to return a fake device
    class FakeDiscover:
        @staticmethod
        async def discover(timeout=5):
            return {
                "192.168.1.50": {
                    "sys_info": {"mac": "aa:bb:cc:dd:ee:ff", "model": "HS100"}
                }
            }

    monkeypatch.setitem(
        __import__("sys").modules,
        "kasa",
        __import__("types").SimpleNamespace(Discover=FakeDiscover),
    )

    db = FakeDB()
    dm = DeviceManager(db)
    results = await dm.discover(timeout=1)
    assert isinstance(results, list)
    assert any(r.get("ip") == "192.168.1.50" for r in results)


@pytest.mark.asyncio
async def test_provision_and_control(monkeypatch):
    db = FakeDB()
    dm = DeviceManager(db)

    # Monkeypatch adapter creation to avoid network calls
    class StubAdapter:
        def __init__(self, ip):
            self.ip = ip

        async def turn_on(self):
            return None

        async def turn_off(self):
            return None

        async def get_state(self):
            return {"is_on": True}

    monkeypatch.setattr(
        dm, "_adapter_for_device", lambda device: StubAdapter(device.get("ip"))
    )

    discovery = {"ip": "192.168.1.50", "mac": "aa:bb:cc:dd:ee:ff", "model": "HS100"}
    device_id = await dm.provision(discovery, owner_id=1, name="Test Plug")
    assert device_id != -1

    # Turn on/off and get state
    await dm.turn_on(device_id)
    await dm.turn_off(device_id)
    state = await dm.get_state(device_id)
    assert isinstance(state, dict)
