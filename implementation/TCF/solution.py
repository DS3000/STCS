#!/usr/bin/python3
from typing import List
import traceback
import signal
import threading
import os

from Thermistor import Thermistor
from Controller import Controller
from BangBangController import BangBangController
from PIDController import PIDController

INPUT_PIPE_PATH: str = "/tmp/temp_info_pipe"
OUTPUT_PIPE_PATH: str = "/tmp/response_pipe"

INFO_LINE_TERMINATOR: str = chr(0)  # NULL character, /x00
INFO_LINE_DELIMITER: str = ';'  # delimiter between values in a line

SETPOINT_MAX_VALUE: float = 20.0
SETPOINT_MIN_VALUE: float = -20.0
INITIAL_SETPOINT_VALUE: float = 0.0
INITIAL_FREQUENCY: float = 5.0  # Hz

INITIAL_PID_KP: float = 0.0
INITIAL_PID_KI: float = 0.0
INITIAL_PID_KD: float = 0.0

controllers_enabled: bool = False
lock: threading.Lock = threading.Lock()

controllers: List[BangBangController | PIDController] = [
    BangBangController(INITIAL_SETPOINT_VALUE),
    BangBangController(INITIAL_SETPOINT_VALUE),
    BangBangController(INITIAL_SETPOINT_VALUE),
    BangBangController(INITIAL_SETPOINT_VALUE),

    # PIDController(INITIAL_SETPOINT_VALUE, INITIAL_PID_KP, INITIAL_PID_KI, INITIAL_PID_KD, INITIAL_FREQUENCY),
    # PIDController(INITIAL_SETPOINT_VALUE, INITIAL_PID_KP, INITIAL_PID_KI, INITIAL_PID_KD, INITIAL_FREQUENCY),
    # PIDController(INITIAL_SETPOINT_VALUE, INITIAL_PID_KP, INITIAL_PID_KI, INITIAL_PID_KD, INITIAL_FREQUENCY),
    # PIDController(INITIAL_SETPOINT_VALUE, INITIAL_PID_KP, INITIAL_PID_KI, INITIAL_PID_KD, INITIAL_FREQUENCY),
]


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


def toggle_controller_menu():
    global controllers_enabled
    with lock:
        controllers_enabled = not controllers_enabled
        if not controllers_enabled:
            turn_off_heaters()


def set_pid_ks(kp: float, ki: float, kd: float):
    global controllers

    for controller in controllers:
        controller.Kp = kp
        controller.Ki = ki
        controller.Kd = kd


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

        with lock:
            set_pid_ks(kp, ki, kd)
        break


def adjust_thermistors_setpoint_menu():
    # TODO implement all options. check the diagram
    msg: str = \
        "1- Adjust setpoint for all heaters\n" \
        "2- Adjust setpoint for specific heater\n" \
        "3- go back\n"

    while True:
        clear_console()
        opt: str = prompt_user_until_valid_input(msg, ["1", "2", "3"])
        match opt:
            case "1":
                val_str: str = input("Adjust setpoint for all heaters to value\n>")
                try:
                    val_num: float = float(val_str)
                except ValueError:
                    input(f"Failed to convert {val_str} to float")
                    continue

                if not (SETPOINT_MIN_VALUE <= val_num <= SETPOINT_MAX_VALUE):
                    input(f"Setpoint must be between {SETPOINT_MIN_VALUE} and {SETPOINT_MAX_VALUE}")
                    continue

                for controller in controllers:
                    controller.setpoint = val_num

            case "2":
                val_str: str = input("Enter a space-separated line (<controller> <setpoint>)\n>")

            case "3":
                pass

        break


def adjust_controller_frequency_menu():
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

        if all(isinstance(x, PIDController) for x in controllers):
            with lock:
                for controller in controllers:
                    controller.freq = freq
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
                "5- Exit".format("Enable" if not controllers_enabled else "Disable")
        opt: str = prompt_user_until_valid_input(msg, ["1", "2", "3", "4", "5"])
        match opt:
            case "1":
                toggle_controller_menu()
            case "2":
                if any(not isinstance(x, PIDController) for x in controllers):
                    input("Controller is not PID. Press enter to continue.")
                    continue

                adjust_pid_ks_menu()
            case "3":
                adjust_thermistors_setpoint_menu()
            case "4":
                adjust_controller_frequency_menu()
            case "5":
                turn_off_heaters()
                want_to_quit = True


def processing():
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

                values: List[int] = []

                for therm, controller in zip(thermistors, controllers):
                    o: float = controller.process(therm.sensor_value)
                    values.append(int(o))

                with lock:
                    if controllers_enabled:
                        write_to_output_pipe(values)

                input_info_line = ""  # clear info line
                clock += 1
            else:
                input_info_line += input_data


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
