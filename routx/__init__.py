# (c) Copyright 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from .wrapper import (
    DEFAULT_STEP_LIMIT,
    Edge,
    Graph,
    KDTree,
    Node,
    OsmCustomProfile,
    OsmFormat,
    OsmLoadingError,
    OsmPenalty,
    OsmProfile,
    StepLimitExceeded,
    earth_distance,
)

__all__ = [
    "DEFAULT_STEP_LIMIT",
    "Edge",
    "Graph",
    "KDTree",
    "Node",
    "OsmCustomProfile",
    "OsmFormat",
    "OsmLoadingError",
    "OsmPenalty",
    "OsmProfile",
    "StepLimitExceeded",
    "earth_distance",
]

__title__ = "routx"
__description__ = "Simple routing over OpenStreetMap data "
__url__ = "https://github.com/MKuranowski/routx-python"
__author__ = "Mikołaj Kuranowski"
__copyright__ = "© Copyright 2025 Mikołaj Kuranowski"
__license__ = "MIT"
__version__ = "0.1.0"
__email__ = "mkuranowski+pypackages@gmail.com"
