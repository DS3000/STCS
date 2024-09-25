#!/usr/bin/python3

import sys
from dataclasses import dataclass, field
from pickle import Pickler
from typing import List
import traceback
import signal
import threading
from time import sleep
import os

INPUT_PIPE_PATH: str = "/tmp/temp_info_pipe"
OUTPUT_PIPE_PATH: str = "/tmp/response_pipe"

INFO_LINE_TERMINATOR: str = chr(0)  # NULL character, /x00
INFO_LINE_DELIMITER: str = ';'  # delimiter between values in a line

SETPOINT_MAX_VALUE: float = 20.0
SETPOINT_MIN_VALUE: float = -20.0
setpoint_value: float = 0.0
frequency: float = 5.0  # Hz

thermistors_setpoints: List[float] = [0.0, 0.0, 0.0, 0.0]

pid_Kp: float = 0.0
pid_Ki: float = 0.0
pid_Kd: float = 0.0

controller_enabled: bool = False
lock: threading.Lock = threading.Lock()


@dataclass()
class Controller:
    setpoint: float = 0.0

    def process(self, measured_value: float) -> float:
        pass


@dataclass()
class BangBang(Controller):
    def process(self, measured_value: float) -> float:
        if measured_value > self.setpoint:
            return 0.0
        return 1.0


@dataclass()
class PID(Controller):
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


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


def heater_values_str(h1: int, h2: int, h3: int, h4: int) -> str:
    fmt: str = "{};{};{};{}\0"
    return fmt.format(h1, h2, h3, h4)


def write_to_output_pipe(heater_values: List[int]):
    with open(OUTPUT_PIPE_PATH, 'w') as pipe:
        data = heater_values_str(heater_values[0],
                                 heater_values[1],
                                 heater_values[2],
                                 heater_values[3])
        pipe.write(data)


def turn_off_heaters():
    write_to_output_pipe([0, 0, 0, 0])


def bang_bang(in_thermister: List[Thermistor], setpoint: float) -> List[int]:
    result: List[int] = [0, 0, 0, 0]

    for i, t in enumerate(in_thermister):
        result[i] = 0
        if t.sensor_value < setpoint:
            result[i] = 1

    return result


def toggle_controller_menu():
    global controller_enabled
    with lock:
        controller_enabled = not controller_enabled
        if not controller_enabled:
            turn_off_heaters()


def set_pid_ks(kp: float, ki: float, kd: float, controllers: List[PidController]):
    with lock:
        for controller in controllers:
            controller.p_tuning = kp
            controller.i_tuning = ki
            controller.d_tuning = kd


def adjust_pid_ks_menu():
    msg: str = \
        "Enter three space-separated values (<Kp> <Ki> <Kd>), or empty string to go back\n"

    while True:
        clear_console()
        user_input = input(msg)

        if len(user_input) == 0:
            break

        parts = user_input.split(' ')
        if len(parts) != 3:
            input("Did not enter three comma-separated values. Press enter to continue.")
            continue

        kp: float = 0.0
        ki: float = 0.0
        kp: float = 0.0

        try:
            kp = float(parts[0])
            ki = float(parts[1])
            kd = float(parts[2])
        except ValueError as _:
            input(f"Could not parse entered line as 3 floats")
            continue

        set_pid_ks(kp, ki, kd)
        break


def adjust_thermistors_setpoint_menu():
    msg: str = \
        "1- Adjust setpoint for all heaters\n" \
        "2- Adjust setpoint for specific heater\n" \
        "3- go back\n"

    opt: str = prompt_user_until_valid_input(msg, ["1", "2", "3"])
    match opt:
        case "1":
            val_str: str = input("Adjust setpoint for all heaters to value:")
            val_num: int = int(val_str)

        case "2":
            pass
        case "3":
            pass


def adjust_controller_frequency_menu():
    global frequency
    msg: str = "Enter the new controller frequency (in Hz), or empty string to go back"

    freq: int = 0
    while True:
        clear_console()
        user_input = input(msg + "\n>")
        if user_input == "":
            break
        try:
            freq = int(user_input)
        except ValueError as _:
            input(f"Failed to convert {user_input} to integer. Press enter to continue...")
            continue

        if freq <= 0:
            input(f"{freq} is an invalid frequency. Must be non-zero positive number. Press enter to continue.")
            continue

        with lock:
            frequency = freq
        break


def prompt_user_until_valid_input(prompt_message: str, valid_options: List[str]) -> str:
    opt: str = ""
    while True:
        clear_console()
        opt = input(prompt_message + "\n>")
        if opt not in valid_options:
            input("Invalid option. Press enter to contine...")
            continue
        break
    return opt


def main_menu():
    want_to_quit: bool = False
    while not want_to_quit:
        with lock:
            msg: str = \
                "1- {0} controller\n" \
                "2- Adjust Kp, Kd, Ki\n" \
                "3- Adjust thermistors setpoint\n" \
                "4- Adjust controller frequency\n" \
                "5- Exit".format("Enable" if not controller_enabled else "Disable")
        opt: str = prompt_user_until_valid_input(msg, ["1", "2", "3", "4", "5"])
        match opt:
            case "1":
                toggle_controller_menu()
            case "2":
                adjust_pid_ks_menu()
            case "3":
                adjust_thermistors_setpoint_menu()
            case "4":
                adjust_controller_frequency_menu()
            case "5":
                turn_off_heaters()
                want_to_quit = True


def processing():
    # initialize controlers
    pid_controllers: List[PidController] = [
        PidController(pid_Kp, pid_Ki, pid_Kd),
        PidController(pid_Kp, pid_Ki, pid_Kd),
        PidController(pid_Kp, pid_Ki, pid_Kd),
        PidController(pid_Kp, pid_Ki, pid_Kd)
    ]

    clock: int = 0
    with open(INPUT_PIPE_PATH, 'r') as input_pipe:
        input_info_line: str = ""
        while True:
            input_data: str = input_pipe.read(1)

            if len(input_data) == 0:
                # pipe closed
                break

            # read from the input stream until info line break (at info_line_terminator)
            if input_data[0] == INFO_LINE_TERMINATOR:
                parts: List[str] = input_info_line.split(INFO_LINE_DELIMITER)
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
                    values = bang_bang(thermistors, setpoint_value)
                else:
                    # use pids
                    dt: float = 1.0 / frequency
                    values = pids(pid_controllers, thermistors, dt)

                with lock:
                    if controller_enabled:
                        write_to_output_pipe(values)

                input_info_line = ""  # clear info line
                clock += 1
            else:
                input_info_line += input_data


def pids(pid_controllers, thermistors, dt: float) -> List[int]:
    result: List[int] = []
    for therm, pid in zip(thermistors, pid_controllers):
        pid_out = pid.calc_output(therm.sensor_value, setpoint_value, dt)
        result.append(int(pid_out))
    return result


def handler(signum: int, frame):
    print("Pressed Ctrl-C. Turning off all heaters before terminating")
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
        print("Turning off all heaters before terminating")
        turn_off_heaters()
        exit()
