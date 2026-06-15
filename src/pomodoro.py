import sys

if sys.platform == "darwin":
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        if bundle:
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info:
                info['CFBundleName'] = 'Pomodoro'
                info['CFBundleDisplayName'] = 'Pomodoro'
    except Exception:
        pass

import tkinter as tk
import ttkbootstrap as tb
import os
from datetime import datetime, date
from storage import StorageManager

FONT_FAMILY = "Helvetica"


def get_resource_path(filename):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


def apply_window_icon(window):
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSImage
            for ext in ["png", "icns", "ico"]:
                icon_path = get_resource_path(f"stopwatch.{ext}")
                if os.path.exists(icon_path):
                    image = NSImage.alloc().initWithContentsOfFile_(icon_path)
                    if image:
                        NSApplication.sharedApplication().setApplicationIconImage_(image)
                        break
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            ico_path = get_resource_path("stopwatch.ico")
            if os.path.exists(ico_path):
                window.iconbitmap(ico_path)
        except Exception:
            pass
        return

    try:
        png_path = get_resource_path("stopwatch.png")
        if os.path.exists(png_path):
            img = tk.PhotoImage(file=png_path)
            window.iconphoto(True, img)
            window._icon_image = img
            return
    except Exception:
        pass

    try:
        ico_path = get_resource_path("stopwatch.ico")
        if os.path.exists(ico_path):
            window.iconbitmap(ico_path)
    except Exception:
        pass


