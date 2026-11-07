import unittest

from oci_ootb_instance_power_scheduler.validate import validate_plan

WEEKDAYS = ["MO", "TU", "WE", "TH", "FR"]


def schedule(name, action, time="21:00", days=None, selector=None):
    return {
        "name": name,
        "action": action,
        "time_utc": time,
        "days": days or WEEKDAYS,
        "tag_selector": selector if selector is not None else {"env": "dev"},
    }


def instance(name, tags):
    return {"name": name, "tags": tags}


def paired_plan():
    return {
        "schedules": [
            schedule("stop", "STOP"),
            schedule("start", "START", time="08:00"),
        ],
        "instances": [instance("a", {"env": "dev", "schedule": "nightly"})],
    }


def rule_ids(findings):
    return {f.rule_id for f in findings}


class TestValidatePlan(unittest.TestCase):
    def test_clean_plan_has_no_findings(self):
        self.assertEqual(validate_plan(paired_plan()), [])

    def test_pow001_stop_without_start(self):
        plan = paired_plan()
        plan["schedules"] = [schedule("stop", "STOP")]
        self.assertIn("POW001", rule_ids(validate_plan(plan)))

    def test_pow001_start_on_other_days_not_paired(self):
        plan = paired_plan()
        plan["schedules"][1]["days"] = ["SA"]
        self.assertIn("POW001", rule_ids(validate_plan(plan)))

    def test_pow001_partial_overlap_is_paired(self):
        plan = paired_plan()
        plan["schedules"][1]["days"] = ["FR", "SA"]
        self.assertNotIn("POW001", rule_ids(validate_plan(plan)))

    def test_pow001_different_selector_not_paired(self):
        plan = paired_plan()
        plan["schedules"][1]["tag_selector"] = {"env": "qa"}
        plan["instances"].append(instance("q", {"env": "qa", "schedule": "nightly"}))
        self.assertIn("POW001", rule_ids(validate_plan(plan)))

    def test_pow002_tagged_instance_without_coverage(self):
        plan = paired_plan()
        plan["instances"].append(instance("b", {"env": "qa", "schedule": "nightly"}))
        self.assertIn("POW002", rule_ids(validate_plan(plan)))

    def test_pow002_untagged_instance_ignored(self):
        plan = paired_plan()
        plan["instances"].append(instance("prod", {"env": "prod"}))
        self.assertNotIn("POW002", rule_ids(validate_plan(plan)))

    def test_pow003_same_time_conflict(self):
        plan = paired_plan()
        plan["schedules"][1]["time_utc"] = plan["schedules"][0]["time_utc"]
        self.assertIn("POW003", rule_ids(validate_plan(plan)))

    def test_pow003_different_time_ok(self):
        plan = paired_plan()
        self.assertNotIn("POW003", rule_ids(validate_plan(plan)))

    def test_pow004_invalid_time(self):
        plan = paired_plan()
        plan["schedules"][0]["time_utc"] = "25:00"
        self.assertIn("POW004", rule_ids(validate_plan(plan)))

    def test_pow004_invalid_days(self):
        plan = paired_plan()
        plan["schedules"][0]["days"] = ["XX"]
        self.assertIn("POW004", rule_ids(validate_plan(plan)))

    def test_pow004_unknown_action(self):
        plan = paired_plan()
        plan["schedules"][0]["action"] = "PAUSE"
        self.assertIn("POW004", rule_ids(validate_plan(plan)))

    def test_pow005_selector_matches_nothing(self):
        plan = paired_plan()
        plan["schedules"].append(schedule("ghost", "STOP", selector={"env": "staging"}))
        self.assertIn("POW005", rule_ids(validate_plan(plan)))

    def test_findings_sorted_high_first(self):
        plan = paired_plan()
        plan["schedules"] = [schedule("stop", "STOP", time="25:00")]  # POW001 HIGH + POW004 LOW
        findings = validate_plan(plan)
        self.assertEqual(findings[0].severity, "HIGH")
        self.assertEqual(findings[-1].severity, "LOW")

    def test_missing_lists_rejected(self):
        with self.assertRaises(ValueError):
            validate_plan({"schedules": []})

    def test_non_object_entries_rejected(self):
        with self.assertRaises(ValueError):
            validate_plan({"schedules": ["junk"], "instances": []})


if __name__ == "__main__":
    unittest.main()
