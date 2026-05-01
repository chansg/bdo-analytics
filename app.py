"""
Repository-root launcher for the BDO Market Intelligence dashboard.

The actual Streamlit app lives in ``bdo-intelligence/app.py``. This small file
exists so the common command ``streamlit run app.py`` also works from the
repository root.
"""

import runpy
import sys
from pathlib import Path

from streamlit.runtime.scriptrunner import get_script_run_ctx


APP_DIR = Path(__file__).resolve().parent / "bdo-intelligence"
APP_FILE = APP_DIR / "app.py"


if get_script_run_ctx(suppress_warning=True) is None:
    print("\nThis is a Streamlit dashboard launcher.")
    print("Start it with this command:\n")
    print("    streamlit run app.py\n")
    sys.exit(0)


# Make imports like ``from api.market import ...`` resolve exactly as they do
# when the nested app is launched directly from the bdo-intelligence folder.
sys.path.insert(0, str(APP_DIR))

# Execute the real dashboard file inside this Streamlit run.
runpy.run_path(str(APP_FILE), run_name="__main__")
