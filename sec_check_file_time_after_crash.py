from pathlib import Path
from datetime import datetime


CRASH_TIME_YEAR = 2000
CRASH_TIME_MONTH = 1
CRASH_TIME_DAY = 1
CRASH_TIME_HOURS = 1
CRASH_TIME_MINUTES = 1


def check_time_diff(timestamp):
    t = datetime.fromtimestamp(timestamp)
    return CRASH_TIME_YEAR == t.year and CRASH_TIME_MONTH == t.month and CRASH_TIME_DAY == t.day and CRASH_TIME_HOURS == t.hour and (t.minute -1 <= CRASH_TIME_MINUTES <= t.minute + 3)


for path in Path("C:\\").glob("**/*"):
  stats = path.stat()
  if check_time_diff(stats.st_atime) or check_time_diff(stats.st_mtime) or check_time_diff(stats.st_ctime):
    print(path)
