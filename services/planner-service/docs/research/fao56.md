# FAO-56 crop water requirements for a daily drip-irrigation planner

**Source:** Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper No. 56. FAO, Rome. ISBN 92-5-104219-5.
Online edition: https://www.fao.org/3/x0490E/x0490e00.htm (this URL now returns 301 to `http://www.fao.org/4/x0490E/x0490e00.htm`; all pages were read from the `https://www.fao.org/4/x0490E/` mirror, see [Sources](#sources)).

**Date accessed:** 2026-11-17

**Summary.** FAO-56 gets crop water use as ETc = Kc × ETo. Kc follows a piecewise-linear curve over four growth stages and is built from three values (Kc ini, Kc mid, Kc end) and four stage lengths. Kc mid and Kc end are adjusted for wind, humidity and crop height. Kc ini is adjusted for how often and how heavily the soil is wetted, and for partial wetting such as drip. Water stress is modelled with a root-zone "bucket": TAW, RAW = p·TAW, and a stress coefficient Ks that applies once depletion Dr goes past RAW. A daily depletion balance drives scheduling: irrigate when Dr reaches RAW, and apply a net depth no larger than Dr. Annex 8 implements this in a spreadsheet. It uses the dual Kc method, not the single one, irrigates the morning after the previous day's ending depletion passes RAW, and sets the net depth equal to that depletion. FAO-56 says nothing about gross depth or application efficiency in the chapters read here.

Notation: FAO writes ETo (subscript o). Equation, table and figure numbers below are FAO's own. Equation images were checked against the GIF files on the FAO page, because the HTML text leaves the equation bodies out.

---

## 1. From ETo and Kc to crop water need

### 1.1 The crop coefficient approach
- **ETc = Kc · ETo**, with ETc and ETo in mm/d and Kc dimensionless. This is **Ch. 5, Eq. 56**, repeated as **Ch. 6, Eq. 58** (Ch. 6 later refers to it as "Eq. 58").
- Kc rolls up four ways a crop differs from the grass reference: crop height, albedo, canopy resistance, and soil evaporation (Ch. 5, "Crop coefficient approach").
- ETc from Kc is the **standard-condition** upper envelope: no water, salinity, density, pest or disease limits. Non-standard conditions give ETc adj (Ch. 5; Part C).
- The Table 12 Kc values assume a "standard climate": sub-humid, RHmin ≈ 45%, u2 ≈ 2 m/s (Ch. 5 "Climate"; Table 12 title).

### 1.2 Single vs dual coefficient (Ch. 5, Table 10; Ch. 6 intro)
- **Single Kc** averages soil evaporation and transpiration over time. FAO recommends it for planning, design, irrigation management, basic schedules, and real-time scheduling of **non-frequent** applications such as surface and sprinkler irrigation. Time step: daily, 10-day or monthly (Table 10). It suits systems irrigated every several days, "often ten days or more" (Ch. 5, "Single crop coefficient approach").
- **Dual Kc = Kcb + Ke** (Ch. 5, Eq. 57) separates transpiration (Kcb) from soil evaporation (Ke). Table 10 lists it for "real time irrigation scheduling", "irrigation scheduling for high frequency water application (**microirrigation** and automated sprinkler irrigation)", and detailed water balances. Daily time step, computer solution only.
- Ch. 5 ("Dual crop coefficient approach") says the dual method is best where daily changes in surface wetness matter, "the case for high frequency irrigation with microirrigation systems". Ch. 6 intro: the single Kc is relevant "for normal irrigation planning and management purposes" and for basic schedules. Kcb + Ke is needed "only when values for Kc are needed on a daily basis for specific fields".
- **Implication for drip:** FAO's own selection criteria (Table 10) point drip scheduling toward the dual method. A single-Kc daily planner is an accepted simplification. It is not FAO's recommended method for microirrigation.

### 1.3 Growth stages (Ch. 5, "Crop growth stages"; Fig. 23)
| Stage | From → to (FAO definition) |
|---|---|
| Initial | Planting to about 10% ground cover. ET is mostly soil evaporation. |
| Crop development | 10% cover to effective full cover (often at flowering; fc ≈ 0.7–0.8, or LAI ≈ 3) |
| Mid-season | Effective full cover to start of maturity (leaf ageing, yellowing). Kc is at its maximum. |
| Late season | Start of maturity to harvest or full senescence |

### 1.4 Constructing the Kc curve (Ch. 6, "Construction of the Kc curve"; Fig. 25, Fig. 34)
Three steps (Ch. 6, "Annual crops"):
1. Set the four stage lengths (Table 11 or local data) and take Kc ini, Kc mid and Kc end (Table 12).
2. Adjust them for wetting frequency (Kc ini) and climate (Kc mid, Kc end).
3. Join them with straight lines. The curve is flat at Kc ini through the initial stage, rises linearly to Kc mid during development, is flat at Kc mid through mid-season, and falls linearly to Kc end during the late season.

