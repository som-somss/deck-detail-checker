from dataclasses import dataclass
from typing import Optional

@dataclass
class DeckSpec:
    type_name: str
    b1: Optional[float]
    b2: Optional[float]
    length: Optional[float]
    deck_qty: Optional[int] = None

    def display(self):
        if self.b1 is None or self.length is None:
            return ""
        if self.b2 is not None and abs(self.b2-self.b1) > 1e-9:
            return f"{self.b1:.3f}~{self.b2:.3f} × {self.length:.3f}"
        return f"{self.b1:.3f} × {self.length:.3f}"
