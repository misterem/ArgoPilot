# Judgment log

## Unknown `farm_id` in a plot body

- **Agent suggested:** `422 VALIDATION` with detail `Unknown farm`, the same as an unknown crop, soil, or emitter. `404` was rejected because the URL itself (`/v1/plots`) exists; only a field inside the body is wrong.
- **Decided:** `422 VALIDATION`, detail `Unknown farm`, on both POST and PATCH (`_check_references` in `plots.py`).
- **Why:** `404` would suggest that the requested resource is missing, but `/v1/plots` exists. The request is well formed and points at a farm that doesn't exist, which is what `422` covers. Treating `farm_id` the same as `crop_id`, `soil_id` and `emitter_id` gives clients one rule for all bad references.

## `GET /v1/plots?farm_id=` for a farm that does not exist

- **Agent suggested:** `200 []`, following "No rows means `200` and `[]`", rather than checking the farm and returning `404`.
- **Decided:** `200 []`. The farm is not looked up, and `farm_id` is not validated as a UUID here, so any value without matching plots returns `[]` (`list_plots` in `plots.py`).
- **Why:** The spec says that no rows means `200` and `[]`, and a filter is a query over a collection, not a lookup of the farm. It also keeps the list endpoint to a single query, with no extra farm lookup.
## Response body of `GET /v1/farms/{id}/area`

- **Agent suggested:** `{"farm_id": "<id>", "area_m2": <sum>}`. The unit is in the field name, like `Plot.area_m2`, and echoing `farm_id` makes the body self-describing. A bare `{"area_m2": ...}` is the minimal alternative.
- **Decided:**
- **Why:**

## `GET /v1/farms/{id}/area` for a farm with no plots, and for an unknown farm

- **Agent suggested:** a farm that exists but has no plots returns `200` with `area_m2: 0`, since the farm is there and the sum of nothing is zero. An unknown farm returns `404 NOT_FOUND`, because the id is in the path (unlike the `?farm_id=` filter entry above, which is a query over a collection, not a lookup of one farm).
- **Decided:**
- **Why:**
