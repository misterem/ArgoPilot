---
name: irrigation-calc-reference
description: Use when computing or coding anything about crop water need or irrigation scheduling in AgroPilot (planner-service, drip planner) — ETo, ETc, crop coefficient Kc, growth stages, Kc curve, TAW, RAW, depletion Dr, water stress Ks, deep percolation, daily soil water balance, when to irrigate and how much, tomato or bell/sweet pepper values, FAO-56 / FAO Paper 56, Annex 8. Also use when checking such a calculation or test value by hand.
---

# Irrigation calculation reference (FAO-56)

The planner's domain is FAO Irrigation and Drainage Paper 56. Use the formulas, units and conventions below as given; do not re-derive them or pull values from memory. The full research note, with every source and caveat, is [services/planner-service/docs/research/fao56.md](../../../services/planner-service/docs/research/fao56.md) (cited below as **fao56.md §n**). Read the relevant section there before deciding anything this page marks as **open**.

FAO writes ETo (subscript o). Equation, table and figure numbers are FAO's own.

## Units

| Symbol | Meaning | Unit |
|---|---|---|
| ETo | reference evapotranspiration (FAO Penman-Monteith) | mm/day |
| ETc, ETc adj | crop ET, unstressed / stress-adjusted | mm/day |
| Kc, Kcb, Ke, Ks | crop, basal, evaporation, stress coefficients | dimensionless |
| i | day number since planting, 1…season length | day |
| L ini, L dev, L mid, L late | stage lengths | days |
| u2 | mean daily wind speed at 2 m | m/s |
| RHmin | mean daily minimum relative humidity | % (e.g. 30, not 0.30) |
| h | mean crop height | m |
| θFC, θWP | soil water at field capacity / wilting point | m³/m³ |
| available water | θFC − θWP expressed per metre of soil | mm/m (= 1000·(θFC − θWP)) |
| Zr | rooting depth | m |
| TAW, RAW, Dr | total / readily available water, root-zone depletion | mm |
| p (also MAD) | fraction of TAW usable without stress | fraction 0–1 |
| P, RO, I, CR, DP | rain, runoff, net irrigation, capillary rise, deep percolation | mm/day, **net, averaged over the whole field** |
| fw | fraction of the soil surface wetted | fraction (trickle 0.3–0.4, Table 20) |

## Formulas

**Crop water need** (Ch. 5 Eq. 56 = Ch. 6 Eq. 58): `ETc = Kc · ETo`

**Kc on day i** (Ch. 6 Eq. 66): `Kc_i = Kc_prev + ((i − ΣL_prev) / L_stage) · (Kc_next − Kc_prev)`
- Initial stage: Kc = Kc ini (flat). Development: Kc ini → Kc mid. Mid-season: Kc mid (flat). Late: Kc mid → Kc end.
- ΣL_prev is the sum of the lengths of all stages before the current one.

**Climate adjustment** (Ch. 6 Eq. 62 for Kc mid, Eq. 65 for Kc end, same form):
`Kc = Kc(Tab) + [0.04(u2 − 2) − 0.004(RHmin − 45)] · (h/3)^0.3`
- Valid for 1 ≤ u2 ≤ 6 m/s, 20 ≤ RHmin ≤ 80 %, 0.1 < h < 10 m. Use stage means (mid-season for Kc mid, late season for Kc end).
- Apply Eq. 65 only when Kc end(Tab) ≥ 0.45.

**Kc ini under drip** (Ch. 6): Eq. 61 `Iw = I / fw`, then pick from Fig. 29 (≤ 10 mm) / Fig. 30 (≥ 40 mm), interpolating with Eq. 59; then Eq. 60 `Kc ini = fw · Kc ini(fig)`. The figures are graphs only (fao56.md §1.6).

**Soil bucket** (Ch. 8):
- Eq. 82 `TAW = 1000 · (θFC − θWP) · Zr`
- Eq. 83 `RAW = p · TAW`
- p adjustment (Ch. 8, Table 22 fn 2): `p = p(Table 22) + 0.04 · (5 − ETc)`, clamp 0.1 ≤ p ≤ 0.8. FAO allows either a constant p or this daily adjustment (**open**, fao56.md §5.3). The choice can flip whether a day is stressed, so always state which one you used.
- Eq. 84 `Ks = (TAW − Dr) / (TAW − RAW)` when Dr > RAW, else Ks = 1
- Eq. 81 `ETc adj = Ks · Kc · ETo` (single Kc); Eq. 80 `ETc adj = (Ks · Kcb + Ke) · ETo` (dual Kc)

