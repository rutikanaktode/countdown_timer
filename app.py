import tkinter as tk
from tkinter import messagebox
import threading
import time
import math
import os
import sys
import subprocess

# ─── Sound generation using Python standard library ───────────────────────────

def play_beep_sound():
    """Play alert sound using cross-platform approach."""
    try:
        # Try platform-specific sound first
        if sys.platform == "win32":
            import winsound
            for _ in range(3):
                winsound.Beep(880, 300)
                time.sleep(0.1)
                winsound.Beep(1100, 300)
                time.sleep(0.1)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
            time.sleep(0.5)
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
        else:
            # Linux – try paplay / aplay / beep
            for cmd in [["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                        ["aplay", "/usr/share/sounds/alsa/Front_Center.wav"],
                        ["beep", "-f", "880", "-l", "300"]]:
                if subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
                    subprocess.run(cmd, check=False)
                    break
            else:
                print("\a\a\a")  # Terminal bell fallback
    except Exception:
        print("\a\a\a")


# ─── Canvas arc helper ─────────────────────────────────────────────────────────

def arc_coords(cx, cy, r, start_deg, end_deg, steps=120):
    """Return flat list of (x, y) points for a canvas polygon arc."""
    points = []
    for i in range(steps + 1):
        angle = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        points.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])
    return points


# ─── Main Application ──────────────────────────────────────────────────────────

class CountdownTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("⏱ Countdown Timer")
        self.root.resizable(False, False)
        self.root.configure(bg="#0a0a0f")

        # State
        self.total_seconds   = 0
        self.remaining       = 0
        self.running         = False
        self.paused          = False
        self._timer_thread   = None
        self._stop_flag      = threading.Event()

        # Dimensions
        self.W, self.H = 480, 620
        self.CX, self.CY = self.W // 2, 240
        self.R_OUTER = 160
        self.R_INNER = 120

        self._build_ui()
        self._draw_ring(1.0)          # full ring on startup

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Canvas (clock face) ──────────────────────────────────────────────
        self.canvas = tk.Canvas(
            self.root, width=self.W, height=300,
            bg="#0a0a0f", highlightthickness=0
        )
        self.canvas.pack()

        # Background glow circle
        self.canvas.create_oval(
            self.CX - self.R_OUTER - 12, self.CY - self.R_OUTER - 12,
            self.CX + self.R_OUTER + 12, self.CY + self.R_OUTER + 12,
            fill="#12121e", outline="#1e1e32", width=2
        )

        # Track ring (dark)
        self.canvas.create_oval(
            self.CX - self.R_OUTER, self.CY - self.R_OUTER,
            self.CX + self.R_OUTER, self.CY + self.R_OUTER,
            fill="", outline="#1e1e38", width=28
        )

        # Progress arc placeholder (drawn dynamically)
        self.arc_id = None

        # Inner circle
        self.canvas.create_oval(
            self.CX - self.R_INNER, self.CY - self.R_INNER,
            self.CX + self.R_INNER, self.CY + self.R_INNER,
            fill="#0d0d1a", outline="#1a1a2e", width=2
        )

        # Time display text
        self.time_var = tk.StringVar(value="00:00:00")
        self.canvas.create_text(
            self.CX, self.CY - 14,
            text="", font=("Courier", 32, "bold"),
            fill="#ffffff", tags="time_text"
        )
        self.canvas.create_text(
            self.CX, self.CY + 22,
            text="READY", font=("Courier", 11),
            fill="#4a4a7a", tags="status_text"
        )

        # ── Controls frame ───────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg="#0a0a0f")
        ctrl.pack(fill="x", padx=30)

        lbl_style = {"bg": "#0a0a0f", "fg": "#4a4a8a",
                     "font": ("Courier", 9, "bold")}
        spin_style = {
            "bg": "#12121e", "fg": "#e0e0ff",
            "font": ("Courier", 22, "bold"),
            "relief": "flat", "bd": 0,
            "highlightthickness": 1,
            "highlightbackground": "#2a2a4a",
            "highlightcolor": "#6060ff",
            "insertbackground": "#6060ff",
            "buttonbackground": "#1a1a2e",
            "width": 3, "justify": "center"
        }

        # Hours
        hf = tk.Frame(ctrl, bg="#0a0a0f")
        hf.pack(side="left", expand=True)
        tk.Label(hf, text="HRS", **lbl_style).pack()
        self.hours_var = tk.StringVar(value="0")
        self.h_spin = tk.Spinbox(hf, from_=0, to=23,
                                 textvariable=self.hours_var, **spin_style)
        self.h_spin.pack()

        # Colon
        tk.Label(ctrl, text=":", bg="#0a0a0f", fg="#3a3a6a",
                 font=("Courier", 26, "bold")).pack(side="left", pady=(16, 0))

        # Minutes
        mf = tk.Frame(ctrl, bg="#0a0a0f")
        mf.pack(side="left", expand=True)
        tk.Label(mf, text="MIN", **lbl_style).pack()
        self.minutes_var = tk.StringVar(value="0")
        self.m_spin = tk.Spinbox(mf, from_=0, to=59,
                                 textvariable=self.minutes_var, **spin_style)
        self.m_spin.pack()

        # Colon
        tk.Label(ctrl, text=":", bg="#0a0a0f", fg="#3a3a6a",
                 font=("Courier", 26, "bold")).pack(side="left", pady=(16, 0))

        # Seconds
        sf = tk.Frame(ctrl, bg="#0a0a0f")
        sf.pack(side="left", expand=True)
        tk.Label(sf, text="SEC", **lbl_style).pack()
        self.seconds_var = tk.StringVar(value="0")
        self.s_spin = tk.Spinbox(sf, from_=0, to=59,
                                 textvariable=self.seconds_var, **spin_style)
        self.s_spin.pack()

        # ── Button row ───────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg="#0a0a0f")
        btn_frame.pack(pady=22)

        self.start_btn = self._make_btn(btn_frame, "▶  START",
                                        "#00c8ff", "#003a5a", self._start)
        self.start_btn.pack(side="left", padx=8)

        self.pause_btn = self._make_btn(btn_frame, "⏸  PAUSE",
                                        "#a0a0ff", "#1a1a40", self._pause)
        self.pause_btn.pack(side="left", padx=8)
        self.pause_btn.config(state="disabled")

        self.reset_btn = self._make_btn(btn_frame, "↺  RESET",
                                        "#ff6060", "#3a1010", self._reset)
        self.reset_btn.pack(side="left", padx=8)

        # ── Status bar ───────────────────────────────────────────────────────
        self.status_bar = tk.Label(
            self.root, text="Set a time and press START",
            bg="#0d0d1a", fg="#4a4a7a",
            font=("Courier", 9), pady=6
        )
        self.status_bar.pack(fill="x", side="bottom")

        # Update clock face with 0
        self._update_display(0, 0)

    def _make_btn(self, parent, text, fg, bg, cmd):
        btn = tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=fg, activebackground=bg,
            activeforeground=fg,
            font=("Courier", 10, "bold"),
            relief="flat", bd=0,
            padx=14, pady=8, cursor="hand2",
            highlightthickness=1,
            highlightbackground=fg,
            highlightcolor=fg
        )
        return btn

    # ── Ring Drawing ───────────────────────────────────────────────────────────

    def _draw_ring(self, fraction):
        """Draw progress arc. fraction = 1.0 (full) → 0.0 (empty)."""
        if self.arc_id:
            self.canvas.delete(self.arc_id)

        if fraction <= 0:
            self.arc_id = None
            return

        # Color: cyan → amber → red as time drains
        if fraction > 0.5:
            r, g, b = int(255 * (1 - fraction) * 2), 200, 255
        elif fraction > 0.2:
            r, g, b = 255, int(200 * fraction * 2), 60
        else:
            r, g, b = 255, int(60 * fraction * 5), 60

        color = f"#{r:02x}{g:02x}{b:02x}"

        start_angle = -90          # top
        sweep       = -360 * fraction
        end_angle   = start_angle + sweep

        self.arc_id = self.canvas.create_arc(
            self.CX - self.R_OUTER, self.CY - self.R_OUTER,
            self.CX + self.R_OUTER, self.CY + self.R_OUTER,
            start=start_angle + 90,
            extent=sweep,
            outline=color, width=18,
            style="arc"
        )

    # ── Display Update ─────────────────────────────────────────────────────────

    def _update_display(self, remaining, total):
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        time_str = f"{h:02d}:{m:02d}:{s:02d}"
        self.canvas.itemconfig("time_text", text=time_str)
        fraction = remaining / total if total > 0 else 1.0
        self._draw_ring(fraction)

    def _set_status(self, text, color="#4a4a7a"):
        self.canvas.itemconfig("status_text", text=text, fill=color)
        self.status_bar.config(text=text)

    # ── Timer Logic ────────────────────────────────────────────────────────────

    def _start(self):
        if self.running and not self.paused:
            return

        if self.paused:
            self.paused = False
            self.start_btn.config(state="disabled")
            self.pause_btn.config(state="normal", text="⏸  PAUSE")
            self._set_status("RUNNING", "#00c8ff")
            return

        # Fresh start
        try:
            h = int(self.hours_var.get())
            m = int(self.minutes_var.get())
            s = int(self.seconds_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers.")
            return

        total = h * 3600 + m * 60 + s
        if total <= 0:
            messagebox.showwarning("No Time Set", "Please set a time greater than 0.")
            return

        self.total_seconds = total
        self.remaining     = total
        self.running       = True
        self.paused        = False
        self._stop_flag.clear()

        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text="⏸  PAUSE")
        self._set_spinboxes(False)
        self._set_status("RUNNING", "#00c8ff")

        self._timer_thread = threading.Thread(target=self._run_timer, daemon=True)
        self._timer_thread.start()

    def _pause(self):
        if not self.running:
            return
        if self.paused:
            # Resume
            self.paused = False
            self.start_btn.config(state="disabled")
            self.pause_btn.config(text="⏸  PAUSE")
            self._set_status("RUNNING", "#00c8ff")
        else:
            # Pause
            self.paused = True
            self.start_btn.config(state="normal", text="▶  RESUME")
            self.pause_btn.config(text="▶  RESUME")
            self._set_status("PAUSED", "#a0a0ff")

    def _reset(self):
        self._stop_flag.set()
        self.running = False
        self.paused  = False
        self.remaining     = 0
        self.total_seconds = 0

        self.start_btn.config(state="normal", text="▶  START")
        self.pause_btn.config(state="disabled", text="⏸  PAUSE")
        self._set_spinboxes(True)
        self._draw_ring(1.0)
        self.canvas.itemconfig("time_text", text="00:00:00")
        self._set_status("READY", "#4a4a7a")

    def _run_timer(self):
        while self.remaining > 0 and not self._stop_flag.is_set():
            if not self.paused:
                self.root.after(0, self._update_display,
                                self.remaining, self.total_seconds)
                time.sleep(1)
                if not self.paused:
                    self.remaining -= 1
            else:
                time.sleep(0.1)

        if not self._stop_flag.is_set():
            self.root.after(0, self._on_finish)

    def _on_finish(self):
        self.running = False
        self._update_display(0, self.total_seconds)
        self._set_status("TIME'S UP! 🔔", "#ff4444")
        self.start_btn.config(state="normal", text="▶  START")
        self.pause_btn.config(state="disabled")
        self._set_spinboxes(True)
        self._flash_effect()
        threading.Thread(target=play_beep_sound, daemon=True).start()
        messagebox.showinfo("⏰ Time's Up!", "Your countdown has finished!")

    def _flash_effect(self, count=0):
        """Flash the ring red a few times."""
        if count >= 6:
            self._draw_ring(0)
            return
        color = "#ff2222" if count % 2 == 0 else "#330000"
        if self.arc_id:
            self.canvas.delete(self.arc_id)
        self.arc_id = self.canvas.create_arc(
            self.CX - self.R_OUTER, self.CY - self.R_OUTER,
            self.CX + self.R_OUTER, self.CY + self.R_OUTER,
            start=90, extent=-360,
            outline=color, width=18, style="arc"
        )
        self.root.after(200, self._flash_effect, count + 1)

    def _set_spinboxes(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for sp in (self.h_spin, self.m_spin, self.s_spin):
            sp.config(state=state)


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()

    # Center window
    root.update_idletasks()
    W, H = 480, 620
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

    app = CountdownTimer(root)
    root.mainloop()