from dataclasses import dataclass, field


@dataclass()
class Controller:
    setpoint: float = field(init=True, default=0.0)

    def process(self, measured_value: float) -> float:
        pass