**Daily balance** (Ch. 8):
- Eq. 85 `Dr,i = Dr,i−1 − (P − RO)_i − I_i − CR_i + ETc,i + DP_i`
- Eq. 86 `0 ≤ Dr,i ≤ TAW`
- Eq. 88 `DP_i = (P − RO)_i + I_i − ETc,i − Dr,i−1`, floored at 0
- Eq. 87 initial `Dr = 1000 · (θFC − θ) · Zr`, or Dr ≈ 0 after heavy rain/irrigation
- Rain below 0.2 · ETo can be ignored; CR = 0 if the water table is > 1 m below the roots (Ch. 8).

**Root growth** (Annex 8 Eq. 8-1, Kcb-based; Eq. 8-3 is the time-based alternative): `Zr_i = Zr min + (Zr max − Zr min) · (Kcb_i − Kcb ini) / (Kcb mid − Kcb ini)` before mid-season, Zr max after. Roots never shrink. When Zr grows, add the new subsoil's deficit to Dr (Ch. 8 Ex. 38).

**Irrigation rule** (Ch. 8 "Forecasting or allocating irrigations"; Annex 8): irrigate when `Dr ≥ RAW`; net depth `I ≤ Dr` (Annex 8 uses `I = Dr` of the previous day's end, applied next morning). Annex 8 stops irrigating at the midpoint of the late season.

## Order of a day (Ch. 8 Ex. 38; Annex 8)

1. Morning: subtract any irrigation decided yesterday and today's P − RO from yesterday's ending Dr, floor at 0 → Dr start.
2. Kc for day i (Eq. 66), ETc = Kc · ETo.
3. Zr, TAW, p, RAW for the day.
4. Ks from Eq. 84 (Ex. 38 uses Dr start; Annex 8 uses the first-estimate ending depletion — **open**, fao56.md §4).
5. ETc adj, DP (Eq. 88), ending Dr (Eq. 85), clamp (Eq. 86).
6. If ending Dr ≥ RAW, schedule I = ending Dr for tomorrow morning.

## Crop values

| | Tomato | Sweet (bell) pepper | Source |
|---|---|---|---|
| Kc ini | 0.6 (Solanaceae group row; crop row blank) | 0.6 (group row) | Table 12 |
| Kc mid | 1.15 (1.20 staked) | 1.05 (1.15 staked) | Table 12, fn 2 |
| Kc end | 0.70–0.90 (**open**: FAO gives no pick rule) | 0.90 | Table 12 |
| max h (m) | 0.6 | 0.7 | Table 12 |
| Zr max (m) | 0.7–1.5 (smaller end for scheduling) | 0.5–1.0 | Table 22 |
| p (ETc ≈ 5 mm/d) | 0.40 | 0.30 | Table 22 |
| Kc cut under plastic mulch | 35 % (Table 25); general 10–30 % (**open**) | 10–30 % | Ch. 10 |

Stage lengths, days (Table 11; FAO urges local data):

| Crop | Ini | Dev | Mid | Late | Total | Planting | Region |
|---|---|---|---|---|---|---|---|
| Pepper | 25/30 (**open**) | 35 | 40 | 20 | 125 | April/June | Europe and Medit. |
| Pepper | 30 | 40 | 110 | 30 | 210 | October | Arid Region |
| Tomato | 30 | 40 | 40 | 25 | 135 | January | Arid Region |
| Tomato | 35 | 40 | 50 | 30 | 155 | Apr/May | Calif., USA |
| Tomato | 25 | 40 | 60 | 30 | 155 | Jan | Calif. Desert, USA |
| Tomato | 35 | 45 | 70 | 30 | 180 | Oct/Nov | Arid Region |
| Tomato | 30 | 40 | 45 | 30 | 145 | April/May | Mediterranean |

Typical θFC − θWP by soil (m³/m³, Table 19): sand 0.05–0.11, loamy sand 0.06–0.12, sandy loam 0.11–0.15, loam 0.13–0.18, silt loam 0.13–0.19, silt 0.16–0.20, silty clay loam 0.13–0.18, silty clay 0.13–0.19, clay 0.12–0.20.

## Worked cases (by hand; use as test oracles)

Inputs not taken from an FAO table are chosen for the example and say so.

### Case 1 — Kc curve and ETc, tomato (Mediterranean row: 30/40/45/30 = 145 d)

Chosen: Kc end(Tab) = 0.80 (middle of 0.70–0.90), u2 = 3 m/s, RHmin = 30 %, h = 0.6 m for both mid and late stages, ETo = 5.0 mm/d.

1. Climate term: 0.04·(3 − 2) − 0.004·(30 − 45) = 0.04 + 0.06 = 0.10. Height factor (0.6/3)^0.3 = 0.2^0.3 = 0.6170. Adjustment = 0.0617.
2. Kc mid = 1.15 + 0.0617 = **1.2117**. Kc end = 0.80 + 0.0617 = **0.8617** (0.80 ≥ 0.45, so Eq. 65 applies).
3. Stage boundaries: initial days 1–30, development 31–70, mid 71–115, late 116–145.
4. Day 50 (development): Kc = 0.6 + (50 − 30)/40 · (1.2117 − 0.6) = 0.6 + 0.5 · 0.6117 = **0.9059**. ETc = 0.9059 · 5.0 = **4.53 mm**.
5. Day 130 (late): Kc = 1.2117 + (130 − 115)/30 · (0.8617 − 1.2117) = 1.2117 − 0.175 = **1.0367**.
6. Day 10 → 0.6; day 100 → 1.2117 (flat stages).

### Case 2 — Bucket and stress, pepper on sandy loam

Chosen: θFC − θWP = 0.12 (inside Table 19 sandy loam 0.11–0.15), Zr = 0.5 m (Table 22 low end, for scheduling), Kc = 1.05 (mid-season, unadjusted), ETo = 6.2 mm/d, Dr = 20 mm.

1. TAW = 1000 · 0.12 · 0.5 = **60 mm**.
2. ETc = 1.05 · 6.2 = **6.51 mm/d**.
3. p = 0.30 + 0.04 · (5 − 6.51) = 0.30 − 0.0604 = **0.2396** (inside 0.1–0.8).
4. RAW = 0.2396 · 60 = **14.38 mm**.
5. Dr = 20 > RAW, so Ks = (60 − 20)/(60 − 14.38) = 40/45.62 = **0.877**.
6. ETc adj = 0.877 · 6.51 = **5.71 mm/d** (unstressed would be 6.51).

### Case 3 — Three-day balance with a trigger, tomato on silty clay (Ch. 8 Ex. 36 bucket)

From Ex. 36: Zr = 0.8 m, p = 0.40, θFC − θWP = 0.12 → TAW = **96 mm**, RAW = 0.40 · 96 = **38.4 mm** (Ex. 36 rounds to 38). Chosen: Kc = 1.15 constant (mid-season), p not ETc-adjusted, RO = 0, CR = 0, Dr at the end of day 0 = 30 mm.

| Day | ETo | P | I (morning) | Dr start | Ks | ETc | DP | Dr end | Decision |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 5.0 | 0 | 0 | 30.00 | 1 | 5.75 | 0 | **35.75** | 35.75 < 38.4, none |
| 2 | 4.0 | 0.5 (< 0.2·4 = 0.8, ignored) | 0 | 35.75 | 1 | 4.60 | 0 | **40.35** | 40.35 ≥ 38.4 → I = 40.35 mm tomorrow |
| 3 | 5.5 | 10 | 40.35 | 0 (floored) | 1 | 6.325 | **3.675** | **0** | none |

Day 3 checks: DP = 10 + 40.35 − 6.325 − 40.35 = 3.675 (Eq. 88). Dr end = 40.35 − 10 − 40.35 + 6.325 + 3.675 = 0 (Eq. 85). The rain that exceeds the day's ET drains; Dr never goes below 0.

## Common mistakes

- Treating I as the emitter or gross depth. FAO's I is net and field-averaged; efficiency, run-time and wetted-bulb volume are **not in FAO-56** (fao56.md §5.3) — ask before inventing a conversion.
- Applying the p adjustment without clamping, or using RHmin as a fraction in Eq. 62.
- Letting Dr go negative instead of moving the excess into DP.
- Applying Eq. 65 to a Kc end below 0.45.
- Using Table 12/22 ranges as single numbers without stating which end was chosen.
- Assuming the single-Kc method is FAO's recommendation for drip. Table 10 points microirrigation to the dual Kcb + Ke method; single Kc is a simplification (fao56.md §1.2) — **open** design decision.
- Filling a gap from memory. Items marked **open** here, and those listed in fao56.md §5.3, are decisions for the user.
