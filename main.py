#!/usr/bin/env python3

import datetime
import re
from collections import defaultdict
from typing import Set

import requests
from dateutil.parser import parse
from flask import Response
from prometheus_client import CollectorRegistry, Gauge, Histogram, generate_latest

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


class LocationsReport:
    registry: CollectorRegistry
    total_locations: Gauge
    total_reports: Gauge
    total_yesses: Gauge
    total_nos: Gauge
    ago_hours: Histogram

    seen_ages: Set[int]
    now: datetime.datetime

    def __init__(self):
        self.registry = CollectorRegistry()
        self.total_locations = Gauge(
            "locations_total_total", "Total number of locations", registry=self.registry
        )
        self.total_reports = Gauge(
            "locations_reports_total", "Total number of reports", registry=self.registry
        )
        self.total_yeses = Gauge(
            "locations_yeses_total",
            "Total number of 'Yes' reports",
            labelnames=["walkin", "min_age"],
            registry=self.registry,
        )
        self.total_nos = Gauge(
            "locations_nos_total",
            "Total number of 'No' reports",
            labelnames=["why"],
            registry=self.registry,
        )
        self.ago_hours = Histogram(
            "locations_report_stale_hours",
            "How long ago the report came",
            buckets=range(0, 24 * 7 * 3, 6),
            labelnames=["yes"],
            registry=self.registry,
        )
        self.seen_ages = set()
        self.now = datetime.datetime.now(datetime.timezone.utc)

    def serve(self):
        response = requests.get("https://api.vaccinateca.com/v1/locations.json")
        response.raise_for_status()

        data = response.json()
        self.total_locations.set(len(data["content"]))
        yeses = {True: defaultdict(int), False: defaultdict(int)}
        nos = defaultdict(int)
        for loc in data["content"]:
            self.observe_location(loc, yeses, nos)

        for walkin in (True, False):
            for age in ["None"] + sorted(self.seen_ages):
                self.total_yeses.labels(walkin, age).set(yeses[walkin][age])
        for reason in ["No: other"] + no_reasons:
            self.total_nos.labels(reason[4:].capitalize()).set(nos[reason])
        return Response(generate_latest(registry=self.registry), mimetype="text/plain")

    def observe_location(self, loc, yeses, nos):
        if not bool(loc["Has Report"]):
            return

        self.total_reports.inc()

        info = loc.get("Availability Info", [])
        is_yes = bool(loc["Latest report yes?"])
        terminal_no = False
        if is_yes:
            walkin = "Yes: walk-ins accepted" in info
            age = "None"
            for tag in sorted(info):
                maybe_age_tag = re.match(r"Yes: vaccinating (\d+)\+", tag)
                if maybe_age_tag:
                    age = maybe_age_tag.group(1)
                    self.seen_ages.add(age)
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
            self.ago_hours.labels(is_yes).observe(
                (self.now - latest).total_seconds() / 60 / 60
            )


def serve(request):
    LocationsReport().serve()


def main():
    print(LocationsReport().serve().get_data().decode("utf-8"))


if __name__ == "__main__":
    main()
