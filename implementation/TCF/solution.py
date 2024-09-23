#!/usr/bin/python3

import os
import errno
import sys
from typing import List

input_pipe_path: str = "/tmp/temp_info_pipe"
output_pipe_path: str = "/tmp/response_pipe"

info_line_terminator: str = chr(0) # NULL character, /x00
info_line_delimiter: str = ';'


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
        
        if input_data[0] == info_line_terminator: # end of info line
            
            print(f'{clock} Read: "{info_line}"', flush=True)
            
            parts: List[str] = info_line.split(info_line_delimiter)
            if len(parts) != 5:
                continue
            
            counter, h1, h2, h3, h4 = parts
            
            print(f" incoming {counter} h1: {h1}, h2: {h2}, h3: {h3}, h4: {h4}")
                
            
            info_line = "" #clear info line
            clock += 1
            
            
        else:
            info_line += input_data        
        
        # with open(output_pipe_path, 'w') as output_pipe:
        #     data_to_write = "fony data"
        #     print(f"{clock} Writing {data_to_write}")
        #     output_pipe.write(data_to_write)

    