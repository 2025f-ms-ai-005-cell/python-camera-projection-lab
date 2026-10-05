"""Distortion-free camera-frame projection learning lab; standard library only."""
import argparse
import csv
import html
import json
import math
import sys
import tempfile
from pathlib import Path

def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite number')
    return float(value)

def validate_camera(camera):
    if not isinstance(camera, dict):
        raise ValueError('Camera must be an object')
    result = {key: finite(camera[key]) for key in ['fx', 'fy', 'cx', 'cy']}
    if result['fx'] <= 0 or result['fy'] <= 0:
        raise ValueError('Focal lengths must be positive')
    for key in ['width', 'height']:
        value = camera[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8192:
            raise ValueError('Image dimensions must be integers in 1..8192')
        result[key] = value
    return result

def project(point, camera):
    if not isinstance(point, (list, tuple)) or len(point) != 3:
        raise ValueError('Point must have exactly three coordinates')
    x, y, z = map(finite, point)
    if z <= 1e-6:
        return {'xyz': [x, y, z], 'status': 'behind_or_near_plane', 'uv': None}
    u, v = camera['fx'] * x / z + camera['cx'], camera['fy'] * y / z + camera['cy']
    if not math.isfinite(u) or not math.isfinite(v):
        raise ValueError('Projection overflow')
    status = 'in_frame' if 0 <= u < camera['width'] and 0 <= v < camera['height'] else 'outside_frame'
    return {'xyz': [x, y, z], 'status': status, 'uv': [u, v]}

def backproject(u, v, z, camera):
    u, v, z = map(finite, [u, v, z])
    if z <= 1e-6:
        raise ValueError('Positive optical-axis depth required')
    xyz = [(u - camera['cx']) * z / camera['fx'], (v - camera['cy']) * z / camera['fy'], z]
    if not all(math.isfinite(value) for value in xyz):
        raise ValueError('Backprojection overflow')
    return xyz

def process(data):
    camera = validate_camera(data['camera'])
    points = data['points']
    if not isinstance(points, list) or not 1 <= len(points) <= 10000:
        raise ValueError('Provide 1..10000 points')
    rows = [dict(index=i, **project(point, camera)) for i, point in enumerate(points)]
    counts = {status: sum(row['status'] == status for row in rows)
              for status in ['in_frame', 'outside_frame', 'behind_or_near_plane']}
    return {'camera': camera, 'counts': counts, 'points': rows,
            'convention': 'camera frame: X right, Y down, Z forward; z is axial depth'}

def svg_report(report):
    cam = report['camera']
    w, h = cam['width'], cam['height']
    dots = ''.join(f'<circle cx="{row["uv"][0]:.3f}" cy="{row["uv"][1]:.3f}" r="5" fill="#65e2bf"><title>Point {row["index"]}; Z={row["xyz"][2]:.3f}</title></circle>'
                   for row in report['points'] if row['status'] == 'in_frame')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="Synthetic projected image plane"><rect width="{w}" height="{h}" fill="#15263e"/><path d="M {cam["cx"]} 0 V {h} M 0 {cam["cy"]} H {w}" stroke="#5a6f8b" stroke-dasharray="6 6"/>{dots}</svg>'

def export(data, output):
    report = process(data)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output exists; select a new directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        stage = Path(folder) / 'report'
        stage.mkdir()
        (stage / 'results.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        (stage / 'projection.svg').write_text(svg_report(report), encoding='utf-8')
        with (stage / 'points.csv').open('w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['index', 'X', 'Y', 'Z', 'u', 'v', 'status'])
            for row in report['points']:
                writer.writerow([row['index'], *row['xyz'], *(row['uv'] or ['', '']), row['status']])
        counts = report['counts']
        rows = ''.join(f'<tr><td>{row["index"]}</td><td>{html.escape(str(row["xyz"]))}</td><td>{html.escape(str(row["uv"]))}</td><td>{row["status"]}</td></tr>' for row in report['points'][:100])
        page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Camera Projection Lab</title>
<style>body{{margin:0;padding:48px;background:#0b1528;color:#eef5ff;font:18px system-ui}}h1{{font-size:44px;color:#65e2bf}}.cards{{display:flex;gap:20px;flex-wrap:wrap}}.card{{padding:22px;background:#1e304b;border-radius:16px}}img{{width:min(100%,800px);margin:24px 0;border-radius:16px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;border-bottom:1px solid #345}}a{{color:#65e2bf}}</style>
<h1>Camera Projection Lab</h1><p>From 3D camera coordinates to 2D pixels · Synthetic learning fixture</p>
<div class="cards"><div class="card">In frame: {counts['in_frame']}</div><div class="card">Outside: {counts['outside_frame']}</div><div class="card">Behind / near: {counts['behind_or_near_plane']}</div></div>
<img src="projection.svg" alt="Computed synthetic projected point image plane"><p>X right · Y down · Z forward. Dashed lines mark principal point axes.</p><p>u = fx X/Z + cx · v = fy Y/Z + cy</p><table><tr><th>Point</th><th>Camera XYZ</th><th>Pixel UV</th><th>Status</th></tr>{rows}</table><p>HTML shows first 100 points; all records are exported.</p><a href="results.json">JSON</a> · <a href="points.csv">CSV</a><p>No calibration, lens distortion, occlusion reasoning or robot control. In-frame projection does not establish visibility.</p></html>'''
        (stage / 'index.html').write_text(page, encoding='utf-8')
        stage.rename(output)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 2_000_000:
            raise ValueError('Input file too large')
        data = json.loads(args.input.read_text(encoding='utf-8'))
        report = export(data, args.output)
        print(json.dumps(report['counts']))
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        print('Invalid input or output: check schema, finite coordinates, camera values and new output path.', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