**Kc on day i, Ch. 6, Eq. 66** (checked against the equation image):

  Kc i = Kc prev + [(i − Σ(L prev)) / L stage] · (Kc next − Kc prev)

Here i is the day number in the season (1…length of the season), L stage is the length of the current stage, and Σ(L prev) is the sum of the lengths of all earlier stages. During the development stage Kc prev = Kc ini and Kc next = Kc mid. During the late season Kc prev = Kc mid and Kc next = Kc end. FAO says Eq. 66 "applies to all four stages"; in the initial and mid stages it reduces to a constant. In Example 28 (dry beans, stages 25/25/30/20 days, Kc 0.15/1.19/0.35), Kc at days 20, 40, 70 and 95 comes to 0.15, 0.77, 1.19 and 0.56.

Ch. 6 also cautions that Table 11 lengths are "useful only as a general guide". Local observations of stage dates should be used wherever possible (Ch. 6, "Length of growth stages"; Box 15 shows the error from a wrong mid-season length).

### 1.5 Climate adjustment of Kc mid and Kc end (Ch. 6)
**Eq. 62 (Kc mid):** Kc mid = Kc mid(Tab) + [0.04(u2 − 2) − 0.004(RHmin − 45)] · (h/3)^0.3

**Eq. 65 (Kc end):** Kc end = Kc end(Tab) + [0.04(u2 − 2) − 0.004(RHmin − 45)] · (h/3)^0.3

- u2 is the mean daily wind speed at 2 m during the stage, valid for 1 ≤ u2 ≤ 6 m/s. RHmin is the mean daily minimum RH during the stage, valid for 20% ≤ RHmin ≤ 80%. h is the mean plant height during the stage, 0.1 m < h < 10 m. For h < 0.1 m, do not apply Eq. 62 (Ch. 6, "Determination of Kc mid"). For Kc mid, u2 and RHmin are averaged over the mid-season. For Kc end they are averaged over the late season. Annex 8 follows this.
- **When it applies:** wherever RHmin ≠ 45% or u2 ≠ 2 m/s. **Eq. 65 is applied only when Kc end (Tab) ≥ 0.45.** Below that, Kc end = Kc end(Tab) (Ch. 6, "Crop coefficient for the end of the late season stage").
- If humidity data are missing, RHmin can come from Tmax and Tdew (Eq. 63), or from Tmin used in place of Tdew (Eq. 64). For arid and semi-arid climates, subtract 2 °C from Tmin first (Ch. 6, footnote to Eq. 64, citing Annex 6 Eq. 6-6). The equation bodies of Eq. 63/64 were not transcribed here.
- Wetting frequency in mid-season: if irrigation comes more often than every 3 days **and** Kc mid(Tab) < 1.0, Kc mid can be replaced by about 1.1–1.3, "especially where the irrigation system moistens an important fraction of the soil surface (fw > 0.3)" (Ch. 6, "Adjustment for frequency of wetting"). Tomato (1.15) and pepper (1.05) are already ≥ 1.0, so this does not apply to them.
- Text discrepancy: Ch. 6 says Box 14 shows Kc mid variation "for tomatoes", but Box 14 on the page is titled and worked for a **wheat** crop.

### 1.6 Kc ini considerations (Ch. 6, "Crop coefficient for the initial stage")
- Table 12 Kc ini values are "only approximations" for preliminary or planning studies. Kc ini depends on the wetting interval, the evaporating power (ETo), and the size of the wetting event. It can range from 0.1 to 1.15 (Ch. 6). Table 9 (Ch. 5) gives rough values by wetting interval and ETo class.
- **Fig. 29** covers light events (≤ 10 mm, all soils). FAO says it can also be used for "high frequency systems such as microirrigation". **Fig. 30a/b** covers heavy events (≥ 40 mm), split into coarse soils and medium/fine soils.
- **Eq. 59** interpolates for 10–40 mm events: Kc ini = Kc ini(Fig29) + [(I − 10)/(40 − 10)] · [Kc ini(Fig30) − Kc ini(Fig29)].
- **Partial wetting (drip):** **Eq. 60** gives Kc ini = fw · Kc ini(Tab, Fig). **Eq. 61** gives Iw = I / fw: divide the field-average depth by fw to get the depth on the wetted strip, then use that depth to choose between the figures. Ch. 6 says trickle fw "may be only 0.4". Table 20 (Ch. 7) gives 0.3–0.4 for trickle irrigation. When rain and partial irrigation both wet the soil in the initial period, fw is weighted by infiltration depth.
- **Example 26 (trickle):** I = 12 mm every 2 days, fw = 0.4, ETo = 4 mm/d, medium soil. Iw = 30 mm. Fig. 29 gives 0.85 and Fig. 30b gives 1.15, so Eq. 59 gives 1.05. Then Kc ini = 0.4 × 1.05 = 0.42, and ETc = 1.7 mm/d.
- Numerical Kc ini procedure: Annex 7 (Eq. 7-3). **Not read; unverified here.**

