# Start here â€” V144
Run 01_START_ETABS_TO_OPENSEES.py. Other root files are compatibility modules and should normally be left alone. Numbered launchers 02â€“09 are optional shortcuts to workflow stages, not an automatic certification pipeline.
1. Select EDB and export location. Refresh selected export runtime when upgrading existing exports.
2. Open input inventory and obtain missing values using per-check instructions. Actual available values are read from the selected folder; unknown calibration/reinforcement is never invented.
3. Gravity and load path: compare story/pattern loads and reactions, inspect source assignments and mesh convergence.
4. Modal ULS/SLS: run Both and compare modes/mass; verify correct stiffness/model identity.
5. Equivalent static reference and eligible cases: calculate then run selected signed/eccentricity cases.
6. MRSM ULS/SLS: compare forces, drift and deflection using source identity.
7. Linear history: one earthquake first, then complete paired record suite after checks.
8. CURRENT BUILDING exploratory nonlinear frames + ELASTIC walls: select earthquake, XY and 1 s trial. Actual roof/member/section plots are generated; full record is much slower. This is not the separate portal demo and not a calibrated nonlinear-wall model.
9. Reviewed nonlinear model: needs project constitutive materials/reinforcement, FSAM mappings and benchmarks. Follow step 2 guide. A checked box or literature template alone does not establish calibration.
Main GUI top bar opens connectivity, structural frames, 3D loads and floor loads directly. Missing HTML means export must run first.
New trial capture: default tracked frame tag 100001, local end N/My/Mz and section-1 axial strain/curvatures. These are not steel/concrete fiber stresses. Existing histories without new channels display explicit missing-record messages. Force-vs-roof path is a selected-member relation, not total base shear. No invented elastic baseline comparison.


V144 checks: Python syntax; numbered launcher target files; Tk workflow construction; live-export read-only input inventory; saved legacy-history plot; all new plot channels via synthetic parser fixture. The fixture is not building response.
Actual current-building exploratory smoke test: gravity PASS at 286447.788933 kN, max downward Uz -0.0189513033 m, elapsed 189.780 s. It was interrupted during the subsequent 20-mode nonlinear eigenanalysis after an extended wait. No completed transient, yielding, force/curvature loop, or design acceptance is claimed from this smoke test. New recording and plots require a completed new trial. Production full nonlinear wall model remains dependent on project material and FSAM calibration inputs. No live D: export or EDB was modified.
