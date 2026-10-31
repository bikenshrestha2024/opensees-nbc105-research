# V131 changes and validation

## Code visibility and RC editor repair

The full implementation is in components/, split by analysis stage. Root historical files are compatibility loaders so existing exported model imports still work. No solver implementation was removed merely to shorten these entry files. Open SOURCE_CODE_MAP_V131.md, or use the new main-window button to open the complete source folder.

V130's RC editor still parsed the root Define_Section loader for a literal RC_SECTION_CONFIG. V131 reads and commits components/sections/definitions.py, including the exported-runtime fallback. This fixes the reported missing-literal error. The parameter register now reads current section configuration values from the actual source file rather than repeating a hard-coded M35 table. No unverified strength or confinement parameter has been promoted to a project-calibrated value.

## Citation corrections

[SFI-MVLEM-3D](https://kkolozvari.github.io/SFI-MVLEM-3D/) is the original four-node RC wall formulation: Kolozvari, Kalbasi, Orakcal and Wallace (2021), Journal of Building Engineering 44, 102946, doi:10.1016/j.jobe.2021.102946.

[E-SFI-MVLEM-3D](https://kkolozvari.github.io/E-SFI-MVLEM-3D/) is the later efficient formulation used by this package's nonlinear wall command: Kolozvari, Lopez and Massone (2023), Engineering Structures 294, 116700, doi:10.1016/j.engstruct.2023.116700. These references describe wall elements, not steel braces. Their numerical examples do not calibrate this building's wall materials.

The SHS_350x350x16 section is now identified as a BRACE in the library display. Its Steel02 link documents the material formulation; it is not evidence for the SHS dimensions, steel grade, local buckling or connection behavior. FVD/BRB remain separate brace targets requiring device-specific parameters.

Concrete01/Steel02 links are marked formulation references only for user-entered/template numerical properties. No project parameter source was supplied for the inherited RC presets; those values remain explicitly uncalibrated.

## Gravity load investigation

Rebuild with V131 to create:

- Gravity_Storey_Load_Breakdown_V131.xlsx: Storey totals, Source detail, Read me.
- Gravity_Storey_Load_Breakdown_V131.csv and JSON.
- Gravity_Source_Load_Detail_V131.csv: source object, source pattern, component, classification, gravity factor, unfactored and applied kN.
- Gravity GUI: Storey load breakdown tab, refresh button and horizontal scroll.
- Next gravity report workbook: Storey load breakdown and Source load detail sheets.

Dead load includes beam, column, brace, shear-wall and slab self-weight; floor finish; partitions; other source dead loads. Live and roof live remain separate. Unknown patterns stay unclassified. Both unfactored load totals and actually applied preload totals are shown. Classification does not change solver loads or mass factors.

Allocation follows the exact assembled equivalent nodal vertical forces: each contribution goes to the next diaphragm level at or above its node. Base-node shares remain in BASE, so total applied load reconciles without dropping fixed-node forces. Member weights spanning floors are apportioned through their consistent nodal forces. These are source loads allocated by level, not cumulative column forces or storey reactions.

## Supplied-model check

Workspace copy rebuilt without assembly errors: 25 storeys plus BASE. Sum of source loads reconciled with the assembled gravity total within 7.2e-9 kN.

| Unfactored component | kN |
|---|---:|
| Beam self-weight | 53,984.055 |
| Column self-weight | 56,733.868 |
| Brace self-weight | 1,308.789 |
| Shear-wall self-weight | 52,934.365 |
| Slab self-weight | 44,986.712 |
| Floor finish (dead) | 18,000.000 |
| Partitions (dead) | 18,000.000 |
| Other dead | 26,100.000 |
| Total dead | 272,047.789 |
| Full live | 48,000.000 |
| Applied live at 0.30 | 14,400.000 |
| Applied gravity total | 286,447.789 |

No roof-live assignment was present; zero here does not establish that roof live is unnecessary. No unclassified source vertical loads were found in this supplied export.

28 inherited regressions passed. RC builder automatic refresh and gravity ledger GUI construction passed; the GUI loaded all 26 levels. All Python sources parsed. No full-building V131 gravity solve or earthquake ensemble was rerun: this update audits unchanged applied-load vectors and changes reporting/classification and editor paths. V130 engineering capability limits continue to apply. Live D: files were not modified.
