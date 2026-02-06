"""
DeviceManager module

Provides a DeviceManager class that implements discovery, provisioning,
and basic control (turn_on/turn_off/get_state) for smart plugs. This file
implements a `KasaAdapter` using `python-kasa`. The existing
`smart_device_manager.py` is left untouched.

The API is async and designed to be called from Quart route handlers.
"""

import logging
from datetime import datetime
from ipaddress import ip_address, ip_network
from typing import List, Dict, Optional
from kasa.iot import IotPlug

try:
    import netifaces
except ImportError:
    netifaces = None

from constants import ONELIGHT_LOG_NAME

logger = logging.getLogger(ONELIGHT_LOG_NAME)


def get_broadcast_target() -> Optional[str]:
    """
    Detect primary non-loopback network and return broadcast address for discovery.

    Returns broadcast address (e.g., '192.168.1.255') or None if detection fails.
    Tries all non-loopback interfaces and returns the first with a valid IPv4 address.
    """
    if netifaces is None:
        logger.warning("netifaces not installed; will use default discovery")
        return None

    try:
        gateways = netifaces.gateways()
        gateway_data = gateways["default"][netifaces.AF_INET]
        if len(gateway_data) == 2:
            gateway, default_iface = gateway_data
        elif len(gateway_data) == 3:
            gateway, default_iface, _ = gateway_data
        else:
            gateway, default_iface = "", ""

        addrs = netifaces.ifaddresses(default_iface)
        addrs_ipv4 = addrs[netifaces.AF_INET][0]

        if "broadcast" in addrs_ipv4:
            target = addrs_ipv4["broadcast"]
            logger.info(f"Broadcast target found: {target}")
            return target
        logger.warning(
            f"No broadcast address could be found for interface '{default_iface}' (gateway={gateway})"
        )
        return None

    except Exception as e:
        logger.exception("Error detecting network interfaces: %s", e)
        return None


class DeviceAdapter:
    """Abstract adapter interface for devices."""

    async def turn_on(self) -> None:
        raise NotImplementedError()

    async def turn_off(self) -> None:
        raise NotImplementedError()

    async def get_state(self) -> Dict:
        raise NotImplementedError()


class KasaAdapter(DeviceAdapter):
    """Adapter that uses python-kasa SmartPlug for control."""

    def __init__(self, ip: str):
        self.ip = ip
        self.plug = None

    async def _ensure(self):
        try:
            from kasa import SmartPlug
        except Exception as exc:
            logger.error("python-kasa is required for KasaAdapter: %s", exc)
            raise
        if not self.plug:
            self.plug = SmartPlug(self.ip)
            try:
                await self.plug.update()
            except Exception:
                logger.exception("Failed to update SmartPlug at %s", self.ip)

    async def turn_on(self) -> None:
        await self._ensure()
        try:
            await self.plug.turn_on()
        except Exception:
            logger.exception("KasaAdapter.turn_on() failed for %s", self.ip)
            raise

    async def turn_off(self) -> None:
        await self._ensure()
        try:
            await self.plug.turn_off()
        except Exception:
            logger.exception("KasaAdapter.turn_off() failed for %s", self.ip)
            raise

    async def get_state(self) -> Dict:
        await self._ensure()
        try:
            # Some versions expose `.is_on` boolean after update()
            state = getattr(self.plug, "is_on", None)
            if state is None:
                # Fallback to reported state string
                state = getattr(self.plug, "state", None)
            return {"is_on": bool(state)}
        except Exception:
            logger.exception("KasaAdapter.get_state() failed for %s", self.ip)
            return {"is_on": False}


