#!/bin/sh
# Mantém o servidor em primeiro plano; exec repassa o SIGTERM direto ao Python.
set -eu
cd "$(dirname "$0")"
exec python3 app.py
