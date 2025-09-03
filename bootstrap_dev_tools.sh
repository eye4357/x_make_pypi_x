#!/usr/bin/env bash
# Shell bootstrap: run from the repo root
python -m pip install -U -r requirements-dev.txt
python -m pre_commit install
python -m pre_commit run --all-files
