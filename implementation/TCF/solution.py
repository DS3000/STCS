#!/usr/bin/python3

import sys
from dataclasses import dataclass
from typing import List

input_pipe_path: str = "/tmp/temp_info_pipe"
output_pipe_path: str = "/tmp/response_pipe"

info_line_terminator: str = chr(0)  # NULL character, /x00
info_line_delimiter: str = ';'

setpoint_value: float = 10.0
setpoint_upper_threshold: float = 15.0
setpoint_lower_threshold: float = 5.0


@dataclass
class Thermistor:
    sensor_value: float
    heater_state: bool

    def __str__(self):
        return "Temp: {}, State: {}".format(self.sensor_value,
                                            "on" if self.heater_state else "off")


def set_heater_values(h1: int, h2: int, h3: int, h4: int) -> str:
    return "{};{};{};{}\0".format(h1, h2, h3, h4)


def write_to_output_pipe(heater_values: List[int], verbose: bool = False):
    with open(output_pipe_path, 'w') as pipe:
        data = set_heater_values(heater_values[0], heater_values[1], heater_values[2], heater_values[3])
        if verbose:
            print(f" Writing {data_to_write}")
        pipe.write(data)


def bang_bang(in_thermister: List[Thermistor], setpoint: float,
              upper_threshold: float, lower_threshold: float) -> List[int]:
    result: List[int] = [0, 0, 0, 0]

    for i, t in enumerate(in_thermister):
        if t.sensor_value < lower_threshold:
            result[i] = 1
        elif t.sensor_value > upper_threshold:
            result[i] = 0

    return result


def pid(in_thermister: List[Thermistor], setpoint: float,
        upper_threshold: float, lower_threshold: float, dt: float) -> List[int]:
    #TODO: implement PID controller, possibly using a class to keep track of historic values
    # like previous error, and integral
    # https://en.wikipedia.org/wiki/Proportional%E2%80%93integral%E2%80%93derivative_controller#Pseudocode

    result: List[int] = [0, 0, 0, 0]

    for i, t in enumerate(in_thermister):
        p_factor: float = 0.0
        i_factor: float = 0.0
        d_factor: float = 0.0

        error_factor: float = setpoint - t.sensor_value

        result[i] = int(p_factor + i_factor + d_factor)
        pass

    return result


def main():
    print(f"Opening {input_pipe_path}... ", end="")
    sys.stdout.flush()

    clock: int = 0
    with open(input_pipe_path, 'r') as input_pipe:
        print("done!")
        input_info_line: str = ""
        while True:
            input_data: str = input_pipe.read(1)

            if len(input_data) == 0:
                print("Pipe closed")
                break

            # read from the input stream until info line break (at info_line_terminator)
            if input_data[0] == info_line_terminator:

                # print(f'{clock} Read: "{input_info_line}"', flush=True)

                parts: List[str] = input_info_line.split(info_line_delimiter)
                if len(parts) != 5:
                    continue
                # parts format:
                # <clock_timestamp>;<t1_temp>-<t1_heater_state>;<t2_temp>-<t2_heater_state>;<t3_temp>-<t3_heater_state>;<t4_temp>-<t4_heater_state><\0>
                # note: line ends with NULL \0 character, and thermistor temperatures and heater states are dash separated
                timestamp, t1, t2, t3, t4 = parts

                read_therm_values: List[str] = [t1, t2, t3, t4]
                thermistors: List[Thermistor] = []

                # split each thermistor values, and append to thermistors list
                for t in read_therm_values:
                    idx_sep: int = t.rfind('-')

                    temp_str: str = t[:idx_sep]
                    temp: float = float(temp_str)

                    # convert str to int, then int to bool
                    state_str: str = t[idx_sep:]
                    state_int: int = int(state_str)
                    state: bool = bool(state_int)

                    thermistors.append(Thermistor(temp, state))

                print(f"timestamp: {timestamp}")
                for i, t in enumerate(thermistors):
                    print("\t", i + 1, t)
                print()

                values: List[int] = bang_bang(thermistors, setpoint_value, setpoint_upper_threshold,
                                              setpoint_lower_threshold)
                write_to_output_pipe(values)

                input_info_line = ""  # clear info line
                clock += 1
            else:
                input_info_line += input_data


if __name__ == '__main__':
    try:
        main()
    except:
        # fallback, to when the process is interrupted via Ctrl-C
        # set all heater values to zero
        with open(output_pipe_path, 'w') as output_pipe:
            data_to_write = set_heater_values(0, 0, 0, 0)
            output_pipe.write(data_to_write)