### 1.7 Other drip / partial-cover notes (kept minimal)
- **Ch. 7, Eq. 75:** few = min(1 − fc, fw). For drip, where emitters sit under the canopy, FAO suggests cutting fw to about 1/2–1/3 of the Table 20 value, or multiplying fw by [1 − (2/3)fc] (Ch. 7, "Exposed and wetted soil fraction"). **Example 34** (cotton, drip, fw = 0.3) gives Kc = 1.15, lower than for sprinkler or furrow.
- **Table 20 (Ch. 7):** trickle irrigation fw = 0.3…0.4. Precipitation and sprinkler fw = 1.0.
- **Table 21 (Ch. 7):** typical fc by stage: initial 0.0–0.1, development 0.1–0.8, mid 0.8–1.0, late 0.8–0.2.
- **Table 17 (Ch. 7), basal Kcb:** Solanaceae group Kcb ini 0.15. Sweet peppers Kcb mid 1.00², Kcb end 0.80. Tomato Kcb mid 1.10², Kcb end 0.60–0.80. Footnote ² for staked crops: peppers 1.10, tomatoes 1.15.
- **Plastic mulch (Ch. 10, "Effects of surface mulches", Table 25):** under trickle irrigation, plastic mulch cuts soil evaporation by about 50–80% and raises transpiration by about 10–30%. The net effect is a 10–30% lower Kc. For horticultural crops, reduce Kc mid and Kc end by 10–30%, using the higher value for frequent trickle irrigation. Kc ini under mulch is "often as low as 0.10". Table 25 lists **tomato: 35% Kc reduction** (Haddadin and Ghawi, 1983). Reduce less where the mulch does not cover the wetted soil or where rain is substantial.
- Table 12 footnote 16 (pineapple only) says Kc can drop by 0.10 for drip under plastic mulch. That note is crop-specific and not for tomato or pepper.

---

## 2. Tomato and sweet (bell) pepper values

### 2.1 Table 12 (Ch. 6): single Kc and maximum height
Kc ini for Solanaceae appears only in the group row. The crop rows leave that column blank, so the group value applies. The column header is an image, which reads "Kc ini¹".

| Row in Table 12 | Kc ini¹ | Kc mid | Kc end | Max crop height h (m) |
|---|---|---|---|---|
| b. Vegetables – Solanum Family (group row) | 0.6 | 1.15 | 0.80 | — |
| Sweet Peppers (bell) | (0.6, group) | 1.05² | 0.90 | 0.7 |
| Tomato | (0.6, group) | 1.15² | 0.70–0.90 | 0.6 |

Footnotes that apply, paraphrased with short quotes:
- **¹ (Kc ini column):** these are general values for typical irrigation management. With frequent wetting, such as high-frequency sprinkling or daily rain, they "may increase substantially and may approach 1.0 to 1.2". They are better estimated from Figs. 29/30, Annex 7 Eq. 7-3, or the dual Kcb ini + Ke.
- **² (Kc mid):** beans, peas, legumes, tomatoes, peppers and cucumbers are sometimes grown on stakes 1.5–2 m tall. For those, use higher Kc: **1.15 for peppers** and **1.20 for tomatoes**. "Under these conditions h should be increased also."
- The table title sets the conditions: non-stressed, well-managed crops in sub-humid climates (RHmin ≈ 45%, u2 ≈ 2 m/s), for use with FAO Penman-Monteith ETo.

### 2.2 Table 11 (Ch. 6): stage lengths in days
Table title footnote *: lengths "are indicative of general conditions, but may vary substantially from region to region, with climate and cropping conditions, and with crop variety. The user is strongly encouraged to obtain appropriate local information." Primary source: FAO-24 (Doorenbos & Pruitt 1977), Table 22.

