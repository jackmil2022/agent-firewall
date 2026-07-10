#!/usr/bin/env python
from __future__ import annotations

import json
import sys


payload = json.load(sys.stdin)
print(json.dumps({"ok": True, "goal": payload.get("goal", ""), "correction": payload.get("correction", "")}))
