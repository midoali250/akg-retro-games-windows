"""Signed update verification/download primitives. No network trust in SHA alone.

A host application must pin a real Ed25519 public key and allowed HTTPS origins,
provide user consent, and implement platform-specific installation. No keys or
URLs are provisioned by this module.
"""
import base64,hashlib,json,os,re,tempfile,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_MANIFEST=131072
MAX_PACKAGE=2_000_000_000
HEX=re.compile(r'^[0-9a-f]{64}$')
PLATFORMS={'android','windows','linux','macos'}
class UpdateError(ValueError):pass

def _pairs(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise UpdateError('duplicate JSON key')
  result[k]=v
 return result

def _json(data):
 try:return json.loads(data,object_pairs_hook=_pairs)
 except (UnicodeError,json.JSONDecodeError,TypeError) as e:raise UpdateError('invalid JSON') from e

def _b64(value,max_decoded):
 if not isinstance(value,str) or len(value)>max_decoded*2:raise UpdateError('invalid encoding')
 try:result=base64.b64decode(value,validate=True)
 except (ValueError,TypeError) as e:raise UpdateError('invalid encoding') from e
 if len(result)>max_decoded:raise UpdateError('oversized content')
 return result

def _https_origin(url,allowed_origins):
 if not isinstance(url,str) or len(url)>4096:raise UpdateError('invalid URL')
 try:
  u=urllib.parse.urlsplit(url)
  if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or u.fragment:raise UpdateError('invalid HTTPS URL')
  host=u.hostname.encode('idna').decode('ascii').lower();port=u.port or 443
 except (ValueError,UnicodeError) as e:raise UpdateError('invalid URL') from e
 if (host,port) not in allowed_origins:raise UpdateError('origin not allowed')
 return url

def verify_manifest(envelope_bytes,public_key,product,platform,current_version,allowed_origins):
 """Authenticate exact payload bytes, validate identity, version and destination."""
 if not isinstance(envelope_bytes,bytes) or len(envelope_bytes)>MAX_MANIFEST:raise UpdateError('oversized or invalid manifest')
 if platform not in PLATFORMS or not isinstance(product,str) or not product:raise UpdateError('invalid expected identity')
 if type(current_version) is not int or current_version<0:raise UpdateError('invalid current version')
 if not isinstance(public_key,bytes) or len(public_key)!=32:raise UpdateError('invalid public key')
 env=_json(envelope_bytes)
 if not isinstance(env,dict) or set(env)!={'payload','signature'}:raise UpdateError('invalid envelope')
 payload=_b64(env['payload'],MAX_MANIFEST);signature=_b64(env['signature'],64)
 if len(signature)!=64:raise UpdateError('invalid signature length')
 try:Ed25519PublicKey.from_public_bytes(public_key).verify(signature,payload)
 except (InvalidSignature,ValueError) as e:raise UpdateError('signature verification failed') from e
 manifest=_json(payload)
 required={'schema_version','product','platform','version_code','size_bytes','sha256','url'}
 if not isinstance(manifest,dict) or set(manifest)!=required:raise UpdateError('invalid manifest fields')
 if type(manifest['schema_version']) is not int or manifest['schema_version']!=1:raise UpdateError('unsupported schema')
 if manifest['product']!=product or manifest['platform']!=platform:raise UpdateError('wrong product or platform')
 version=manifest['version_code'];size=manifest['size_bytes'];digest=manifest['sha256']
 if type(version) is not int or version<=current_version:raise UpdateError('not a newer version')
 if type(size) is not int or not 0<size<=MAX_PACKAGE:raise UpdateError('invalid size')
 if not isinstance(digest,str) or not HEX.fullmatch(digest):raise UpdateError('invalid hash')
 _https_origin(manifest['url'],allowed_origins)
 return manifest

class _RestrictedRedirect(urllib.request.HTTPRedirectHandler):
 def __init__(self,allowed_origins):self.allowed_origins=allowed_origins
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  _https_origin(newurl,self.allowed_origins)
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def download_verified(manifest,destination,allowed_origins,timeout=60):
 """Download to a sibling temporary file; publish only after exact size and hash."""
 url=_https_origin(manifest.get('url'),allowed_origins)
 expected_size=manifest.get('size_bytes');expected_hash=manifest.get('sha256')
 if type(expected_size) is not int or not 0<expected_size<=MAX_PACKAGE or not isinstance(expected_hash,str) or not HEX.fullmatch(expected_hash):raise UpdateError('invalid authenticated metadata')
 destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
 opener=urllib.request.build_opener(_RestrictedRedirect(allowed_origins))
 fd,tmp=tempfile.mkstemp(prefix='.update-',suffix='.part',dir=destination.parent)
 try:
  total=0;digest=hashlib.sha256()
  with os.fdopen(fd,'wb') as f,opener.open(urllib.request.Request(url,headers={'User-Agent':'BitVault-Update/1','Accept-Encoding':'identity'}),timeout=timeout) as response:
   if response.status!=200:raise UpdateError('unexpected HTTP status')
   while True:
    block=response.read(1024*1024)
    if not block:break
    total+=len(block)
    if total>expected_size:raise UpdateError('download exceeds expected size')
    digest.update(block);f.write(block)
   f.flush();os.fsync(f.fileno())
  if total!=expected_size or digest.hexdigest()!=expected_hash:raise UpdateError('download integrity mismatch')
  os.replace(tmp,destination)
 except BaseException:
  try:os.unlink(tmp)
  except OSError:pass
  raise
 return destination
