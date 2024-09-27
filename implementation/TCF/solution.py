#!/usr/bin/python3

import os
import threading
import signal
import traceback
import datetime
from typing import List
from enum import Enum

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

MIN_FREQUENCY: float = 1.0
MAX_FREQUENCY: float = 5.0
INITIAL_FREQUENCY: float = 5.0  # Hz
assert (MIN_FREQUENCY <= INITIAL_FREQUENCY <= MAX_FREQUENCY)

INITIAL_PID_KP: float = 1.0
INITIAL_PID_KI: float = 1.0
INITIAL_PID_KD: float = 1.0

g_frequency: float = INITIAL_FREQUENCY
g_Kp: float = INITIAL_PID_KP
g_Ki: float = INITIAL_PID_KI
g_Kd: float = INITIAL_PID_KD

g_controllers_enabled: bool = False
g_lock: threading.Lock = threading.Lock()


class ControllerMode(Enum):
    BangBang = 1
    PID = 2


g_controller_mode: ControllerMode = ControllerMode.BangBang
g_controllers: List[BangBangController | PIDController] = []

match g_controller_mode:
    case ControllerMode.BangBang:
        for _ in range(4):
            g_controllers.append(
                BangBangController(INITIAL_SETPOINT_VALUE)
            )
    case ControllerMode.PID:
        for _ in range(4):
            g_controllers.append(
                PIDController(INITIAL_SETPOINT_VALUE, INITIAL_PID_KP, INITIAL_PID_KI, INITIAL_PID_KD, INITIAL_FREQUENCY)
            )


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


def set_pid_ks(kp: float, ki: float, kd: float):
    global g_controllers, g_Kp, g_Ki, g_Kd

    for controller in g_controllers:
        controller.Kp = kp
        controller.Ki = ki
        controller.Kd = kd
    g_Kp = kp
    g_Ki = ki
    g_Kd = kd


def adjust_pid_ks_menu():
    with g_lock:
        msg: str = f"Current Kp {g_Kp}, Ki {g_Ki} Kd {g_Kd}\n\n" + \
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

        try:
            kp = float(parts[0])
            ki = float(parts[1])
            kd = float(parts[2])
        except ValueError as _:
            input(f"Could not parse entered line as 3 floats")
            continue

        with g_lock:
            set_pid_ks(kp, ki, kd)
        break


def set_controllers_setpoint(ctls: List[Controller], setpoint: float):
    if not (SETPOINT_MIN_VALUE <= setpoint <= SETPOINT_MAX_VALUE):
        raise ValueError(f"Setpoints must be between {SETPOINT_MIN_VALUE} and {SETPOINT_MAX_VALUE}.")

    for c in ctls:
        c.setpoint = setpoint


def adjust_controllers_setpoint_menu():
    with g_lock:
        setpoints_str = "\n".join(f"Controller {i + 1} setpoint {x.setpoint}" for i, x in enumerate(g_controllers))
        msg: str = setpoints_str + "\n\n" \
                                   "1- Adjust setpoint for all controllers\n" \
                                   "2- Adjust setpoint for specific controller\n" \
                                   "3- go back\n"

    while True:
        clear_console()
        opt: str = prompt_user_until_valid_input(msg, ["1", "2", "3"])
        match opt:
            case "1":
                val_str: str = input("Adjust setpoint for all controllers to value\n>")
                try:
                    val_num: float = float(val_str)
                except ValueError:
                    input(f"Failed to convert {val_str} to float")
                    continue

                try:
                    with g_lock:
                        set_controllers_setpoint(g_controllers, val_num)
                        pass
                except ValueError as e:
                    input(e)
                    continue

            case "2":
                val_str: str = input("Enter a space-separated line (<controller> <setpoint>)\n>")
                parts = val_str.strip().split(' ')
                if len(parts) != 2:
                    input("Did not enter two line-separated values. Press enter to continue.")
                    continue

                controller_idx, setpoint = parts

                try:
                    controller_idx: int = int(controller_idx)
                except ValueError:
                    input(f"Failed to convert {controller_idx} to integer. Press enter to continue.")
                    continue

                if controller_idx < 1 or controller_idx > 4:
                    input(f"Invalid controller index. Must be value between 1 and 4")
                    continue

                try:
                    setpoint: float = float(setpoint)
                except ValueError:
                    input(f"Failed to convert {setpoint} to float. Press enter to continue.")
                    continue

                try:
                    with g_lock:
                        ctls = [g_controllers[controller_idx - 1]]
                        set_controllers_setpoint(ctls, setpoint)
                except ValueError as e:
                    input(e)
                    continue
            case "3":
                pass

        break


def adjust_controller_frequency_menu():
    global g_frequency
    with (g_lock):
        msg: str = f"Current frequency: {g_frequency} hz\n\n" + \
                   f"Enter the new controller frequency between {MIN_FREQUENCY} Hz and {MAX_FREQUENCY} Hz, or empty string to go back"

    while True:
        clear_console()
        user_input = input(msg + "\n>")
        if user_input == "":
            break
        try:
            freq = float(user_input)
        except ValueError:
            input(f"Failed to convert {user_input} to float. Press enter to continue.")
            continue

        if not (MIN_FREQUENCY <= freq <= MAX_FREQUENCY):
            input(
                f"{freq} is an invalid frequency. Must be between {MIN_FREQUENCY} Hz and {MAX_FREQUENCY} Hz. Press enter to continue.")
            continue

        with g_lock:
            if all(isinstance(x, PIDController) for x in g_controllers):
                for controller in g_controllers:
                    controller.freq = freq
            g_frequency = freq
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


