"""Default-off actual endpoint delivery, then once-only real training metadata."""
import runpy
from storage_20261122 import CONTROL as C
from e1_frozen_report_20261126 import run
run()
runpy.run_path(str(C/'report_extensions_startup_20261126.py'),run_name='__main__')
runpy.run_path(str(C/'refresh_extension_daily_20261126.py'),run_name='__main__')