| Crop | Init. | Dev. | Mid | Late | Total | Plant date | Region |
|---|---|---|---|---|---|---|---|
| Sweet peppers (bell) | 25/30 | 35 | 40 | 20 | 125 | April/June | Europe and Medit. |
| Sweet peppers (bell) | 30 | 40 | 110 | 30 | 210 | October | Arid Region |
| Tomato | 30 | 40 | 40 | 25 | 135 | January | Arid Region |
| Tomato | 35 | 40 | 50 | 30 | 155 | Apr/May | Calif., USA |
| Tomato | 25 | 40 | 60 | 30 | 155 | Jan | Calif. Desert, USA |
| Tomato | 35 | 45 | 70 | 30 | 180 | Oct/Nov | Arid Region |
| Tomato | 30 | 40 | 45 | 30 | 145 | April/May | Mediterranean |

Note: in the first pepper row the stages add to 120 with Init. = 25 and to 125 with Init. = 30. The table gives one total (125), so it matches the 30-day value. FAO does not say which planting date goes with which initial length.

### 2.3 Table 22 (Ch. 8): rooting depth and depletion fraction
| Crop | Maximum root depth¹ Zr (m) | Depletion fraction² p (for ET ≈ 5 mm/day) |
|---|---|---|
| Sweet Peppers (bell) | 0.5–1.0 | 0.30 |
| Tomato | 0.7–1.5 | 0.40 |

- **¹** The larger Zr values are for soils with no significant layering or other restriction on rooting. The smaller values "may be used for irrigation scheduling", and the larger ones for modelling soil water stress or rainfed conditions.
- **²** p applies for ETc ≈ 5 mm/day and can be adjusted as p = p(Table 22) + 0.04(5 − ETc), with p as a fraction and ETc in mm/day.
- **Example 36 (Ch. 8)** uses tomato with Zr ≈ 0.8 m and p = 0.40. Results: TAW/RAW = 72/29 mm on loamy sand, 136/54 mm on silt, and 96/38 mm on silty clay.

---

## 3. The soil bucket (Ch. 8)

In plain words, the root zone is a tank measured as **depletion Dr**: how many mm below field capacity it sits. Dr = 0 means full (field capacity). Dr = TAW means empty (wilting point). The crop uses water at the full rate until Dr reaches RAW. Beyond RAW, ET falls linearly to zero at Dr = TAW.

| Item | FAO equation | Meaning |
|---|---|---|
| Total available water | **Eq. 82:** TAW = 1000(θFC − θWP)·Zr | mm; θ in m³/m³, Zr in m |
| Readily available water | **Eq. 83:** RAW = p·TAW | p is the fraction of TAW usable without stress |
| p adjusted for ET rate | **Ch. 8 text and Table 22 fn 2:** p = p(Table 22) + 0.04(5 − ETc), limited to 0.1 ≤ p ≤ 0.8 | Higher ETc gives a smaller p. Fig. 41 shows the effect. |
| Stress coefficient (Dr > RAW) | **Eq. 84:** Ks = (TAW − Dr)/(TAW − RAW) = (TAW − Dr)/((1 − p)·TAW) | Ks = 1 when Dr ≤ RAW (Fig. 42) |
| Adjusted ET, single Kc | **Eq. 81:** ETc adj = Ks·Kc·ETo | |
| Adjusted ET, dual Kc | **Eq. 80:** ETc adj = (Ks·Kcb + Ke)·ETo | FAO calls this "generally more valid" because Ks affects transpiration only. Eq. 81 is reasonable where soil evaporation is small. |
| Daily balance | **Eq. 85:** Dr,i = Dr,i−1 − (P − RO)i − Ii − CRi + ETc,i + DPi | All terms in mm for day i |
| Bounds | **Eq. 86:** 0 ≤ Dr,i ≤ TAW | |
| Initial depletion | **Eq. 87:** Dr,i−1 = 1000(θFC − θi−1)·Zr | Or assume Dr ≈ 0 after heavy rain or irrigation |
| Deep percolation | **Eq. 88:** DPi = (Pi − ROi) + Ii − ETc,i − Dr,i−1 ≥ 0 | DP = 0 while Dr,i > 0 |

Notes on the p adjustment (Ch. 8, "Readily available water"):
- p usually runs from 0.30 for shallow-rooted crops at high ETc (> 8 mm/d) to 0.70 for deep-rooted crops at low ETc (< 3 mm/d). 0.50 is common.
- In hot, dry weather p is 10–25% below Table 22; at low ETc it can be up to 20% above.
- A constant p per growing period is often used.
- For fine (clay) soils, reduce p by 5–10%. For coarse (sand) soils, increase it by 5–10%.
- RAW is similar to Merriam's Management Allowed Depletion (MAD). MAD < RAW where there is risk aversion. MAD > RAW where stress is intended.

