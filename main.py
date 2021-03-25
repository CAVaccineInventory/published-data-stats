#!/usr/bin/env python3

import datetime
from collections import defaultdict

import requests
from dateutil.parser import parse
from flask import Response
from prometheus_client import CollectorRegistry, Gauge, Histogram, generate_latest

ages = [16, 18, 50, 65, 70, 75, 80, 85]

no_reasons = [
    "No: incorrect contact information",
    "No: location permanently closed",
    "No: may be a vaccination site in the future",
    "No: no vaccine inventory",
    "No: not open to the public",
    "No: only vaccinating health care workers",
    "No: only vaccinating staff",
    "No: will never be a vaccination site",
]

# We consider a no with these reasons (more or less) final.
terminal_no_reasons = set(
    [
        "No: location permanently closed",
        "No: will never be a vaccination site",
    ]
)


def serve(request):
    registry = CollectorRegistry()
    total_locations = Gauge(
        "locations_total_total", "Total number of locations", registry=registry
    )
    total_reports = Gauge(
        "locations_reports_total", "Total number of reports", registry=registry
    )
    total_yeses = Gauge(
        "locations_yeses_total",
        "Total number of 'Yes' reports",
        labelnames=["walkin", "min_age"],
        registry=registry,
    )
    total_nos = Gauge(
        "locations_nos_total",
        "Total number of 'No' reports",
        labelnames=["why"],
        registry=registry,
    )
    ago_hours = Histogram(
        "locations_report_stale_hours",
        "How long ago the report came",
        buckets=range(0, 24 * 7 * 3, 6),
        labelnames=["yes"],
        registry=registry,
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    response = requests.get("https://api.vaccinateca.com/v1/locations.json")
    response.raise_for_status()

    data = response.json()
    total_locations.set(len(data["content"]))
    reports = 0
    yeses = {True: defaultdict(int), False: defaultdict(int)}
    nos = defaultdict(int)
    for loc in data["content"]:
        if bool(loc["Has Report"]):
            reports += 1
            info = loc.get("Availability Info", [])
            is_yes = bool(loc["Latest report yes?"])
            terminal_no = False
            if is_yes:
                walkin = "Yes: walk-ins accepted" in info
                age = "None"
                for possible_age in ages:
                    if f"Yes: vaccinating {possible_age}+" in info:
                        age = possible_age
                        break
                yeses[walkin][age] += 1
            else:
                for reason in no_reasons:
                    if reason in info:
                        nos[reason] += 1
                        if reason in terminal_no_reasons:
                            terminal_no = True
                        break

            # We only care about freshness for non-terminal nos.
            if not terminal_no:
                latest = parse(loc["Latest report"])
                ago_hours.labels(is_yes).observe(
                    (now - latest).total_seconds() / 60 / 60
                )

    total_reports.set(reports)
    for walkin in (True, False):
        for age in ["None"] + ages:
            total_yeses.labels(walkin, age).set(yeses[walkin][age])
    for reason in ["No: other"] + no_reasons:
        total_nos.labels(reason[4:].capitalize()).set(nos[reason])
    return Response(generate_latest(registry=registry), mimetype="text/plain")


def main():
    print(serve(None).get_data().decode("utf-8"))


if __name__ == "__main__":
    main()
