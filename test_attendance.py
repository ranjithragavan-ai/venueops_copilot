import datetime
start_time_iso = "2026-07-13T14:55:51.358730+00:00"
try:
    start_dt = datetime.datetime.fromisoformat(start_time_iso)
    now = datetime.datetime.now(datetime.timezone.utc)
    if now >= start_dt:
        current_attendance = 100000
    else:
        time_remaining = (start_dt - now).total_seconds()
        elapsed_in_window = 1800 - time_remaining
        if elapsed_in_window < 0:
            current_attendance = 0
        else:
            fill_percentage = elapsed_in_window / 1800
            current_attendance = int(100000 * fill_percentage)
    print("Success:", current_attendance)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Error:", repr(e))
