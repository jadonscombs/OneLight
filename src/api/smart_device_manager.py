"""
Project OneLight.

Scaffolding and implementation for interacting with TP-Link HS100 Smart Plug.

Follow these guides (in preferred order):
1. https://github.com/python-kasa/python-kasa?tab=readme-ov-file (larger support)
2. https://github.com/jkbenaim/hs100 (Linux-only)

Provisioning a new smart plug device:
https://python-kasa.readthedocs.io/en/latest/cli.html#provisioning

$ kasa --host 192.168.0.1 wifi join "YOUR_SSID"

When prompted for "Keytype," enter "3" (no quotes) for WPA2-PSK


Once provisioned, you can discover HS100 using the command:
$ kasa --target XXX.XXX.XXX.255 --type plug discover

    (just replace "XXX.XXX.XXX" with the network portion that your development
    device is on. often it is "192.168.0" or "192.168.1")
"""

import asyncio
from kasa import Device, DeviceConfig, Discover
import subprocess
import json
import logging
import pathlib
import pprint
import traceback
from typing import Optional

logger = logging.getLogger("onelight-app")

DEFAULT_CONFIG_PATH = pathlib.Path(__file__).parents[2] / ".ignore" / "config.json"
DEFAULT_BROADCAST = "255.255.255.255"
NULL_IP = "X.X.X.X"
HS100 = "hs100"
UNKNOWN = "UNKNOWN"
ON = "ON"
OFF = "OFF"

CODE_200 = "200"
CODE_400 = "400"

# Lightweight device cache
# - a device type (e.g., "hs100") can have 2+ devices listed by {ip:config}
device_cache = {
    HS100: {
    }
}


async def get_hs100_device() -> Optional[Device]:
    """
    Returns only the first HS100 device accessible.

    For now, this is not scalable (2+ HS100s) and will need expansion later.
    """

    # Check device cache
    if len(device_cache[HS100]) > 0:
        try:
            first_hs100_ip = list(device_cache[HS100].keys())[0]
            device = await Device.connect(host=first_hs100_ip)
            if isinstance(device, Device):
                return device
        except Exception:
            logger.exception(
                "Exception attempting to connect to cached HS100 "
                f"device with IP {first_hs100_ip}"
            )

    # Check for device via broadcast
    ip_broadcast_target = get_hs100_broadcast_ip()
    logger.info(f"Fallback: Search via broadcast IP {ip_broadcast_target}")

    hs100_device_candidates = await Discover.discover(
        target=ip_broadcast_target,
        port=9999
    )
    if len(hs100_device_candidates) > 0:
        logger.info(f"Found {len(hs100_device_candidates)} device(s):")
        for ip, device in hs100_device_candidates.items():
            conf_ = pprint.pformat(
                device.config.to_dict(),
                indent=4,
                sort_dicts=False
            )
            logger.info(f"config:\n{conf_}")
            if is_hs100_device(device):
                update_device_cache(device, is_hs100=True)
                return device

    # Check for device via hard-set endpoint IP
    try_host_ip = get_hs100_uncertain_ip()
    logger.info(f"Fallback: Using host IP {try_host_ip}")
    if try_host_ip is not None:
        device = await Device.connect(host=try_host_ip)
        if is_hs100_device(device):
            conf_ = pprint.pformat(
                device.config.to_dict(),
                indent=4,
                sort_dicts=False
            )
            logger.info(
                f"config:\n{conf_}"
            )
            update_device_cache(device, is_hs100=True)
            return device

    return None


async def ping_hs100_device() -> str:
    """
    Return 200 if HS100 device reachable.

    Otherwise, return 400 (optionally with reason).
    """
    device: Optional[Device] = await get_hs100_device()
    return CODE_200 if device is not None else CODE_400


async def turn_on_hs100(device: Optional[Device] = None):
    if device is None:
        device = await get_hs100_device()
    if isinstance(device, Device):
        await device.turn_on()


async def turn_off_hs100(device: Optional[Device] = None):
    if device is None:
        device = await get_hs100_device()
    if isinstance(device, Device):
        await device.turn_off()


async def get_hs100_on_state(device: Optional[Device] = None):
    if device is None:
        device = await get_hs100_device()
    if isinstance(device, Device):
        state = "ON" if device.is_on else "OFF"
    else:
        state = "UNKNOWN STATE"
    return f"{HS100}: {state}"


def load_config(json_config_path: pathlib.Path = DEFAULT_CONFIG_PATH):
    path = pathlib.Path(json_config_path)
    with open(path, 'r') as config:
        try:
            return json.load(config)
        except Exception:
            logger.exception("Exception in load_config()...")
    logger.warning("Returning empty JSON config...")
    return {}


def get_hs100_broadcast_ip():
    return load_config().get("hs100", {}).get("network", {}).get("broadcast", DEFAULT_BROADCAST)


def get_hs100_uncertain_ip():
    return load_config().get("hs100", {}).get("network", {}).get("uncertain_host_ip", None)


def get_hs100_mac():
    return load_config().get("hs100", {}).get("mac", "XX:XX:XX:XX:XX:XX")


def is_hs100_device(device: Device):
    """
    Return True if <Device> is confirmed to be an HS100.

    Warning: Currently hard-set on using MAC address to determine this.
    """
    return device.device_id == get_hs100_mac()


def update_device_cache(device: Device, is_hs100: bool = False):
    model = HS100 if is_hs100 else UNKNOWN
    device_cache[model][device.host] = device.config.to_dict()
    logger.debug(f"Updated device cache - is_hs100: {is_hs100}")
