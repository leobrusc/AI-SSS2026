from pathlib import Path
import csv,json,hashlib,sys,subprocess,platform
from datetime import datetime,timezone
root=Path.cwd(); a=root/'reviewer_analysis'; stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); out=root/'generated/camera_ready'/('discovery-'+stamp); out.mkdir(parents=True)
files=[p for d in ['results','generated','workspace','config','src','tests','scripts','fixtures'] for p in (root/d).rglob('*') if p.is_file() and 'camera_ready' not in p.parts and '__pycache__' not in p.parts]
with (out/'initial_file_hashes.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.writer(f);w.writerow(['path','SHA256','bytes']);w.writerows((str(p.relative_to(root)),hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size) for p in files)
print(out); print('historical files:',len(files)); print('manuscripts:',[str(p) for p in root.rglob('main.tex') if '.venv' not in p.parts]);print('bibliographies:',[str(p) for p in root.rglob('*.bib') if '.venv' not in p.parts])
