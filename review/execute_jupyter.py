"""Run the notebook through a real Jupyter kernel and retain its output."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
path = root / 'notebook/fingerprint_by_design.ipynb'
nb = nbformat.read(path, as_version=4)
client = NotebookClient(nb, timeout=300, kernel_name='python3',
                        resources={'metadata': {'path': str(root)}})
client.execute()
nbformat.write(nb, path)
print('PASS: real Jupyter execution from project root;',
      sum(c.cell_type == 'code' for c in nb.cells), 'code cells')
