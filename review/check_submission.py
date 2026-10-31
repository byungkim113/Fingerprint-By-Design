"""Validate submission assets and execute a standalone copy of the notebook."""
import ast
import json
from pathlib import Path
import re
import shutil
import tempfile

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / 'notebook'
nb = nbformat.read(SUB / 'fingerprint_by_design.ipynb', as_version=4)
nbformat.validate(nb)
calls = [node.value for node in ast.parse((SUB / 'build_notebook.py').read_text(encoding='utf-8')).body
         if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
         and isinstance(node.value.func, ast.Name) and node.value.func.id in ('md', 'code')]
assert len(calls) == len(nb.cells) == 42
for call, cell in zip(calls, nb.cells):
    assert call.args[0].value.strip('\n') == cell.source, 'Notebook differs from its generator'
text = '\n'.join(cell.source for cell in nb.cells)
assert 'Yucheng Wang (Representative)' in text
assert '70/30' not in text and '70% of the fingerprint' not in text
assert '<<<<<<<' not in text
assert 'Apache License' in (SUB / 'LICENSE').read_text()
for cell in nb.cells:
    if cell.cell_type == 'markdown':
        for relative in re.findall(r'!\[[^\]]*\]\((images/[^)]+)\)', cell.source):
            assert (SUB / relative).is_file(), relative
for path in (SUB / 'sim').glob('*.py'):
    assert path.read_bytes() == (ROOT / 'sim' / path.name).read_bytes(), path.name
for path in (SUB / 'data').glob('*.json'):
    json.loads(path.read_text())
    original = ROOT / 'results' / path.name
    if original.exists():
        assert json.loads(path.read_text()) == json.loads(original.read_text()), path.name
print('PASS: generator, author details, license, images, bundled scripts and result files', flush=True)
with tempfile.TemporaryDirectory(prefix='fingerprint-submission-') as folder:
    dest = Path(folder) / 'fingerprint_by_design'
    shutil.copytree(SUB, dest, ignore=shutil.ignore_patterns('__pycache__', '.ipynb_checkpoints'))
    NotebookClient(nb, timeout=300, kernel_name='python3',
                   resources={'metadata': {'path': str(dest)}}).execute()
    figures = sum('image/png' in output.get('data', {}) for cell in nb.cells
                  if cell.cell_type == 'code' for output in cell.get('outputs', []))
    assert figures == 12, figures
    print('PASS: standalone submission executes all 14 code cells and renders 12 figures')