class PomodoroApp:

    def __init__(self, storage_manager, headless=False):
        self.storage = storage_manager
        self.settings = self.storage.settings

        self.current_mode = "Work"
        self.completed_pomodoros = 0
        self.timer_running = False
        self.pomodoro_time = 0
        self.stopwatch_start_time = None
        self.stopwatch_accumulated_seconds = 0
        self.is_maximized = False
        self.editing_todo_ids = set()

        self.root = None
        self.mode_label = None
        self.timer_label = None
        self.start_btn = None
        self.stop_btn = None
        self.skip_btn = None
        self.mode_frame = None
        self.mode_var = None
        self.maximize_btn = None
        self.minimize_btn = None
        self.menu_bar = None
        self.timer_frame = None

        self.todo_entry = None
        self.todo_list_frame = None
        self.todo_list_canvas = None

        if not headless:
            self.create_ui()

    def create_ui(self):
        self.root = tb.Window(themename="superhero")
        apply_window_icon(self.root)
        self.root.title("Pomodoro")

        width = self.settings.get("window_width", 290)
        height = self.settings.get("window_height", 290)
        self.root.geometry(f"{width}x{height}")
        self.root.attributes("-topmost", True)

        self.mode_var = tk.StringVar(value=self.settings.get("timer_mode", "Pomodoro"))
        self.mode_frame = tb.Frame(self.root)
        self.mode_frame.pack(pady=(12, 0))

        def on_mode_change(*args):
            if not self.timer_running:
                self.settings["timer_mode"] = self.mode_var.get()
                self.storage.save_settings()
                if self.settings["timer_mode"] == "Stopwatch":
                    self.set_mode("Stopwatch")
                else:
                    self.set_mode("Work")

        self.mode_var.trace_add("write", on_mode_change)

        tb.Radiobutton(
            self.mode_frame, text="Pomodoro", variable=self.mode_var, value="Pomodoro"
        ).pack(side="left", padx=5)
        tb.Radiobutton(
            self.mode_frame, text="Stopwatch", variable=self.mode_var, value="Stopwatch"
        ).pack(side="left", padx=5)

        self.mode_label = tb.Label(self.root, text="", font=(FONT_FAMILY, 12, "bold"))
        self.mode_label.pack(pady=(8, 0))

        self.timer_frame = tb.Frame(self.root)
        self.timer_frame.pack(pady=0)

        self.timer_label = tb.Label(
            self.timer_frame, text="", font=(FONT_FAMILY, self.settings["label_font_size"], "bold")
        )
        self.timer_label.pack(side="left")

        self.start_btn = tb.Button(
            self.root, text="Start", command=self.start_pomodoro, bootstyle="primary", width=12
        )
        self.start_btn.pack(pady=4)

        self.stop_btn = tb.Button(
            self.root, text="Stop", command=self.stop_pomodoro, bootstyle="danger", width=12
        )
        self.skip_btn = tb.Button(
            self.root, text="Skip Break", command=self.skip_break, bootstyle="secondary", width=12
        )

        max_icon = "⤢" if sys.platform == "darwin" else "⛶"
        self.maximize_btn = tb.Label(
            self.timer_frame, text=max_icon, cursor="hand2", font=(FONT_FAMILY, 18), bootstyle="info"
        )
        self.maximize_btn.bind("<Button-1>", lambda e: self.maximize_timer())
        self.minimize_btn = tb.Label(
            self.timer_frame, text="⤡", cursor="hand2", font=(FONT_FAMILY, 18), bootstyle="info"
        )
        self.minimize_btn.bind("<Button-1>", lambda e: self.minimize_timer())
        self.maximize_btn.pack(side="left", padx=(5, 0), anchor="center")

        self.menu_bar = self.build_menu(self.root)

        if sys.platform != "darwin":
            self.root.bind("<FocusIn>", self.on_focus_in)
            self.root.bind("<FocusOut>", self.on_focus_out)
            self.root.attributes("-alpha", self.settings["unfocus_transparency"])

        if self.settings.get("timer_mode") == "Stopwatch":
            self.set_mode("Stopwatch")
        else:
            self.set_mode("Work")

        def on_close():
            try:
                geom = self.root.geometry()
                size = geom.split("+")[0]
                w, h = map(int, size.split("x"))
                if not self.is_maximized:
                    self.settings["window_width"] = w
                    self.settings["window_height"] = h
                self.storage.save_settings()
            except Exception as e:
                print(f"Error saving window size on close: {e}")
            self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_close)

    def build_menu(self, window, exclude=None):
        exclude = exclude or set()
        all_items = [
            ("Settings", self.open_settings_dialog),
            ("Todos",    self.open_todos_dialog),
            ("Report",   self.open_report_dialog),
            ("Font +",   self.increase_font),
            ("Font -",   self.decrease_font),
        ]
        menu_bar = tk.Menu(window, tearoff=0)
        window.config(menu=menu_bar)
        for label, cmd in all_items:
            if label in exclude:
                continue
            if sys.platform == "darwin":
                sub = tk.Menu(menu_bar, tearoff=0)
                menu_bar.add_cascade(label=label, menu=sub)
                sub.add_command(label=label, command=cmd)
            else:
                menu_bar.add_command(label=label, command=cmd)
        return menu_bar

    def increase_font(self):
        self.settings["label_font_size"] = min(self.settings["label_font_size"] + 2, 72)
        self.timer_label.configure(font=(FONT_FAMILY, self.settings["label_font_size"], "bold"))
        self.storage.save_settings()

    def decrease_font(self):
        self.settings["label_font_size"] = max(self.settings["label_font_size"] - 2, 8)
        self.timer_label.configure(font=(FONT_FAMILY, self.settings["label_font_size"], "bold"))
        self.storage.save_settings()

    def open_todos_dialog(self):
        todos_win = tb.Toplevel(self.root)
        apply_window_icon(todos_win)
        todos_win.title("Todos")
        todos_win.geometry("300x400")
        todos_win.attributes("-topmost", True)

        todo_title = tb.Label(todos_win, text="Todos", font=(FONT_FAMILY, 12, "bold"), bootstyle="primary")
        todo_title.pack(anchor="w", pady=(5, 5), padx=5)

        input_frame = tb.Frame(todos_win)
        input_frame.pack(fill="x", pady=2, padx=5)

        self.todo_entry = tb.Entry(input_frame, font=(FONT_FAMILY, 10), bootstyle="secondary")
        self.todo_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.todo_entry.bind("<Return>", lambda e: self.add_todo_item())

        add_btn = tb.Button(input_frame, text="Add", command=self.add_todo_item, bootstyle="info", width=5)
        add_btn.pack(side="right")

        list_container = tb.Frame(todos_win)
        list_container.pack(fill="both", expand=True, pady=5)

        bg_color = tb.Style().colors.bg
        self.todo_list_canvas = tk.Canvas(list_container, borderwidth=0, highlightthickness=0, bg=bg_color)
        todo_scrollbar = tb.Scrollbar(list_container, orient="vertical", command=self.todo_list_canvas.yview)

        self.todo_list_frame = tb.Frame(self.todo_list_canvas)
        canvas_window = self.todo_list_canvas.create_window((0, 0), window=self.todo_list_frame, anchor="nw", width=260)

        def on_canvas_configure(event):
            self.todo_list_canvas.itemconfig(canvas_window, width=event.width)

        self.todo_list_canvas.bind("<Configure>", on_canvas_configure)

        self.todo_list_frame.bind(
            "<Configure>",
            lambda e: self.todo_list_canvas.configure(
                scrollregion=self.todo_list_canvas.bbox("all")
            )
        )

        self.todo_list_canvas.configure(yscrollcommand=todo_scrollbar.set)
        self.todo_list_canvas.pack(side="left", fill="both", expand=True)
        todo_scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            if sys.platform == "win32":
                self.todo_list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif sys.platform == "darwin":
                self.todo_list_canvas.yview_scroll(int(-1 * event.delta), "units")
            else:
                if event.num == 4:
                    self.todo_list_canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.todo_list_canvas.yview_scroll(1, "units")

        def bind_mousewheel(event):
            self.todo_list_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            if sys.platform == "linux":
                self.todo_list_canvas.bind_all("<Button-4>", _on_mousewheel)
                self.todo_list_canvas.bind_all("<Button-5>", _on_mousewheel)

        def unbind_mousewheel(event):
            self.todo_list_canvas.unbind_all("<MouseWheel>")
            if sys.platform == "linux":
                self.todo_list_canvas.unbind_all("<Button-4>")
                self.todo_list_canvas.unbind_all("<Button-5>")

        self.todo_list_canvas.bind("<Enter>", bind_mousewheel)
        self.todo_list_canvas.bind("<Leave>", unbind_mousewheel)

        self.render_todos()
        self.todo_entry.focus_set()

    def render_todos(self):
        if self.todo_list_frame is None:
            return

        for widget in self.todo_list_frame.winfo_children():
            widget.destroy()

        for todo in self.storage.todos:
            item_frame = tb.Frame(self.todo_list_frame)
            item_frame.pack(fill="x", pady=4, padx=5)

            todo_id = todo["id"]
            if todo_id in self.editing_todo_ids:
                edit_var = tk.StringVar(value=todo["text"])
                edit_entry = tb.Entry(
                    item_frame,
                    textvariable=edit_var,
                    font=(FONT_FAMILY, 10),
                    bootstyle="info",
                )

                def save_edit(event=None, t=todo, var=edit_var):
                    new_text = var.get().strip()
                    if new_text:
                        t["text"] = new_text
                        self.storage.save_todos()
                    self.editing_todo_ids.discard(t["id"])
                    self.render_todos()

                edit_entry.bind("<Return>", save_edit)

                save_btn = tb.Button(
                    item_frame,
                    text="✔",
                    bootstyle="success-link",
                    width=2,
                    command=save_edit
                )
                save_btn.pack(side="right", padx=2)
                edit_entry.pack(side="left", fill="x", expand=True, padx=2)
                edit_entry.focus_set()
                edit_entry.select_range(0, tk.END)
                edit_entry.icursor(tk.END)
            else:
                var = tk.BooleanVar(value=todo["done"])
                cb = tb.Checkbutton(
                    item_frame,
                    variable=var,
                    bootstyle="success",
                    command=lambda t=todo, v=var: self.toggle_todo_status(t, v.get())
                )

                fg_color = "gray" if todo["done"] else "white"
                font_style = (FONT_FAMILY, 10, "overstrike") if todo["done"] else (FONT_FAMILY, 10)

                lbl = tb.Label(
                    item_frame,
                    text=todo["text"],
                    font=font_style,
                    foreground=fg_color,
                    anchor="w",
                    justify="left",
                    wraplength=140
                )
                lbl.bind("<Double-1>", lambda e, tid=todo_id: self.start_edit(tid))

                def make_configure_handler(frame=item_frame, label_widget=lbl):
                    def handler(event):
                        if event.widget != frame:
                            return
                        lbl_width = max(50, event.width - 135)
                        try:
                            current_wrap = int(label_widget.cget("wraplength"))
                        except ValueError:
                            current_wrap = 0
                        if current_wrap != lbl_width:
                            label_widget.configure(wraplength=lbl_width)
                    return handler

                item_frame.bind("<Configure>", make_configure_handler(item_frame, lbl))

                edit_btn = tb.Button(
                    item_frame,
                    text="🖋️",
                    bootstyle="info-link",
                    width=3,
                    command=lambda tid=todo_id: self.start_edit(tid)
                )

                del_btn = tb.Button(
                    item_frame,
                    text="❌",
                    bootstyle="danger-link",
                    width=3,
                    command=lambda t=todo: self.delete_todo_item(t)
                )

                del_btn.pack(side="right", padx=0)
                edit_btn.pack(side="right", padx=0)
                cb.pack(side="left", padx=1)
                lbl.pack(side="left", fill="x", expand=True, padx=1)

        self.todo_list_frame.update_idletasks()
        self.todo_list_canvas.configure(scrollregion=self.todo_list_canvas.bbox("all"))

    def add_todo_item(self):
        if self.todo_entry is None:
            return
        text = self.todo_entry.get().strip()
        if text:
            todo_id = int(datetime.now().timestamp() * 1000)
            self.storage.todos.append({
                "id": todo_id,
                "text": text,
                "done": False
            })
            self.storage.save_todos()
            self.todo_entry.delete(0, tk.END)
            self.render_todos()

    def toggle_todo_status(self, todo, is_done):
        todo["done"] = is_done
        self.storage.save_todos()
        self.render_todos()

    def start_edit(self, todo_id):
        self.editing_todo_ids.add(todo_id)
        self.render_todos()

    def delete_todo_item(self, todo):
        if todo in self.storage.todos:
            self.storage.todos.remove(todo)
            self.storage.save_todos()
            self.render_todos()

    def on_focus_in(self, event):
        if event.widget == self.root:
            self.root.wm_attributes("-alpha", 1.0)

    def on_focus_out(self, event):
        if event.widget == self.root:
            self.root.wm_attributes("-alpha", self.settings["unfocus_transparency"])

    def open_settings_dialog(self):
        settings_win = tb.Toplevel(self.root)
        apply_window_icon(settings_win)
        settings_win.title("Settings")
        geom = "320x400" if sys.platform == "darwin" else "320x460"
        settings_win.geometry(geom)
        settings_win.attributes("-topmost", True)

        def create_slider(parent, label_text, var, from_, to, is_float=False):
            frame = tb.Frame(parent)
            frame.pack(pady=5, fill="x", padx=20)

            val_label = tb.Label(
                frame,
                text=(
                    f"{label_text} {var.get():.1f}"
                    if is_float
                    else f"{label_text} {var.get()}"
                ),
                font=(FONT_FAMILY, 10),
            )
            val_label.pack(anchor="w")

            def update_label(val):
                v = float(val) if is_float else int(float(val))
                var.set(v)
                val_label.config(
                    text=f"{label_text} {v:.1f}" if is_float else f"{label_text} {v}"
                )

            scale = tb.Scale(
                frame,
                from_=from_,
                to=to,
                orient="horizontal",
                command=update_label,
                bootstyle="info",
            )
            scale.set(var.get())
            scale.pack(fill="x", pady=2)
            return scale

        work_var = tk.IntVar(value=self.settings["work_time"])
        create_slider(settings_win, "Work Time (min):", work_var, 1, 60)

        short_var = tk.IntVar(value=self.settings["short_break"])
        create_slider(settings_win, "Short Break (min):", short_var, 1, 30)

        long_var = tk.IntVar(value=self.settings["long_break"])
        create_slider(settings_win, "Long Break (min):", long_var, 1, 60)

        interval_var = tk.IntVar(value=self.settings["long_break_interval"])
        create_slider(settings_win, "Long Break Interval:", interval_var, 1, 10)

        sound_var = tk.BooleanVar(value=self.settings["sound_enabled"])
        tb.Checkbutton(
            settings_win,
            text="Play Sound on Finish",
            variable=sound_var,
            bootstyle="success, round-toggle",
        ).pack(pady=10)

        trans_var = tk.DoubleVar(value=self.settings["unfocus_transparency"])
        if sys.platform != "darwin":
            create_slider(
                settings_win, "Unfocused Transparency:", trans_var, 0.1, 1.0, is_float=True
            )

        def save():
            try:
                self.settings["work_time"] = int(work_var.get())
                self.settings["short_break"] = int(short_var.get())
                self.settings["long_break"] = int(long_var.get())
                self.settings["long_break_interval"] = int(interval_var.get())
                self.settings["sound_enabled"] = sound_var.get()
                self.settings["unfocus_transparency"] = float(trans_var.get())
                self.storage.save_settings()
                if sys.platform != "darwin":
                    self.root.attributes("-alpha", self.settings["unfocus_transparency"])
                if not self.timer_running:
                    if self.settings["timer_mode"] == "Stopwatch":
                        self.set_mode("Stopwatch")
                    else:
                        if self.current_mode == "Stopwatch":
                            self.set_mode("Work")
                        else:
                            self.set_mode(self.current_mode)
                settings_win.destroy()
            except ValueError:
                pass

        def reset_stats():
            from tkinter import messagebox
            confirm = messagebox.askyesno(
                "Confirm Reset",
                "Are you sure you want to reset today's statistics? This cannot be undone.",
                parent=settings_win
            )
            if confirm:
                if self.storage.reset_today_stats():
                    messagebox.showinfo("Reset Complete", "Today's statistics have been reset.", parent=settings_win)
                else:
                    messagebox.showerror("Error", "Could not reset today's statistics.", parent=settings_win)

        tb.Button(
            settings_win,
            text="🗑  Reset Today's Stats",
            command=reset_stats,
            bootstyle="danger-outline",
            width=20
        ).pack(pady=5)

        tb.Button(
            settings_win, text="Save Settings", command=save, bootstyle="success", width=20
        ).pack(pady=15)

    def set_mode(self, mode):
        self.current_mode = mode
        if mode == "Work":
            self.pomodoro_time = self.settings["work_time"] * 60
            self.mode_label.config(
                text=f"{mode} {self.completed_pomodoros + 1}/{self.settings['long_break_interval']}",
                bootstyle="primary",
            )
            self.skip_btn.pack_forget()
        elif mode == "Short Break":
            self.pomodoro_time = self.settings["short_break"] * 60
            self.mode_label.config(text=mode, bootstyle="success")
            self.stop_btn.pack_forget()
            if not self.is_maximized:
                self.skip_btn.pack(pady=4)
        elif mode == "Long Break":
            self.pomodoro_time = self.settings["long_break"] * 60
            self.mode_label.config(text=mode, bootstyle="success")
            self.stop_btn.pack_forget()
            if not self.is_maximized:
                self.skip_btn.pack(pady=4)
        elif mode == "Stopwatch":
            self.pomodoro_time = 0
            self.mode_label.config(text=mode, bootstyle="secondary")
            self.skip_btn.pack_forget()
            self.stop_btn.pack_forget()

        minutes, seconds = divmod(self.pomodoro_time, 60)
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

    def start_pomodoro(self):
        self.timer_running = True
        self.start_btn.pack_forget()

        for child in self.mode_frame.winfo_children():
            child.configure(state="disabled")

        if self.current_mode == "Stopwatch":
            self.stopwatch_start_time = datetime.now()
            self.stopwatch_accumulated_seconds = 0
            self.start_btn.config(
                text="Pause", command=self.pause_pomodoro, bootstyle="warning"
            )
            self.start_btn.pack(pady=4)
            self.stop_btn.pack(pady=4)
            self.update_timer()
        else:
            self.start_btn.config(
                text="Pause", command=self.pause_pomodoro, bootstyle="warning"
            )
            self.start_btn.pack(pady=4)
            if self.current_mode in ["Short Break", "Long Break"]:
                self.skip_btn.pack(pady=4)
                self.stop_btn.pack_forget()
            else:
                self.stop_btn.pack(pady=4)
                self.skip_btn.pack_forget()
            self.update_timer()

    def pause_pomodoro(self):
        self.timer_running = False
        if self.current_mode == "Stopwatch" and self.stopwatch_start_time is not None:
            elapsed = (datetime.now() - self.stopwatch_start_time).total_seconds()
            self.stopwatch_accumulated_seconds += elapsed
            self.stopwatch_start_time = None

        self.start_btn.config(
            text="Continue", command=self.continue_pomodoro, bootstyle="success"
        )

    def continue_pomodoro(self):
        self.timer_running = True
        if self.current_mode == "Stopwatch":
            self.stopwatch_start_time = datetime.now()

        self.start_btn.config(
            text="Pause", command=self.pause_pomodoro, bootstyle="warning"
        )
        self.update_timer()

    def stop_pomodoro(self):
        self.timer_running = False
        if self.current_mode == "Stopwatch":
            elapsed = 0
            if self.stopwatch_start_time is not None:
                elapsed = (datetime.now() - self.stopwatch_start_time).total_seconds()
            total_active = self.stopwatch_accumulated_seconds + elapsed
            self.storage.log_session("Stopwatch", total_active)
            self.stopwatch_start_time = None
            self.stopwatch_accumulated_seconds = 0
        else:
            total_duration = self.settings["work_time"] * 60 if self.current_mode == "Work" else (
                self.settings["short_break"] * 60 if self.current_mode == "Short Break" else self.settings["long_break"] * 60
            )
            elapsed = total_duration - self.pomodoro_time
            self.storage.log_session(self.current_mode, elapsed)

        self.start_btn.config(
            text="Start", command=self.start_pomodoro, bootstyle="primary"
        )
        self.start_btn.pack_forget()
        self.start_btn.pack(pady=4)
        self.stop_btn.pack_forget()
        self.skip_btn.pack_forget()
        self.set_mode("Work")

        for child in self.mode_frame.winfo_children():
            child.configure(state="normal")

    def skip_break(self):
        self.timer_running = False
        if self.current_mode in ["Short Break", "Long Break"]:
            total_duration = (
                self.settings["short_break"] * 60 if self.current_mode == "Short Break" else self.settings["long_break"] * 60
            )
            elapsed = total_duration - self.pomodoro_time
            self.storage.log_session(self.current_mode, elapsed)

        self.start_btn.config(
            text="Start", command=self.start_pomodoro, bootstyle="primary"
        )
        self.start_btn.pack_forget()
        self.start_btn.pack(pady=4)
        self.stop_btn.pack_forget()
        self.skip_btn.pack_forget()
        self.set_mode("Work")

        for child in self.mode_frame.winfo_children():
            child.configure(state="normal")

    def update_timer(self):
        if self.timer_running:
            if self.current_mode == "Stopwatch":
                minutes, seconds = divmod(self.pomodoro_time, 60)
                self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
                self.pomodoro_time += 1
                self.root.after(1000, self.update_timer)
            else:
                if self.pomodoro_time > 0:
                    minutes, seconds = divmod(self.pomodoro_time, 60)
                    self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
                    self.pomodoro_time -= 1
                    self.root.after(1000, self.update_timer)
                else:
                    self.timer_running = False

                    if self.is_maximized:
                        self.minimize_timer()

                    if self.settings["sound_enabled"]:
                        if sys.platform == "linux":
                            sound_file = get_resource_path("complete.oga")
                            os.system(f'paplay "{sound_file}" 2>/dev/null &')
                        else:
                            self.root.bell()

                    self.start_btn.config(
                        text="Start", command=self.start_pomodoro, bootstyle="primary"
                    )

                    for child in self.mode_frame.winfo_children():
                        child.configure(state="normal")

                    if self.current_mode == "Work":
                        self.completed_pomodoros += 1
                        self.storage.log_session("Work", self.settings["work_time"] * 60)
                        if (
                            self.completed_pomodoros > 0
                            and self.completed_pomodoros % self.settings["long_break_interval"] == 0
                        ):
                            self.set_mode("Long Break")
                        else:
                            self.set_mode("Short Break")
                    else:
                        if self.current_mode == "Long Break":
                            self.completed_pomodoros = 0
                        self.set_mode("Work")

    def maximize_timer(self):
        if not self.is_maximized:
            try:
                geom = self.root.geometry()
                size = geom.split("+")[0]
                w, h = map(int, size.split("x"))
                self.settings["window_width"] = w
                self.settings["window_height"] = h
                self.storage.save_settings()
            except Exception as e:
                print(f"Error saving window size: {e}")

        self.is_maximized = True
        self.root.config(menu="")

        self.mode_frame.pack_forget()
        self.mode_label.pack_forget()
        self.start_btn.pack_forget()
        self.stop_btn.pack_forget()
        self.skip_btn.pack_forget()
        self.maximize_btn.pack_forget()

        width = self.settings.get("maximized_window_width", 240)
        height = self.settings.get("maximized_window_height", 80)
        self.root.geometry(f"{width}x{height}")

        self.timer_frame.pack_forget()
        self.timer_frame.pack(pady=(15, 5))

        self.minimize_btn.pack(side="left", padx=(5, 0), anchor="center")

    def minimize_timer(self):
        if self.is_maximized:
            try:
                geom = self.root.geometry()
                size = geom.split("+")[0]
                w, h = map(int, size.split("x"))
                self.settings["maximized_window_width"] = w
                self.settings["maximized_window_height"] = h
                self.storage.save_settings()
            except Exception as e:
                print(f"Error saving maximized window size: {e}")

        self.is_maximized = False

        self.minimize_btn.pack_forget()
        self.root.config(menu=self.menu_bar)

        width = self.settings.get("window_width", 290)
        height = self.settings.get("window_height", 290)
        self.root.geometry(f"{width}x{height}")

        self.timer_frame.pack_forget()
        self.timer_frame.pack(pady=0)

        self.mode_frame.pack(pady=(12, 0))
        self.mode_label.pack(pady=(8, 0))

        self.start_btn.pack(pady=4)
        if self.current_mode in ["Short Break", "Long Break"]:
            self.skip_btn.pack(pady=4)
            self.stop_btn.pack_forget()
        elif self.start_btn.cget("text") in ["Pause", "Continue"]:
            self.stop_btn.pack(pady=4)
            self.skip_btn.pack_forget()
        else:
            self.stop_btn.pack_forget()
            self.skip_btn.pack_forget()

        self.maximize_btn.pack(side="left", padx=(5, 0), anchor="center")

    def open_report_dialog(self):
        today = date.today().isoformat()
        history = self.storage.load_history()
        today_sessions = [s for s in history if s.get("date") == today]

        work_sessions = [s for s in today_sessions if s["type"] == "Work"]
        stopwatch_sessions = [s for s in today_sessions if s["type"] == "Stopwatch"]

        total_work_secs = sum(s["duration_seconds"] for s in work_sessions)
        total_sw_secs = sum(s["duration_seconds"] for s in stopwatch_sessions)
        total_focus_secs = total_work_secs + total_sw_secs

        def fmt_time(secs):
            h, rem = divmod(int(secs), 3600)
            m, s = divmod(rem, 60)
            if h > 0:
                return f"{h}h {m}m {s}s"
            elif m > 0:
                return f"{m}m {s}s"
            return f"{s}s"

        report_win = tb.Toplevel(self.root)
        apply_window_icon(report_win)
        report_win.title("Daily Report")
        report_win.geometry("300x260")
        report_win.attributes("-topmost", True)
        report_win.resizable(False, False)

        tb.Label(
            report_win,
            text="📊 Daily Report",
            font=(FONT_FAMILY, 14, "bold"),
            bootstyle="primary",
        ).pack(pady=(16, 4))

        tb.Label(
            report_win,
            text=today,
            font=(FONT_FAMILY, 9),
            bootstyle="secondary",
            foreground="white",
        ).pack(pady=(0, 12))

        stats_frame = tb.Frame(report_win, padding=10)
        stats_frame.pack(fill="x", padx=20)

        def stat_row(label, value):
            row = tb.Frame(stats_frame)
            row.pack(fill="x", pady=4)
            tb.Label(row, text=label, font=(FONT_FAMILY, 10), foreground="white").pack(side="left")
            tb.Label(row, text=value, font=(FONT_FAMILY, 10, "bold"), foreground="white").pack(side="right")

        tb.Separator(stats_frame).pack(fill="x", pady=(0, 8))
        stat_row("🕐 Total Focus Time", fmt_time(total_focus_secs))
        total_sessions = len(today_sessions)
        stat_row("💼 Total Sessions", str(total_sessions))
        stat_row("⏱  Pomodoro Time", fmt_time(total_work_secs))
        stat_row("⏩ Stopwatch Time", fmt_time(total_sw_secs))

        if not today_sessions:
            tb.Label(
                report_win,
                text="No sessions recorded today yet.",
                font=(FONT_FAMILY, 9),
                bootstyle="secondary",
            ).pack(pady=10)


def create_app():
    storage = StorageManager()
    app = PomodoroApp(storage)
    app.root.mainloop()


if __name__ == "__main__":
    create_app()
