# Reference growth tables (not shipped in this scaffold)

Drop LMS CSVs here and percentile bands light up. Nothing is fetched at runtime
— vendoring is what keeps the local-only promise true on a machine with no
internet, which is the machine most likely to want it.

## Expected columns

    sex,age_days,l,m,s

- `sex` — `f` or `m` (only the first character is read).
- `age_days` — age in days. Published tables are in months; convert with
  `age_days = months * 30.4375` and keep the conversion in the commit message.
- `l`, `m`, `s` — the published skewness, median and coefficient of variation.

## Where the data comes from

- **CDC, stature-for-age, 2–20 years** — the US clinical reference, and the one
  a paediatrician's chart is drawn from.
- **WHO, length/height-for-age, 0–2 years** — the standard below 2, where CDC
  does not apply and where measurement is *recumbent length*, not standing
  height. Mixing the two across the age-2 boundary without noting it produces a
  visible step that is a change of instrument, not of child.

Both are published by public health bodies and are redistributable, but
**confirm the licence text for the specific file you vendor** and record the
source URL, retrieval date and any unit conversion in a sibling `.source.md`.
A reference table with no provenance is not a reference.

## Naming

`cdc-stature-2-20.csv`, `who-height-0-2.csv`. The stem is what `load_table()`
takes.
