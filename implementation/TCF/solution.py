#!/usr/bin/python3

import os
import errno
import sys
from typing import List
import io

input_pipe_path: str = "/tmp/temp_info_pipe"
output_pipe_path: str = "/tmp/response_pipe"

info_line_terminator: str = chr(0) # NULL character, /x00
info_line_delimiter: str = ';'


def set_heater_values(h1: int, h2: int, h3: int, h4: int) -> str:
    return "{};{};{};{}\0".format(h1, h2, h3, h4)


def main():
    heater_values = []

    if len(sys.argv) == 5:
        heater_values = sys.argv[1:]
    else:
        print("Needs 4 arguments, space-separated 1/0 representing on/off state for each heater")
        exit()


    print(f"Opening {input_pipe_path}... ", end="")
    sys.stdout.flush()
    clock: int = 0
    with open(input_pipe_path, 'r') as input_pipe:
        print("done!")
        info_line: str = ""
        while True:
            input_data: str = input_pipe.read(1)
            
            if len(input_data) == 0:
                print("Pipe closed")
                break
            
            # read from the input stream until info line break (at info_line_terminator)
            if input_data[0] == info_line_terminator:
                
                # print(f'{clock} Read: "{info_line}"', flush=True)
                
                parts: List[str] = info_line.split(info_line_delimiter)
                if len(parts) != 5:
                    continue
                
                counter, h1, h2, h3, h4 = parts
                
                # print(f" incoming {counter} h1: {h1}, h2: {h2}, h3: {h3}, h4: {h4}")
                    
                
                with open(output_pipe_path, 'w') as output_pipe:
                    data_to_write = set_heater_values(heater_values[0], heater_values[1], heater_values[2], heater_values[3])                    
                    # print(f"{clock} Writing {data_to_write}")
                    output_pipe.write(data_to_write)
                    
                info_line = "" #clear info line
                clock += 1
                
                
                
            else:
                info_line += input_data        
        


if __name__=='__main__':
    try:
        main()
    except:
        # fallback, to when the process is interrupted via Ctrl-C
        # set all heater values to zero
        with open(output_pipe_path, 'w') as output_pipe:
            data_to_write = set_heater_values(0, 0, 0, 0)
            output_pipe.write(data_to_write)
                