"""Validation logic for Resource Scheduler power schedules.

OCI Resource Scheduler is the built-in OCI feature that starts and stops
resources on a recurrence. This module works on a static JSON plan: schedule
definitions (action, time, days, tag selector) plus an instance inventory.
It checks that every instance meant to be scheduled is covered, that STOP
schedules have a matching START, and that schedules do not conflict. All
analysis is offline; no OCI calls.
"""

import re
from dataclasses import dataclass

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# Tag that marks an instance as meant to be power-scheduled.
SCHEDULE_TAG = "schedule"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    subject: str
    message: str


def _selector_key(selector):
    return tuple(sorted((selector or {}).items()))


def _matches(selector, tags):
    return all(tags.get(k) == v for k, v in (selector or {}).items())


def _valid_schedule_shape(schedule):
    """POW004: time format, day codes, action values."""
    findings = []
    name = schedule.get("name", "<unnamed>")
    if schedule.get("action") not in ("START", "STOP"):
        findings.append(Finding("POW004", "LOW", name, f"unknown action '{schedule.get('action')}'; expected START or STOP"))
    time_utc = schedule.get("time_utc") or ""
    if not TIME_RE.match(time_utc):
        findings.append(Finding("POW004", "LOW", name, f"invalid time_utc '{time_utc}'; expected HH:MM 24-hour UTC"))
    days = schedule.get("days")
    if not isinstance(days, list) or not days or any(d not in DAYS for d in days):
        findings.append(Finding("POW004", "LOW", name, f"invalid days {days!r}; expected a non-empty list of MO..SU"))
    return findings


def validate_plan(document):
    if not isinstance(document, dict):
        raise ValueError("document must be an object")
    schedules = document.get("schedules")
    instances = document.get("instances")
    if not isinstance(schedules, list) or not isinstance(instances, list):
        raise ValueError("document must contain 'schedules' and 'instances' lists")
    for schedule in schedules:
        if not isinstance(schedule, dict):
            raise ValueError("each schedule entry must be an object")
    for instance in instances:
        if not isinstance(instance, dict):
            raise ValueError("each instance entry must be an object")

    findings = []
    for schedule in schedules:
        findings.extend(_valid_schedule_shape(schedule))

    # POW005: selector that matches no instance (dead schedule).
    for schedule in schedules:
        selector = schedule.get("tag_selector") or {}
        matched = [i for i in instances if _matches(selector, i.get("tags") or {})]
        if not matched:
            findings.append(Finding("POW005", "LOW", schedule.get("name", "<unnamed>"),
                                    f"selector {selector} matches no instance in the inventory; the schedule does nothing"))

    # POW001: STOP coverage without a paired START on overlapping days.
    stops = [s for s in schedules if s.get("action") == "STOP"]
    starts = [s for s in schedules if s.get("action") == "START"]
    for stop in stops:
        stop_days = set(stop.get("days") or [])
        paired = any(
            _selector_key(s.get("tag_selector")) == _selector_key(stop.get("tag_selector"))
            and stop_days & set(s.get("days") or [])
            for s in starts
        )
        if not paired:
            findings.append(Finding("POW001", "HIGH", stop.get("name", "<unnamed>"),
                                    "STOP schedule has no START schedule for the same tag selector on any overlapping day; stopped instances never come back"))

    # POW002: instances marked for scheduling but covered by no schedule.
    for instance in instances:
        tags = instance.get("tags") or {}
        if not tags.get(SCHEDULE_TAG):
            continue
        covered = any(_matches(s.get("tag_selector") or {}, tags) for s in schedules)
        if not covered:
            findings.append(Finding("POW002", "MEDIUM", instance.get("name", "<unnamed>"),
                                    f"tagged '{SCHEDULE_TAG}={tags[SCHEDULE_TAG]}' but no schedule selector covers it"))

    # POW003: conflicting schedules on the same selector, day and time.
    for i, first in enumerate(schedules):
        for second in schedules[i + 1:]:
            if _selector_key(first.get("tag_selector")) != _selector_key(second.get("tag_selector")):
                continue
            if first.get("action") == second.get("action"):
                continue
            if first.get("time_utc") == second.get("time_utc") and set(first.get("days") or []) & set(second.get("days") or []):
                findings.append(Finding("POW003", "MEDIUM", f"{first.get('name', '<unnamed>')} / {second.get('name', '<unnamed>')}",
                                        f"START and STOP fire at {first.get('time_utc')} on overlapping days for the same selector; the outcome is undefined"))

    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id, f.subject, f.message))
