#!/usr/bin/env bash
# Runs the whole ML pipeline: prepare -> train -> evaluate -> baselines -> ONNX
# Extra arguments are passed to the training script, e.g. ./run_pipeline.sh --epochs 20
set -e
cd "$(dirname "$0")"
python scripts/02_prepare_data.py
python scripts/03_train.py "$@"
python scripts/04_evaluate.py
python scripts/05_baselines.py
python scripts/06_export_onnx.py
echo "Pipeline finished. Start the website with ./start_app.sh"
