# V133 executed validation

## New checks executed in this pass

- **47 regression tests passed.** These include prior CQC/native acceleration-unit/static/drift/source tests plus workload bounds, display extrema preservation, differing floor-center reconstruction, unmatched-master rejection, progressive recording, compatibility forwarding, adaptive-substep callbacks and cyclic yielding solver-lifecycle equivalence.
- All Python sources parsed; **44 root modules imported**, and **485 implementation functions** inventoried. Inventory and exact-duplicate reports are navigational reviews, not independent mathematical certification of every line/branch.
- Main analysis constructor/autofill checks populated linear/nonlinear, gravity, modal and site-spectrum fields with source references. The nonlinear and linear GUI run handlers were separately exercised to capture configuration: selecting one pair forwarded exactly that pair and the preliminary flag. Execution was intercepted before launching the test configuration.
- New history inspector, full-model playback with matching geometry fingerprint, frame rendering, and gravity source-chart/filter constructors were exercised without Tk callback errors. This is functional GUI construction/rendering verification, not pixel-by-pixel visual approval of every layout.
- Fresh full supplied-model linear pipeline ran synthetic 0.045 s paired input in XY and YX, nine steps each. Latest total stage time was approximately 53.6 s; environment load affects timings. XY model/gravity 16.74 s, eigenanalysis 4.35 s, transient/recording 4.63 s; YX 16.60 s, 4.89 s, 4.41 s respectively. Eight roof/displacement/drift peaks matched V132 within maximum absolute difference 1.53e-20. New progressive CSVs, complete-state/hash metadata, workload, performance, drift, deformation and summary exports completed.
- A small synthetic yielding nonlinear pipeline ran XY/YX with committed-Rayleigh damping and separately with modal damping. The latter uses the iterative solver required by OpenSees. Both completed. These are deliberately invented test fixtures, not this building's material calibration, earthquake design record or NLTHA approval. Toy model speed must not be extrapolated to the full building.
- The new nonlinear solver lifecycle matched the previous rebuild-each-step lifecycle across 400 steps on a cyclic yielding native OpenSees model. Adaptive-bisection callback tests checked that intermediate accepted samples are retained; successful toy runs do not imply all real-model convergence cases will succeed.

## Previously executed checks retained as V132 evidence

Worked_Example_V132 and VALIDATION_V132.md retain the actual earlier full-model checks: assembled gravity, four signed initial P-Delta runs, one ULS X+ E0 comparison solve, separate modal audits, and 12 MRSM cases (SLS/ULS x X/Y x E0/E+/E-). Those analysis equations were not changed in this pass. The 24 ESM exports were syntax-checked previously; all 24 were not solved. A successful modal audit is not a substitute for running static/dynamic action cases.

## What was not demonstrated

No real full-building nonlinear earthquake suite, project-specific wall/frame/device calibration, independent ETABS member-load reconciliation, full capacity design, complete irregularity certification or blanket NBC compliance approval was demonstrated. Missing evidence is explicit in the coverage/limits documents and execution gates. Known >=33 Hz MRSM cases still require an implemented/reviewed missing-mass treatment.

## Package integrity

FILE_MANIFEST_V133.json records SHA-256 hashes of packaged files. BUILD_INTEGRITY_V133.json lists the import check. The release ZIP is CRC-checked and every listed file hash is compared with its archived contents. Prior releases and live D: sources/results were preserved.
