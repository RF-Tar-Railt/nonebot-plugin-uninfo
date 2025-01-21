from datetime import datetime, timedelta
import json


class DatetimeJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return int(obj.timestamp())
        elif isinstance(obj, timedelta):
            return obj.total_seconds()
        return json.JSONEncoder.default(self, obj)


if __name__ == "__main__":
    data = {
        "1": datetime.now(),
        "2": timedelta(days=1),
        "3": {"4": datetime.now(), "5": timedelta(days=1)},
        "4": [datetime.now(), timedelta(days=1)],
    }
    print(json.dumps(data, cls=DatetimeJsonEncoder))
