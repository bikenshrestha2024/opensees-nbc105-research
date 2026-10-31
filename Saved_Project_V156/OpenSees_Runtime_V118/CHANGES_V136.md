# V136 - layout, animation and blank-panel repairs

Extract the full package into a new folder and launch RUN_ETABS_TO_OPENSEES.py. Rebuild the saved export to update its copied runtime. Do not mix individual compatibility files with older components.

## Repairs
- The scrolling helper now handles nested Frames without calling window-only geometry methods. This fixes the readiness editor stopping before its checklist and Save controls appear.
- Readiness approval and Save controls stay in a fixed footer. All 16 evidence items remain required; no approval is fabricated.
- Embedded charts resize directly to their panel with toolbar space reserved, instead of nesting a fixed-size plot inside a competing scrolling canvas. Main log starts at eight rows instead of consuming a default large area.
- Deformation controls are split across two rows; toolbar is reserved at the bottom. Added a 0-100% slider; source/displacement segments are cached for animation. Animation renders each frame before scheduling the next, preventing a backlog of draw/timer events on larger models. Play, Pause/final, camera presets and six-DOF node readout remain available.
- MRSM animation is explicitly an illustration interpolating a nonconcurrent CQC envelope, not a physical earthquake movie. Use recorded-history playback for actual time evolution.
- Irregularity no longer opens silently empty when there is no saved result: it reads the selected assembled model and immediately shows geometry and explicit NOT EVALUATED response checks. Plan inspection uses that preview. Calculate selected states runs the separate centered-load response review needed for soft-storey/torsion; a modal audit alone does not calculate those quantities.

## Nonlinear error in supplied screenshots
Two distinct issues were present. The blank checklist was a GUI fault, repaired here. The model itself reports nonlinear_parameters_reviewed=False, missing nonlinear material file and zero wall FSAM mappings. These are genuine missing model prerequisites. A readiness template or checked approval cannot construct calibrated RC/wall material behavior. Complete the visible checklist with evidence and supply/review the material definitions and wall mappings before execution. This release retains the existing nonlinear gate and does not claim the building nonlinear analysis has run successfully.

## Verification
Executed native Tk checks with the workspace model: 17 readiness controls (16 items plus approval), 127 geometry-preview rows, and animation advanced through 8 frames. Parsed all Python sources. The responsive MRSM chart measured 1096 x 595 pixels in an 1100 x 740 test window; its hidden state tab correctly remains unmapped until selected. No structural equations or material properties were changed. The live D: export was not modified. Prior numerical results and earlier limitation documents are retained as historical evidence.

V135 design-check limitations remain: no automatic RC reinforcement-demand/interaction-surface engine and no fabricated nonlinear component acceptance limits.
