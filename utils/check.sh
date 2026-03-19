#!/usr/bin/env bash
cd src
ruff format && ruff check &&
mypy --strict --strict --strict main.py