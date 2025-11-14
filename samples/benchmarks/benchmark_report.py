import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlparse

from savant_rs.py.log import get_logger, init_logging

REPORT_PATH = os.environ.get("REPORT_PATH", None)
SERVER_METRICS_PROMETHEUS_ENDPOINT = os.environ.get(
    "SERVER_METRICS_PROMETHEUS_ENDPOINT", None
)
CLIENT_METRICS_PROMETHEUS_ENDPOINT = os.environ.get(
    "CLIENT_METRICS_PROMETHEUS_ENDPOINT", None
)
DURATION = os.environ.get("DURATION", "60")

logger = get_logger(os.path.basename(__file__))


@dataclass
class PrometheusMetric:
    id: str
    name: str
    attributes: defaultdict[str, str]
    value: float

    @classmethod
    def parse(cls, line: str) -> PrometheusMetric:
        id, val = line.split(maxsplit=2)
        name, attrs = id.rstrip("}").split("{") if "{" in id else (id, "")
        attributes = {
            name: val.strip('"')
            for name, val in (attr.split("=") for attr in attrs.split(",") if attr)
        }
        return cls(
            id=id, name=name, attributes=defaultdict(str, attributes), value=float(val)
        )


@dataclass
class Report:
    duration: timedelta
    drops: float
    messages: float
    messages_per_sec: float
    data_size: float
    data_size_per_sec: float
    delay_average: float
    delay_ratio_histogram: list[tuple[tuple[float, float], float]]


def fetch_prometheus_data(prometheus_endpoint: str) -> dict[str, PrometheusMetric]:
    url = urlparse(prometheus_endpoint)
    conn = HTTPConnection(url.netloc)
    conn.request("GET", url.path)
    response = conn.getresponse()
    metrics = (
        PrometheusMetric.parse(line)
        for line in response.read().decode().splitlines()
        if line and not line.startswith("#")
    )
    return {metric.id: metric for metric in metrics}


def diff(
    start_data: dict[str, PrometheusMetric], end_data: dict[str, PrometheusMetric]
) -> dict[str, PrometheusMetric]:
    ids = {*start_data.keys(), *end_data.keys()}
    nulls = {id: PrometheusMetric.parse(f"{id} 0") for id in ids}
    return {
        id: PrometheusMetric(
            id=id,
            name=start_data.get(id, null).name,
            attributes=start_data.get(id, null).attributes,
            value=end_data.get(id, null).value - start_data.get(id, null).value,
        )
        for id, null in nulls.items()
    }


def build_report(
    start: datetime,
    start_data: dict[str, PrometheusMetric],
    end: datetime,
    end_data: dict[str, PrometheusMetric],
) -> Report:
    duration = end - start
    data = diff(start_data, end_data)
    drops = 0.0
    messages = 0.0
    data_size = 0.0
    delay_sum = 0.0
    delay_count = 0.0
    delay_buckets = defaultdict[float, float](float)

    for metric in data.values():
        attrs = metric.attributes
        match metric.name:
            case "ws_read_drops_total":
                drops += metric.value
            case "messages_total" if (
                attrs["service"] == "Client" and attrs["socket"] == "Sink"
            ):
                messages += metric.value
            case "message_size_sum" if (
                attrs["service"] == "Client" and attrs["socket"] == "Sink"
            ):
                data_size += metric.value
            case "delay_sum" if attrs["path_start"] == attrs["path_end"] == "Client":
                delay_sum += metric.value
            case "delay_count" if attrs["path_start"] == attrs["path_end"] == "Client":
                delay_count += metric.value
            case "delay_bucket" if attrs["path_start"] == attrs["path_end"] == "Client":
                boundary = float(attrs["le"])
                delay_buckets[boundary] += metric.value

    delay_bucket_boundaries = [0.0, *delay_buckets.keys()]
    delay_bucket_boundaries.sort()
    delay_ratio_histogram = [
        ((lower, upper), (delay_buckets[upper] - delay_buckets[lower]) / delay_count)
        for lower, upper in zip(delay_bucket_boundaries, delay_bucket_boundaries[1:])
    ]
    return Report(
        duration=duration,
        drops=drops,
        messages=messages,
        messages_per_sec=messages / duration.total_seconds(),
        data_size=data_size,
        data_size_per_sec=data_size / duration.total_seconds(),
        delay_average=delay_sum / delay_count,
        delay_ratio_histogram=delay_ratio_histogram,
    )


def fix_report_owner(path: Path) -> None:
    expected = os.stat(__file__)
    current = os.stat(path)
    if current.st_uid == expected.st_uid and current.st_gid == expected.st_gid:
        return
    os.chown(path.parent, expected.st_uid, expected.st_gid)
    os.chown(path, expected.st_uid, expected.st_gid)


def save_report(path: Path, report: Report) -> None:
    report_content = "Benchmark Report:\n\n"
    report_content += f"Duration: {report.duration}\n"
    report_content += f"Message Drops: {report.drops}\n"
    report_content += f"Total Messages: {report.messages}\n"
    report_content += f"Messages per Second: {report.messages_per_sec}\n"
    report_content += f"Total Data transferred: {report.data_size}\n"
    report_content += f"Data per Second: {report.data_size_per_sec}\n"
    report_content += f"Average Message Delay: {report.delay_average}\n"

    report_content += "Message Delay Histogram:\n"
    for (lower, upper), ratio in report.delay_ratio_histogram:
        bar = "▇" * int(30 * ratio)
        report_content += f" {bar:30} {ratio:10.4%} ( {lower:.4} ; {upper:.4} ]\n"

    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as file:
        file.write(report_content)

    fix_report_owner(path)


def monitor_and_report(
    path: Path,
    duration: float,
    server_prometheus_endpoint: str,
    client_prometheus_endpoint: str,
) -> None:
    start = datetime.now()
    start_data = {
        **fetch_prometheus_data(server_prometheus_endpoint),
        **fetch_prometheus_data(client_prometheus_endpoint),
    }

    time.sleep(duration)

    end = datetime.now()
    end_data = {
        **fetch_prometheus_data(server_prometheus_endpoint),
        **fetch_prometheus_data(client_prometheus_endpoint),
    }

    report = build_report(start, start_data, end, end_data)
    save_report(path, report)


if __name__ == "__main__":
    init_logging()
    assert (
        REPORT_PATH
        and SERVER_METRICS_PROMETHEUS_ENDPOINT
        and CLIENT_METRICS_PROMETHEUS_ENDPOINT
    )
    monitor_and_report(
        path=Path(REPORT_PATH),
        duration=float(DURATION),
        server_prometheus_endpoint=SERVER_METRICS_PROMETHEUS_ENDPOINT,
        client_prometheus_endpoint=CLIENT_METRICS_PROMETHEUS_ENDPOINT,
    )
