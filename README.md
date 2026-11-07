# oci-ootb-instance-power-scheduler

An out-of-the-box OCI cost workflow: **stop dev instances at night and start them in the morning with OCI Resource Scheduler, and validate the schedule plan before applying it**. Resource Scheduler is OCI's built-in feature for starting/stopping resources on a recurrence - no cron host or custom poller to run. This repo wires the built-in part (Terraform) and adds the missing safety part: a local validator that catches the plans that strand instances or do nothing.

## What it is

Two pieces:

1. **`infra/main.tf`** - Terraform template for a nightly STOP / morning START schedule pair over dev instances, using `oci_resource_schedule_schedule` with iCal recurrence.
2. **`src/`** - an offline validator. It reads a static JSON plan (schedule definitions plus an instance inventory) and reports coverage gaps, STOP schedules with no matching START, same-time START/STOP conflicts, malformed times/days, and dead selectors. Exit code 2 on HIGH findings, so a broken plan can be gated in CI.

## What it is NOT (honest limits)

- The Terraform template has **not** been plan/apply validated against a tenancy. It is a structural starting point; review it against the current OCI provider docs before any real apply.
- The validator consumes a **static JSON plan** (schema below). It does not call the OCI API; building the plan from live schedules and a live inventory is out of scope here.
- Coverage is tag-selector matching only (exact key=value); it does not evaluate the full iCal recurrence language. STOP/START pairing requires the same selector and at least one overlapping day.
- The `schedule=nightly` tag convention for "this instance should be scheduled" is local, not an OCI convention.
- No live resources, cost, or tenancy data are involved in any run of this repo.

## Input schema

```json
{
  "schedules": [
    {
      "name": "dev-nightly-stop",
      "action": "STOP",
      "time_utc": "15:30",
      "days": ["MO", "TU", "WE", "TH", "FR"],
      "tag_selector": {"env": "dev"}
    }
  ],
  "instances": [
    {"name": "dev-app-1", "tags": {"env": "dev", "schedule": "nightly"}}
  ]
}
```

`action` must be START or STOP; `days` uses two-letter codes MO..SU.

## Rules

| Rule | Severity | Finding |
| --- | --- | --- |
| POW001 | HIGH | STOP schedule with no START for the same selector on any overlapping day; stopped instances never come back |
| POW002 | MEDIUM | Instance tagged `schedule=...` but covered by no schedule selector |
| POW003 | MEDIUM | START and STOP fire at the same time on overlapping days for the same selector |
| POW004 | LOW | Malformed time, invalid day codes, or unknown action |
| POW005 | LOW | Selector matches no instance; the schedule does nothing |

## Run

Requires Python 3.10+, no third-party dependencies.

```sh
PYTHONPATH=src python3 -m oci_ootb_instance_power_scheduler samples/broken-power-plan.json
PYTHONPATH=src python3 -m oci_ootb_instance_power_scheduler samples/corrected-power-plan.json
```

Or the end-to-end demo (broken plan -> corrected plan, with expected exit codes):

```sh
sh demo.sh
```

Expected demo output: the broken plan reports 2 high, 2 medium, 3 low findings and exits 2; the corrected plan reports zero findings and exits 0.

## Test

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

20 unit tests cover every rule on positive and negative inputs, selector/day pairing logic, conflict detection, malformed-input handling, and CLI exit codes. CI runs the same tests plus the demo on Python 3.10/3.11/3.12.
