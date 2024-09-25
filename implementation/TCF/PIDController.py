from dataclasses import dataclass, field

from Controller import Controller


@dataclass()
class PIDController(Controller):
    Kp: float = 0.0
    Ki: float = 0.0
    Kd: float = 0.0
    freq: float = 5.0  # Hz

    integral: float = field(init=False, default=0.0)
    previous_error: float = field(init=False, default=0.0)

    def process(self, measured_value: float) -> float:
        dt: float = 1.0 / self.freq

        error_factor: float = self.setpoint - measured_value
        p_factor: float = error_factor
        self.integral = self.integral + error_factor * dt
        d_factor: float = (error_factor - self.previous_error) / dt

        result: float = (self.Kp * p_factor +
                         self.Ki * self.integral +
                         self.Kd * d_factor)
        self.previous_error = error_factor
        return result
