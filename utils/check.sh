#!/usr/bin/env bash
cd rolltv
ruff format && ruff check &&
mypy --strict --strict --strict main.py