from dataclasses import dataclass
from typing import Optional

@dataclass
class Spec:
    type_name: str
    b1: Optional[float]=None
    b2: Optional[float]=None
    length: Optional[float]=None
    x: Optional[float]=None
    y: Optional[float]=None

    def width_text(self):
        if self.b1 is None:
            return ""
        if self.b2 is not None and abs(self.b1-self.b2)>0.001:
            return f"{self.b1:.3f}~{self.b2:.3f}"
        return f"{self.b1:.3f}"

    def size_text(self):
        if self.length is None:
            return self.width_text()
        return f"{self.width_text()} × {self.length:.3f}"
