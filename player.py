import pyautogui
import time
import json

def play():
    with open("recording.json", "r") as file:
        events = json.load(file)

    previous_time = 0 

    for event in events:
        delay = event["time"] - previous_time
        time.sleep(delay)
        previous_time = event["time"]

        if event["type"] == "move":
            pyautogui.moveTo(event["x"], event["y"])

        elif event["type"] == "click" and event["pressed"]:
            pyautogui.click(event["x"], event["y"])