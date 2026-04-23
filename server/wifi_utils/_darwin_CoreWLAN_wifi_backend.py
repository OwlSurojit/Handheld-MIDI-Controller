import time
from CoreWLAN import CWWiFiClient
from CoreLocation import (
    CLLocationManager,
    kCLAuthorizationStatusNotDetermined,
    kCLAuthorizationStatusAuthorizedAlways,
    kCLAuthorizationStatusAuthorizedWhenInUse
)
from server.wifi_utils._wifi_backend_interface import _WiFiBackendInterface

class _DarwinCoreWLANWiFiBackend(_WiFiBackendInterface):
    
    def __init__(self):
        super().__init__("darwin")
        self._iface = None
        self._location_manager = None
        self._networks = []

    def is_authorized(self) -> bool:
        if self._location_manager is None:
            self._location_manager = CLLocationManager.alloc().init()
            self._location_manager.requestWhenInUseAuthorization()
            while self._location_manager.authorizationStatus() == kCLAuthorizationStatusNotDetermined:
                time.sleep(0.5)
        return self._location_manager.authorizationStatus() in [kCLAuthorizationStatusAuthorizedWhenInUse, kCLAuthorizationStatusAuthorizedAlways]

    @property
    def iface(self):
        if self._iface is None:
            if not self.is_authorized():
                print("WARNING: Location access is not enabled. The app will not be able to read SSIDs.")
            self._iface = CWWiFiClient.sharedWiFiClient().interface()
        return self._iface

    def current_ssid(self) -> str:
        return self.iface.ssid()

    def scan_ssids(self) -> set[str]:
        networks, _ = self.iface.scanForNetworksWithName_error_(None, None)
        self._networks = list(networks)
        return set(n.ssid() for n in networks if n.ssid())

    def disconnect(self) -> bool:
        try:
            self.iface.disassociate()
            return True
        except:
            return False

    """
    Unfortunately, with CoreWLAN it is not possible to connect using system stored credentials.
    The password always needs to be supplied.    
    """
    def connect(self, ssid: str, password: str | None = None) -> bool:
        for net in self._networks:
            if net.ssid() == ssid:
                network = net
                break
        else:
            networks, _ = self.iface.scanForNetworksWithName_error_(ssid, None)
            if not networks:
                return False
            network = list(networks)[0] # order does not matter since connecting to any network with a given SSID will select the strongest one anyways
        self.disconnect()
        success, _ = self.iface.associateToNetwork_password_error_(network, password if password else None, None)
        if success:
            time.sleep(1) # Unfortunately this is necessary, as there is no way to detect when the connection succeeded (iface ssid is set immediately)
        return success
        

    def delete_temp_profiles(self) -> bool:
        return True