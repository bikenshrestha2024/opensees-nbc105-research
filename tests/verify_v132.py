import unittest,sys,tempfile,json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from OpenSees_Model_Response_Spectrum_V132 import cqc_matrix,combine,design_cd
from OpenSees_Response_Checks_V132 import drift_check,irregularity
from NBC105_Analysis_Settings_V109 import calculate_esm

class V132Checks(unittest.TestCase):
    def test_cqc_single_mode(self):
        np.testing.assert_allclose(combine([[2.,-3.]],cqc_matrix([10.])),[2.,3.])
    def test_cqc_close_modes(self):
        rho=cqc_matrix([10.,10.001]);self.assertGreater(rho[0,1],.99);self.assertAlmostEqual(float(combine([1.,2.],cqc_matrix([10.,10.]))),3.)
    def test_dynamic_curve_and_service_reduction(self):
        cfg=dict(soil='C',Z=.35,I=1.,rmu=3.5,omegau=1.4,omegas=1.2,limit_state='ULS')
        self.assertAlmostEqual(design_cd(0.,cfg),.35/4.9)
        self.assertAlmostEqual(design_cd(.1,cfg),2.5*.35/4.9)
        cfg['limit_state']='SLS';self.assertAlmostEqual(design_cd(.1,cfg),.2*2.5*.35/1.2)
    def test_uls_comparison_retains_ineligibility(self):
        rows=[dict(story_number=1,height_m=95.,dead_load_kN=100.,other_live_load_kN=10.)]
        r=calculate_esm(rows,period_s=2.,soil_type='C',zoning_factor_z=.35,importance_factor_i=1.,limit_state='ULS',irregular=True,diagnostic_reference=True)
        self.assertFalse(r['code_eligible']);self.assertTrue(r['diagnostic_reference_only']);self.assertGreater(r['base_shear_kN'],0.)
    def test_drift_limits(self):
        self.assertEqual(drift_check([dict(design_drift_ratio=.007)],'SLS')[0]['status'],'EXCEEDS')
        self.assertEqual(drift_check([dict(design_drift_ratio=.024)],'ULS')[0]['status'],'PASS')
    def test_history_edge_export(self):
        from OpenSees_Response_Checks_V132 import export_history_checks
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as tmp:
            folder=Path(tmp);data=dict(base_z_m=0.,nodes={'1':[0.,0.,0.],'2':[0.,0.,3.]},diaphragms=[dict(master_tag=3,master_xyz=[0.,0.,3.],storey_number=1,slave_node_tags=[2])],frames=[dict(nodes=[1,2])],shells=[])
            (folder/'OpenSees_Complete_Model_Data_V118.json').write_text(json.dumps(data),encoding='utf-8')
            lines=[dict(time_s=0.,S1_UX_m=0.,S1_UY_m=0.,S1_drift_X=0.,S1_drift_Y=0.),dict(time_s=.1,S1_UX_m=.03,S1_UY_m=.015,S1_drift_X=.01,S1_drift_Y=.005)]
            peaks=export_history_checks(lines,[dict(story_name='S1',node=3,height=3.)],folder,'fixture','ULS',folder/'model.py')
            self.assertAlmostEqual(peaks['X'],.01);self.assertTrue((folder/'Deformation_fixture_V132.json').is_file())

    def test_workbook_period_uses_numeric_provenance(self):
        from types import SimpleNamespace
        from OpenSees_Earthquake_Analysis_NBC105_V111 import ESMGui
        class V:
            def __init__(self,value):self.value=value
            def get(self):return self.value
        g=SimpleNamespace(awx=V('1.958293628808864'),awy=V('2.203080332409972'),period_factor=V('1.25'),rayleigh_tx=V(''),rayleigh_ty=V(''),excel_tx=V('2.0385674 s - source cell'),excel_ty=V('1.9219798 s - source cell'),use_workbook_periods=V(True),period_sources={},project_input_audit={'values':{'workbook_adopted_tx':2.03856740011866}})
        self.assertAlmostEqual(ESMGui._adopted_axis_period(g,'X',95.),2.03856740011866)
        self.assertIn('Imported',g.period_sources['X'])
    def test_service_workbook_is_case_specific(self):
        from OpenSees_Project_Inputs_V123 import source_workbooks,SERVICE_SCALING
        paths=source_workbooks(ROOT,ROOT/'tests','SLS');self.assertIn(SERVICE_SCALING,[p.name for p in paths if p])

    def test_native_rsa_acceleration_units(self):
        import openseespy.opensees as ops
        ops.wipe();ops.model('basic','-ndm',1,'-ndf',1);ops.node(1,0.);ops.node(2,1.);ops.fix(1,1);ops.mass(2,1.);ops.uniaxialMaterial('Elastic',1,100.);ops.element('truss',1,1,2,1.,1);ops.eigen('-fullGenLapack',1);ops.modalProperties('-return');ops.responseSpectrumAnalysis(1,'-Tn',0.,6.,'-Sa',.980665,.980665,'-mode',1)
        self.assertAlmostEqual(abs(ops.nodeDisp(2,1)),.980665/100.,places=10);ops.wipe()

if __name__=='__main__':unittest.main()
