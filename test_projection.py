import math
import tempfile
import unittest
from pathlib import Path
from projection import validate_camera, project, backproject, process, export

CAM = {'fx':100,'fy':100,'cx':50,'cy':50,'width':100,'height':100}

class ProjectionTests(unittest.TestCase):
    def test_center(self):
        self.assertEqual(project([0,0,2],CAM)['uv'],[50,50])
    def test_depth_scaling(self):
        self.assertEqual(project([1,0,2],CAM)['uv'][0],100)
        self.assertEqual(project([1,0,4],CAM)['uv'][0],75)
    def test_frame_boundary(self):
        self.assertEqual(project([1,0,2],CAM)['status'],'outside_frame')
        self.assertEqual(project([-1,0,2],CAM)['status'],'in_frame')
    def test_behind(self):
        for z in [0,-1,1e-6]:
            self.assertIsNone(project([0,0,z],CAM)['uv'])
    def test_roundtrip(self):
        point=[.5,-.3,4]
        uv=project(point,CAM)['uv']
        for expected, actual in zip(point,backproject(*uv,4,CAM)):
            self.assertAlmostEqual(expected,actual)
    def test_invalid_points(self):
        for point in [[1,2],[1,True,3],[0,0,math.nan],[0,0,math.inf]]:
            with self.assertRaises(ValueError): project(point,CAM)
    def test_invalid_camera(self):
        for key, value in [('fx',0),('fy',-1),('width',True),('height',100.5)]:
            with self.assertRaises(ValueError): validate_camera(dict(CAM,**{key:value}))
    def test_invalid_depth(self):
        with self.assertRaises(ValueError): backproject(0,0,0,CAM)
    def test_empty(self):
        with self.assertRaises(ValueError): process({'camera':CAM,'points':[]})
    def test_export(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'report'
            data={'camera':CAM,'points':[[0,0,1]]}
            export(data,out)
            for name in ['index.html','projection.svg','points.csv','results.json']:
                self.assertTrue((out/name).exists())
            with self.assertRaises(ValueError): export(data,out)

if __name__=='__main__': unittest.main()
