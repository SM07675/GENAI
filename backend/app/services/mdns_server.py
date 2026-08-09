"""mDNS Zeroconf Server for Android Genie Companion discovery.
Advertises _genie._tcp.local on the local Wi-Fi network so Android devices
can automatically discover the PC without typing IP addresses.
"""

import socket
import logging
from typing import Optional

logger = logging.getLogger("genie.mdns")

_zeroconf_instance = None
_service_info = None

def get_local_ip() -> str:
    """Get primary local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually establish a connection
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def start_mdns_service(port: int = 8000, name: str = "Genie PC Hub") -> bool:
    """Register _genie._tcp.local service on local network."""
    global _zeroconf_instance, _service_info
    try:
        from zeroconf import Zeroconf, ServiceInfo
    except ImportError:
        logger.info("zeroconf package not installed; mDNS broadcast disabled (fallback to manual IP / QR pairing).")
        return False

    try:
        local_ip = get_local_ip()
        service_type = "_genie._tcp.local."
        service_name = f"{name}.{service_type}"

        _service_info = ServiceInfo(
            type_=service_type,
            name=service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={
                "version": "1.0",
                "device": "pc_hub",
                "name": name,
            },
            server=f"{socket.gethostname()}.local."
        )

        _zeroconf_instance = Zeroconf()
        _zeroconf_instance.register_service(_service_info)
        logger.info(f"mDNS service '{service_name}' registered at {local_ip}:{port}")
        return True
    except Exception as e:
        logger.warning(f"Failed to start mDNS zeroconf service: {e}")
        return False

def stop_mdns_service():
    """Unregister mDNS service on shutdown."""
    global _zeroconf_instance, _service_info
    if _zeroconf_instance and _service_info:
        try:
            _zeroconf_instance.unregister_service(_service_info)
            _zeroconf_instance.close()
            logger.info("mDNS service unregistered.")
        except Exception as e:
            logger.warning(f"Error unregistering mDNS service: {e}")
        _zeroconf_instance = None
        _service_info = None
