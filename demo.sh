#!/bin/sh
# Validates the seeded broken plan and the corrected plan.
set -u
export PYTHONPATH="$(dirname "$0")/src"

echo "=== Validating samples/broken-power-plan.json ==="
python3 -m oci_ootb_instance_power_scheduler samples/broken-power-plan.json
echo "exit code: $? (2 = high-severity findings present, expected for the seeded plan)"
echo
echo "=== Validating samples/corrected-power-plan.json ==="
python3 -m oci_ootb_instance_power_scheduler samples/corrected-power-plan.json
echo "exit code: $? (0 = no high-severity findings, expected for the corrected plan)"
