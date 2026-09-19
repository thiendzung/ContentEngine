from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.research.production as production_module
from app.modules.harness.policy import BudgetLimits
from app.modules.knowledge.retrieval import RetrievalHit
from app.modules.research.contracts import (
    CommercialBias,
    IntendedUse,
    PageDocument,