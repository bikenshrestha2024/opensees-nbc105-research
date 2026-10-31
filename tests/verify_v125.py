from pathlib import Path
import unittest,sys,json,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from OpenSees_Mapping_Audit_V125 import collect,save_assignment,validate_device,add_device

class Checks(unittest.TestCase):
    def fixture(self,path):
        top=dict(node_map=[dict(etabs_point_name='P1',opensees_node_tag=1,coordinates_m=[0,0,0])],elements=[dict(etabs_object='1',dimension='area_polygon',category='SHEAR WALL',assigned_property='Wall 600',node_tags=[1],node_names=['P1'],element_tag=11),dict(etabs_object='2',dimension='line_2_node',category='BRACE',assigned_section='SHS',node_tags=[1,2],node_names=['P1','P2'],element_tag=12)])
        (path/'OpenSees_Element_Connectivity.json').write_text(json.dumps(top))
        (path/'OpenSees_Area_Section_Assignment_Audit.json').write_text(json.dumps(dict(assignments=[dict(etabs_area_object='1',assigned_property='Wall 600',material_name='M45',thickness_m=.6)])))
    def test_nested_area_audit_and_category(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d);self.fixture(p);data=collect(p)
            self.assertEqual(data['properties'][0]['material'],'M45');self.assertEqual(data['properties'][0]['thickness_m'],.6)
    def test_per_element_selection_and_activation_guard(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
            p=Path(d);self.fixture(p)
            result=save_assignment(p,['FRAME:2'],'FVD_MAXWELL');self.assertFalse(result['active'])
            with self.assertRaises(ValueError):save_assignment(p,['AREA:1'],'FVD_MAXWELL')
            with self.assertRaises(ValueError):save_assignment(p,['FRAME:2'],'FVD_MAXWELL',active=True)
    def test_no_inferred_fvd_stiffness(self):
        from Define_Section_V109 import define_fvd_material
        with self.assertRaises(ValueError):define_fvd_material(None)
    def test_device_implementation_receives_explicit_values(self):
        class Ops:
            def __init__(self):self.commands=[]
            def uniaxialMaterial(self,*args):self.commands.append(args)
            def element(self,*args):self.commands.append(args)
        ops=Ops();selection=dict(target='FVD_MAXWELL',citation='Unit-test synthetic inputs, not project calibration',parameters=dict(K=1000,Cd=20,alpha=.5,weight_reviewed=True))
        add_device(ops,100001,dict(nodes=[1,2]),selection)
        self.assertEqual(ops.commands[0][0],'ViscousDamper');self.assertEqual(ops.commands[0][2:5],(1000.,20.,.5))
        self.assertEqual(ops.commands[1][0],'twoNodeLink')
    def test_excel_reference_not_modal_claim(self):
        from OpenSees_ETABS_Periods_V125 import workbook_references
        refs=workbook_references(ROOT,ROOT)
        self.assertAlmostEqual(refs['adopted_X']['value'],2.03856740011866)
        self.assertAlmostEqual(refs['adopted_Y']['value'],1.921979776706312)
        self.assertIn('not eigenperiod',refs['adopted_X']['kind']);self.assertNotIn('modal_X',refs)
    def test_open_requested_starts_etabs_on_attach_failure(self):
        from OpenSees_ETABS_Periods_V125 import attach_or_open
        import comtypes.client
        class Sap:
            def OpenFile(self,path):self.opened=path;return 0
        class App:
            def __init__(self):self.SapModel=type('Model',(),{})();self.SapModel.File=Sap();self.started=False
            def ApplicationStart(self):self.started=True;return 0
        app=App()
        class Helper:
            def QueryInterface(self,*args):return self
            def CreateObjectProgID(self,name):return app
        with patch('OpenSees_Project_Inputs_V123.connect_etabs',side_effect=RuntimeError('unavailable')),patch('OpenSees_ETABS_Periods_V125.source_edb',return_value=str(ROOT/'fake.EDB')),patch.object(comtypes.client,'CreateObject',return_value=Helper()):
            self.assertIs(attach_or_open(ROOT,True),app)
        self.assertTrue(app.started);self.assertTrue(app.SapModel.File.opened.endswith('fake.EDB'))

if __name__=='__main__':unittest.main(verbosity=2)
