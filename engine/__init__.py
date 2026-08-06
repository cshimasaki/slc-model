"""
SLC financial model — the mechanics layer.

Python is the single source of computational truth. The assumptions layer
(../assumptions/*.yaml) supplies the inputs; the export layer (../export)
renders the results to JSON, HTML and Excel. Nothing downstream re-implements
any of the arithmetic here.

    from engine.model import run
    result = run("stress")
    result.state.statements.net_assets[-1]
"""

from .assumptions import Assumptions, load, load_all
from .model import ModelRun, run, run_all

__all__ = ["Assumptions", "load", "load_all", "ModelRun", "run", "run_all"]
