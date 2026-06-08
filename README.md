# Daily Exercise Manager

A lightweight Windows desktop app for planning workouts, checking off completion, and tracking day-by-day progress.

## Features

- Pick a date and manage its workout plan
- Add, edit, delete, and mark workouts complete
- Each workout starts a timer for the selected day and turns green only after the minimum timer finishes
- When today's workout timer starts, `audio.mp3` loops in the background until the active workout ends
- Workouts left unfinished after the day passes are marked skipped in red
- View simple progress counts and a recent streak summary
- Stores data locally in `exercise_data.json`

## Run

```powershell
python exercise_manager.py
```

Or double-click `Open Exercise Manager.bat` to launch it like a normal desktop app.

## Open Like A Desktop App

1. Right-click `Open Exercise Manager.bat`.
2. Select `Send to` -> `Desktop (create shortcut)`.
3. Use that desktop shortcut to open the app anytime.

Optional: Right-click the shortcut and choose `Pin to Start`.

## Notes

- Audio playback uses Windows PowerShell and WPF media APIs, so this feature is Windows-only.
- Date input uses `YYYY-MM-DD`.
- Target minutes must be 3 or more so the timer rule stays above the 2-minute minimum.