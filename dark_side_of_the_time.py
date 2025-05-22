from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Tuple
import csv
import io
import os

DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV = "DARK_SIDE_OF_THE_TIME_DATA_FILE"
DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV = "DARK_SIDE_OF_THE_TIME_SCHEMA_FILE"


@dataclass
class Activity:
    date: str
    start: datetime
    end: datetime
    activity_type: str

    @classmethod
    def deserialize(cls, dirty_string: dict[str, str], schema: str) -> "Activity":
        string = {k.strip(): v.strip() for k, v in dirty_string.items()}
        activity_type = string["activity_type"].strip()
        time_end = string["time_end"].strip()
        if not time_end:
            time_end = string["time_start"].strip()
        if activity_type not in schema:
            raise ValueError(f"Activity type '{activity_type}' not found in schema.")
        return cls(date=string["date"].strip(),
                   start=datetime.strptime(string["time_start"].strip(), "%H:%M"),
                   end=datetime.strptime(time_end, "%H:%M"),
                   activity_type=activity_type)


def main():
    activities = read_activities()
    output = "\n".join([
        create_report_of_today_activities(activities)
    ])
    print(output)


def read_activities() -> list[Activity]:
    data_str = os.environ.get(DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV)
    schema_str = os.environ.get(DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV)
    data_csv = Path(data_str).read_text() if data_str else None
    schema = Path(schema_str).read_text() if schema_str else None
    if not data_csv:
        print(f"You need to define the environment variable {DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV}"
            " to a valid data file path.")
        exit(1)
    if not schema:
        print(f"You need to define the environment variable {DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV}"
            " to a valid schema file path.")
        exit(1)
    return [Activity.deserialize(x, schema) for x in csv.DictReader(io.StringIO(data_csv))]

def create_report_of_today_activities(activities = list[Activity]) -> str:
    if not activities:
        return ""
    last_date = activities[-1].date
    output = [
        f"# {last_date}",
        "",
        "| Start | End | Duration (min) | Break Duration (min) | Activity Type |",
        "|-------|-----|---------------|-----------------------|---------------|",
    ]

    today_activities = [x for x in activities if x.date == last_date]
    total_duration = 0
    total_break_duration = 0
    for i, activity in enumerate(today_activities):
        start = activity.start.strftime("%H:%M")
        end = activity.end.strftime("%H:%M")
        duration = int((activity.end - activity.start).total_seconds() / 60)
        if i == 0:
            break_duration = 0
        else:
            previous = today_activities[i - 1]
            break_duration = int((activity.start - previous.end).total_seconds() / 60)
        output.append(f"| {start} | {end} | {duration} | {break_duration} "
                      f"| {activity.activity_type} |")
        total_duration += duration
        total_break_duration += break_duration

    output.append("")
    output.append(f"**Total Duration:** {total_duration / 60:.2f}h")
    output.append(f"**Total Break Duration:** {total_break_duration / 60:.2f}h")
    return "\n".join(output)




if __name__ == "__main__":
    main()
