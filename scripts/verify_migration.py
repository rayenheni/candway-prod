"""Verify migration file syntax and check DB connection."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verify migration file is valid Python
import importlib.util
migration_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "alembic", "versions", "c4d5e6f7a8b9_architecture_refactor_phase_2.py"
)
spec = importlib.util.spec_from_file_location("migration", migration_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(f"Revision: {mod.revision}")
print(f"Down revision: {mod.down_revision}")
print(f"Has upgrade: {hasattr(mod, 'upgrade')}")
print(f"Has downgrade: {hasattr(mod, 'downgrade')}")

# Try running alembic check
from alembic.config import Config
from alembic.script import ScriptDirectory
alembic_cfg = Config(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini"))
script = ScriptDirectory.from_config(alembic_cfg)
head = script.get_current_head()
print(f"Alembic head: {head}")

# Check if MySQL is reachable
try:
    from backend.database import engine
    with engine.connect() as conn:
        result = conn.execute(mod.sa.text("SELECT 1")).scalar()
        print(f"DB connection OK, SELECT 1 = {result}")
except Exception as e:
    print(f"DB connection: {e}")
