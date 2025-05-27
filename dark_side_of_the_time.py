from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import DefaultDict
import csv
import io
import os

DARK_SIDE_OF_THE_TIME_DATA_FILE_ENV = "DARK_SIDE_OF_THE_TIME_DATA_FILE"
DARK_SIDE_OF_THE_TIME_SCHEMA_FILE_ENV = "DARK_SIDE_OF_THE_TIME_SCHEMA_FILE"
DATE_FORMAT = "%b %d"
YEAR_DATE_TIME_FORMAT = f"%Y {DATE_FORMAT} %H:%M"


@dataclass
class Activity:
    start: datetime
    end: datetime
    activity_type: str

    @classmethod
    def deserialize(cls, dirty_values: dict[str, str], schema: str) -> "Activity":
        cls.validate_csv(dirty_values)
        values = {k.strip(): v.strip() for k, v in dirty_values.items()}
        activity_type = values["activity_type"].strip()
        if activity_type not in schema:
            raise ValueError(f"Activity type '{activity_type}' not found in schema.")

        year_str = values["year"].strip()
        date_str = values["date"].strip()
        time_start = values["time_start"].strip()
        time_end = values["time_end"].strip()
        if not time_end:
            time_end = time_start
        date_start_str = f"{year_str} {date_str} {time_start}"
        date_end_str = f"{year_str} {date_str} {time_end}"

        return cls(
            start=datetime.strptime(date_start_str, YEAR_DATE_TIME_FORMAT),
            end=datetime.strptime(date_end_str, YEAR_DATE_TIME_FORMAT),
            activity_type=activity_type,
        )

    def get_break_duration_in_minutes(self, previous: "Activity") -> int:
        break_duration = int((self.start - previous.end).total_seconds() / 60)
        assert break_duration >= 0
        return break_duration

    def get_duration_in_minutes(self) -> int:
        duration = int((self.end - self.start).total_seconds() / 60)
        assert duration >= 0
        return duration

    @staticmethod
    def validate_csv(dirty_values: dict[str, str]) -> None:
        values = {k.strip(): v for k, v in dirty_values.items()}
        required_fields = ["year", "date", "time_start", "activity_type"]
        for field in required_fields:
            assert field in values and values[field], (
                f"Missing required field: '{field}'"
            )


def main():
    activities = read_activities()
    output = "\n".join(
        [
            create_total_activity_report(activities),
            "",
            create_previous_week_activity_report(activities),
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
        duration = activity.get_duration_in_minutes()
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
        duration = activity.get_duration_in_minutes()
        break_duration = (
            0
            if i == 0
            else activity.get_break_duration_in_minutes(today_activities[i - 1])
        )
        output.append(
            f"| {start} | {end} | {duration} | {break_duration} "
            f"| {activity.activity_type} |"
        )

    total_duration = get_total_duration(today_activities) / 60.0
    total_break_duration = get_total_break_duration(today_activities) / 60.0
    output.append("")
    output.append(f"**Total Duration:** {total_duration:.2f}h")
    output.append(f"**Total Break Duration:** {total_break_duration:.2f}h")
    return "\n".join(output)


def create_previous_week_activity_report(activities: list[Activity]) -> str:
    if not activities:
        return ""
    week_activities = get_last_week_activities(activities)

    total_duration = get_total_duration(week_activities) / 60.0
    total_break_duration = get_total_break_duration(week_activities) / 60.0
    output = [
        "# Last Week",
        "",
        create_activity_duration_report(week_activities),
        "",
        f"**Total Duration:** {total_duration:.2f}h",
        f"**Total Break Duration:** {total_break_duration:.2f}h",
    ]
    return "\n".join(output)


def create_total_activity_report(activities: list[Activity]) -> str:
    if not activities:
        return ""

    total_duration = get_total_duration(activities) / 60.0
    total_break_duration = get_total_break_duration(activities) / 60.0
    output = [
        "# Total",
        "",
        create_activity_duration_report(activities),
        "",
        f"**Total Duration:** {total_duration:.2f}h",
        f"**Total Break Duration:** {total_break_duration:.2f}h",
    ]
    return "\n".join(output)


def create_weekly_activity_report(activities: list[Activity]) -> str:
    if not activities:
        return ""
    week_activities = get_this_week_activities(activities)

    total_duration = get_total_duration(week_activities) / 60.0
    total_break_duration = get_total_break_duration(week_activities) / 60.0
    output = [
        "# This Week",
        "",
        create_activity_duration_report(week_activities),
        "",
        f"**Total Duration:** {total_duration:.2f}h",
        f"**Total Break Duration:** {total_break_duration:.2f}h",
    ]
    return "\n".join(output)


def get_daily_activities(activities: list[Activity]) -> list[Activity]:
    last_date = activities[-1].start.date()
    return [x for x in activities if x.start.date() == last_date]


def get_date_at_midnight(date: datetime) -> datetime:
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def get_days_since_sunday(date: datetime) -> int:
    return (date.weekday() + 1) % 7


def get_last_week_activities(activities: list[Activity]) -> list[Activity]:
    date = activities[-1].start
    sunday = get_sunday_before(date)
    previous_sunday = sunday - timedelta(days=7)
    return [x for x in activities if previous_sunday <= x.start < sunday]


def get_sunday_before(date: datetime) -> datetime:
    return get_date_at_midnight(date - timedelta(days=get_days_since_sunday(date)))


def get_this_week_activities(activities: list[Activity]) -> list[Activity]:
    date = activities[-1].start
    sunday = get_sunday_before(date)
    return [x for x in activities if sunday <= x.start]


def get_total_break_duration(activities: list[Activity]) -> int:
    total_break_duration = 0
    for i, activity in enumerate(activities[1:], start=1):
        previous = activities[i - 1]
        if activity.start.date() == previous.end.date():
            total_break_duration += activity.get_break_duration_in_minutes(previous)
    return total_break_duration


def get_total_duration(activities: list[Activity]) -> int:
    return sum(x.get_duration_in_minutes() for x in activities)


if __name__ == "__main__":
    main()
