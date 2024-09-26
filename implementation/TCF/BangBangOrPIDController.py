from dataclasses import dataclass, field

from Controller import Controller
from BangBangController import BangBangController
from PIDController import PIDController

@dataclass
class BangBangOrPIDController:
    bangBang: BangBangController = field(default=None)
    pid: PIDController = field(default=None)
