# CSV copies of the 2026-11-12 model diagnostics

93 CSV tables, 629674357 bytes in total. Every CSV corresponds to one existing Parquet with the same relative path and stem. The original Parquet files and original scientific results are retained.

- `curves/` (including nested controls): per-epoch curves and the already exported diagnostic endpoint predictions.
- `predictions/` (including controls and `r0_reconstruction/`): molecule/atom predictions, truth and identifiers.
- `features/` and `features_observed/`: the already exported dimensional statistics.

Encoding is UTF-8 with BOM; delimiter comma; standard CSV quoting. `CSV_MANIFEST.json` lists every source Parquet, destination, row count, byte count, column order and Arrow type. Null is `\N`; a scalar string beginning with backslash gains one leading backslash (remove it when interpreting a string column). Lists/dictionaries use JSON within one quoted cell. Finite floats use their shortest round-trip decimal representation; NaN/Infinity/-Infinity are explicit tokens. These are format conversions only: no new fitting, statistical aggregation, rescoring or review/readback of exports.

The largest CSV is 23970587 bytes, so all files are below the50MB compression threshold and are delivered directly as `.csv`. The original T1 snapshot scope is unchanged. U0 tables and native training logs are outside these three requested families.
