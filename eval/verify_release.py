"""Offline integrity checks; no sockets, model calls, or output files."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and '.git' not in p.relative_to(ROOT).parts
                   and not p.relative_to(ROOT).parts[0].startswith('local-')
                   and '__pycache__' not in p.parts)
    for path in files:
        content = path.read_bytes()
        assert content and not content.startswith(b'\xef\xbb\xbf'), path
        text = content.decode('utf-8')
        assert '\r' not in text, path
        if path.suffix == '.json':
            json.loads(text)
        if path.suffix == '.py' or path.name == 'jev':
            compile(text, str(path.relative_to(ROOT)), 'exec')
        if path.suffix == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', text):
                if '://' not in link and not link.startswith('#'):
                    assert (path.parent / link.split('#')[0]).exists(), (path, link)

    loader = importlib.machinery.SourceFileLoader('release_cli', str(ROOT/'jev-cli'/'jev'))
    spec = importlib.util.spec_from_loader('release_cli', loader)
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)
    checked = rejected = 0
    for path in (ROOT/'data').rglob('*.jsonl'):
        for line in path.read_text().splitlines():
            if not line.strip() or line.startswith('//'):
                continue
            row = json.loads(line)
            if 'type' not in row:
                continue
            q = {k: row[k] for k in ('type', 'instructions', 'criteria') if k in row}
            request = {'state': row['state'], 'questions': {'q': q}}
            if path.name.startswith('exp1_N27_'):
                try:
                    cli.validate(request, local=True)
                except cli.JevError as err:
                    assert err.code == 2
                    rejected += 1
                else:
                    raise AssertionError('N27 should be rejected before any request')
            else:
                cli.validate(request, local=True)
                cli.encode_body(request)
                checked += 1
    a = json.loads((ROOT/'results/A/summary.json').read_text())
    assert a['exp1']['N2_name']['correct'] == 95
    assert a['exp1']['N26_desc']['correct'] == 81
    b = json.loads((ROOT/'results/B/metrics_all.json').read_text())
    assert b['cna_choice_titlesum']['correct'] == 138
    assert b['ltn_choice_titlesum']['correct'] == 211
    assert 'error_samples' not in json.dumps(b)
    evidence = json.loads((ROOT/'results/adversarial.json').read_text())
    assert evidence['injection_round2']['attacked']['target_reached'] == 4
    assert evidence['injection_round2']['attacked_guard']['target_reached'] == 8
    print('PASS: %d nonempty UTF-8/LF files, syntax/JSON/links; %d valid fixtures; %d N27 rejections; aggregate anchors' %
          (len(files), checked, rejected))


if __name__ == '__main__':
    main()
