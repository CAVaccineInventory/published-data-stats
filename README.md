# published-table-stats

This is a stateless Cloud Function which fetches the current state of
the published data from `api.vaccinateca.com` and provides a
Prometheus-formatted summary of the data.

Making the Prometheus collector stateless removes all `rate()` calls
from graphs based on its data, since the numbers are always
point-in-time values.  This is usual for gauges, but unusual for
histograms, which are expected to be accumulators.

## Running locally

Since the function is stateless, and only accesses public data, it's
very easy to test locally:

```
python3 -mvenv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py
```

## Deploying

The included `deploy.sh` script deploys the script.
