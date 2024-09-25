#!/usr/bin/python3

import sys
from dataclasses import dataclass, field
from typing import List
import traceback
import signal
import threading
from time import sleep

input_pipe_path: str = "/tmp/temp_info_pipe"
output_pipe_path: str = "/tmp/response_pipe"

info_line_terminator: str = chr(0)  # NULL character, /x00
info_line_delimiter: str = ';'

setpoint_value: float = 0.0
setpoint_upper_threshold: float = 1.0
setpoint_lower_threshold: float = -1.0

p_tuning: float = 0.8
i_tuning: float = 0.2
d_tuning: float = 0.2

freq: float = 5.0  # Hz
dt: float = 1.0 / freq

controller_enabled: bool = False

lock: threading.Lock = threading.Lock()


@dataclass
class Thermistor:
    sensor_value: float

    def __str__(self):
        return f"Temp: {self.sensor_value}"


@dataclass()
class PidController:
    integral: float = field(init=False, default=0.0)
    previous_error: float = field(init=False, default=0.0)

    p_tuning: float = 1.0
    i_tuning: float = 1.0
    d_tuning: float = 1.0

    def calc_output(self, measured_value: float, setpoint: float, dt: float) -> float:
        error_factor: float = setpoint - measured_value
        p_factor: float = error_factor
        self.integral = self.integral + error_factor * dt
        d_factor: float = (error_factor - self.previous_error) / dt

        result: float = (self.p_tuning * p_factor +
                         self.i_tuning * self.integral +
                         self.d_tuning * d_factor)
        self.previous_error = error_factor
        return result


def heater_values_str(h1: int, h2: int, h3: int, h4: int) -> str:
    return "{};{};{};{}\0".format(h1, h2, h3, h4)


def write_to_output_pipe(heater_values: List[int]):
    with open(output_pipe_path, 'w') as pipe:
        data = heater_values_str(heater_values[0],
                                 heater_values[1],
                                 heater_values[2],
                                 heater_values[3])
        pipe.write(data)


def turn_off_heaters():
    write_to_output_pipe([0, 0, 0, 0])


def bang_bang(in_thermister: List[Thermistor], setpoint: float,
              upper_threshold: float, lower_threshold: float) -> List[int]:
    result: List[int] = [0, 0, 0, 0]

    for i, t in enumerate(in_thermister):
        if t.sensor_value < lower_threshold or t.sensor_value < upper_threshold:
            result[i] = 1
        elif t.sensor_value > upper_threshold:
            result[i] = 0

    return result


def toggle_controller_menu():
    global controller_enabled
    enabled: bool = False
    with lock:
        controller_enabled = not controller_enabled
        enabled = controller_enabled
    if not enabled:
        turn_off_heaters()


def adjust_pid_ks_menu():
    pass


def adjust_setpoint_menu():
    pass


def adjust_frequency_menu():
    pass


def main_menu():
    want_to_quit: bool = False
    while not want_to_quit:
        valid_opt: bool = False
        while not valid_opt:
            msg: str = \
                "1- {0} controller\n" \
                "2- Adjust Kp, Kd, Ki\n" \
                "3- Adjust thermistors setpoint\n" \
                "4- Adjust frequency\n" \
                "5- Exit".format("Enable" if not controller_enabled else "Disable")

            opt: str = input(msg + "\n>")

            match opt:
                case "1":
                    toggle_controller_menu()
                case "2":
                    adjust_pid_ks_menu()
                case "3":
                    adjust_setpoint_menu()
                case "4":
                    adjust_frequency_menu()
                case "5":
                    turn_off_heaters()
                    want_to_quit = True
                case _:
                    input("Invalid Option. Press enter to contine...")
                    continue
            valid_opt = True


def processing():
    pid_controllers: List[PidController] = [
        PidController(p_tuning, i_tuning, d_tuning),
        PidController(p_tuning, i_tuning, d_tuning),
        PidController(p_tuning, i_tuning, d_tuning),
        PidController(p_tuning, i_tuning, d_tuning)
    ]

    clock: int = 0
    with open(input_pipe_path, 'r') as input_pipe:
        input_info_line: str = ""
        while True:
            input_data: str = input_pipe.read(1)

            if len(input_data) == 0:
                # pipe closed
                break

            # read from the input stream until info line break (at info_line_terminator)
            if input_data[0] == info_line_terminator:
                parts: List[str] = input_info_line.split(info_line_delimiter)
                if len(parts) != 5:
                    continue

                # parts format:
                # <clock_timestamp>;<therm1_sensor_temp>-<therm1_temp_diff>;...\0
                # notes:
                # line ends with NULL \0 character
                # thermistor sensor value and previous sensor value are also dash-separated,
                #  which means parsing the numbers is going to be a doozy
                #  e.g. "-10.00000--25" would be -10.0 current sensor value and -25 temp difference
                timestamp, t1, t2, t3, t4 = parts

                read_therm_values: List[str] = [t1, t2, t3, t4]
                thermistors: List[Thermistor] = []

                # split each thermistor values, and append to thermistors list
                for t in read_therm_values:
                    idx_sep: int = t.find('-')
                    temp_str: str = t[:idx_sep]

                    if idx_sep == 0:
                        # temp is a negative value because it's prefixed with minus sign
                        next_dash_idx = t.find('-', 1)
                        temp_str = t[:next_dash_idx]

                    temp: float = float(temp_str)
                    thermistors.append(Thermistor(temp))

                values: List[int] = [0, 0, 0, 0]

                use_bang_bang: bool = True
                if use_bang_bang:
                    values = bang_bang(thermistors, setpoint_value, setpoint_upper_threshold,
                                       setpoint_lower_threshold)
                else:
                    # use pids
                    values = pids(pid_controllers, thermistors)

                enabled: bool = False
                with lock:
                    enabled = controller_enabled

                if enabled:
                    write_to_output_pipe(values)

                input_info_line = ""  # clear info line
                clock += 1
            else:
                input_info_line += input_data


def pids(pid_controllers, thermistors) -> List[int]:
    result: List[int] = []
    for therm, pid in zip(thermistors, pid_controllers):
        pid_out = pid.calc_output(therm.sensor_value, setpoint_value, dt)
        result.append(int(pid_out))
    return result


def handler(signum: int, frame):
    print("Pressed Ctrl-C. Turning off heaters before exiting")
    turn_off_heaters()
    exit()


def main():
    process_thread: threading.Thread = threading.Thread(target=processing, daemon=True)
    process_thread.start()
    main_menu()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, handler)
    try:
        main()
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        print(e)
        # fallback when an unhandled exception is thrown
        # set all heater values to zero
        turn_off_heaters()
        exit()
