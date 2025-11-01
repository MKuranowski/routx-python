# (c) Copyright 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from collections.abc import Iterator, MutableMapping
from ctypes import byref, cast, pointer
from dataclasses import dataclass
from enum import IntEnum
from os import PathLike
from typing import Final, NamedTuple, Self

from . import c

DEFAULT_STEP_LIMIT: Final[int] = 1000000
"""Recommended A* step limit for Graph.find_route."""


class StepLimitExceeded(ValueError):
    """Graph.find_route exceeded its step limit."""

    pass


class OsmLoadingError(ValueError):
    """Raised with the underlying library has failed to load OSM data data. See logs for details."""

    pass


class Node(NamedTuple):
    """
    An element of a Graph.

    Due to turn restriction processing, one OpenStreetMap node may be represented by
    multiple nodes in the graph. If that is the case, a "canonical" node
    (not bound by any turn restriction) will have `id == osm_id`.

    Nodes with `id == 0` are used by the underlying library to signify the absence of a node,
    are considered false-y and must not be used by consumers.
    """

    id: int
    osm_id: int
    lat: float
    lon: float

    @property
    def is_canonical(self) -> bool:
        return self.id == self.osm_id

    def __bool__(self) -> bool:
        return self.id != 0


class Edge(NamedTuple):
    """
    Outgoing (one-way) connection from a Node.

    `cost` must be greater than the crow-flies distance between the two nodes.
    """

    to: int
    cost: float


class OsmPenalty(NamedTuple):
    """Numeric multiplier for OSM ways with specific keys and values."""

    key: str
    """
    Key of an OSM way for which this penalty applies,
    used for `value` comparison (e.g. "highway" or "railway").
    """

    value: str
    """
    Value under `key` of an OSM way for which this penalty applies.
    E.g. "motorway", "residential", or "rail".
    """

    penalty: float
    """
    Multiplier of the length, to express preference for a specific way.
    Must be not less than one and be finite.
    """


