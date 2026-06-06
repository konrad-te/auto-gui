import pyautogui
import time
import json

# load the saved mouse events from recording.json
def play():
    with open("recording.json", "r") as file:
        events = json.load(file)

    # keep track of the time of the previous event
    previous_time = 0 

    # go through every recorded mouse event in order
    for event in events:
        # wait the same amount of time as in the recording
        delay = event["time"] - previous_time
        time.sleep(delay)
        previous_time = event["time"]

        # move the mouse to the recorded position
        if event["type"] == "move":
            pyautogui.moveTo(event["x"], event["y"])

        # click only when the recorded mouse button was pressed
        elif event["type"] == "click" and event["pressed"]:
            pyautogui.click(event["x"], event["y"])
