import json
from typing import Any


class JsonFormatter:
    def format(self, data: Any) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False)