def flush_old_data_in_pipe(pipe_path: str):
    fifo_fd = os.open(pipe_path, os.O_RDONLY | os.O_NONBLOCK)

    try:
        while True:
            try:
                # Read data in non-blocking mode
                old_data = os.read(fifo_fd, 4096)  # Read chunks of old data (size can be adjusted)
                if not old_data:
                    break  # Exit loop if no data is present
            except BlockingIOError:
                break  # No more old data, pipe is cleared
    finally:
        os.close(fifo_fd)


def main_menu():
    global g_controllers_enabled, g_controller_mode, g_controllers

    want_to_quit: bool = False
    while not want_to_quit:
        with g_lock:
            msg: str = \
                "1- {0} controller\n".format("Enable" if not g_controllers_enabled else "Disable") + \
                "2- Adjust Kp, Kd, Ki\n" \
                "3- Adjust controller setpoint\n" \
                "4- Adjust controller frequency\n" \
                "5- Set controller mode to {0}\n".format(
                    "PID" if g_controller_mode == ControllerMode.BangBang else "BangBang") + \
                "6- Exit"
        opt: str = prompt_user_until_valid_input(msg, ["1", "2", "3", "4", "5", "6"])
        match opt:
            case "1":
                with g_lock:
                    g_controllers_enabled = not g_controllers_enabled
                    if not g_controllers_enabled:
                        turn_off_heaters()
                    else:
                        flush_old_data_in_pipe(INPUT_PIPE_PATH)
            case "2":
                with g_lock:
                    if any(not isinstance(x, PIDController) for x in g_controllers):
                        input("Controller is not PID. Press enter to continue.")
                        continue

                adjust_pid_ks_menu()
            case "3":
                adjust_controllers_setpoint_menu()
            case "4":
                adjust_controller_frequency_menu()
            case "5":
                with g_lock:
                    controllers: List[Controller] = [x for x in g_controllers]
                    g_controllers.clear()

                    if g_controller_mode == ControllerMode.BangBang:
                        g_controller_mode = ControllerMode.PID

                        for controller in controllers:
                            g_controllers.append(
                                PIDController(controller.setpoint, g_Kp, g_Ki, g_Kd, g_frequency),
                            )

                    elif g_controller_mode == ControllerMode.PID:
                        g_controller_mode = ControllerMode.BangBang

                        for controller in controllers:
                            g_controllers.append(
                                BangBangController(controller.setpoint),
                            )

            case "6":
                turn_off_heaters()
                want_to_quit = True


def processing():
    while True:
        with g_lock:
            if not g_controllers_enabled:
                # skip reading from input pipe and writing to output pipe
                continue

        prev_time = datetime.datetime.now()
        time_acc_usec: int = 0
        with g_lock:
            target_dt_microsecs = int(1.0 / g_frequency * 1_000_000)

        iteration: int = 0

        with open(INPUT_PIPE_PATH, 'r') as input_pipe:
            while True:
                curr_time = datetime.datetime.now()
                dt = curr_time - prev_time
                time_acc_usec += dt.microseconds
                prev_time = curr_time

                if time_acc_usec < target_dt_microsecs:
                    continue

                iteration += 1
                input_info_line_buffer: str = ""
                while True:
                    input_data: str = input_pipe.read(1)

                    if len(input_data) == 0:
                        # pipe closed
                        break

                    # read into input_info_line until info line break
                    if input_data[0] != INFO_LINE_TERMINATOR:
                        input_info_line_buffer += input_data
                        continue

                    parts: List[str] = input_info_line_buffer.split(INFO_LINE_DELIMITER)
                    assert (len(parts) == 5)

                    # raw line data:
                    # <clock_int>;<thermistor1_temp>-<heater1_power>;...;<thermistor4_temp>-<heater4_power>;
                    # e.g. 1234;-10.00000-25;-10.00000-25;-10.00000-25;-10.00000-25"
                    timestamp, t1, t2, t3, t4 = parts

                    read_thermistor_values: List[str] = [t1, t2, t3, t4]
                    thermistors: List[Thermistor] = []

                    # split each thermistor info values, and append to thermistors list
                    for t in read_thermistor_values:
                        idx_sep: int = t.find('-')
                        therm_temp_str: str = t[:idx_sep]

                        if idx_sep == 0:
                            # temp is a negative value because it's prefixed with minus sign
                            next_dash_idx = t.find('-', 1)
                            therm_temp_str = t[:next_dash_idx]

                        therm_temp: float = float(therm_temp_str)
                        thermistors.append(Thermistor(therm_temp))

                    with g_lock:
                        output_heater_values: List[int] = []

                        for therm, controller in zip(thermistors, g_controllers):
                            controller_output: float = controller.process(therm.sensor_value)
                            output_heater_values.append(int(controller_output))

                        write_to_output_pipe(output_heater_values)

                    break
                time_acc_usec = 0
                with g_lock:
                    if not g_controllers_enabled:
                        break


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