class DeviceManager:
    """
    High-level device manager that persists devices in the OneLight DB
    and uses adapters for control.
    """

    def __init__(self, db):
        self.db = db
        # adapter cache keyed by device id
        self._adapter_cache: Dict[int, DeviceAdapter] = {}

    async def discover(self, timeout: int = 5) -> List[Dict]:
        """Discover devices on the local network using python-kasa.

        Returns a list of discovery records: {ip, mac, model, raw}
        Filters out devices that are already registered in the database.
        Automatically detects the primary WiFi network broadcast address
        to avoid router restrictions on global broadcast.
        """
        try:
            from kasa import Discover
        except Exception as exc:
            logger.error("python-kasa is required for discovery: %s", exc)
            raise

        discovered = []
        try:
            # Try to detect WiFi network broadcast address
            target = get_broadcast_target()

            # Perform discovery with or without target
            if target:
                results = await Discover.discover(target=target, timeout=timeout)
            else:
                logger.info("Using default discovery (no specific target)")
                results = await Discover.discover(timeout=timeout)

            if not results or len(results) == 0:
                logger.info(
                    "No devices found in initial discovery, retrying " "with default"
                )
                results = await Discover.discover()

            logger.info(f"Raw discover results returned {len(results)} device dicts.")

            for ip, info in results.items():
                logger.debug(f"param 'info' for IP {ip} is type '{type(info)}'")
                logger.debug(f"fields for <info> object: {dir(info)}")

                # Try common locations for mac/model
                mac = None
                model = None
                if isinstance(info, dict):
                    mac = info.get("mac") or info.get("sys_info", {}).get("mac")
                    model = info.get("model") or info.get("sys_info", {}).get("model")
                else:
                    try:
                        mac = info.mac
                        model = info.model
                        info = info.config.to_dict()
                    except Exception:
                        pass

                # Skip devices that are already registered (by IP or MAC)
                existing_by_ip = self.db.get_device_by_ip(ip) if ip else None
                existing_by_mac = self.db.get_device_by_mac(mac) if mac else None
                if existing_by_ip or existing_by_mac:
                    logger.info("Skipping already-registered device at %s", ip)
                    continue

                discovered.append({"ip": ip, "mac": mac, "model": model, "raw": info})
        except Exception:
            logger.exception("Device discovery failed")

        logger.debug(f"type of discovered[0]: {type(discovered[0])}")
        logger.debug(f"type of discovered.ip: {type(discovered[0].get('ip'))}")
        logger.debug(f"type of discovered.raw: {type(discovered[0].get('raw'))}")

        return discovered

    async def provision(self, discovery_record: Dict, owner_id: int, name: str) -> int:
        """Register a discovered device into the database and mark provisioned.

        discovery_record should include `ip`, `mac`, and `model` keys.
        Returns the new device id on success or -1 on failure.
        """
        ip = discovery_record.get("ip")
        mac = discovery_record.get("mac")
        model = discovery_record.get("model") or "unknown"
        device_id = self.db.add_device(
            name=name, model=model, owner_id=owner_id, ip=ip, mac=mac, provisioned=True
        )
        if device_id and device_id != -1:
            logger.info(
                f"Provisioned device {name} (id={device_id}) " f"for owner {owner_id}"
            )
            return device_id
        logger.error(f"Failed to provision device {name} for owner {owner_id}")
        return -1

    def get_device(self, device_id: int) -> Optional[dict]:
        return self.db.get_device_by_id(device_id)

    def _adapter_for_device(self, device: dict) -> DeviceAdapter:
        device_id = int(device["id"])
        if device_id in self._adapter_cache:
            return self._adapter_cache[device_id]
        ip = device.get("ip")
        if not ip:
            raise RuntimeError("Device has no IP address")
        adapter = KasaAdapter(ip)
        self._adapter_cache[device_id] = adapter
        return adapter

    async def turn_on(self, device_id: int) -> None:
        device = self.get_device(device_id)
        if not device:
            raise KeyError("Device not found")
        adapter = self._adapter_for_device(device)
        await adapter.turn_on()
        # update DB status
        now = datetime.utcnow().isoformat()
        self.db.update_device_status(device_id, "on", last_seen=now)

    async def turn_off(self, device_id: int) -> None:
        device = self.get_device(device_id)
        if not device:
            raise KeyError("Device not found")
        adapter = self._adapter_for_device(device)
        await adapter.turn_off()
        now = datetime.utcnow().isoformat()
        self.db.update_device_status(device_id, "off", last_seen=now)

    async def get_state(self, device_id: int) -> Dict:
        device = self.get_device(device_id)
        if not device:
            raise KeyError("Device not found")
        adapter = self._adapter_for_device(device)
        state = await adapter.get_state()
        now = datetime.utcnow().isoformat()
        self.db.update_device_status(
            device_id, "on" if state.get("is_on") else "off", last_seen=now
        )
        return state
