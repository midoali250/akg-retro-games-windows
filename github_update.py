"""Independently authenticated GitHub release checks for desktop builds.

This downloads a verified update after user consent. Replacing an installed
application is intentionally left to the user; platform installers vary.
"""
import base64,json,re,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from signed_updates import MAX_MANIFEST,UpdateError,_RestrictedRedirect,verify_manifest,download_verified
PRODUCT='akg-retro-games'
ORIGINS={('github.com',443),('release-assets.githubusercontent.com',443),('objects.githubusercontent.com',443),('github-releases.githubusercontent.com',443)}
EXTENSIONS={'windows':'.exe','linux':'.appimage','macos':'.zip'}

def load_key(root,platform):
 d=json.loads((Path(root)/'updates'/'public-key.json').read_text(encoding='utf8'))
 if d.get('algorithm')!='Ed25519' or d.get('platform')!=platform:raise UpdateError('Wrong update key for platform')
 try:key=base64.b64decode(d['public_key_base64'],validate=True)
 except (KeyError,ValueError,TypeError) as e:raise UpdateError('Invalid update key') from e
 if len(key)!=32:raise UpdateError('Invalid update key')
 return key

def load_version(root):
 d=json.loads((Path(root)/'updates'/'version.json').read_text(encoding='utf8'))
 v=d.get('version_code')
 if type(v) is not int or v<1:raise UpdateError('Invalid installed version')
 return v

def _check_release_url(url,platform):
 p=urllib.parse.urlsplit(url);parts=p.path.split('/')
 if platform not in EXTENSIONS or p.scheme!='https' or p.hostname!='github.com' or p.username or p.password or p.query or p.fragment or p.port not in (None,443) or len(parts)!=7 or parts[1]!='midoali250' or parts[2]!='akg-retro-games-'+platform or parts[3:5]!=['releases','download'] or not parts[5]:raise UpdateError('Update URL does not match this platform repository')
 filename=urllib.parse.unquote(parts[6])
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+ -]{0,179}',filename) or not filename.lower().endswith(EXTENSIONS[platform]):raise UpdateError('Invalid update filename')
 return filename

def check(platform,root,current=None):
 if current is None:current=load_version(root)
 if platform not in EXTENSIONS:raise UpdateError('Unsupported platform')
 key=load_key(root,platform);url='https://github.com/midoali250/akg-retro-games-'+platform+'/releases/latest/download/akg-update-manifest.json'
 opener=urllib.request.build_opener(_RestrictedRedirect(ORIGINS))
 try:
  with opener.open(urllib.request.Request(url,headers={'User-Agent':'AKG-Retro-Games-Update/1','Accept-Encoding':'identity'}),timeout=25) as response:
   if response.status!=200:raise UpdateError('Unexpected response')
   raw=response.read(MAX_MANIFEST+1)
 except urllib.error.HTTPError as e:
  if e.code==404:return None
  raise UpdateError('Cannot fetch update manifest') from e
 try:manifest=verify_manifest(raw,key,PRODUCT,platform,current,ORIGINS)
 except UpdateError as e:
  if str(e)=='not a newer version':return None
  raise
 _check_release_url(manifest['url'],platform)
 return manifest

def download(platform,manifest,directory):
 name=_check_release_url(manifest['url'],platform)
 return download_verified(manifest,Path(directory)/name,ORIGINS)
