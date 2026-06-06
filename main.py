import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pyautogui
from pynput import keyboard, mouse

# choose where recordings are saved and how often mouse movement is recorded
recording_file = Path("recording.json")
move_interval = 0.02
move_distance = 2


# create the main app window and store all app state
class macro_app:
    def __init__(self, root):
        # set up the window title, size, and background color
        self.root = root
        self.root.title("mouse macro")
        self.root.geometry("500x560")
        self.root.resizable(False, False)
        self.root.configure(bg="#f4f6f8")

        # store recording and playback state
        self.events = []
        self.recording = False
        self.playing = False
        self.stop_playback = threading.Event()
        self.record_start_time = 0
        self.last_move_time = 0
        self.last_move_position = None
        self.mouse_listener = None
        self.playback_speed = 1.0
        self.auto_attack = False
        self.stop_auto_attack = threading.Event()
        self.auto_thread = None
        self.battle_top_left = None
        self.battle_bottom_right = None
        self.attack_point = None
        self.check_interval = 2.0

        # store text that the gui updates while the app runs
        self.status_text = tk.StringVar(value="idle")
        self.count_text = tk.StringVar(value="0 events")
        self.file_text = tk.StringVar(value=str(recording_file))
        self.speed_text = tk.StringVar(value="1.00x")
        self.speed_value = tk.DoubleVar(value=1.0)
        self.auto_text = tk.StringVar(value="auto reattack off")
        self.region_text = tk.StringVar(value="battle area not set")
        self.attack_text = tk.StringVar(value="attack point not set")
        self.interval_text = tk.StringVar(value="2.0s")
        self.interval_value = tk.DoubleVar(value=2.0)

        # build the window, start hotkeys, and handle closing the app
        self.build_gui()
        self.start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    # build all visible parts of the gui
    def build_gui(self):
        # create the main padded area inside the window
        frame = tk.Frame(self.root, bg="#f4f6f8", padx=22, pady=20)
        frame.pack(fill="both", expand=True)

        # create the title area
        header = tk.Frame(frame, bg="#f4f6f8")
        header.pack(fill="x")

        tk.Label(
            header,
            text="mouse macro recorder",
            font=("segoe ui", 17, "bold"),
            bg="#f4f6f8",
            fg="#111827",
        ).pack(anchor="w")

        # create tab buttons for the two main tools
        tabs = tk.Frame(frame, bg="#f4f6f8")
        tabs.pack(fill="x", pady=(18, 14))

        self.macro_tab_button = self.make_tab_button(tabs, "macro recorder", lambda: self.show_page("macro"))
        self.auto_tab_button = self.make_tab_button(tabs, "auto reattack", lambda: self.show_page("auto"))
        self.macro_tab_button.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.auto_tab_button.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # create the page area and build both pages
        self.page_area = tk.Frame(frame, bg="#f4f6f8")
        self.page_area.pack(fill="both", expand=True)

        self.macro_page = tk.Frame(self.page_area, bg="#f4f6f8")
        self.auto_page = tk.Frame(self.page_area, bg="#f4f6f8")

        self.build_macro_page(self.macro_page)
        self.build_auto_page(self.auto_page)
        self.show_page("macro")

    # build the macro recording and playback page
    def build_macro_page(self, parent):
        # create the row that shows current status and event count
        status_row = tk.Frame(parent, bg="#f4f6f8")
        status_row.pack(fill="x", pady=(0, 14))

        tk.Label(
            status_row,
            textvariable=self.status_text,
            font=("segoe ui", 10, "bold"),
            bg="#e8edf3",
            fg="#111827",
            padx=10,
            pady=5,
        ).pack(side="left")

        tk.Label(
            status_row,
            textvariable=self.count_text,
            font=("segoe ui", 10),
            bg="#f4f6f8",
            fg="#374151",
        ).pack(side="left", padx=(12, 0))

        # show which file the macro is saved to
        tk.Label(
            parent,
            textvariable=self.file_text,
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#6b7280",
        ).pack(anchor="w", pady=(0, 18))

        # create the playback speed control
        speed_box = tk.Frame(parent, bg="#f4f6f8")
        speed_box.pack(fill="x", pady=(0, 18))

        speed_header = tk.Frame(speed_box, bg="#f4f6f8")
        speed_header.pack(fill="x")

        tk.Label(
            speed_header,
            text="playback speed",
            font=("segoe ui", 10, "bold"),
            bg="#f4f6f8",
            fg="#111827",
        ).pack(side="left")

        tk.Label(
            speed_header,
            textvariable=self.speed_text,
            font=("segoe ui", 10, "bold"),
            bg="#f4f6f8",
            fg="#2563eb",
        ).pack(side="right")

        tk.Scale(
            speed_box,
            from_=0.25,
            to=3.0,
            resolution=0.25,
            orient="horizontal",
            variable=self.speed_value,
            command=self.update_speed,
            bg="#f4f6f8",
            fg="#374151",
            highlightthickness=0,
            troughcolor="#d1d5db",
            length=360,
        ).pack(fill="x", pady=(4, 0))

        # create the button area
        buttons = tk.Frame(parent, bg="#f4f6f8")
        buttons.pack(fill="x")

        # add the main control buttons
        self.make_button(buttons, "record / stop", "f8", self.toggle_recording, "#2563eb", "#1d4ed8")
        self.make_button(buttons, "play", "f9", self.play_recording, "#111827", "#030712")
        self.make_button(buttons, "stop", "f10", self.stop_all, "#dc2626", "#b91c1c")

        # show macro hotkeys only on the macro page
        tk.Label(
            parent,
            text="f8 records mouse movement and clicks\nf9 repeats the saved macro\nf10 stops the current action",
            justify="left",
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#4b5563",
        ).pack(anchor="w", pady=(16, 0))

    # build the auto reattack setup and control page
    def build_auto_page(self, parent):
        # create the auto reattack controls
        auto_box = tk.Frame(parent, bg="#e8edf3", padx=14, pady=12)
        auto_box.pack(fill="x")

        auto_header = tk.Frame(auto_box, bg="#e8edf3")
        auto_header.pack(fill="x")

        tk.Label(
            auto_header,
            text="auto reattack",
            font=("segoe ui", 10, "bold"),
            bg="#e8edf3",
            fg="#111827",
        ).pack(side="left")

        tk.Label(
            auto_header,
            textvariable=self.auto_text,
            font=("segoe ui", 9, "bold"),
            bg="#e8edf3",
            fg="#374151",
        ).pack(side="right")

        tk.Label(
            auto_box,
            textvariable=self.status_text,
            font=("segoe ui", 9, "bold"),
            bg="#e8edf3",
            fg="#111827",
        ).pack(anchor="w", pady=(10, 0))

        tk.Label(
            auto_box,
            textvariable=self.region_text,
            font=("segoe ui", 9),
            bg="#e8edf3",
            fg="#4b5563",
        ).pack(anchor="w", pady=(8, 0))

        tk.Label(
            auto_box,
            textvariable=self.attack_text,
            font=("segoe ui", 9),
            bg="#e8edf3",
            fg="#4b5563",
        ).pack(anchor="w", pady=(2, 8))

        auto_buttons = tk.Frame(auto_box, bg="#e8edf3")
        auto_buttons.pack(fill="x")

        self.make_small_button(auto_buttons, "top left  f5", self.set_battle_top_left).pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.make_small_button(auto_buttons, "bottom right  f6", self.set_battle_bottom_right).pack(side="left", expand=True, fill="x", padx=4)
        self.make_small_button(auto_buttons, "attack  f7", self.set_attack_point).pack(side="left", expand=True, fill="x", padx=(4, 0))

        interval_header = tk.Frame(auto_box, bg="#e8edf3")
        interval_header.pack(fill="x", pady=(10, 0))

        tk.Label(
            interval_header,
            text="check every",
            font=("segoe ui", 9, "bold"),
            bg="#e8edf3",
            fg="#111827",
        ).pack(side="left")

        tk.Label(
            interval_header,
            textvariable=self.interval_text,
            font=("segoe ui", 9, "bold"),
            bg="#e8edf3",
            fg="#2563eb",
        ).pack(side="right")

        tk.Scale(
            auto_box,
            from_=0.5,
            to=10.0,
            resolution=0.5,
            orient="horizontal",
            variable=self.interval_value,
            command=self.update_interval,
            bg="#e8edf3",
            fg="#374151",
            highlightthickness=0,
            troughcolor="#d1d5db",
            length=360,
        ).pack(fill="x", pady=(2, 6))

        self.make_small_button(auto_box, "test red mark", self.test_mark_detection).pack(fill="x", pady=(0, 5))
        self.make_button(auto_box, "toggle auto reattack", "", self.toggle_auto_attack, "#059669", "#047857")

        # show auto reattack setup hotkeys only on this page
        tk.Label(
            parent,
            text="f5 captures top left\nf6 captures bottom right\nf7 captures fallback attack point",
            justify="left",
            font=("segoe ui", 9),
            bg="#f4f6f8",
            fg="#4b5563",
        ).pack(anchor="w", pady=(16, 0))

    # create one tab button
    def make_tab_button(self, parent, label, command):
        return tk.Button(
            parent,
            text=label,
            command=command,
            font=("segoe ui", 10, "bold"),
            bg="#e8edf3",
            fg="#374151",
            activebackground="#dbeafe",
            activeforeground="#111827",
            bd=0,
            relief="flat",
            height=2,
            cursor="hand2",
        )

    # show one page and hide the other
    def show_page(self, page_name):
        self.macro_page.pack_forget()
        self.auto_page.pack_forget()

        if page_name == "macro":
            self.macro_page.pack(fill="both", expand=True)
            self.macro_tab_button.configure(bg="#2563eb", fg="white")
            self.auto_tab_button.configure(bg="#e8edf3", fg="#374151")
        else:
            self.auto_page.pack(fill="both", expand=True)
            self.auto_tab_button.configure(bg="#2563eb", fg="white")
            self.macro_tab_button.configure(bg="#e8edf3", fg="#374151")

    # create one styled button
    def make_button(self, parent, label, hotkey, command, color, active_color):
        button_text = f"{label}    {hotkey}" if hotkey else label

        button = tk.Button(
            parent,
            text=button_text,
            command=command,
            font=("segoe ui", 10, "bold"),
            bg=color,
            fg="white",
            activebackground=active_color,
            activeforeground="white",
            bd=0,
            relief="flat",
            height=2,
            cursor="hand2",
        )
        button.pack(fill="x", pady=5)
        return button

    # create one compact button for setup actions
    def make_small_button(self, parent, label, command):
        return tk.Button(
            parent,
            text=label,
            command=command,
            font=("segoe ui", 8, "bold"),
            bg="#ffffff",
            fg="#111827",
            activebackground="#f3f4f6",
            activeforeground="#111827",
            bd=0,
            relief="flat",
            height=2,
            cursor="hand2",
        )

    # update the playback speed when the slider changes
    def update_speed(self, value):
        self.playback_speed = float(value)
        self.speed_text.set(f"{self.playback_speed:.2f}x")

    # update how often auto reattack checks the battle list
    def update_interval(self, value):
        self.check_interval = float(value)
        self.interval_text.set(f"{self.check_interval:.1f}s")

    # save the current mouse position as the battle-list top left corner
    def set_battle_top_left(self):
        self.battle_top_left = pyautogui.position()
        self.update_battle_region_text()

    # save the current mouse position as the battle-list bottom right corner
    def set_battle_bottom_right(self):
        self.battle_bottom_right = pyautogui.position()
        self.update_battle_region_text()

    # save the current mouse position as the fallback trainer to click
    def set_attack_point(self):
        self.attack_point = pyautogui.position()
        self.attack_text.set(f"attack point: {self.attack_point.x}, {self.attack_point.y}")

    # show the saved battle-list area in the gui
    def update_battle_region_text(self):
        if not self.battle_top_left or not self.battle_bottom_right:
            self.region_text.set("battle area not set")
            return

        x, y, width, height = self.get_battle_region()
        self.region_text.set(f"battle area: {x}, {y}, {width}x{height}")

    # convert the two saved corners into a screenshot region
    def get_battle_region(self):
        left = min(self.battle_top_left.x, self.battle_bottom_right.x)
        top = min(self.battle_top_left.y, self.battle_bottom_right.y)
        right = max(self.battle_top_left.x, self.battle_bottom_right.x)
        bottom = max(self.battle_top_left.y, self.battle_bottom_right.y)
        return left, top, right - left, bottom - top

    # turn auto reattack on or off
    def toggle_auto_attack(self):
        if self.auto_attack:
            self.stop_auto_attack_loop()
            return

        if not self.battle_top_left or not self.battle_bottom_right or not self.attack_point:
            messagebox.showinfo("setup needed", "set the battle area and attack point first")
            return

        self.auto_attack = True
        self.stop_auto_attack.clear()
        self.auto_text.set("auto reattack on")
        self.auto_thread = threading.Thread(target=self.run_auto_attack_loop, daemon=True)
        self.auto_thread.start()

    # stop the auto reattack background loop
    def stop_auto_attack_loop(self):
        self.auto_attack = False
        self.stop_auto_attack.set()
        self.auto_text.set("auto reattack off")

    # check the battle list repeatedly and click fallback if no red mark exists
    def run_auto_attack_loop(self):
        while not self.stop_auto_attack.wait(self.check_interval):
            if self.recording or self.playing:
                continue

            try:
                if not self.trainer_is_marked():
                    pyautogui.click(self.attack_point.x, self.attack_point.y)
                    self.root.after(0, lambda: self.status_text.set("auto reattack clicked"))
            except Exception:
                self.root.after(0, lambda: self.status_text.set("auto reattack error"))

    # take a screenshot of the battle list and look for the red mark color
    def trainer_is_marked(self):
        region = self.get_battle_region()
        screenshot = pyautogui.screenshot(region=region)
        return self.has_red_mark(screenshot)

    # detect the red marked trainer pixels from the screenshot
    def has_red_mark(self, image):
        red_pixels = 0

        for red, green, blue in image.convert("RGB").getdata():
            is_red = red >= 150 and green <= 85 and blue <= 85 and red - green >= 70

            if is_red:
                red_pixels += 1

            if red_pixels >= 12:
                return True

        return False

    # manually test if the saved battle-list area has a red mark
    def test_mark_detection(self):
        if not self.battle_top_left or not self.battle_bottom_right:
            messagebox.showinfo("setup needed", "set the battle area first")
            return

        if self.trainer_is_marked():
            self.status_text.set("red mark found")
        else:
            self.status_text.set("no red mark found")

    # register global hotkeys so they work outside the app window
    def start_hotkeys(self):
        self.hotkeys = keyboard.GlobalHotKeys({
            "<f5>": self.safe_set_battle_top_left,
            "<f6>": self.safe_set_battle_bottom_right,
            "<f7>": self.safe_set_attack_point,
            "<f8>": self.safe_toggle_recording,
            "<f9>": self.safe_play_recording,
            "<f10>": self.safe_stop_all,
        })
        self.hotkeys.start()

    # send the f5 hotkey action back to the gui thread
    def safe_set_battle_top_left(self):
        self.root.after(0, self.set_battle_top_left)

    # send the f6 hotkey action back to the gui thread
    def safe_set_battle_bottom_right(self):
        self.root.after(0, self.set_battle_bottom_right)

    # send the f7 hotkey action back to the gui thread
    def safe_set_attack_point(self):
        self.root.after(0, self.set_attack_point)

    # send the f8 hotkey action back to the gui thread
    def safe_toggle_recording(self):
        self.root.after(0, self.toggle_recording)

    # send the f9 hotkey action back to the gui thread
    def safe_play_recording(self):
        self.root.after(0, self.play_recording)

    # send the f10 hotkey action back to the gui thread
    def safe_stop_all(self):
        self.root.after(0, self.stop_all)

    # start recording if idle, or stop recording if already recording
    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    # begin listening to mouse movement, clicks, and scrolls
    def start_recording(self):
        if self.playing:
            return

        # reset old recording data and update the gui
        self.events = []
        self.recording = True
        self.record_start_time = time.perf_counter()
        self.last_move_time = 0
        self.last_move_position = None
        self.status_text.set("recording")
        self.count_text.set("0 events")

        self.mouse_listener = mouse.Listener(
            on_move=self.record_move,
            on_click=self.record_click,
            on_scroll=self.record_scroll,
        )
        self.mouse_listener.start()

    # stop listening and save the recorded events to json
    def stop_recording(self):
        self.recording = False

        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

        with recording_file.open("w", encoding="utf-8") as file:
            json.dump(self.events, file, indent=2)

        self.status_text.set("saved")
        self.count_text.set(f"{len(self.events)} events")

    # calculate when an event happened compared to the recording start
    def event_time(self):
        return round(time.perf_counter() - self.record_start_time, 4)

    # add one event to the current recording
    def add_event(self, event):
        if not self.recording:
            return

        event["time"] = self.event_time()
        self.events.append(event)
        self.root.after(0, lambda: self.count_text.set(f"{len(self.events)} events"))

    # record mouse movement without saving too many tiny movements
    def record_move(self, x, y):
        now = time.perf_counter()

        if self.last_move_position:
            old_x, old_y = self.last_move_position
            moved_far_enough = abs(x - old_x) >= move_distance or abs(y - old_y) >= move_distance
        else:
            moved_far_enough = True

        waited_long_enough = now - self.last_move_time >= move_interval

        if moved_far_enough and waited_long_enough:
            self.last_move_time = now
            self.last_move_position = (x, y)
            self.add_event({"type": "move", "x": x, "y": y})

    # record mouse button presses and releases
    def record_click(self, x, y, button, pressed):
        self.add_event({
            "type": "click",
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
        })

    # record mouse wheel scrolling
    def record_scroll(self, x, y, dx, dy):
        self.add_event({
            "type": "scroll",
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
        })

    # load the saved macro and start playback in the background
    def play_recording(self):
        if self.recording or self.playing:
            return

        if not recording_file.exists():
            messagebox.showinfo("no recording", "record something first with f8")
            return

        with recording_file.open("r", encoding="utf-8") as file:
            events = json.load(file)

        self.playing = True
        self.stop_playback.clear()
        self.status_text.set("playing")
        self.count_text.set(f"{len(events)} events")

        thread = threading.Thread(target=self.run_playback, args=(events,), daemon=True)
        thread.start()

    # repeat every saved event using the selected speed
    def run_playback(self, events):
        previous_time = 0

        for event in events:
            if self.stop_playback.is_set():
                break

            delay = max(0, event["time"] - previous_time)
            delay = delay / max(self.playback_speed, 0.25)

            if self.stop_playback.wait(delay):
                break

            previous_time = event["time"]

            # move the mouse to the saved position
            if event["type"] == "move":
                pyautogui.moveTo(event["x"], event["y"])

            # click only when the saved event was a button press
            elif event["type"] == "click" and event["pressed"]:
                button = event.get("button", "left")
                pyautogui.click(event["x"], event["y"], button=button)

            # replay mouse wheel scrolling
            elif event["type"] == "scroll":
                pyautogui.moveTo(event["x"], event["y"])
                pyautogui.scroll(event["dy"])

        self.playing = False
        self.root.after(0, lambda: self.status_text.set("idle"))

    # stop recording or ask playback to stop
    def stop_all(self):
        if self.auto_attack:
            self.stop_auto_attack_loop()

        if self.recording:
            self.stop_recording()

        if self.playing:
            self.stop_playback.set()
            self.status_text.set("stopping")

    # stop background listeners before closing the window
    def close_app(self):
        self.stop_all()

        if hasattr(self, "hotkeys"):
            self.hotkeys.stop()

        self.root.destroy()


# start the app when this file is run directly
if __name__ == "__main__":
    root = tk.Tk()
    app = macro_app(root)
    root.mainloop()

