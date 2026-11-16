## Decisions

1. **Coarsen, never relax K.** The grid is projected once and binned at 40, 20, 10 and 5 cells across
   the answers' longer side (never finer than 20 m); the first step showing ≥ 60 % of respondents wins,
   else the step showing the most (ties: the finer). K and "omit, don't mask" are untouched.
2. **Explicit sizes still win**: `cells_across=` fixes the grid (the spray wrapper and tests use it).
3. **The note is server-side and translated** (the visitor's language, like the rest of the page);
   the renderer replaces an empty map with it and appends it to the caption otherwise. No bounds are
   sent for an empty map: an extent of one or two respondents would be their location.
