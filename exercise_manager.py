import calendar
import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


APP_TITLE = "Daily Exercise Manager"
DATA_FILE = Path(__file__).with_name("exercise_data.json")
AUDIO_FILE = Path(__file__).with_name("audio.mp3")

APP_BG = "#eef2f7"
SURFACE = "#ffffff"
SURFACE_ALT = "#f8fafc"
HERO_BG = "#0f172a"
HERO_ACCENT = "#38bdf8"
TEXT = "#0f172a"
MUTED = "#64748b"
PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
COMPLETE = "#166534"
COMPLETE_BG = "#ecfdf5"
SKIPPED = "#ff0000"
SKIPPED_BG = "#fef2f2"
CARD_BORDER = "#dbe3ee"


@dataclass
class WorkoutEntry:
    day: str
    exercise: str
    target_minutes: int
    completed_minutes: int = 0
    notes: str = ""
    status: str = "open"
    started_at: str | None = None
    paused_at: str | None = None
    completed_at: str | None = None
    skipped_at: str | None = None

    @property
    def completed(self) -> bool:
        return self.status == "completed"

    @property
    def skipped(self) -> bool:
        return self.status == "skipped"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_entry(entry: WorkoutEntry, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    today = now.date()
    entry_day = datetime.strptime(entry.day, "%Y-%m-%d").date()
    changed = False

    if entry.target_minutes < 3:
        entry.target_minutes = 3
        changed = True

    if entry.status == "completed":
        if entry.completed_minutes != entry.target_minutes:
            entry.completed_minutes = entry.target_minutes
            changed = True
        if entry.paused_at is not None:
            entry.paused_at = None
            changed = True
        if entry.completed_at is None:
            entry.completed_at = now.isoformat(timespec="seconds")
            changed = True
        return changed

    if entry.status == "skipped":
        if entry.completed_minutes != 0:
            entry.completed_minutes = 0
            changed = True
        if entry.skipped_at is None:
            entry.skipped_at = now.isoformat(timespec="seconds")
            changed = True
        return changed

    if entry.status == "paused":
        if entry.paused_at is None:
            entry.paused_at = now.isoformat(timespec="seconds")
            changed = True
        return changed

    if entry_day < today:
        entry.status = "skipped"
        entry.completed_minutes = 0
        entry.paused_at = None
        entry.skipped_at = now.isoformat(timespec="seconds")
        changed = True
        return changed

    if entry_day > today:
        return changed

    started_at = parse_datetime(entry.started_at)
    if started_at is None:
        entry.started_at = now.isoformat(timespec="seconds")
        entry.paused_at = None
        started_at = now
        changed = True

    if entry.paused_at is not None:
        paused_at = parse_datetime(entry.paused_at)
        if paused_at is not None and started_at is not None:
            started_at = started_at + (now - paused_at)
            entry.started_at = started_at.isoformat(timespec="seconds")
            changed = True
        entry.paused_at = None

    elapsed_seconds = max(0, int((now - started_at).total_seconds()))
    elapsed_minutes = min(entry.target_minutes, elapsed_seconds // 60)

    if entry.completed_minutes != elapsed_minutes:
        entry.completed_minutes = elapsed_minutes
        changed = True

    if elapsed_seconds >= entry.target_minutes * 60:
        entry.status = "completed"
        entry.completed_minutes = entry.target_minutes
        entry.paused_at = None
        entry.completed_at = now.isoformat(timespec="seconds")
        changed = True

    return changed


def today_iso() -> str:
    return date.today().isoformat()


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"entries": []}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return {"entries": []}
    if "entries" not in data or not isinstance(data["entries"], list):
        return {"entries": []}
    return data


def save_data(data: dict) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


class ExerciseManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x700")
        self.minsize(960, 620)

        self.data = load_data()
        self.selected_day = tk.StringVar(value=today_iso())
        self.view_mode = tk.StringVar(value="Day")
        self.day_label = tk.StringVar()
        self.summary_text = tk.StringVar()
        self.timer_text = tk.StringVar(value="Timer idle until you open today\'s date.")
        self.pause_button_text = tk.StringVar(value="Pause")
        self._timer_job: str | None = None
        self._toolbar_compact: bool | None = None
        self._audio_process: subprocess.Popen | None = None
        self._audio_active_key: str | None = None

        self._normalize_all_entries()

        self._build_styles()
        self._build_layout()
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh_all()
        self._schedule_timer_tick()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=APP_BG)
        style.configure("Hero.TFrame", background=HERO_BG)
        style.configure("HeroPanel.TFrame", background="#111c33", relief="flat", borderwidth=0)
        style.configure("Card.TFrame", background=SURFACE, relief="flat", borderwidth=0)
        style.configure("Title.TLabel", background=HERO_BG, foreground="#f8fafc", font=("Segoe UI", 23, "bold"))
        style.configure("Subtitle.TLabel", background=HERO_BG, foreground="#cbd5e1", font=("Segoe UI", 10))
        style.configure("HeroTitle.TLabel", background=HERO_BG, foreground="#f8fafc", font=("Segoe UI", 23, "bold"))
        style.configure("HeroSubtitle.TLabel", background=HERO_BG, foreground="#cbd5e1", font=("Segoe UI", 10))
        style.configure("HeroChip.TLabel", background="#1f2a44", foreground="#f8fafc", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("HeroChip.TLabel", background=HERO_ACCENT, foreground=HERO_BG, font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("TimerChip.TLabel", background=HERO_ACCENT, foreground=HERO_BG, font=("Segoe UI", 11, "bold"), padding=(14, 7))
        style.configure("HeroPanelLabel.TLabel", background="#111c33", foreground="#93c5fd", font=("Segoe UI", 9, "bold"))
        style.configure("HeroPanelValue.TLabel", background="#111c33", foreground="#f8fafc", font=("Segoe UI", 15, "bold"))
        style.configure("HeroPanelBody.TLabel", background="#111c33", foreground="#e2e8f0", font=("Segoe UI", 12, "bold"), wraplength=360)
        style.configure("TimerMetric.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("SectionTitle.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 12, "bold"))
        style.configure("SectionMeta.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 12, "bold"))
        style.configure("Metric.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("MetricLabel.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Body.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Footer.TLabel", background=APP_BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8), background=PRIMARY, foreground="#ffffff")
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7), background=SURFACE, foreground=TEXT)
        style.configure("Treeview", rowheight=34, font=("Segoe UI", 10), background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=SURFACE_ALT, foreground=TEXT, relief="flat")
        style.map("Primary.TButton", background=[("active", PRIMARY_DARK)], foreground=[("active", "white")])
        style.map("TButton", background=[("active", "#eff6ff")])
        style.map("Treeview", background=[("selected", PRIMARY)], foreground=[("selected", "white")])

    def _build_layout(self) -> None:
        self.configure(background=APP_BG)

        header = ttk.Frame(self, style="Hero.TFrame", padding=(24, 22, 24, 18))
        header.pack(fill="x")
        header.columnconfigure(0, weight=3)
        header.columnconfigure(1, weight=2)

        header_left = ttk.Frame(header, style="Hero.TFrame")
        header_left.grid(row=0, column=0, sticky="nsew")

        ttk.Label(header_left, text="Daily Exercise Manager", style="HeroTitle.TLabel").pack(anchor="w")
        ttk.Label(
            header_left,
            text="A clean daily tracker for timed workouts, automatic completion, and skipped days that stay visible.",
            style="HeroSubtitle.TLabel",
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        hero_chips = ttk.Frame(header_left, style="Hero.TFrame")
        hero_chips.pack(anchor="w", pady=(14, 0))
        ttk.Label(hero_chips, textvariable=self.day_label, style="HeroChip.TLabel").pack(side="left")
        ttk.Label(hero_chips, textvariable=self.timer_text, style="TimerChip.TLabel").pack(side="left", padx=(10, 0))

        hero_panel = ttk.Frame(header, style="HeroPanel.TFrame", padding=(16, 14))
        hero_panel.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        hero_panel.columnconfigure(0, weight=1)

        ttk.Label(hero_panel, text="Selected date", style="HeroPanelLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(hero_panel, textvariable=self.day_label, style="HeroPanelValue.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 8))
        ttk.Label(
            hero_panel,
            textvariable=self.timer_text,
            style="HeroPanelBody.TLabel",
            justify="left",
        ).grid(row=2, column=0, sticky="w")

        body = ttk.Frame(self, style="App.TFrame", padding=(22, 14, 22, 22))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Card.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(4, weight=1)
        left.columnconfigure(0, weight=1)

        left_header = ttk.Frame(left, style="Card.TFrame")
        left_header.grid(row=0, column=0, sticky="ew")
        left_header.columnconfigure(1, weight=1)

        ttk.Label(left_header, text="Today at a glance", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(left_header, text="Quick summary and timer status for the selected day.", style="SectionMeta.TLabel").grid(row=0, column=1, sticky="e")

        metrics = ttk.Frame(left, style="Card.TFrame")
        metrics.grid(row=1, column=0, sticky="ew", pady=(12, 14))
        metrics.columnconfigure((0, 1), weight=1)

        self.total_metric = ttk.Label(metrics, text="0", style="Metric.TLabel")
        self.total_metric.grid(row=0, column=0, sticky="w")
        ttk.Label(metrics, text="planned exercises", style="MetricLabel.TLabel").grid(row=1, column=0, sticky="w")

        self.done_metric = ttk.Label(metrics, text="0", style="Metric.TLabel")
        self.done_metric.grid(row=0, column=1, sticky="w")
        ttk.Label(metrics, text="completed today", style="MetricLabel.TLabel").grid(row=1, column=1, sticky="w")
        self.timer_metric = ttk.Label(metrics, textvariable=self.timer_text, style="TimerMetric.TLabel", wraplength=360, justify="left")
        self.timer_metric.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 12))

        ttk.Separator(left, orient="horizontal").grid(row=3, column=0, sticky="ew", pady=(0, 12))

        day_controls = ttk.Frame(left, style="Card.TFrame")
        day_controls.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        day_controls.columnconfigure(1, weight=1)

        ttk.Label(day_controls, text="Selected date", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8), columnspan=2)
        ttk.Button(day_controls, text="Previous", command=self.previous_day).grid(row=1, column=0, sticky="w")
        day_entry = ttk.Entry(day_controls, textvariable=self.selected_day, width=16)
        day_entry.grid(row=1, column=1, sticky="ew", padx=(10, 10))
        ttk.Button(day_controls, text="Next", command=self.next_day).grid(row=1, column=2, sticky="e")
        ttk.Button(day_controls, text="Jump to Today", style="Primary.TButton", command=self.go_to_today).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        self.summary_label = ttk.Label(left, textvariable=self.summary_text, style="Body.TLabel", wraplength=360, justify="left")
        self.summary_label.grid(row=5, column=0, sticky="nw")

        right = ttk.Frame(body, style="Card.TFrame", padding=18)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        self.topbar = ttk.Frame(right, style="Card.TFrame")
        self.topbar.grid(row=0, column=0, sticky="ew")

        self.topbar_title = ttk.Label(self.topbar, text="Workouts for the selected day", style="CardTitle.TLabel")
        self.topbar_view_label = ttk.Label(self.topbar, text="View", style="SectionMeta.TLabel")
        self.topbar_view_picker = ttk.Combobox(self.topbar, textvariable=self.view_mode, values=("Day", "Calendar"), state="readonly", width=10)
        self.topbar_view_picker.bind("<<ComboboxSelected>>", lambda _event: self.refresh_all())
        self.topbar_add_button = ttk.Button(self.topbar, text="Add", style="Primary.TButton", command=self.add_entry)
        self.topbar_edit_button = ttk.Button(self.topbar, text="Edit", command=self.edit_entry)
        self.topbar_delete_button = ttk.Button(self.topbar, text="Delete", command=self.delete_entry)
        self.topbar_plus_button = ttk.Button(self.topbar, text="+1 Minute", command=self.add_one_minute)
        self.topbar_pause_button = ttk.Button(self.topbar, textvariable=self.pause_button_text, command=self.pause_entry)
        self.topbar_quit_button = ttk.Button(self.topbar, text="Quit", command=self.quit_entry)

        self._toolbar_widgets = [
            self.topbar_title,
            self.topbar_view_label,
            self.topbar_view_picker,
            self.topbar_add_button,
            self.topbar_edit_button,
            self.topbar_delete_button,
            self.topbar_plus_button,
            self.topbar_pause_button,
            self.topbar_quit_button,
        ]

        columns = ("exercise", "target", "done", "status", "notes")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", selectmode="browse")
        self.tree.grid(row=2, column=0, sticky="nsew", pady=(14, 0))

        self.tree.heading("exercise", text="Exercise")
        self.tree.heading("target", text="Target min")
        self.tree.heading("done", text="Done min")
        self.tree.heading("status", text="Status")
        self.tree.heading("notes", text="Notes")

        self.tree.column("exercise", width=220, anchor="w")
        self.tree.column("target", width=100, anchor="center")
        self.tree.column("done", width=100, anchor="center")
        self.tree.column("status", width=100, anchor="center")
        self.tree.column("notes", width=300, anchor="w")
        self.tree.tag_configure("day_complete", foreground=COMPLETE, background=COMPLETE_BG)
        self.tree.tag_configure("day_incomplete", foreground=SKIPPED, background=SKIPPED_BG)
        # subtle alternating row background to improve readability
        self.tree.tag_configure("alt", background="#fbfdff")
        self.tree.bind("<Double-1>", self.jump_to_selected_day)

        # Calendar grid container (hidden by default)
        self.calendar_frame = ttk.Frame(right, style="Card.TFrame")
        self.calendar_frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        self.calendar_frame.grid_remove()

        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns", pady=(14, 0))
        self.tree.configure(yscrollcommand=scrollbar.set)

        self._layout_toolbar(compact=False)

        footer = ttk.Label(
            self,
            text="Store your plan locally in exercise_data.json.",
            style="Footer.TLabel",
            padding=(22, 0, 22, 14),
        )
        footer.pack(anchor="w")

    def current_day(self) -> str:
        raw = self.selected_day.get().strip()
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            messagebox.showerror("Invalid date", "Use YYYY-MM-DD, for example 2026-05-20.")
            self.selected_day.set(today_iso())
            return today_iso()

    def entries_for_day(self, day: str | None = None) -> list[WorkoutEntry]:
        target_day = day or self.current_day()
        entries = []
        for item in self.data["entries"]:
            if item.get("day") == target_day:
                entries.append(WorkoutEntry(**item))
        return entries

    def _normalize_all_entries(self) -> bool:
        now = datetime.now()
        changed = False
        normalized_entries = []

        for raw_entry in self.data.get("entries", []):
            entry = WorkoutEntry(**raw_entry)
            if normalize_entry(entry, now=now):
                changed = True
            normalized_entries.append(asdict(entry))

        self.data["entries"] = normalized_entries
        if changed:
            save_data(self.data)
        return changed

    def _update_timer_text(self) -> None:
        day = self.current_day()

        if day != today_iso():
            self.timer_text.set("Timer is only active for today. Select today to watch the countdown.")
            return

        entries = self.entries_for_day(day)
        active_entries = [entry for entry in entries if not entry.completed and not entry.skipped]

        if not entries:
            self.timer_text.set("No workouts for today yet, so no timer is running.")
            return

        paused_entry = next((entry for entry in entries if entry.status == "paused" or entry.paused_at is not None), None)
        if paused_entry is not None:
            self.timer_text.set(f"{paused_entry.exercise} is paused. Resume it to continue the timer.")
            return

        if not active_entries:
            self.timer_text.set("All workouts for today are already green or skipped.")
            return

        active_entry = active_entries[0]
        started_at = parse_datetime(active_entry.started_at)
        if started_at is None:
            self.timer_text.set(f"Starting {active_entry.exercise}. {active_entry.target_minutes} min total.")
            return

        elapsed_seconds = max(0, int((datetime.now() - started_at).total_seconds()))
        remaining_seconds = max(0, active_entry.target_minutes * 60 - elapsed_seconds)
        elapsed_minutes, elapsed_remainder = divmod(elapsed_seconds, 60)

        if remaining_seconds == 0:
            self.timer_text.set(f"{active_entry.exercise} finished. Marked complete.")
            return

        remaining_minutes = (remaining_seconds + 59) // 60
        self.timer_text.set(f"Running {active_entry.exercise}: {elapsed_minutes}:{elapsed_remainder:02d} elapsed, {remaining_minutes} min left.")

    def _active_audio_entry(self) -> WorkoutEntry | None:
        if self.current_day() != today_iso():
            return None

        for entry in self.entries_for_day(today_iso()):
            if entry.completed or entry.skipped or entry.status == "paused" or entry.paused_at is not None:
                continue
            if parse_datetime(entry.started_at) is None:
                continue
            return entry
        return None

    def _audio_entry_key(self, entry: WorkoutEntry) -> str:
        started_at = entry.started_at or ""
        paused_at = entry.paused_at or ""
        return f"{entry.day}|{entry.exercise}|{started_at}|{paused_at}|{entry.status}"

    def _stop_audio_loop(self) -> None:
        if self._audio_process is not None:
            try:
                self._audio_process.terminate()
                self._audio_process.wait(timeout=2)
            except Exception:
                try:
                    self._audio_process.kill()
                except Exception:
                    pass
            self._audio_process = None
        self._audio_active_key = None

    def _start_audio_loop(self, entry: WorkoutEntry) -> None:
        if self._audio_process is not None:
            return
        if not AUDIO_FILE.exists():
            return

        audio_uri = AUDIO_FILE.resolve().as_uri()
        script = (
            "Add-Type -AssemblyName PresentationCore,WindowsBase; "
            "$player = New-Object System.Windows.Media.MediaPlayer; "
            "$player.Volume = 1.0; "
            "$player.add_MediaEnded({ param($sender, $eventArgs) $sender.Position = [TimeSpan]::Zero; $sender.Play() }); "
            f"$player.Open([Uri]::new('{audio_uri}')); "
            "$player.Play(); "
            "[System.Windows.Threading.Dispatcher]::Run()"
        )

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._audio_process = subprocess.Popen(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            self._audio_active_key = self._audio_entry_key(entry)
        except Exception:
            self._audio_process = None
            self._audio_active_key = None

    def _sync_audio_loop(self) -> None:
        entry = self._active_audio_entry()
        if entry is None:
            self._stop_audio_loop()
            return

        entry_key = self._audio_entry_key(entry)
        if self._audio_active_key != entry_key:
            self._stop_audio_loop()
            self._start_audio_loop(entry)

    def _schedule_timer_tick(self) -> None:
        self._timer_tick()
        self._timer_job = self.after(1000, self._schedule_timer_tick)

    def _timer_tick(self) -> None:
        if self._normalize_all_entries():
            self.refresh_summary()
            self.refresh_tree()
        self._update_timer_text()
        self._sync_audio_loop()

    def _on_close(self) -> None:
        if self._timer_job is not None:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
        self._stop_audio_loop()
        self.destroy()

    def current_view(self) -> str:
        view = self.view_mode.get().strip()
        return view if view in {"Day", "Calendar"} else "Day"

    def view_dates(self) -> list[date]:
        anchor = datetime.strptime(self.current_day(), "%Y-%m-%d").date()
        view = self.current_view()
        return [anchor]

    def view_label(self) -> str:
        dates = self.view_dates()
        if not dates:
            return self.current_day()
        if len(dates) == 1:
            return dates[0].isoformat()
        return f"{dates[0].isoformat()} to {dates[-1].isoformat()}"

    def upsert_entries(self, entries: list[WorkoutEntry], day: str | None = None) -> None:
        target_day = day or self.current_day()
        remaining = [item for item in self.data["entries"] if item.get("day") != target_day]
        remaining.extend(asdict(entry) for entry in entries)
        self.data["entries"] = remaining
        save_data(self.data)

    def refresh_all(self) -> None:
        self.refresh_summary()
        self.refresh_tree()
        self._update_timer_text()
        self._update_pause_button_text()

    def _on_resize(self, _event: tk.Event) -> None:
        if self.winfo_exists():
            self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        width = max(self.winfo_width(), 960)
        left_width = max(300, int(width * 0.38))
        right_width = max(520, width - left_width - 86)
        compact_toolbar = width < 1240

        self.summary_label.configure(wraplength=max(260, left_width - 60))
        self.timer_metric.configure(wraplength=max(260, left_width - 60))
        self.tree.column("exercise", width=max(180, int(right_width * 0.28)), stretch=True)
        self.tree.column("target", width=max(85, int(right_width * 0.11)), stretch=False)
        self.tree.column("done", width=max(85, int(right_width * 0.11)), stretch=False)
        self.tree.column("status", width=max(110, int(right_width * 0.15)), stretch=False)
        self.tree.column("notes", width=max(220, int(right_width * 0.35)), stretch=True)
        self._layout_toolbar(compact=compact_toolbar)
        self.update_idletasks()

    def _layout_toolbar(self, compact: bool) -> None:
        if not hasattr(self, "topbar"):
            return
        if compact == self._toolbar_compact:
            return

        for widget in self._toolbar_widgets:
            widget.grid_forget()

        for column in range(9):
            self.topbar.columnconfigure(column, weight=0)
        for row in range(3):
            self.topbar.rowconfigure(row, weight=0)

        if compact:
            self.topbar.rowconfigure(0, weight=0)
            self.topbar.rowconfigure(1, weight=0)
            self.topbar.rowconfigure(2, weight=0)
            for column in range(3):
                self.topbar.columnconfigure(column, weight=1)

            self.topbar_title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
            self.topbar_view_label.grid(row=0, column=3, sticky="e", padx=(18, 6), pady=(0, 8))
            self.topbar_view_picker.grid(row=0, column=4, sticky="w", pady=(0, 8))

            self.topbar_add_button.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
            self.topbar_edit_button.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
            self.topbar_delete_button.grid(row=1, column=2, sticky="ew", pady=(0, 8))
            self.topbar_plus_button.grid(row=2, column=0, sticky="ew", padx=(0, 8))
            self.topbar_pause_button.grid(row=2, column=1, sticky="ew", padx=(0, 8))
            self.topbar_quit_button.grid(row=2, column=2, sticky="ew")
        else:
            self.topbar.rowconfigure(0, weight=0)
            for column in range(9):
                self.topbar.columnconfigure(column, weight=1 if column >= 2 else 0)

            self.topbar_title.grid(row=0, column=0, sticky="w")
            self.topbar_view_label.grid(row=0, column=1, sticky="e", padx=(18, 6))
            self.topbar_view_picker.grid(row=0, column=2, sticky="ew")
            self.topbar_add_button.grid(row=0, column=3, sticky="ew", padx=(18, 8))
            self.topbar_edit_button.grid(row=0, column=4, sticky="ew", padx=(0, 8))
            self.topbar_delete_button.grid(row=0, column=5, sticky="ew", padx=(0, 8))
            self.topbar_plus_button.grid(row=0, column=6, sticky="ew", padx=(0, 8))
            self.topbar_pause_button.grid(row=0, column=7, sticky="ew", padx=(0, 8))
            self.topbar_quit_button.grid(row=0, column=8, sticky="ew")

        self._toolbar_compact = compact

    def _update_pause_button_text(self) -> None:
        day, entries, index = self.selected_entry_context()
        if index is None or index >= len(entries):
            self.pause_button_text.set("Pause")
            return

        entry = entries[index]
        if entry.status == "paused" or entry.paused_at is not None:
            self.pause_button_text.set("Resume")
        else:
            self.pause_button_text.set("Pause")

    def refresh_summary(self) -> None:
        day = self.current_day()
        entries = self.entries_for_day(day)
        total = len(entries)
        completed = sum(1 for entry in entries if entry.completed)
        skipped = sum(1 for entry in entries if entry.skipped)
        self.total_metric.configure(text=str(total))
        self.done_metric.configure(text=str(completed))

        week_start = datetime.strptime(day, "%Y-%m-%d").date() - timedelta(days=6)
        streak = 0
        for offset in range(7):
            check_day = (week_start + timedelta(days=offset)).isoformat()
            daily_entries = self.entries_for_day(check_day)
            if daily_entries and all(entry.completed for entry in daily_entries):
                streak += 1

        if total == 0:
            summary = "No workouts are planned for this date yet. Add a few exercises to start tracking progress."
        elif completed == total:
            summary = f"Great work. All {total} planned workouts for {day} are complete. Last 7-day streak score: {streak}/7."
        else:
            remaining = total - completed
            summary = f"{completed} of {total} workouts are complete for {day}. {remaining} still need time and {skipped} are skipped. Last 7-day streak score: {streak}/7."

        self.day_label.set(day)
        self.summary_text.set(summary + f" Current view: {self.current_view().lower()} view for {self.view_label()}.")

    def refresh_tree(self) -> None:
        selected_row = self.tree.selection()
        selected_iid = selected_row[0] if selected_row else None

        for row in self.tree.get_children():
            self.tree.delete(row)

        # hide both views; we'll show the one required
        try:
            self.tree.grid_remove()
        except Exception:
            pass
        try:
            self.calendar_frame.grid_remove()
        except Exception:
            pass

        view = self.current_view()

        if view == "Calendar":
            self._render_calendar()
            self.calendar_frame.grid()
            return

        if view == "Day":
            self.tree.configure(columns=("exercise", "target", "done", "status", "notes"))
            self.tree.heading("exercise", text="Exercise")
            self.tree.heading("target", text="Target min")
            self.tree.heading("done", text="Done min")
            self.tree.heading("status", text="Status")
            self.tree.heading("notes", text="Notes")
            self.tree.column("exercise", width=220, anchor="w")
            self.tree.column("target", width=100, anchor="center")
            self.tree.column("done", width=100, anchor="center")
            self.tree.column("status", width=100, anchor="center")
            self.tree.column("notes", width=300, anchor="w")

            for index, entry in enumerate(self.entries_for_day()):
                if entry.completed:
                    status = "Done"
                    row_tag = "day_complete"
                elif entry.skipped:
                    status = "Skipped"
                    row_tag = "day_incomplete"
                elif entry.status == "paused" or entry.paused_at is not None:
                    status = "Paused"
                    row_tag = "day_incomplete"
                else:
                    status = "Timer running" if parse_datetime(entry.started_at) else "Open"
                    row_tag = "day_incomplete"
                row_tags = [row_tag]
                if index % 2 == 1:
                    row_tags.append("alt")
                self.tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(entry.exercise, entry.target_minutes, entry.completed_minutes, status, entry.notes),
                    tags=tuple(row_tags),
                )
            self.tree.grid()
            active_iid = self._active_day_row_iid()
            target_iid = None
            if active_iid is not None:
                target_iid = active_iid
            elif selected_iid is not None and selected_iid in self.tree.get_children():
                target_iid = selected_iid

            if target_iid is not None and target_iid in self.tree.get_children():
                self.tree.selection_set(target_iid)
                self.tree.focus(target_iid)
                self.tree.see(target_iid)
            return

        self.tree.configure(columns=("day", "planned", "completed", "status", "focus"))
        self.tree.heading("day", text="Date")
        self.tree.heading("planned", text="Planned")
        self.tree.heading("completed", text="Completed")
        self.tree.heading("status", text="Status")
        self.tree.heading("focus", text="Focus / notes")
        self.tree.column("day", width=120, anchor="w")
        self.tree.column("planned", width=90, anchor="center")
        self.tree.column("completed", width=90, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("focus", width=320, anchor="w")

        for index, day_value in enumerate(self.view_dates()):
            day_key = day_value.isoformat()
            day_entries = self.entries_for_day(day_key)
            planned = len(day_entries)
            completed = sum(1 for entry in day_entries if entry.completed)
            skipped = sum(1 for entry in day_entries if entry.skipped)
            if planned == 0:
                status = "No workouts"
                row_tag = "day_incomplete"
            elif completed == planned:
                status = "Complete"
                row_tag = "day_complete"
            elif skipped > 0 and completed + skipped == planned:
                status = "Skipped"
                row_tag = "day_incomplete"
            else:
                status = f"{planned - completed} left"
                row_tag = "day_incomplete"
            focus = ", ".join(entry.exercise for entry in day_entries[:3]) if day_entries else ""
            if len(day_entries) > 3:
                focus = f"{focus}, +{len(day_entries) - 3} more"
            row_tags = [row_tag]
            if index % 2 == 1:
                row_tags.append("alt")
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(day_key, planned, completed, status, focus),
                tags=tuple(row_tags),
            )
        self.tree.grid()

    def _active_day_row_iid(self) -> str | None:
        if self.current_view() != "Day":
            return None

        for index, entry in enumerate(self.entries_for_day()):
            if entry.completed or entry.skipped:
                continue
            if entry.status == "paused" or entry.paused_at is not None or parse_datetime(entry.started_at) is not None:
                return str(index)
        return None

    def selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _on_calendar_click(self, day_date: date) -> None:
        self.selected_day.set(day_date.isoformat())
        self.view_mode.set("Day")
        self.refresh_all()

    def _render_calendar(self) -> None:
        for child in self.calendar_frame.winfo_children():
            child.destroy()

        anchor = datetime.strptime(self.current_day(), "%Y-%m-%d").date()
        year, month = anchor.year, anchor.month
        weeks = calendar.monthcalendar(year, month)

        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        header_font = ("Segoe UI", 10, "bold")
        cell_font = ("Segoe UI", 9)

        for col, wd in enumerate(weekdays):
            lbl = tk.Label(self.calendar_frame, text=wd, font=header_font, background="#fffaf2")
            lbl.grid(row=0, column=col, sticky="nsew", padx=2, pady=2)

        for r, week in enumerate(weeks, start=1):
            self.calendar_frame.grid_rowconfigure(r, weight=1)
            for c, day_num in enumerate(week):
                self.calendar_frame.grid_columnconfigure(c, weight=1)
                if day_num == 0:
                    placeholder = tk.Frame(self.calendar_frame, bg="#f5f5f5", bd=0)
                    placeholder.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
                    continue

                day_date = date(year, month, day_num)
                entries = self.entries_for_day(day_date.isoformat())
                planned = len(entries)
                completed = sum(1 for e in entries if e.completed)

                if planned == 0:
                    bg = "#ffffff"
                elif completed == planned:
                    bg = "#d1fae5"
                else:
                    bg = "#fee2e2"

                cell = tk.Frame(self.calendar_frame, bg=bg, bd=1, relief="solid")
                cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)

                day_lbl = tk.Label(cell, text=str(day_num), anchor="nw", font=cell_font, bg=bg)
                day_lbl.pack(anchor="nw", padx=4, pady=2)

                info = []
                if planned > 0:
                    info.append(f"{planned} planned")
                    info.append(f"{completed} done")
                info_text = "\n".join(info)
                info_lbl = tk.Label(cell, text=info_text, anchor="nw", justify="left", font=("Segoe UI", 8), bg=bg)
                info_lbl.pack(anchor="nw", padx=4, pady=(0, 4))

                # bind click to open day
                cell.bind("<Button-1>", lambda _e, d=day_date: self._on_calendar_click(d))
                day_lbl.bind("<Button-1>", lambda _e, d=day_date: self._on_calendar_click(d))
                info_lbl.bind("<Button-1>", lambda _e, d=day_date: self._on_calendar_click(d))

    def selected_row_day(self) -> str | None:
        index = self.selected_index()
        if index is None:
            return None
        values = self.tree.item(str(index), "values")
        if not values:
            return None
        if self.current_view() == "Day":
            return self.current_day()
        return str(values[0])

    def selected_entry_context(self) -> tuple[str, list[WorkoutEntry], int | None]:
        day = self.selected_row_day() or self.current_day()
        entries = self.entries_for_day(day)
        index = self.selected_index() if self.current_view() == "Day" else None
        return day, entries, index

    def choose_entry_index(self, day: str, entries: list[WorkoutEntry]) -> int | None:
        if not entries:
            messagebox.showinfo("Workout", f"No workouts exist for {day}.")
            return None

        if self.current_view() == "Day":
            index = self.selected_index()
            if index is None:
                messagebox.showinfo("Workout", "Select a workout first.")
                return None
            if index >= len(entries):
                return None
            return index

        if len(entries) == 1:
            return 0

        options = [f"{position + 1}. {entry.exercise}" for position, entry in enumerate(entries)]
        messagebox.showinfo("Select workout", "\n".join([f"Workouts for {day}:"] + options))
        choice = simpledialog.askinteger(
            "Select workout",
            f"Enter a workout number for {day} (1-{len(entries)}):",
            minvalue=1,
            maxvalue=len(entries),
            parent=self,
        )
        if choice is None:
            return None
        return choice - 1

    def jump_to_selected_day(self, _event: tk.Event) -> None:
        row_day = self.selected_row_day()
        if row_day is None:
            return
        self.selected_day.set(row_day)
        self.view_mode.set("Day")
        self.refresh_all()

    def ask_entry_values(self, default: WorkoutEntry | None = None, day: str | None = None) -> WorkoutEntry | None:
        entry_day = day or (default.day if default is not None else self.current_day())
        base = default or WorkoutEntry(day=entry_day, exercise="", target_minutes=30)
        exercise = simpledialog.askstring("Exercise", "Exercise name:", initialvalue=base.exercise, parent=self)
        if exercise is None:
            return None
        exercise = exercise.strip()
        if not exercise:
            messagebox.showerror("Missing exercise", "Exercise name cannot be empty.")
            return None

        target_minutes = simpledialog.askinteger(
            "Target minutes",
            "Target minutes (3 or more):",
            initialvalue=base.target_minutes,
            minvalue=3,
            maxvalue=1000,
            parent=self,
        )
        if target_minutes is None:
            return None

        notes = simpledialog.askstring("Notes", "Optional notes:", initialvalue=base.notes, parent=self)
        if notes is None:
            return None

        return WorkoutEntry(
            day=entry_day,
            exercise=exercise,
            target_minutes=target_minutes,
            completed_minutes=base.completed_minutes,
            notes=notes.strip(),
            status=base.status,
            started_at=base.started_at,
            paused_at=base.paused_at,
            completed_at=base.completed_at,
            skipped_at=base.skipped_at,
        )

    def add_entry(self) -> None:
        entry = self.ask_entry_values(day=self.current_day())
        if entry is None:
            return
        entries = self.entries_for_day()
        entries.append(entry)
        self.upsert_entries(entries, day=self.current_day())
    def edit_entry(self) -> None:
        day, entries, index = self.selected_entry_context()
        if index is None:
            index = self.choose_entry_index(day, entries)
        if index is None or index >= len(entries):
            return
        edited = self.ask_entry_values(entries[index], day=day)
        if edited is None:
            return
        entries[index] = edited
        self.selected_day.set(day)
        self.upsert_entries(entries, day=day)
        self.refresh_all()

    def delete_entry(self) -> None:
        day, entries, index = self.selected_entry_context()
        if index is None:
            index = self.choose_entry_index(day, entries)
        if index is None or index >= len(entries):
            return
        if not messagebox.askyesno("Delete workout", "Remove this workout from the selected day?"):
            return
        del entries[index]
        self.selected_day.set(day)
        self.upsert_entries(entries, day=day)
        self.refresh_all()

    def toggle_done(self) -> None:
        day, entries, index = self.selected_entry_context()
        if index is None:
            index = self.choose_entry_index(day, entries)
        if index is None or index >= len(entries):
            return
        entry = entries[index]
        normalize_entry(entry)
        entries[index] = entry
        self.selected_day.set(day)
        self.upsert_entries(entries, day=day)
        self.refresh_all()

    def _selected_active_entry(self) -> tuple[str, list[WorkoutEntry], int, WorkoutEntry] | None:
        day, entries, index = self.selected_entry_context()
        if index is None:
            index = self.choose_entry_index(day, entries)
        if index is None or index >= len(entries):
            return None
        entry = entries[index]
        if entry.completed or entry.skipped:
            messagebox.showinfo("Workout", "Select an open or running workout.")
            return None
        return day, entries, index, entry

    def add_one_minute(self) -> None:
        selected = self._selected_active_entry()
        if selected is None:
            return
        day, entries, index, entry = selected
        entry.target_minutes += 1
        entries[index] = entry
        self.selected_day.set(day)
        self.upsert_entries(entries, day=day)
        self.refresh_all()

    def pause_entry(self) -> None:
        selected = self._selected_active_entry()
        if selected is None:
            return
        day, entries, index, entry = selected
        if entry.status == "paused":
            entry.status = "open"
            entry.paused_at = None
        else:
            entry.status = "paused"
            entry.paused_at = datetime.now().isoformat(timespec="seconds")
        entries[index] = entry
        self.selected_day.set(day)
        self.upsert_entries(entries, day=day)
        self.refresh_all()

    def quit_entry(self) -> None:
        selected = self._selected_active_entry()
        if selected is None:
            return
        day, entries, index, entry = selected
        if not messagebox.askyesno("Quit workout", f"Stop tracking {entry.exercise} for {day}?"):
            return
        entry.status = "skipped"
        entry.completed_minutes = 0
        entry.paused_at = None
        entry.skipped_at = datetime.now().isoformat(timespec="seconds")
        entries[index] = entry
        self.selected_day.set(day)
        self.upsert_entries(entries, day=day)
        self.refresh_all()

    def go_to_today(self) -> None:
        self.selected_day.set(today_iso())
        self.refresh_all()

    def previous_day(self) -> None:
        anchor = datetime.strptime(self.current_day(), "%Y-%m-%d").date()
        day = anchor - timedelta(days=1)
        self.selected_day.set(day.isoformat())
        self.refresh_all()

    def next_day(self) -> None:
        anchor = datetime.strptime(self.current_day(), "%Y-%m-%d").date()
        day = anchor + timedelta(days=1)
        self.selected_day.set(day.isoformat())
        self.refresh_all()


def main() -> None:
    app = ExerciseManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()