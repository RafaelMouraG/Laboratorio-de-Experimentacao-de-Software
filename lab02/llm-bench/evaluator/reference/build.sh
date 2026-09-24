#!/bin/sh
# Referência só com biblioteca padrão: não há dependências a baixar.
set -eu
cd "$(dirname "$0")"
python3 -m py_compile app.py
