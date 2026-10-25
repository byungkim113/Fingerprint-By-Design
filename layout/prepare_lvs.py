"""Make a local LVS reference with the installed standard-cell library path."""
from pathlib import Path
import re
import sys

source, output, pdk = map(Path, sys.argv[1:4])
text = source.read_text()
library = pdk / 'sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice'
text = re.sub(r'(?mi)^\.include\s+"[^"\r\n]*sky130_fd_sc_hd\.spice"\s*$',
              lambda _: f'.include "{library}"', text)
output.write_text(text)
