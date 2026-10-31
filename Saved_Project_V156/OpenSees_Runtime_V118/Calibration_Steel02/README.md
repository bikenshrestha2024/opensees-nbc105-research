# V154 material calibration work - experimental Steel02 foundation

This is a calibration add-on, not a replacement building model or whole-building approval. Full V153 application remains unchanged.

01_CALIBRATE_STEEL02.py reproduces bounded deterministic calibration using actual SimCenter qfem-0019 stress/strain files (342 samples). Seven parameters are fitted; R0=20,a2=a4=1,sigInit=0 follow the example. Two initial guesses are used. All strain samples are propagated in order; first256 stress samples enter the objective, final86 are withheld. The tail is from the SAME specimen and depends on its prior loading, not independent specimen validation or Bayesian uncertainty quantification. Data source Git blob SHAs and URLs are retained. No acceptance tolerance has been invented.

Training RMSE 26.247 MPa; withheld-tail RMSE32.272MPa; full-history RMSE27.885MPa. Inspect maximum errors too: optimizer convergence is not material acceptance. This coupon is not automatically Fe415, Fe500 or Fe550.

Results include parameter JSON, measured/predicted/residual CSV, four-panel PNG, native material curve, Excel export with unit-conversion formulas and cyclic chart, plus GIF playback. Application card protocol_csv is an absolute generated path; if moved, update it to results/protocol.csv in your extracted folder before using the card in the V152 grade-card editor. All stress values are MPa; multiply by1000 once for kN/m2.

Concrete01 cover card records Terzic Table4 and Base0 measured fc37.8MPa, but cylinder-calibrated E is missing, so peak strain is not fabricated. Confined-core properties require actual transverse reinforcement. See Material_Register.json for source scope and unresolved FVD/BRB/SFI evidence. Neither this add-on nor the papers supplies validated universal nominal-grade cards.

References: SimCenter https://nheri-simcenter.github.io/quoFEM-Documentation/common/user_manual/examples/desktop/qfem-0019/README.html ; multiple-coupon extension qfem-0028; Terzic-Stojadinovic doi10.1061/(ASCE)BE.1943-5592.0000702; Mander observed behaviour doi10.1061/(ASCE)0733-9445(1988)114:8(1827). Source paper review is in the V152/V153 full bundle. Test grade, geometry and boundary applicability before project transfer.
