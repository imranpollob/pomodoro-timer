import tkinter as tk
from tkinter import simpledialog, ttk

default_pomodoro_time = 25  # Default time in minutes
unfocus_transparency = 0.8
label_font_size = 14


def on_focus_in():
    root.wm_attributes("-alpha", 1.0)  # Set window fully opaque on focus


def on_focus_out():
    global unfocus_transparency
    root.wm_attributes("-alpha", unfocus_transparency)


def open_settings_dialog():
    global unfocus_transparency
    new_unfocus_transparency_int = simpledialog.askinteger(
        "Transparency Settings",
        "Enter unfocused transparency (1 to 10):",
        minvalue=1,
        maxvalue=10,
    )

    if new_unfocus_transparency_int is not None:
        unfocus_transparency = new_unfocus_transparency_int / 10.0


def is_integer(P):
    # Validate if input is an integer or empty (for deletion/backspace)
    if P.isdigit() or P == "":
        return True
    else:
        return False


def start_pomodoro():
    global pomodoro_time, timer_running
    if not timer_running:
        try:
            pomodoro_time = int(time_entry.get()) * 60  # Convert minutes to seconds
        except ValueError:
            pomodoro_time = (
                default_pomodoro_time * 60
            )  # Default to 25 minutes if conversion fails
        timer_running = True
        start_btn.config(text="Pause", command=pause_pomodoro)
        time_entry.pack_forget()
        update_timer()
    else:
        pause_pomodoro()


def pause_pomodoro():
    global timer_running
    timer_running = False
    start_btn.pack_forget()
    continue_btn.pack(pady=5)
    stop_btn.pack()


def continue_pomodoro():
    global timer_running
    timer_running = True
    continue_btn.pack_forget()
    stop_btn.pack_forget()
    start_btn.config(text="Pause", command=pause_pomodoro)
    start_btn.pack(pady=5)
    update_timer()


def stop_pomodoro():
    global pomodoro_time, timer_running
    timer_running = False
    pomodoro_time = default_pomodoro_time * 60  # Reset the timer
    time_entry_var.set(default_pomodoro_time)  # Reset the time entry to default value

    continue_btn.pack_forget()  # Hide the continue button
    stop_btn.pack_forget()  # Hide the stop button

    start_btn.config(text="Start", command=start_pomodoro)
    timer_label.config(text="Set timer and start")

    # Pack time_entry before start_btn to maintain their order
    time_entry.pack_forget()
    start_btn.pack_forget()
    time_entry.pack(pady=5)
    start_btn.pack(pady=5)


def update_timer():
    global pomodoro_time, timer_running
    if timer_running:
        if pomodoro_time > 0:
            minutes, seconds = divmod(pomodoro_time, 60)
            timer_label.config(text=f"Time left: {minutes:02d}:{seconds:02d}")
            pomodoro_time -= 1
            root.after(1000, update_timer)  # Update every second
        else:
            stop_pomodoro()


def create_app():
    global root, time_entry, time_entry_var, timer_label, start_btn, continue_btn, stop_btn, timer_running
    root = tk.Tk()
    root.title("Pomodoro Timer")
    root.geometry("200x150")
    root.attributes("-topmost", True)

    timer_running = False

    timer_label = ttk.Label(
        root, text="Set timer and start", font=("Arial", label_font_size, "bold")
    )
    timer_label.pack(pady=15)

    validate_command = (root.register(is_integer), "%P")
    time_entry_var = tk.IntVar(value=default_pomodoro_time)
    time_entry = ttk.Entry(
        root,
        textvariable=time_entry_var,
        validate="key",
        validatecommand=validate_command,
        width=10,
    )
    time_entry.pack(pady=5)

    start_btn = ttk.Button(root, text="Start", command=start_pomodoro)
    start_btn.pack(pady=5)

    continue_btn = ttk.Button(root, text="Continue", command=continue_pomodoro)
    stop_btn = ttk.Button(root, text="Stop", command=stop_pomodoro)

    def increase_font():
        global label_font_size  # Modify global variable
        label_font_size = min(label_font_size + 2, 32)  # Limit max size to 32
        timer_label.configure(font=("Arial", label_font_size, "bold"))

    def decrease_font():
        global label_font_size  # Modify global variable
        label_font_size = max(label_font_size - 2, 8)  # Limit min size to 8
        timer_label.configure(font=("Arial", label_font_size, "bold"))

    # Transparency settings
    menu_bar = tk.Menu(root, tearoff=0)
    root.config(menu=menu_bar)

    menu_bar.add_command(label="🔧", command=open_settings_dialog)
    menu_bar.add_command(label="➕", command=increase_font)
    menu_bar.add_command(label="➖", command=decrease_font)

    root.bind("<FocusIn>", on_focus_in)
    root.bind("<FocusOut>", on_focus_out)
    root.attributes("-alpha", unfocus_transparency)

    root.mainloop()


if __name__ == "__main__":
    create_app()