Notes on the balance terms (Ch. 8, "Soil water balance"):
- **P:** daily rain below about 0.2·ETo "is normally entirely evaporated" and can usually be ignored, especially with single Kc.
- **RO:** use standard hydrology methods. FAO gives no method here.
- **I:** the mean infiltrated net irrigation depth, expressed over the **entire field surface**.
- **CR:** take as zero when the water table is more than about 1 m below the root zone.
- **ETc:** Kc·ETo while Dr ≤ RAW, otherwise Eq. 80/81.
- **DP:** water above field capacity is assumed lost the same day, after that day's ET. This is why Dr never goes below 0.
- Ch. 8 notes that this root-zone DP is not the DPe of the Ch. 7 evaporation layer (Eqs. 77/79).

**Table 19 (located in Ch. 7, "Soil evaporation reduction coefficient", but cited by Ch. 8 for θFC/θWP).** Typical soil water characteristics:

| Soil type (USA texture) | θFC (m³/m³) | θWP (m³/m³) | θFC − θWP (m³/m³) | REW (mm) | TEW (mm, Ze = 0.10 m) |
|---|---|---|---|---|---|
| Sand | 0.07–0.17 | 0.02–0.07 | 0.05–0.11 | 2–7 | 6–12 |
| Loamy sand | 0.11–0.19 | 0.03–0.10 | 0.06–0.12 | 4–8 | 9–14 |
| Sandy loam | 0.18–0.28 | 0.06–0.16 | 0.11–0.15 | 6–10 | 15–20 |
| Loam | 0.20–0.30 | 0.07–0.17 | 0.13–0.18 | 8–10 | 16–22 |
| Silt loam | 0.22–0.36 | 0.09–0.21 | 0.13–0.19 | 8–11 | 18–25 |
| Silt | 0.28–0.36 | 0.12–0.22 | 0.16–0.20 | 8–11 | 22–26 |
| Silt clay loam | 0.30–0.37 | 0.17–0.24 | 0.13–0.18 | 8–11 | 22–27 |
| Silty clay | 0-30 – 0.42 (sic) | 0.17–0.29 | 0.13–0.19 | 8–12 | 22–28 |
| Clay | 0.32–0.40 | 0.20–0.24 | 0.12–0.20 | 8–12 | 22–29 |

TEW = (θFC − 0.5θWP)·Ze (Table 19 footnote). The silty-clay θFC lower bound is printed as "0-30" on the FAO page and is presumably 0.30; that value is unverified. Example 36 uses silty clay θFC ≈ 0.35.

---

## 4. How the worked examples schedule irrigation

### 4.1 Ch. 8, Example 38 (short, dual Kc, 10 days)
- Assumptions: irrigate when RAW is depleted. p = 0.6. All P and I happen early in the day. Zr grows from 0.3 m to 0.35 m. Dr at the start equals RAW. TAW = 130·Zr and RAW = 78·Zr (θFC 0.23, θWP 0.10).
- Columns: Day, ETo, Zr, RAW, Dr start, P−RO, I, Ks, Kcb, Ke, Kc, ETc, DP, Dr end.
- Order each day:
  1. Compute Dr start = max(Dr end of the previous day − I − (P − RO), 0) when water arrives early in the day.
  2. Get Ks from Eq. 84.
  3. Compute Kc = Ks·Kcb + Ke and ETc (Eq. 80).
  4. Compute DP (Eq. 88).
  5. Compute Dr end (Eq. 85).
- Trigger and depth: "Irrigation is required when Dr, i ≥ RAW." On day 10, Dr start = 27 = RAW, so a **net depth of 27 mm** "refills the root zone and avoids water loss by deep percolation". Day 1 had a given 40 mm irrigation on Dr = 23 mm, which gave DP = 17 mm.
- Growing roots: when Zr increases, add the subsoil deficit: Dr,i = Dr,i−1 + 1000(θFC − θsub,i−1)·ΔZr. The example assumes the subsoil is at field capacity.
- General rule (Ch. 8, "Forecasting or allocating irrigations"): irrigate before or when RAW is depleted (Dr,i ≤ RAW). Keep the net depth **Ii ≤ Dr,i** to avoid deep percolation losses that "may leach relevant nutrients out of the root zone".

### 4.2 Annex 8, full spreadsheet (Figure 8.1, Box 8.1)
**Method:** Annex 8 demonstrates the **dual** Kc method (Kcb + Ke, Ch. 7) with the Ch. 8 root-zone balance. The crop is dry edible beans, the same case as Boxes 15/16.

