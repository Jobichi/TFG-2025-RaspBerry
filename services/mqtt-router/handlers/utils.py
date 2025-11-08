import json
from datetime import datetime, date

def safe_json_dumps(obj):
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.strftime("%Y-%m-%d %H:%M:%S")

        raise TypeError(f"Type {type(o)} not serializable")

    return json.dumps(obj, default=default)
