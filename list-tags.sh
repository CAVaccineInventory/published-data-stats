#!/bin/sh

curl -o - https://api.vaccinateca.com/v1/locations.json | jq -r '.content[] | ."Availability Info" | select(.) | .[]' | sort | uniq -c
