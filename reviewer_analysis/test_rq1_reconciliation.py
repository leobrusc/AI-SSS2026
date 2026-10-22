"""Regression cases for identity collisions and the frozen denominator, not the serializer."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rq1_strict_identity import matches

def test_colorama_is_not_physical_ram():
 expected=dict(kind='typed_name_version',name='ram',version='31.5GB',cdx_type='device')
 assert not matches(expected,dict(name='colorama',type='library',version='0.4.6',purl='pkg:pypi/colorama@0.4.6'))

def test_matching_package_name_does_not_excuse_wrong_version():
 e=dict(kind='python_distribution',name='torch',version='2.0.0')
 assert not matches(e,dict(name='torch',version='1.0.0',purl='pkg:pypi/torch@1.0.0'))

def test_purl_and_component_version_must_agree():
 e=dict(kind='python_distribution',name='torch',version='2.0.0')
 assert not matches(e,dict(name='torch',version='2.0.0',purl='pkg:pypi/torch@1.0.0'))

def test_python_name_normalization_and_url_encoding_are_explicit():
 e=dict(kind='python_distribution',name='a-b',version='1.0+cpu')
 assert matches(e,dict(name='A_B',version='1.0+cpu',purl='pkg:pypi/a-b@1.0%2Bcpu?qualifier=value'))

def test_unversioned_model_does_not_satisfy_revision_pin():
 e=dict(kind='model_revision',name='org/model',revision='a'*40)
 assert not matches(e,dict(type='machine-learning-model',name='org/model'))

def test_same_file_name_different_digest_is_not_identity_match():
 e=dict(kind='file_sha256',name='policy.yaml',SHA256='a'*64,required_source_present=True)
 assert not matches(e,dict(name='policy.yaml',hashes=[dict(alg='SHA-256',content='b'*64)]))

def test_missing_source_is_not_certified_by_a_named_bom_declaration():
 e=dict(kind='file_sha256',name='model.safetensors',SHA256=None,required_source_present=False)
 assert not matches(e,dict(name='model.safetensors'))

def test_duplicate_records_cannot_inflate_represented_asset_count():
 e=dict(kind='typed_name_version',name='service',version='1',cdx_type='application')
 c=dict(name='service',version='1',type='application')
 assert sum(bool([x for x in [c,c] if matches(a,x)]) for a in [e])==1

def test_actual_frozen_denominator_keeps_missing_required_assets():
 root=Path(__file__).resolve().parents[1]
 resultpaths=sorted((root/'results/camera_ready/rq1').glob('*/coverage_result.json'))
 assert resultpaths,'No completed new campaign'
 p=resultpaths[-1];d=json.loads(p.read_text());u=json.loads((p.parent/'frozen_universe_v1.json').read_text())
 raw=json.loads((root/'results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json').read_text())
 assert {a['raw_id'] for a in u['assets'] if a['raw_id']}=={n['id'] for n in raw['nodes']}
 assert {a['asset_id'] for a in u['assets'] if a['asset_id']=='runtime-snapshot'}=={'runtime-snapshot'}
 assert d['N_total']==32 and d['N_applicable']==30
 assert all(a['applicability']=='REQUIRED' for a in u['assets'] if not a['source_present'])
