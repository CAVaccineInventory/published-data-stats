#!/bin/sh

set -eu

gcloud functions deploy summary-stats \
	--project cavaccineinventory \
	--entry-point serve \
	--runtime python38 \
	--trigger-http --allow-unauthenticated \
	--service-account monitoring@cavaccineinventory.iam.gserviceaccount.com \
	--source=.
