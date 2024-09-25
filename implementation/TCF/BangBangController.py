from dataclasses import dataclass

from Controller import Controller


@dataclass()
class BangBangController(Controller):
    def process(self, measured_value: float) -> float:
        if measured_value > self.setpoint:
            return 0.0
        return 1.0
