# ViscousDamper author example

DIRECT PUBLISHED NUMERICAL EXAMPLE | Maxwell spring and nonlinear dashpot. Example-device parameters, not an optimized building damper.

Maxwell series model: udot=Fdot/K + sign(F)*(abs(F)/Cd)^(1/alpha). Dashpot F=Cd*abs(v)^alpha*sign(v); not the same as total device velocity when spring deforms. kN/mm to kN/m: K*1000; Cd*1000^alpha.

Source: https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material
Locator: Example 1; Akcelyan, Lignos and Hikino (2018), SD&EE 113, 488-502

No experimental equivalence or project approval is inferred. This export does not set nonlinear_parameters_reviewed or change the building configuration.
