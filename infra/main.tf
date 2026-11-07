# OCI Resource Scheduler wiring for the power workflow (template; NOT applied).
#
# Resource Scheduler is the out-of-the-box OCI feature that starts and stops
# resources on a recurrence, with no custom poller or cron host to run. This
# template creates a nightly STOP / morning START pair for dev-tagged
# instances. The local validator in src/ checks a schedule plan against an
# instance inventory before anything is applied.
#
# This file has NOT been plan/apply validated against a tenancy - it is a
# structural template. Review against the current provider docs before any
# real apply.

terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
  }
}

variable "compartment_ocid" {
  type        = string
  description = "OCID of the compartment that owns the schedules"
}

variable "instance_ocids" {
  type        = list(string)
  description = "OCIDs of the dev instances to power-schedule"
}

resource "oci_resource_schedule_schedule" "dev_nightly_stop" {
  compartment_id = var.compartment_ocid
  display_name   = "dev-nightly-stop"
  action         = "STOP"

  recurrence {
    recurrence_type    = "ICAL"
    recurrence_details = "FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=15;BYMINUTE=30"
  }

  dynamic "resources" {
    for_each = var.instance_ocids
    content {
      id = resources.value
    }
  }
}

resource "oci_resource_schedule_schedule" "dev_morning_start" {
  compartment_id = var.compartment_ocid
  display_name   = "dev-morning-start"
  action         = "START"

  recurrence {
    recurrence_type    = "ICAL"
    recurrence_details = "FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=2;BYMINUTE=30"
  }

  dynamic "resources" {
    for_each = var.instance_ocids
    content {
      id = resources.value
    }
  }
}
