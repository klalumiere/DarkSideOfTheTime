from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import DefaultDict
import csv
import io
import os

DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV = "DARK_SIDE_OF_THE_TIME_DATA_FILE"
DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV = "DARK_SIDE_OF_THE_TIME_SCHEMA_FILE"
DATE_FORMAT = "%b %d"
DATE_TIME_FORMAT = f"{DATE_FORMAT} %H:%M"


@dataclass
class Activity:
    start: datetime
    end: datetime
    activity_type: str

    @classmethod
    def deserialize(cls, dirty_values: dict[str, str], schema: str) -> "Activity":
        values = {k.strip(): v.strip() for k, v in dirty_values.items()}
        activity_type = values["activity_type"].strip()
        if activity_type not in schema:
            raise ValueError(f"Activity type '{activity_type}' not found in schema.")

        date_str = values["date"].strip()
        time_end = values["time_end"].strip()
        if not time_end:
            time_end = values["time_start"].strip()
        date_start_str = f"{date_str} {values['time_start'].strip()}"
        date_end_str = f"{date_str} {time_end}"

        return cls(
            start=datetime.strptime(date_start_str, DATE_TIME_FORMAT),
            end=datetime.strptime(date_end_str, DATE_TIME_FORMAT),
            activity_type=activity_type,
        )


def main():
    activities = read_activities()
    output = "\n".join(
        [
            create_total_activity_report(activities),
            "",
            create_weekly_activity_report(activities),
            "",
            create_daily_activity_report(activities),
        ]
    )
    print(output)


def read_activities() -> list[Activity]:
    data_str = os.environ.get(DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV)
    schema_str = os.environ.get(DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV)
    data_csv = Path(data_str).read_text() if data_str else None
    schema = Path(schema_str).read_text() if schema_str else None
    if not data_csv:
        print(
            f"You need to define the environment variable {DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV}"
            " to a valid data file path."
        )
        exit(1)
    if not schema:
        print(
            f"You need to define the environment variable {DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV}"
            " to a valid schema file path."
        )
        exit(1)
    return [
        Activity.deserialize(x, schema) for x in csv.DictReader(io.StringIO(data_csv))
    ]


def create_activity_duration_report(activities: list[Activity]) -> str:
    if not activities:
        return ""

    activity_totals: DefaultDict[str, int] = defaultdict(int)
    total_duration = 0
    for activity in activities:
        duration = int((activity.end - activity.start).total_seconds() / 60)
        activity_totals[activity.activity_type] += duration
        total_duration += duration

    output = [
        "| Activity Type | Total Duration (h) | Relative Duration |",
        "|---------------|--------------------|-------------------|",
    ]
    sorted_activity_totals = sorted(
        activity_totals.items(), key=lambda x: x[1], reverse=True
    )
    for activity_type, duration in sorted_activity_totals:
        output.append(
            f"| {activity_type} | {duration / 60.0:.2f}"
            f"| {duration / total_duration:.2f} |"
        )
    return "\n".join(output)


def create_daily_activity_report(activities: list[Activity]) -> str:
    if not activities:
        return ""
    last_start = activities[-1].start
    output = [
        f"# {last_start.strftime(DATE_FORMAT)}",
        "",
        "| Start | End | Duration (min) | Break Duration (min) | Activity Type |",
        "|-------|-----|---------------|-----------------------|---------------|",
    ]

    today_activities = get_daily_activities(activities)
    for i, activity in enumerate(today_activities):
        start = activity.start.strftime("%H:%M")
        end = activity.end.strftime("%H:%M")
        duration = int((activity.end - activity.start).total_seconds() / 60)
        if i == 0:
            break_duration = 0
        else:
            previous = today_activities[i - 1]
            break_duration = int((activity.start - previous.end).total_seconds() / 60)
        output.append(
            f"| {start} | {end} | {duration} | {break_duration} "
            f"| {activity.activity_type} |"
        )

    total_duration = get_total_duration(today_activities) / 60.0
    total_break_duration = get_total_break_duration(today_activities) / 60.0
    output.append("")
    output.append(f"**Total Duration:** {total_duration :.2f}h")
    output.append(f"**Total Break Duration:** {total_break_duration:.2f}h")
    return "\n".join(output)


def create_total_activity_report(activities: list[Activity]) -> str:
    if not activities:
        return ""

    total_duration = get_total_duration(activities) / 60.0
    total_break_duration = get_total_break_duration(activities) / 60.0
    output = [
        f"# Total",
        "",
        create_activity_duration_report(activities),
        "",
        f"**Total Duration:** {total_duration :.2f}h",
        f"**Total Break Duration:** {total_break_duration:.2f}h",
    ]
    return "\n".join(output)


def create_weekly_activity_report(activities: list[Activity]) -> str:
    if not activities:
        return ""
    _, last_week, _ = activities[-1].start.isocalendar()
    week_activities = get_weekly_activities(activities)

    total_duration = get_total_duration(week_activities) / 60.0
    total_break_duration = get_total_break_duration(week_activities) / 60.0
    output = [
        f"# Week {last_week}",
        "",
        create_activity_duration_report(week_activities),
        "",
        f"**Total Duration:** {total_duration :.2f}h",
        f"**Total Break Duration:** {total_break_duration:.2f}h",
    ]
    return "\n".join(output)


def get_daily_activities(activities: list[Activity]) -> list[Activity]:
    last_start = activities[-1].start
    return [x for x in activities if x.start.date() == last_start.date()]


def get_total_break_duration(activities: list[Activity]) -> int:
    total_break_duration = 0
    if not activities:
        return total_break_duration

    for i, activity in enumerate(activities):
        if i == 0:
            break_duration = 0
        else:
            previous = activities[i - 1]
            if activity.start.date() != previous.end.date():
                continue
            break_duration = int((activity.start - previous.end).total_seconds() / 60)
        total_break_duration += break_duration

    return total_break_duration


def get_total_duration(activities: list[Activity]) -> int:
    total_duration = 0
    if not activities:
        return total_duration

    for activity in activities:
        duration = int((activity.end - activity.start).total_seconds() / 60)
        total_duration += duration

    return total_duration


def get_weekly_activities(activities: list[Activity]) -> list[Activity]:
    last_start = activities[-1].start
    last_year, last_week, _ = last_start.isocalendar()
    return [
        x
        for x in activities
        if (x.start.isocalendar()[0], x.start.isocalendar()[1])
        == (last_year, last_week)
    ]


if __name__ == "__main__":
    main()
