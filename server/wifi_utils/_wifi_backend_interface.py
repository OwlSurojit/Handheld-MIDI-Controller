from abc import ABC, abstractmethod

class _WiFiBackendInterface(ABC):
    """Contract implemented by all Wi-Fi backend variants."""

    def __init__(self, system: str):
        self.system = system

    def is_authorized(self) -> bool:
        return True
    
    @abstractmethod
    def current_ssid(self) -> str:
        pass

    @abstractmethod
    def scan_ssids(self) -> set[str]:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass

    @abstractmethod
    def connect(self, ssid: str, password: str | None = None) -> bool:
        pass

    @abstractmethod
    def delete_temp_profiles(self) -> bool:
        pass

    def system_is(self, name: str) -> bool:
        return self.system == name.lower()