class OsmProfile(IntEnum):
    """Predefined OSM conversion profiles."""

    CAR = 1
    """
    Car routing profile.

    Penalties:
    | Tag                    | Penalty |
    |------------------------|---------|
    | highway=motorway       | 1.0     |
    | highway=motorway_link  | 1.0     |
    | highway=trunk          | 2.0     |
    | highway=trunk_link     | 2.0     |
    | highway=primary        | 5.0     |
    | highway=primary_link   | 5.0     |
    | highway=secondary      | 6.5     |
    | highway=secondary_link | 6.5     |
    | highway=tertiary       | 10.0    |
    | highway=tertiary_link  | 10.0    |
    | highway=unclassified   | 10.0    |
    | highway=minor          | 10.0    |
    | highway=residential    | 15.0    |
    | highway=living_street  | 20.0    |
    | highway=track          | 20.0    |
    | highway=service        | 20.0    |

    Access tags: `access`, `vehicle`, `motor_vehicle`, `motorcar`.

    Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
    """

    BUS = 2
    """
    Bus routing profile.

    Penalties:
    | Tag                    | Penalty |
    |------------------------|---------|
    | highway=motorway       | 1.0     |
    | highway=motorway_link  | 1.0     |
    | highway=trunk          | 1.0     |
    | highway=trunk_link     | 1.0     |
    | highway=primary        | 1.1     |
    | highway=primary_link   | 1.1     |
    | highway=secondary      | 1.15    |
    | highway=secondary_link | 1.15    |
    | highway=tertiary       | 1.15    |
    | highway=tertiary_link  | 1.15    |
    | highway=unclassified   | 1.5     |
    | highway=minor          | 1.5     |
    | highway=residential    | 2.5     |
    | highway=living_street  | 2.5     |
    | highway=track          | 5.0     |
    | highway=service        | 5.0     |

    Access tags: `access`, `vehicle`, `motor_vehicle`, `psv`, `bus`, `routing:ztm`.

    Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
    """

    BICYCLE = 3
    """
    Bicycle routing profile.

    Penalties:
    | Tag                    | Penalty |
    |------------------------|---------|
    | highway=trunk          | 50.0    |
    | highway=trunk_link     | 50.0    |
    | highway=primary        | 10.0    |
    | highway=primary_link   | 10.0    |
    | highway=secondary      | 3.0     |
    | highway=secondary_link | 3.0     |
    | highway=tertiary       | 2.5     |
    | highway=tertiary_link  | 2.5     |
    | highway=unclassified   | 2.5     |
    | highway=minor          | 2.5     |
    | highway=cycleway       | 1.0     |
    | highway=residential    | 1.0     |
    | highway=living_street  | 1.5     |
    | highway=track          | 2.0     |
    | highway=service        | 2.0     |
    | highway=bridleway      | 3.0     |
    | highway=footway        | 3.0     |
    | highway=steps          | 5.0     |
    | highway=path           | 2.0     |

    Access tags: `access`, `vehicle`, `bicycle`.

    Disallows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
    """

    FOOT = 4
    """
    Pedestrian routing profile.

    Penalties:
    | Tag                       | Penalty |
    |---------------------------|---------|
    | highway=trunk             | 4.0     |
    | highway=trunk_link        | 4.0     |
    | highway=primary           | 2.0     |
    | highway=primary_link      | 2.0     |
    | highway=secondary         | 1.3     |
    | highway=secondary_link    | 1.3     |
    | highway=tertiary          | 1.2     |
    | highway=tertiary_link     | 1.2     |
    | highway=unclassified      | 1.2     |
    | highway=minor             | 1.2     |
    | highway=residential       | 1.2     |
    | highway=living_street     | 1.2     |
    | highway=track             | 1.2     |
    | highway=service           | 1.2     |
    | highway=bridleway         | 1.2     |
    | highway=footway           | 1.05    |
    | highway=path              | 1.05    |
    | highway=steps             | 1.15    |
    | highway=pedestrian        | 1.0     |
    | highway=platform          | 1.1     |
    | railway=platform          | 1.1     |
    | public_transport=platform | 1.1     |

    Access tags: `access`, `foot`.

    Disallows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad).

    One-way is only considered when explicitly tagged with `oneway:foot` or on
    `highway=footway`, `highway=path`, `highway=steps`, `highway/public_transport/railway=platform`.

    Turn restrictions are only considered when explicitly tagged with `restriction:foot`.
    """

    RAILWAY = 5
    """
    Railway routing profile.

    Penalties:
    | Tag                  | Penalty |
    |----------------------|---------|
    | railway=rail         | 1.0     |
    | railway=light_rail   | 1.0     |
    | railway=subway       | 1.0     |
    | railway=narrow_gauge | 1.0     |

    Access tags: `access`, `train`.

    Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
    """

    TRAM = 6
    """
    Tram and light rail routing profile.

    Penalties:
    | Tag                  | Penalty |
    |----------------------|---------|
    | railway=tram         | 1.0     |
    | railway=light_rail   | 1.0     |

    Access tags: `access`, `tram`.

    Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
    """

    SUBWAY = 7
    """
    Subway routing profile.

    Penalties:
    | Tag            | Penalty |
    |----------------|---------|
    | railway=subway | 1.0     |

    Access tags: `access`, `subway`.

    Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
    """


@dataclass
class OsmCustomProfile:
    """
    Describes how to convert OSM data into a Graph.

    If possible, usage of pre-defined OsmProfiles should be preferred.
    Using custom profile involves reallocation of all arrays and strings
    two times to match ABIs (first from Python to C, then from C to Rust).
    This is only a constant cost incurred on call to Graph.add_from_file or Graph.add_from_memory.
    """

    name: str
    """Human readable name of the routing profile,
    customary the most specific [access tag](https://wiki.openstreetmap.org/wiki/Key:access).

    This value is not used for actual OSM data interpretation,
    except when set to "foot", which adds the following logic:
    - `oneway` tags are ignored - only `oneway:foot` tags are considered, except on:
        - `highway=footway`,
        - `highway=path`,
        - `highway=steps`,
        - `highway=platform`
        - `public_transport=platform`,
        - `railway=platform`;
    - only `restriction:foot` turn restrictions are considered.
    """

    penalties: list[OsmPenalty]
    """
    Tags of OSM ways which can be used for routing.

    A way is matched against all OsmPenalty objects in order, and once an exact key and value match
    is found; the way is used for routing, and each connection between two nodes gets
    a resulting cost equal to the distance between nodes multiplied the penalty.

    All penalties must be normal and not less than zero.

    For example, if there are two penalties:
    1. highway=motorway, penalty=1
    2. highway=trunk, penalty=1.5

    This will result in:
    - a highway=motorway stretch of 100 meters will be used for routing with a cost of 100.
    - a highway=trunk motorway of 100 meters will be used for routing with a cost of 150.
    - a highway=motorway_link or highway=primary won't be used for routing, as they do not any penalty.
    """

    access: list[str]
    """
    List of OSM [access tags](https://wiki.openstreetmap.org/wiki/Key:access#Land-based_transportation)
    (in order from least to most specific) to consider when checking for road prohibitions.

    This list is used mainly to follow the access tags, but also to follow mode-specific one-way
    and turn restrictions.
    """

    disallow_motorroad: bool = False
    """Force no routing over [motorroad=yes](https://wiki.openstreetmap.org/wiki/Key:motorroad) ways."""

    disable_restrictions: bool = False
    """Force ignoring of [turn restrictions](https://wiki.openstreetmap.org/wiki/Turn_restriction)."""


