from datetime import datetime, timedelta
import json


class DatetimeJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return int(obj.timestamp())
        elif isinstance(obj, timedelta):
            return obj.total_seconds()
        return json.JSONEncoder.default(self, obj)
