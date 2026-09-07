"""Download public Valve icons for the locally imported Windrun snapshot."""
import concurrent.futures
import json
from pathlib import Path
import struct
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/'

def download(row):
    ident = row['abilityId']
    name = row.get('shortName')
    result = {'abilityId': ident, 'name': row.get('name'), 'shortName': name}
    if not name:
        return {**result, 'status': 'missing_name'}
    category = 'heroes' if ident < 0 else 'abilities'
    asset_name = name.removesuffix('_ad') if ident in {1517, 1518, 1519, 1520} else name
    result['assetName'] = asset_name
    if asset_name != name:
        result['note'] = 'Base Kez ability icon used for Ability Draft variant; verify visually during recognition.'
    url = BASE + category + '/' + asset_name + '.png'
    path = ROOT / 'assets' / category / (name + '.png')
    result.update(url=url, path=str(path.relative_to(ROOT)))
    try:
        if path.exists():
            payload = path.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=25) as response:
                payload = response.read()
        if payload[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('Not a PNG image')
        width, height = struct.unpack('>II', payload[16:24])
        if not width or not height:
            raise ValueError('Invalid dimensions')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {**result, 'status': 'ok', 'width': width, 'height': height, 'bytes': len(payload)}
    except Exception as exc:
        return {**result, 'status': 'error', 'error': str(exc)}

if __name__ == '__main__':
    data = json.loads((ROOT / 'data/windrun-7.41d.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(download, data['abilityStats']))
    (ROOT / 'data/icon-manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    good = [r for r in results if r['status'] == 'ok']
    print(json.dumps({'downloaded': len(good), 'bytes': sum(r['bytes'] for r in good), 'unresolved': [r for r in results if r['status'] != 'ok']}, ensure_ascii=False, indent=2))