class OsmFormat(IntEnum):
    """Format of the input OSM file."""

    UNKNOWN = 0
    """Unknown format - guess based on content."""

    XML = 1
    """Force uncompressed [OSM XML](https://wiki.openstreetmap.org/wiki/OSM_XML)"""

    XML_GZ = 2
    """
    Force [OSM XML](https://wiki.openstreetmap.org/wiki/OSM_XML)
    with [gzip](https://en.wikipedia.org/wiki/Gzip) compression
    """

    XML_BZ2 = 3
    """
    Force [OSM XML](https://wiki.openstreetmap.org/wiki/OSM_XML)
    with [bzip2](https://en.wikipedia.org/wiki/Bzip2) compression
    """

    PBF = 4
    """Force [OSM PBF](https://wiki.openstreetmap.org/wiki/PBF_Format)"""


class Graph(MutableMapping[int, Node]):
    """
    OpenStreetMap-based network representation as a set of nodes and edges between them.

    Node access is implemented through the standard
    [MutableMapping interface](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)
    from ids (integers) to nodes.

    Node that overwriting existing nodes preserves all outgoing and incoming edges. Thus updating
    a node position might result in violation of the Edge invariant and break route finding.
    It **is discouraged** to update nodes, and it is the caller's responsibility not to break
    this invariant.

    Edge access is implemented through custom get_edges, get_edge, set_edge and delete_edge methods.
    """

    def __init__(self) -> None:
        self.handle = c.lib.routex_graph_new()

    def __del__(self) -> None:
        c.lib.routex_graph_delete(self.handle)

    def __getitem__(self, key: int) -> Node:
        n = _node_from_c(c.lib.routex_graph_get_node(self.handle, key))
        if n.id == 0:
            raise KeyError(key)
        return n

    def __setitem__(self, key: int, value: Node) -> None:
        if key != value.id:
            raise ValueError(f"attempt to save node with id {value.id} under different id, {key}")
        c.lib.routex_graph_set_node(self.handle, _node_to_c(value))

    def __delitem__(self, key: int) -> None:
        deleted = c.lib.routex_graph_delete_node(self.handle, key)
        if not deleted:
            raise KeyError(key)

    def __iter__(self) -> Iterator[int]:
        it_handle = c.GraphIterator_p()
        try:
            c.lib.routex_graph_get_nodes(self.handle, byref(it_handle))
            while n := _node_from_c(c.lib.routex_graph_iterator_next(it_handle)):
                yield n.id
        finally:
            c.lib.routex_graph_iterator_delete(it_handle)

    def __len__(self) -> int:
        return c.lib.routex_graph_get_nodes(self.handle, None).value

    def find_nearest_node(self, lat: float, lon: float) -> Node:
        """
        Find the closest canonical (`id == osm_id`) Node to the given position.

        This function requires computing distance to every Node in the graph
        and is not suitable for large graphs or for multiple searches.
        Use KDTree for faster NN finding.

        If the graph is empty, raises KeyError.
        """
        n = _node_from_c(c.lib.routex_graph_find_nearest_node(self.handle, lat, lon))
        if not n:
            raise KeyError("find_nearest_node on empty Graph")
        return n

    def get_edges(self, from_: int) -> list[Edge]:
        """Gets all outgoing edges from a node with a given id."""
        c_ptr = c.POINTER(c.Edge)()
        c_ptr_len = c.lib.routex_graph_get_edges(self.handle, from_, byref(c_ptr)).value
        return [_edge_from_c(c_ptr[i]) for i in range(c_ptr_len)]

    def get_edge(self, from_: int, to: int) -> float:
        """
        Gets the cost of traversing an edge between nodes with provided ids.
        Returns positive infinity when the provided edge does not exist.
        """
        return c.lib.routex_graph_get_edge(self.handle, from_, to).value


    def set_edge(self, from_: int, to: int, cost: float) -> bool:
        """
        Creates or updates an Edge from one node to another.

        The `cost` must not be smaller than the crow-flies distance between nodes,
        as this would violate the A* invariant and break route finding. It is the
        caller's responsibility to uphold this invariant.

        Returns True if an existing edge was overwritten, False otherwise.

        Note that given an `Edge` object, this method may be called with `g.set_edge(from_, *edge)`.
        """
        return c.lib.routex_graph_set_edge(self.handle, from_, c.Edge(to=to, cost=cost)).value

    def delete_edge(self, from_: int, to: int, /, missing_ok: bool = True) -> None:
        """
        Ensures an Edge from one node to another does not exist.

        If no such edge exists and `missing_ok` is set to `False`, raises KeyError.
        """
        removed = c.lib.routex_graph_delete_edge(self.handle, from_, to).value
        if not removed and not missing_ok:
            raise KeyError((from_, to))

    def find_route(
        self,
        from_: int,
        to: int,
        /,
        without_turn_around: bool = True,
        step_limit: int = DEFAULT_STEP_LIMIT,
    ) -> list[int]:
        """
        Finds the cheapest way between two nodes using the [A* algorithm](https://en.wikipedia.org/wiki/A*_search_algorithm).
        Returns a list node IDs of such route. The list may be empty if no route exists.

        `without_turn_around` defaults to `True` and prevents the algorithm from circumventing
        turn restrictions by suppressing unrealistic turn-around instructions (A-B-A).
        This introduces an extra dimension to the search space, so if the graph doesn't contain
        any turn restriction, this parameter should be set to `False`.

        `step_limit` limits how many nodes can be expanded during search before raising StepLimitExceeded.
        Concluding that no route exists requires expanding all nodes accessible from the start,
        which is usually very time consuming, especially on large datasets.
        """
        func = (
            c.lib.routex_find_route_without_turn_around if without_turn_around else c.lib.find_route
        )
        res = func(self.handle, from_, to, step_limit)
        try:
            res_type = res.type_.value
            if res_type == 0:
                # TODO: Could we return a memoryview with type "q"?
                return [res.union.as_ok.nodes[i].value for i in range(res.union.as_ok.len.value)]
            elif res_type == 1:
                raise KeyError(res.union.as_invalid_reference.invalid_node_id.value)
            elif res_type == 2:
                raise StepLimitExceeded()
            else:
                raise RuntimeError(f"routex_find_route returned unexpected result type: {res_type}")
        finally:
            c.lib.routex_route_result_delete(res)

    def add_from_osm_file(
        self,
        filename: str | bytes | PathLike[str] | PathLike[bytes],
        profile: OsmProfile | OsmCustomProfile,
        /,
        format: OsmFormat = OsmFormat.UNKNOWN,
        bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> None:
        """
        Parses OSM data from the provided file and adds them to this graph.

        `profile` describes how the OSM data should be interpreted.

        `format` describes the file format of the input OSM data. Defaults to auto-detection.

        `bbox` filters features by a specific bounding box, in order:
        left (min lon), bottom (min lat), right (max lon), top (max lat).
        Ignored if all values are zero (default).
        """
        if isinstance(filename, PathLike):
            filename = filename.__fspath__()
        if isinstance(filename, str):
            filename = filename.encode("utf-8")

        ok = c.lib.routex_graph_add_from_osm_file(
            self.handle,
            _osm_options_to_c(profile, format, bbox),
            filename,
        ).value
        if not ok:
            raise OsmLoadingError()

    def add_from_osm_memory(
        self,
        mv: memoryview,
        profile: OsmProfile | OsmCustomProfile,
        /,
        format: OsmFormat = OsmFormat.UNKNOWN,
        bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> None:
        """
        Parses OSM data from the provided contents of a memory file.
        The buffer must be contiguous and also mutable (for reasons only known to
        [ctypes](https://docs.python.org/3/library/ctypes.html#ctypes._CData.from_buffer),
        because the underlying library takes a const pointer).

        `profile` describes how the OSM data should be interpreted.

        `format` describes the file format of the input OSM data. Defaults to auto-detection.

        `bbox` filters features by a specific bounding box, in order:
        left (min lon), bottom (min lat), right (max lon), top (max lat).
        Ignored if all values are zero (default).
        """
        mv = mv.cast("B")
        ok = c.lib.routex_graph_add_from_osm_memory(
            self.handle,
            _osm_options_to_c(profile, format, bbox),
            c.c_ubyte_p.from_buffer(mv),
            len(mv),
        ).value
        if not ok:
            raise OsmLoadingError()


class KDTree:
    """
    [k-d tree data structure](https://en.wikipedia.org/wiki/K-d_tree) which can be used to
    speed up nearest-neighbor search for large datasets.

    Create with `KDTree.build`, as the constructors takes a raw C handler.
    """
    def __init__(self, handle: c.KDTree_p) -> None:
        self.handle = handle

    def __del__(self) -> None:
        c.lib.routex_kd_tree_delete(self.handle)

    @classmethod
    def build(cls, graph: Graph) -> Self:
        """
        Builds a k-d tree with all canonical (`id == osm_id`) nodes contained in the provided graph.
        """
        return cls(c.lib.routex_kd_tree_new(graph.handle))

    def find_nearest_node(self, lat: float, lon: float) -> int:
        """
        Find the closest node to the provided position and returns its id.

        Raises KeyError when the k-d tree contains no nodes.
        """
        id = c.lib.routex_kd_tree_find_nearest_node(self.handle, lat, lon).value
        if id == 0:
            raise KeyError("find_nearest_node on empty KDTree")
        return id


def earth_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return c.lib.routex_earth_distance(lat1, lon1, lat2, lon2).value


def _node_to_c(o: Node) -> c.Node:
    return c.Node(id=o.id, osm_id=o.osm_id, lat=o.lat, lon=o.lon)


def _node_from_c(o: c.Node) -> Node:
    return Node(id=o.id.value, osm_id=o.osm_id.value, lat=o.lat.value, lon=o.lon.value)


def _edge_from_c(o: c.Edge) -> Edge:
    return Edge(to=o.to.value, cost=o.cost.value)


def _osm_profile_to_c(profile: OsmProfile | OsmCustomProfile):
    if isinstance(profile, OsmProfile):
        return cast(c.c_void_p(profile.value), c.OsmProfile_p)

    c_profile = c.OsmProfile()
    c_profile.name = profile.name.encode("utf-8")

    c_profile.penalties = (c.OsmProfilePenalty * len(profile.penalties))()
    for i, (key, value, penalty) in enumerate(profile.penalties):
        c_profile.penalties[i] = c.OsmProfilePenalty(
            key=key.encode("utf-8"),
            value=value.encode("utf-8"),
            penalty=penalty,
        )
    c_profile.penalties_len = len(profile.penalties)

    c_profile.access = (c.c_char_p * len(profile.access))()
    for i, access_key in enumerate(profile.access):
        c_profile.access[i] = access_key.encode("utf-8")
    c_profile.access_len = len(profile.access)

    c_profile.disallow_motorroad = profile.disallow_motorroad
    c_profile.disable_restrictions = profile.disable_restrictions

    return pointer(c_profile)


def _osm_options_to_c(
    profile: OsmProfile | OsmCustomProfile,
    format: OsmFormat,
    bbox: tuple[float, float, float, float],
):
    o = c.OsmOptions()
    o.profile = _osm_profile_to_c(profile)
    o.file_format = format.value
    o.bbox[0] = bbox[0]
    o.bbox[1] = bbox[1]
    o.bbox[2] = bbox[2]
    o.bbox[3] = bbox[3]
    return pointer(o)
