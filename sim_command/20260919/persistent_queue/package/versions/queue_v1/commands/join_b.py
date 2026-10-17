"""B executes this itself, after the shared READY SHA gate. A never launches B."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'queue'))
from qservice import start
if sys.argv[1:]!=['--node','B']:raise SystemExit('exact --node B required')
raise SystemExit(start('B'))
