#!/usr/bin/env python
import readchar

run_in_progress = False

print("i am not kodiaq")

while True:
    x = readchar.readchar()
    if x == 'q':
        if run_in_progress:
            print("First stop run")
        else:
            print("Solong")
            break
    elif x == 'p':
        if run_in_progress:
            print("Stopped run")
            run_in_progress = False
        else:
            print("No run in progress")
    elif x == 's':
        if run_in_progress:
            print("Run already in progress")
        else:
            run_in_progress = True
            print("Started run")
