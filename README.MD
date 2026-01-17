## Quick Start
1. Create a virtual environment (only tested with `python 3.10`)
1. Install dependencies from `requirements.txt` in the virtual env
2. Provision your TP-Link HS100 Smart Plug using [python-kasa instructions here](https://python-kasa.readthedocs.io/en/latest/cli.html#provisioning)
3. Create `config.json` in `PROJECT_ROOT/.ignore/`
4. Enter the below contents in `config.json`:
   ```
   {
        "hs100": {
            "mac": "XX:XX:XX:XX:XX:XX",
            "software": "1.2.6 Build 200727 Rel.120528",
            "make": "TP-Link",
            "model": "hs100",
            "network": {
                "broadcast": "YYY.YYY.YYY.255",
                "uncertain_host_ip": "192.168.1.232"
            }
        }
   }
   ```
    - `mac` should be the MAC address returned in CLI after provisioning
    - `broadcast` is the broadcast IP of the network you're running the hosting machine on
    - `uncertain_host_ip` is the direct IP address of the smart plug that you can optionally specify if you know what it is (should be printed when `kasa` discovers your HS100 device)
5. Ensure your machine and the HS100 are on the same network/SSID (**Note: HS100 only works on 2.4GHz**)
6. Run `src/app.py` : `$ python src/app.py`
7. Whatever local IP your hosting machine is, access the management portal from any other device on the same network (e.g., other computer, mobile device) at `http://MACHINE_IP:3000/`