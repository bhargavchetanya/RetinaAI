#!/usr/bin/env bash
# Unattended training: trains all epochs, auto-resumes if training crashes or
# freezes (watchdog), then runs evaluation, baselines and ONNX export.
# Everything is logged to reports/overnight_log.txt
#
# Usage (from the RetinaAI folder, venv active):
#   caffeinate -dimsu bash scripts/train_overnight.sh
cd "$(dirname "$0")/.."
LOG=reports/overnight_log.txt
mkdir -p reports
echo "===== START $(date) =====" | tee -a "$LOG"

python scripts/03_train.py --num-workers 2 --patience 20 "$@" 2>&1 | tee -a "$LOG"
status=${PIPESTATUS[0]}
attempt=1
while [ "$status" -ne 0 ] && [ "$attempt" -lt 8 ]; do
  attempt=$((attempt + 1))
  echo "===== training stopped (exit $status) – resuming, attempt $attempt, $(date) =====" | tee -a "$LOG"
  sleep 20
  python scripts/03_train.py --num-workers 0 --patience 20 --resume true "$@" 2>&1 | tee -a "$LOG"
  status=${PIPESTATUS[0]}
done
if [ "$status" -ne 0 ]; then
  echo "===== TRAINING FAILED after $attempt attempts $(date) =====" | tee -a "$LOG"
  exit 1
fi

for s in 04_evaluate 05_baselines 06_export_onnx; do
  echo "===== $s $(date) =====" | tee -a "$LOG"
  python scripts/$s.py 2>&1 | tee -a "$LOG"
done
echo "===== ALL DONE $(date) =====" | tee -a "$LOG"
