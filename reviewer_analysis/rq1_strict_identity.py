"""Independent exact-identity measurement; not historical substring matcher."""
import re
from urllib.parse import unquote

def norm(s):return re.sub(r'[-_.]+','-',s.lower())
def matches(e,c):
 k=e['kind']
 if k=='python_distribution':
  p=c.get('purl','')
  if not p.startswith('pkg:pypi/') or '@' not in p:return False
  name,version=p[len('pkg:pypi/'):].split('?',1)[0].rsplit('@',1)
  return norm(c.get('name',''))==norm(e['name'])==norm(unquote(name)) and c.get('version')==e['version']==unquote(version)
 if k=='file_sha256':return bool(e.get('required_source_present') and e.get('SHA256') and c.get('name')==e['name'] and any(h.get('alg')=='SHA-256' and h.get('content')==e['SHA256'] for h in c.get('hashes',[])))
 if k=='model_revision':return c.get('type')=='machine-learning-model' and c.get('name')==e['name'] and c.get('version')==e['revision']
 if k=='typed_name_version':return c.get('type')==e['cdx_type'] and c.get('name','').casefold()==e['name'].casefold() and c.get('version')==e['version']
 return False
