import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from components.inputs.project_workbooks import _wall_aw_from_lines, import_project_inputs
from components.modal.analysis import nbc105_period_estimate


class NBC105PeriodTests(unittest.TestCase):
    def test_wall_aw_uses_each_contiguous_net_segment_length(self):
        area,segments=_wall_aw_from_lines(10.,{
            ('X',2.,.3):[(0.,1.),(1.,2.),(4.,7.)],
            ('Y',5.,.2):[(0.,1.)],
        })
        self.assertAlmostEqual(area['X'],.405)
        self.assertAlmostEqual(area['Y'],.042)
        self.assertEqual([row['wall_length_m'] for row in segments],[2.,3.,1.])

    def test_wall_aw_rejects_invalid_geometry(self):
        for height,lines in (
            (0.,{}),
            (10.,{('X',0.,.3):[(2.,1.)]}),
            (10.,{('Z',0.,.3):[(0.,2.)]}),
        ):
            with self.subTest(height=height,lines=lines),self.assertRaises(ValueError):
                _wall_aw_from_lines(height,lines)

    def test_importer_uses_full_first_story_and_splits_wall_openings(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests',prefix='wall_geometry_fixture_') as tmp:
            folder=Path(tmp)
            workbook_path=folder/'scaling.xlsx'
            workbook=Workbook()
            workbook.active.title='SCALING SUMMARY'
            workbook['SCALING SUMMARY']['B14']=1.
            workbook['SCALING SUMMARY']['B15']=1.
            workbook.save(workbook_path)
            (folder/'NBC105_Workbook_Source.json').write_text(
                json.dumps({'workbooks':[str(workbook_path)]}),encoding='utf-8')
            nodes=[];elements=[];area_assignments=[];tag=1

            def add_wall(axis,plane,intervals,thickness,object_id):
                nonlocal tag
                area_assignments.append({'etabs_area_object':object_id,'thickness':thickness})
                for start,end in intervals:
                    for z0,z1 in ((0.,1.5),(1.5,3.)):
                        if axis=='X':
                            quad=((start,plane,z0),(end,plane,z0),(end,plane,z1),(start,plane,z1))
                        else:
                            quad=((plane,start,z0),(plane,end,z0),(plane,end,z1),(plane,start,z1))
                        tags=[]
                        for xyz in quad:
                            tags.append(tag)
                            nodes.append({'opensees_node_tag':tag,'coordinates_m':list(xyz)})
                            tag+=1
                        elements.append({'category':'SHEAR WALL','etabs_object':object_id,'node_tags':tags})

            add_wall('X',0.,((0.,1.),(1.,2.),(4.,5.5),(5.5,7.)),.3,'wall-x')
            add_wall('Y',5.,((0.,1.),(1.,2.),(4.,5.5),(5.5,7.)),.2,'wall-y')
            nodes.append({'opensees_node_tag':tag,'coordinates_m':[0.,0.,10.]})
            topology={
                'node_map':nodes,'elements':elements,
                'rigid_diaphragm_groups':[
                    {'master_xyz':[0.,0.,3.]},{'master_xyz':[0.,0.,10.]},
                ],
            }
            (folder/'OpenSees_Element_Connectivity.json').write_text(
                json.dumps(topology),encoding='utf-8')
            (folder/'OpenSees_Section_Assignment_Audit.json').write_text(
                json.dumps({'area_assignments':area_assignments}),encoding='utf-8')
            exporter=types.ModuleType('OpenSees_Complete_Export_V118')
            exporter._area_property=lambda assignment,_defaults:{'thickness':assignment['thickness']}
            with patch.dict(sys.modules,{'OpenSees_Complete_Export_V118':exporter}):
                result=import_project_inputs(ROOT,folder,'ULS')
            self.assertAlmostEqual(result['values']['awx'],.405)
            self.assertAlmostEqual(result['values']['awy'],.27)
            self.assertEqual(len(result['values']['wall_geometry_segments']),4)

    def test_nbc_period_equations_and_adopted_period(self):
        result=nbc105_period_estimate(
            height_m=95.,system_type='concrete shear-wall building',
            wall_aw_x_m2=1.9582936288,wall_aw_y_m2=2.2030803324,
            rayleigh_x_s=3.8935194478,rayleigh_y_s=2.0)
        expected_x=.075*95.**.75/(1.9582936288**.5)
        self.assertAlmostEqual(result['empirical_X_s'],expected_x)
        self.assertAlmostEqual(result['amplified_empirical_X_s'],1.25*expected_x)
        self.assertAlmostEqual(result['adopted_design_period_X_s'],1.25*expected_x)
        self.assertEqual(result['adopted_period_status_Y'],
                         'READY: adopted period is lesser of Rayleigh and amplified empirical')
        self.assertEqual(nbc105_period_estimate(
            height_m=95.,system_type='steel moment-resisting frame')['empirical_X_s'],
            .085*95.**.75)

    def test_period_inputs_reject_nonfinite_and_nonpositive_values(self):
        invalid_cases=(
            {'height_m':float('nan'),'system_type':'other structural system'},
            {'height_m':95.,'system_type':'concrete shear-wall building','wall_aw_x_m2':float('inf')},
            {'height_m':95.,'system_type':'other structural system','rayleigh_x_s':0.},
        )
        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                nbc105_period_estimate(**kwargs)

    def test_rayleigh_cache_is_case_and_aw_specific(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests',prefix='period_fixture_') as tmp:
            folder=Path(tmp)
            workbook_path=folder/'scaling.xlsx'
            workbook=Workbook()
            workbook.active.title='SCALING SUMMARY'
            workbook['SCALING SUMMARY']['B14']=2.
            workbook['SCALING SUMMARY']['B15']=3.
            workbook.save(workbook_path)
            (folder/'NBC105_Workbook_Source.json').write_text(
                json.dumps({'workbooks':[str(workbook_path)]}),encoding='utf-8')
            model=folder/'OpenSees_Complete_Model_Data_V118.json'
            model.write_text('{"model":"fixture"}',encoding='utf-8')
            ledger=folder/'NBC105_ESM_Story_Weights_Assembled_V118.csv'
            ledger.write_text('story,height_m\\n1,3\\n',encoding='utf-8')
            model_hash=hashlib.sha256(model.read_bytes()).hexdigest()
            ledger_hash=hashlib.sha256(ledger.read_bytes()).hexdigest()
            output=folder/'OpenSees_Analysis_Results'
            output.mkdir()

            def save(state,period,aw_x=2.,aw_y=3.):
                payload={
                    'method_version':125,'limit_state':state,
                    'model_sha256':model_hash,'story_weights_sha256':ledger_hash,
                    'X':{'period_s':period,'Aw_m2':aw_x},
                    'Y':{'period_s':period+1.,'Aw_m2':aw_y},
                }
                name='NBC105_Rayleigh_Preliminary_V123'+('_SLS' if state=='SLS' else '')+'.json'
                (output/name).write_text(json.dumps(payload),encoding='utf-8')

            save('ULS',1.1)
            save('SLS',2.2)
            uls=import_project_inputs(ROOT,folder,'ULS')
            sls=import_project_inputs(ROOT,folder,'SLS')
            self.assertAlmostEqual(uls['values']['rayleigh_tx'],1.1)
            self.assertAlmostEqual(sls['values']['rayleigh_tx'],2.2)

            save('SLS',2.2,aw_x=2.1)
            stale=import_project_inputs(ROOT,folder,'SLS')
            self.assertNotIn('rayleigh_tx',stale['values'])
            self.assertTrue(any('wall Aw' in note for note in stale['notes']))


if __name__=='__main__':
    unittest.main(verbosity=2)