**User inputs (Fig. 8.1 rows 3–7; Box 8.1):**
| Input | Value |
|---|---|
| Crop | Dry, edible beans |
| Planting date | 22 May (Month 5, Day 22) → J plant 142 |
| Lini/Ldev/Lmid/Llate | 25/25/30/20 days (from Table 11) |
| Stage start days | J dev 167, J mid 192, J late 222, J harv 242 |
| Kcb ini/mid/end (Table 17) | 0.15 / 1.10 / 0.25 |
| Kcb after climate adjustment (Eq. 70) | 0.15 / 1.13 / 0.23 |
| Climate inputs to Eq. 70 | Mid-season mean u2 1.98 m/s, RHmin 29% |
| Kc min / max height | 0.15 / 0.4 m |
| fw (irrigation) / initial fw | 0.5 / 1 |
| REW / TEW / initial De | 8 / 22 / 18 mm |
| Root min / root max | 0.20 / 0.80 m |
| Available water (θFC − θWP) | 160 mm/m |
| MAD, initial stage / after | 70% / 45% |

**Daily input columns:** month, day, year, J, Tmax, u2, Tdew, ETo, and P − RO. RHmin is derived from Tdew and Tmax (Eq. 63).

**Computed columns, in calculation order:**
- Evaporation block: Kcb (Eq. 66), height, Kc max (Eq. 72), net irrigation/fw at the beginning of the day, fc (Eq. 76), fw, few (Eq. 75), De start, Kr (Eq. 74), Ke (Eq. 71), E, DPe, De end (Eq. 77), Kc, ETc.
- Irrigation-scheduling block: root depth, RAW, ending depletion, net irrigation needed, drainage (DP), Ks, adjusted Kc (Ks·Kcb + Ke), corrected ending depletion.

**Order of operations each day (Annex 8 text and Box 8.1 footnotes 4–11):**
1. Apply any irrigation decided at the end of the **previous** day, plus today's precipitation. Both are assumed to happen early in the morning. Runoff is assumed to be zero.
2. Compute Kcb for the day from Eq. 66 and crop height (proportional to Kcb/Kcb mid, never decreasing). Then compute Kc max, fc, fw and few, and the evaporation-layer balance (Kr, Ke).
3. Compute root depth: **Annex 8 Eq. 8-1**, Zr i = Zr min + (Zr max − Zr min)·(Kcb i − Kcb ini)/(Kcb mid − Kcb ini) for J < J mid. **Eq. 8-2:** Zr = Zr max from J mid on. Roots never shrink. A time-based alternative is **Eq. 8-3**, interpolating between J start and J max. Zr min for annuals is about 0.15–0.20 m.
4. Compute RAW = MAD × Zr × available water. MAD is higher in the initial stage. The example assumes p = MAD.
5. First estimate of ending depletion, from Eq. 85 with DP = 0 and unstressed ETc (fn 9).
6. DP from Eq. 88. Excess water drains the same day.
7. Ks from Eq. 84 if the first-estimate depletion exceeds RAW (fn 11).
8. Adjusted Kc = Ks·Kcb + Ke, then the corrected ending depletion Dr,i (Eq. 85).
9. **Decide tomorrow's irrigation:**
   - If the first-estimate ending depletion > RAW, the net irrigation needed equals that depletion. In the Box 8.1 formula this is a strict ">". The Annex text says "greater than or equal to".
   - Irrigation happens only from planting until the **midpoint of the late season**. The last irrigation in the example is day 225.

**Net depth:** "the net depth of irrigation that is retained in the crop root zone is exactly equal to the depletion depth of the previous day". FAO says this "presumes perfect knowledge of soil water depletion by the irrigator" and may be changed by the user. For the evaporation layer, the same depth is divided by fw to give the depth over the wetted strip (fn 4).

**Gross depth and efficiency:** **not covered.** Annex 8 and Chs. 5–8 work only in net, infiltrated depths. No application efficiency appears.

**Rain:** P − RO is a user input, with runoff assumed zero. Rain reduces depletion early in the day. Rain sets fw = 1 for the evaporation layer (Ch. 7 rules). Root-zone drainage from excess rain is assumed to happen the same day.

**Known artefact:** because irrigation waits until the depletion at the end of the previous day is at or above RAW, the spreadsheet "occasionally causes a small amount of stress on the day prior to irrigation". FAO says the procedure "may not always be appropriate" and should be adapted locally.

**Representative rows (Fig. 8.1, rows 14–26; this window starts 15 May, J 135, before planting on J 142):**

