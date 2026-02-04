from abc import ABC, abstractmethod
from dataclasses import dataclass
import requests
from typing import Optional

@dataclass
class ProxyStats:
    total_traffic: float
    traffic_used: float
    traffic_left: float
    used_threads: int

class ProxyProviderProtocol(ABC):
    @abstractmethod
    def get_status(self, username: str, password: str) -> Optional[ProxyStats]:
        pass

class DataimpulseProvider(ProxyProviderProtocol):
    BASE_URL = "https://gw.dataimpulse.com:777/api/stats"

    def get_status(self, username: str, password: str) -> Optional[ProxyStats]:
        try:
            # Autenticación básica con username y password
            response = requests.get(
                self.BASE_URL,
                auth=(username, password),
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            return ProxyStats(
                total_traffic=float(data.get("total_traffic", 0.0)),
                traffic_used=float(data.get("traffic_used", 0.0)),
                traffic_left=float(data.get("traffic_left", 0.0)),
                used_threads=int(data.get("used_threads", 0))
            )
        except requests.RequestException as e:
            print(f"Error fetching Dataimpulse stats: {e}")
            raise e
        except Exception as e:
            print(f"Error parsing Dataimpulse stats: {e}")
            raise e
