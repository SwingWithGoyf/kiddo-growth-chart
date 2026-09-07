# kiddo-growth-chart

An interactive height chart for your kids. **Bring your own data**, everything
stays on your machine, and photo sources are plugins.

Two views over one dataset:

- **By year** — four lines on a calendar axis. Who is tallest now, and when did
  they pass each other.
- **By age** — the same points replotted at `date − dob`, superimposing the
  childhoods. How did each kid compare *at age 8*.

…plus a **video mode** that steps through the measurements and lets each kid
spring taller as their own next measurement lands.

```bash
pip install -e .
python -m kiddo_growth_chart              # runs on the bundled sample family
python -m kiddo_growth_chart --dataset ~/kids.json --photos ~/Pictures/kids
```

Open <http://127.0.0.1:8461/>. With no dataset configured it renders an invented
family so you can see what it does before writing any config.

## Your data

One JSON file. Nothing else, and it never leaves your disk.

```json
{
  "kids": [
    {
      "key": "ada",
      "name": "Ada",
      "dob": "2011-03-14",
      "sex": "f",
      "photo_person_id": "ada",
      "measurements": [
        { "date": "2019-03-25", "value": 49.5, "unit": "in", "method": "clinical" },
        { "date": "2020-04-02", "cm": 131.4, "method": "doorframe" }
      ]
    }
  ]
}
```

Point the app at it with `--dataset` or `$KIDDO_DATASET`.

**Record `method` honestly.** It is not bookkeeping: shoes are worth about 2 cm
and a spine compresses roughly 1 cm between morning and night, both *larger*
than a real quarter of growth in a school-age kid. A series that quietly mixes
methods shows spurts and shrinkage that never happened, so measurements taken
differently are drawn differently — hollow marks, dashed segments — rather than
being averaged into a tidy lie.

Heights are stored canonically in centimetres with the source value and unit
preserved, because a bare `4` with the unit lost is unrecoverable later.

## Photo sources are plugins

The interface is two calls wide:

```python
people()                          # identities this source knows about
photo_for(person_id, start, end)  # one photo of them in that window, or None
```

Two ship in the box.

`folder` reads `<root>/<person>/<year>/*.jpg`, taking dates from the filename,
else the year directory, else mtime — preferring whichever is best known rather
than whichever is nearest, so a date guessed from a folder never outranks one
stated in a filename.

`immich` talks to an [Immich](https://immich.app) server. A kid's
`photo_person_id` is an Immich person UUID, and because Immich stores a bounding
box per detected face, this provider fills in the face box that `folder` cannot.
Point it at a server and an API key from Account Settings → API Keys:

```json
{
  "provider": "immich",
  "provider_options": {
    "url": "https://immich.example.com",
    "api_key_env": "IMMICH_API_KEY"
  }
}
```

Run with `--config that.json`. The key is read from the environment so it stays
out of the file; `api_key` sets it inline instead. A rejected key raises rather
than returning `None`, because "no photo of this kid that year" is exactly how a
misconfiguration would otherwise hide behind a plausible chart. Timeouts and
server errors do return `None`. Visit `/providers.json` to list the person UUIDs
to bind your kids to.

Write your own by subclassing `PhotoProvider` and advertising it:

```toml
[project.entry-points."kiddo_growth_chart.providers"]
myserver = "my_package.provider:MyProvider"
```

Two rules the interface takes seriously:

- **A face box is optional.** Cropping to a face is what makes a matched-age row
  read as a comparison instead of four unrelated snapshots — but a folder of
  photos has no faces, and a renderer that *required* a box would make the
  plugin model theatre. Return `None` and the renderer centre-crops.
- **`None` is a real answer.** Coverage is always thinnest in the earliest
  years, which is exactly where the matched-age view is most interesting. A
  provider must never widen its window to find something: in a graphic whose
  whole premise is matched age, an off-by-four-years portrait is a lie that
  reads as data. The chart draws the point with no portrait instead.

Photos are **proxied** through the app, never linked, so a provider's
credentials stay in the server process and never reach the page.

## Embedding it in a site you already run

It is a Flask blueprint, so an existing app mounts it at a path it already
serves — no extra port, no new firewall or ACL grant:

```python
from kiddo_growth_chart.config import Config
from kiddo_growth_chart.web import blueprint

app.register_blueprint(
    blueprint(Config(provider="folder", provider_options={"root": "/srv/photos"})),
    url_prefix="/heights",
)
```

## Local by construction

The only network traffic is whatever *your* configured photo provider makes on
your behalf. No CDN fonts or scripts, no telemetry, no reference data fetched at
runtime — `tests/test_local_only.py` fails the build on an outbound socket or a
third-party URL in any asset, because this is the one claim the project's whole
audience is choosing it for.

Percentile bands are computed locally from **vendored** LMS tables (see
`src/kiddo_growth_chart/growth/tables/README.md`); none ship in this scaffold, so
bands stay off until you add one. They default to off regardless — a family
keepsake and a clinical percentile are different objects.

## Nothing here interpolates

A smooth curve through four points a year apart invents the *shape* of a spurt
nobody measured, so the chart joins measurements with straight segments and
draws the measurements as marks. Video mode is the same rule in motion: a value
**holds** until the next real measurement and then springs — and the spring is
applied to the figure only. The ruler and the readout snap, because the peak of
an overshoot is a height that never existed.

For the same reason each kid steps on **their own** measurement dates. Visit
dates differ, so springing all four on a shared beat would assert that four
children grew at the same moment.

## Development

```bash
pip install -e ".[dev]"
pytest
python sample/make_sample.py      # regenerate the invented family
```

**Never commit real data.** The sample family is invented, `/data/` and
`*.local.json` are gitignored, and a dataset belongs at a runtime path outside
this tree. Git keeps what you later delete, and here that would be children's
names, dates of birth and clinical measurements.

Bug reports: please describe the *shape* of your data — counts, date ranges, a
redacted row — rather than attaching photos of your kids.

## Licence

MIT. See [LICENSE](LICENSE).