| J | ETo | P−RO | Kcb | Ke | Zr (m) | RAW | Ending depl. (1st est.) | Net irr. needed | Ks | Kc adj | Corrected ending depl. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 135 | 3.4 | – | 0.15 | 0.31 | 0.20 | 22.4 | 19.6 | – | 1.00 | 0.46 | 19.6 |
| 138 | 3.8 | – | 0.15 | 0.11 | 0.20 | 22.4 | 23.2 | – | 0.92 | 0.25 | 23.2 |
| 139 | 3.1 | 2.5 | 0.15 | 0.27 | 0.20 | 22.4 | 21.9 | – | 1.00 | 0.42 | 21.9 |
| 141 | 4.8 | – | 0.15 | 0.21 | 0.20 | 22.4 | 24.1 | – | 0.83 | 0.33 | 23.9 |
| 142 | 4.9 | – | 0.15 | 0.13 | 0.20 | 22.4 | 25.3 | **25.3** | 0.70 | 0.23 | 25.1 |
| 143 | 5.2 | – | 0.15 | 0.61 | 0.20 | 22.4 | 3.7 | – | 1.00 | 0.76 | 3.7 |
| 147 | 5.3 | – | 0.15 | 0.04 | 0.20 | 22.4 | 14.7 | – | 1.00 | 0.19 | 14.7 |

How to read the table:
- RAW = 0.70 × 0.20 m × 160 mm/m = 22.4 mm, and TAW = 32 mm. Ks on J 138 is (32 − 23.2)/(32 − 22.4) = 0.92.
- The 25.3 mm needed at the end of J 142 is applied on the morning of J 143. On that day the evaporation-layer column shows 50.6 mm (= 25.3 / fw 0.5).
- The J 141 row is the case where Ks < 1 but no irrigation was triggered. Irrigation counts only from J plant (142), and the first trigger fires at the end of J 142.
- The FAO HTML figure shows only these 13 day-rows (rows 14–26). The rest of the season, to J 242, is in Figs. 8.2/8.3 as graphs only, so later rows were not checked.

---

## 5. Implications for a daily drip planner

### 5.1 Inputs FAO's procedure needs
- **Daily weather:** ETo (FAO Penman-Monteith, Ch. 4). Rain P. Runoff RO, or the assumption RO = 0 (Annex 8). For Kc climate adjustment, stage-mean u2 and RHmin (Eqs. 62/65), or Tmax/Tdew or Tmin to estimate RHmin (Eqs. 63/64).
- **Crop:** planting date. Four stage lengths (Table 11, preferably local). Kc ini/mid/end (Table 12). Max height h (Table 12, raised if staked, fn 2). Zr range and p (Table 22).
- **Soil:** θFC and θWP, or available water in mm/m (Table 19 or measured). Initial depletion (Eq. 87, or ≈ 0 after a wetting).
- **System:** wetted fraction fw (Table 20, trickle 0.3–0.4). Ground-cover fraction fc by stage (Table 21). Mulch (Ch. 10, Table 25).

### 5.2 Per-day steps (single-Kc variant, each step traceable to FAO)
1. **Day index and stage.** Find the day number i since planting and its stage from the stage lengths (Ch. 6, Table 11).
2. **Kc for day i.** Use Eq. 66 on the adjusted points:
   - Kc ini from Eqs. 59–61 for drip, i.e. fw × the figure value. Use ~0.10 under full plastic mulch (Ch. 10).
   - Kc mid from Eq. 62.
   - Kc end from Eq. 65, applied only if Kc end ≥ 0.45.
   - Apply the mulch reduction if relevant (Ch. 10, Table 25).
3. **Potential ET.** ETc = Kc·ETo (Eq. 56/58).
4. **Root depth and bucket size.**
   - Zr for the day: Annex 8 Eq. 8-1 or 8-3, never decreasing. When Zr grows, add the subsoil deficit to Dr (Ch. 8, Example 38 note 5).
   - TAW from Eq. 82.
   - p from Table 22, optionally adjusted by +0.04(5 − ETc) and limited to 0.1–0.8 (Ch. 8). Then RAW from Eq. 83.
5. **Start-of-day depletion.** Subtract any irrigation (net, field-average) and effective rain (P − RO; rain < 0.2·ETo may be ignored) applied early in the day, flooring at 0 (Ch. 8 Ex. 38 note 5; Annex 8).
6. **Stress.** Ks = 1 if Dr ≤ RAW, otherwise Eq. 84. ETc adj = Ks·Kc·ETo (Eq. 81).
7. **End-of-day balance.** Dr,i from Eq. 85 with CR = 0 when the water table is > 1 m below the roots. DP from Eq. 88. Clamp to 0 ≤ Dr ≤ TAW (Eq. 86).
8. **Irrigation decision.** If Dr,i ≥ RAW (Ch. 8; Annex 8 uses the end-of-day value), schedule a net depth I ≤ Dr,i for the next morning. Annex 8 uses I = Dr,i. Optionally stop irrigating after the midpoint of the late season, as Annex 8 does for beans.

