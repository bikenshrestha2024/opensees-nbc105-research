"""Small independent fixtures for assembly, equilibrium and manifest selection."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from OpenSees_Complete_Export_V118 import (
    prepare_complete_export,build_complete_model,autoselect_inputs,
    _area_property,_consistent_segment_load,_basis,_validate_insertion_point,
)
import openseespy.opensees as ops


class CompleteExportTests(unittest.TestCase):
    def test_insertion_stiffness_flag(self):
        _validate_insertion_point([8,False,False,[0,0,0],[0,0,0],'Local',0], '251')
        _validate_insertion_point([8,False,False,[1,0,0],[0,0,0],'Local',0], '251')
        with self.assertRaisesRegex(ValueError, 'StiffTransform=True'):
            _validate_insertion_point([8,False,True,[0,0,0],[0,0,0],'Local',0], '251')
        with self.assertRaises(ValueError):
            _validate_insertion_point([8,False], '251')

    def test_wall_signature_recovery(self):
        row=dict(property_type='wall',assigned_property='Wall600',material_name='1',thickness_m=None,
                 raw_property_api={'GetWall':repr([1,1,'M45',.6,0,'','guid',0])})
        p=_area_property(row,{'M45':dict(E=3e7,nu=.2,weight=25)})
        self.assertEqual(p['material'],'M45');self.assertEqual(p['thickness'],.6)

    def test_consistent_line_load_preserves_end_moments(self):
        # Independent fixed-end beam identities for a uniform downward load.
        f=_consistent_segment_load(6,_basis([0,0,0],[6,0,0]),0,6,[0,0,-10],[0,0,-10])
        self.assertAlmostEqual(f[2],-30);self.assertAlmostEqual(f[8],-30)
        self.assertAlmostEqual(abs(f[4]),10*6**2/12)
        self.assertAlmostEqual(f[4],-f[10])

    def test_connected_export_equilibrium_and_autoselection(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests',prefix='assembled_fixture_') as tmp:
            p=Path(tmp)
            xyz={1:[0,0,0],2:[2,0,0],3:[0,0,3],4:[2,0,3],5:[2,2,3],6:[0,2,3],7:[1,0,3]}
            frames=[dict(etabs_object=str(i),dimension='line_2_node',category=c,node_tags=ns)
                    for i,c,ns in ((1,'COLUMN',[1,3]),(2,'COLUMN',[2,4]),(3,'BEAM',[3,4]))]
            area=dict(etabs_object='A',dimension='area_polygon',category='FLOOR',node_tags=[3,4,5,6])
            topology=dict(node_map=[dict(etabs_point_name=str(n),opensees_node_tag=n,coordinates_m=q) for n,q in xyz.items()],
                elements=frames+[area],rigid_diaphragm_groups=[dict(storey_number=1,master_xyz=[1,1,3],slave_node_tags=[3,4,5,6,7])])
            rows=[dict(etabs_object=str(i),assigned_section='Column' if i<3 else 'Beam',section_type='rectangle',
                width_m=.3,depth_m=.3 if i<3 else .5,E_kN_m2=3e7,G_kN_m2=1.25e7,weight_per_volume=25)
                for i in (1,2,3)]
            section=dict(frame_assignments=rows,area_assignments=[dict(etabs_area_object='A',assigned_property='Slab150',
                property_type='slab',material_name='M35',thickness_m=.15,material_values=dict(E=3e7,poisson_ratio=.2,weight_per_volume=25))],
                frame_distributed_load_assignments=[dict(object='3',pattern='Wall',direction_code=10,coordinate_system='Global',load_type=1,distance_start=0,distance_end=2,value_start=2,value_end=2)])
            loads=dict(direct_uniform_loads_status='READ',uniform_load_sets_status='READ',applied_area_loads=[dict(object='A',pattern='Floor Finish',direction_code=6,coordinate_system='Global',value=-2)],
                etabs_load_pattern_self_weight_multipliers=[dict(pattern='Self Weight',multiplier=1)],base_supports=dict(node_tags=[1,2]))
            for filename,data in [('OpenSees_Element_Connectivity.json',topology),('OpenSees_Section_Assignment_Audit.json',section),('OpenSees_Load_Conversion_Audit.json',loads),('OpenSees_Source_Model_Metadata_V118.json',{'pattern_types':{},'scope':'synthetic test fixture'})]:
                (p/filename).write_text(json.dumps(data),encoding='utf-8')
            manifest,report=prepare_complete_export(p,runtime_dir=ROOT)
            self.assertEqual(report['assembly_errors'],[])
            self.assertGreaterEqual(report['shell_mesh_cells'],2)
            mesh=json.loads((p/'OpenSees_Complete_Model_Data_V118.json').read_text(encoding='utf-8-sig'))
            self.assertAlmostEqual(sum(c['area'] for c in mesh['shells']),4.0)
            self.assertTrue(all(c['area']>0 for c in mesh['shells']))
            self.assertGreaterEqual(report['frame_segments'],4)  # conforming refinement may add segments
            self.assertAlmostEqual(report['total_downward_load_kN'],48)
            result=build_complete_model(p,preload=True)
            self.assertTrue(result['preload_completed'])
            check=json.loads((p/'OpenSees_Complete_Gravity_Check_V118.json').read_text())
            self.assertLess(check['equilibrium_error_percent'],1e-6)
            self.assertTrue(all(v>0 and math.isfinite(v) for v in ops.eigen(2)))
            class Variable:
                def set(self,value):self.value=value
            class GUI:
                model=Variable();stories=Variable();output=Variable();readiness=Variable()
            gui=GUI();self.assertTrue(autoselect_inputs(gui,p,'linear_model_script'))
            self.assertEqual(Path(gui.model.value).name,'OpenSees_Complete_Linear_Model.py')
            self.assertEqual(Path(gui.stories.value).name,manifest['story_master_csv'])
            # Calibration remains required even when an elastic model converges.
            with self.assertRaisesRegex(ValueError,'reviewed frame and wall'):
                build_complete_model(p,mode='nonlinear',preload=True)
            ops.wipe()


if __name__=='__main__':unittest.main(verbosity=2)