### 5.3 Open questions and gaps
- **Single vs dual.** FAO recommends the dual Kcb + Ke method for microirrigation and real-time scheduling (Table 10; Ch. 5). A single-Kc planner departs from that. We need to decide whether the simplification is acceptable, or whether to add Ke with few (Ch. 7, Eq. 75 and the drip fw reduction).
- **Gross depth / efficiency.** FAO-56 (Chs. 5–8, Annex 8) works only in net infiltrated depth. Emitter efficiency, distribution uniformity and leaching requirement must come from elsewhere. The salinity material in Ch. 8 (Eqs. 89–92, Table 23) was not reviewed.
- **Field-average vs wetted-strip depth.** FAO's I is expressed over the whole field (Ch. 8). Converting to drip run-time needs emitter spacing, flow and wetted area. FAO does not cover this.
- **Partial wetting of the root zone.** FAO's bucket assumes the whole root zone over the whole field fills to field capacity. With drip, only a wetted bulb is replenished. FAO gives no drip-specific TAW (for example, a fraction of the soil volume wetted). Unverified: whether any FAO-56 section covers this.
- **Trigger timing.** Annex 8 decides on the end-of-day depletion and irrigates the next morning, which can cause one-day stress. It also uses a strict ">" in its formula, against the text's "≥". A daily drip planner may prefer to irrigate before RAW, i.e. MAD < RAW (Ch. 8, MAD discussion).
- **Choice of p vs MAD**, and whether p is held constant or adjusted daily for ETc (Ch. 8 allows both).
- **Stage lengths.** Table 11 tomato/pepper rows are regional examples. FAO strongly urges local data (Table 11 fn *). Ambiguity: the pepper "25/30" initial length.
- **Kc ini for drip** depends on Figs. 29/30, which are graphs only. The numerical alternative is in Annex 7 (Eq. 7-3), which was not read here.
- **Staked or tall tomatoes and peppers.** Use the fn 2 Kc mid values (1.20 / 1.15) and a larger h. FAO does not say how much larger.
- **Tomato Kc end** is a range (0.70–0.90). FAO gives no rule for choosing within it beyond the general harvest-fresh vs dry-down guidance (Ch. 5, Ch. 6, "Kc end").
- **Plastic mulch.** Table 25 gives tomato a 35% Kc reduction, while the general guidance is 10–30%. The value to use is the user's choice.
- **Runoff and capillary rise** are left to the user (RO: "standard procedures from hydrological texts"; CR: deferred to "a future FAO publication").
- **Greenhouse or protected tomatoes** are outside the scope of these chapters. Not checked.

---

## Sources
Pages read on 2026-11-17. The `fao.org/3/` URL redirects (301) to `fao.org/4/`.
- https://www.fao.org/3/x0490E/x0490e00.htm → redirected to http://www.fao.org/4/x0490E/x0490e00.htm (table of contents, citation)
- https://www.fao.org/4/x0490E/x0490e0a.htm — Ch. 5 (Eqs. 56–57, Tables 9–10, Figs. 20–27)
- https://www.fao.org/4/x0490E/x0490e0b.htm — Ch. 6 (Eqs. 58–66, Tables 11–14, Examples 23–28, Box 15)
- https://www.fao.org/4/x0490E/x0490e0c.htm — Ch. 7, used minimally (Table 17, Table 19, Table 20, Table 21, Eq. 75, Example 34)
- https://www.fao.org/4/x0490E/x0490e0e.htm — Ch. 8 (Eqs. 80–88, Table 22, Examples 36 and 38)
- https://www.fao.org/4/x0490E/x0490e0g.htm — Ch. 10, plastic mulch section only (Table 25)
- https://www.fao.org/4/x0490E/x0490e0p.htm — Annex 8 (Box 8.1, Table 8.1, Eqs. 8-1 to 8-3)
- Equation and figure images on the same pages, checked visually:
  - https://www.fao.org/4/x0490E/x0490e2a.gif (Table 12 "Kc ini¹" header)
  - x0490e2b.gif (Eq. 59), x0490e2d.gif (Eq. 62), x0490e2i.gif (Eq. 65), x0490e2k.gif (Eq. 66)
  - x0490e2w.gif (Eq. 84)
  - x0490e5z.gif (Eq. 8-1), x0490e60.gif (Eq. 8-3)
  - x0490e7e.gif, x0490e7f.gif, x0490e7g.gif (Figure 8.1 spreadsheet)

  All are under `https://www.fao.org/4/x0490E/`.

Not read: Annex 7 (Kc ini numerical method), Ch. 4 (ETo), Ch. 9 (Eq. 98, sparse vegetation), and the rest of Ch. 10. Items that depend on them are marked unverified above.
