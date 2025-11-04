# routx-python

Python bindings for [routx](https://github.com/mkuranowski/routx) -
library for simple routing over [OpenStreetMap](https://www.openstreetmap.org/) data.

Routx converts OSM data into a standard weighted directed graph representation,
and runs A* to find shortest paths between nodes. Interpretation of OSM data
is customizable via profiles. Routx supports one-way streets,
access tags (on ways only) and turn restrictions.

## Usage

`pip install routx` in a [virtual environment](https://docs.python.org/3/library/venv.html).

Precompiled wheels are available certain platforms (aarch64, x86-64 × GNU Linux, MacOS and Windows).
On anything else, [cargo](https://doc.rust-lang.org/cargo/getting-started/installation.html)
(please don't `curl | sh` and install from your system's package manager),
[ninja and C/C++ compiler toolchain](https://mesonbuild.com/Getting-meson.html#dependencies).

Of note is the lack of support for musl-based Linux systems, due to [lacking Rust support](https://github.com/rust-lang/rust/issues/59302).

```python
import routx

g = routx.Graph()
g.add_from_osm_file("path/to/monaco.pbf", routx.OsmProfile.CAR)

start_node = g.find_nearest_node(43.7384, 7.4246)
end_node = g.find_nearest_node(43.7478, 7.4323)
route = g.find_route(start_node.id, end_node.id)

for node_id in route:
    node = g[node_id]
    print(node.lat, node.lon)
```

## Reference

Unless noted otherwise, `__init__` methods behave as expected for standard
NamedTuple/dataclass/IntEnum objects.

### routx.DEFAULT_STEP_LIMIT

```py
DEFAULT_STEP_LIMIT: Final[int] = 1000000
```

Recommended A* step limit for routx.Graph.find_route.

### routx.Node

```
class Node(NamedTuple):
    id: int
    osm_id: int
    lat: float
    lon: float
```

An element of a [Graph](#routxgraph). A [named tuple](https://docs.python.org/3/library/typing.html#typing.NamedTuple).

Due to turn restriction processing, one OpenStreetMap node may be represented by
multiple nodes in the graph. If that is the case, a "canonical" node
(not bound by any turn restriction) will have `id == osm_id`.

Nodes with `id == 0` are used by the underlying library to signify the absence of a node,
are considered false-y and must not be used by consumers.

*Methods*:
- `__bool__(self) -> bool` - True if id is not zero.

*Read-only properties*:
- `is_canonical: bool` - True if `id == osm_id`.

### routx.Edge

```
class Edge(NamedTuple):
    to: int
    cost: float
```

Outgoing (one-way) connection from a [Node](#routxnode). A [named tuple](https://docs.python.org/3/library/typing.html#typing.NamedTuple).

`cost` must be greater than the crow-flies distance between the two nodes.

### routx.Graph

```
class Graph(MutableMapping[int, Node]):
    pass  # no attributes, constructor accepts no arguments
```

OpenStreetMap-based network representation as a set of [nodes](#routexnode) and [edges](#routxedge) between them.

Node access is implemented through the standard
[MutableMapping interface](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)
from ids (integers) to [nodes](#routxnode).

Note that overwriting existing nodes preserves all outgoing and incoming edges. Thus updating
a node position might result in violation of the Edge invariant and break route finding.
It **is discouraged** to update nodes, and it is the caller's responsibility not to break
this invariant.

*Methods* (other than the implemented for and inherited from `MutableMapping[int, Node]`):

- `find_nearest_node(lat: float, lon: float) -> Node` - find the closest canonical (`id == osm_id`) Node to the given position.

    This function requires computing distance to every Node in the graph
    and is not suitable for large graphs or for multiple searches.
    Use [KDTree](#routxkdtree) for faster NN finding.

    If the graph is empty, raises KeyError.

- `get_edges(self, from_: int) -> list[Edge]` - gets all outgoing edges from a node with a given id.

- `get_edge(self, from_: int, to: int) -> float` - gets the cost of traversing an edge between nodes with provided ids.
    Returns positive infinity when the provided edge does not exist.

- `set_edge(self, from_: int, to: int, cost: float) -> bool` - creates or updates an Edge from one node to another.

    The `cost` must not be smaller than the crow-flies distance between nodes,
    as this would violate the A* invariant and break route finding. It is the
    caller's responsibility to uphold this invariant.

    Returns True if an existing edge was overwritten, False otherwise.

    Note that given an `Edge` object, this method may be called with `graph.set_edge(from_, *edge)`.

- `delete_edge(self, from_: int, to: int, /, missing_ok: bool = True) -> None` -
    ensures an Edge from one node to another does not exist.
    If no such edge exists and `missing_ok` is set to `False`, raises KeyError.

- ```
    find_route(
        self,
        from_: int,
        to: int,
        /,
        without_turn_around: bool = True,
        step_limit: int = DEFAULT_STEP_LIMIT,
    ) -> list[int]
    ```
    Finds the cheapest way between two nodes using the [A* algorithm](https://en.wikipedia.org/wiki/A*_search_algorithm).
    Returns a list node IDs of such route. The list may be empty if no route exists.

    `without_turn_around` defaults to `True` and prevents the algorithm from circumventing
    turn restrictions by suppressing unrealistic turn-around instructions (A-B-A).
    This introduces an extra dimension to the search space, so if the graph doesn't contain
    any turn restriction, this parameter should be set to `False`.

    `step_limit` limits how many nodes can be expanded during search before raising StepLimitExceeded.
    Concluding that no route exists requires expanding all nodes accessible from the start,
    which is usually very time consuming, especially on large datasets.

- ```
    add_from_osm_file(
        self,
        filename: str | bytes | PathLike[str] | PathLike[bytes],
        profile: OsmProfile | OsmCustomProfile,
        /,
        format: OsmFormat = OsmFormat.UNKNOWN,
        bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> None
    ```
    Parses OSM data from the provided file and adds them to this graph.

    `profile` describes how the OSM data should be interpreted.

    `format` describes the file format of the input OSM data. Defaults to auto-detection.

    `bbox` filters features by a specific bounding box, in order:
    left (min lon), bottom (min lat), right (max lon), top (max lat).
    Ignored if all values are zero (default).

- ```
    add_from_osm_memory(
        self,
        mv: memoryview,
        profile: OsmProfile | OsmCustomProfile,
        /,
        format: OsmFormat = OsmFormat.UNKNOWN,
        bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> None
    ```
    Parses OSM data from the provided contents of a memory file.
    The buffer must be contiguous and also mutable (for reasons only known to
    [ctypes](https://docs.python.org/3/library/ctypes.html#ctypes._CData.from_buffer),
    because the underlying library takes a const pointer).

    `profile` describes how the OSM data should be interpreted.

    `format` describes the file format of the input OSM data. Defaults to auto-detection.

    `bbox` filters features by a specific bounding box, in order:
    left (min lon), bottom (min lat), right (max lon), top (max lat).
    Ignored if all values are zero (default).

### routx.KDTree

```
class KDTree:
    pass # no attributes, private constructor
```

*Methods*:
- `find_nearest_node(self, lat: float, lon: float) -> Node` - finds the closest node to the provided position and returns its id.
    Raises KeyError when the k-d tree contains no nodes.

*Class Methods*:
- `KDTree.build(graph: Graph) -> Self` - builds a k-d tree with all canonical 
    (`id == osm_id`) nodes contained in the provided graph.

### routx.OsmProfile

```
class OsmProfile(IntEnum):
    CAR = 1
    BUS = 2
    BICYCLE = 3
    FOOT = 4
    RAILWAY = 5
    TRAM = 6
    SUBWAY = 7
```

Predefined OSM conversion profiles. An [IntEnum](https://docs.python.org/3/library/enum.html#enum.IntEnum).

<details>
<summary>CAR</summary>
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
</details>

<details>
<summary>BUS</summary>
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
</details>

<details>
<summary>BICYCLE</summary>
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
</details>

<details>
<summary>FOOT</summary>
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
</details>

<details>
<summary>RAILWAY</summary>
Penalties:

| Tag                  | Penalty |
|----------------------|---------|
| railway=rail         | 1.0     |
| railway=light_rail   | 1.0     |
| railway=subway       | 1.0     |
| railway=narrow_gauge | 1.0     |

Access tags: `access`, `train`.

Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
</details>

<details>
<summary>TRAM</summary>
Penalties:

| Tag                  | Penalty |
|----------------------|---------|
| railway=tram         | 1.0     |
| railway=light_rail   | 1.0     |

Access tags: `access`, `tram`.

Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
</details>

<details>
<summary>SUBWAY</summary>
Penalties:

| Tag            | Penalty |
|----------------|---------|
| railway=subway | 1.0     |

Access tags: `access`, `subway`.

Allows [motorroads](https://wiki.openstreetmap.org/wiki/Key:motorroad) and considers turn restrictions.
</details>


### routx.OsmFormat

```
class OsmFormat(IntEnum):
    UNKNOWN = 0
    XML = 1
    XML_GZ = 2
    XML_BZ2 = 3
    PBF = 4
```

Format of the input OSM file. An [IntEnum](https://docs.python.org/3/library/enum.html#enum.IntEnum).

*Values*:
- `UNKNOWN` - unknown format - guess based on content.
- `XML` - force uncompressed [OSM XML](https://wiki.openstreetmap.org/wiki/OSM_XML).
- `XML_GZ` - force [OSM XML](https://wiki.openstreetmap.org/wiki/OSM_XML) with [gzip](https://en.wikipedia.org/wiki/Gzip) compression.
- `XML_BZ2` - force [OSM XML](https://wiki.openstreetmap.org/wiki/OSM_XML)
    with [bzip2](https://en.wikipedia.org/wiki/Bzip2) compression.
- `PBF` - force [OSM PBF](https://wiki.openstreetmap.org/wiki/PBF_Format).

### routx.OsmPenalty

```
class OsmPenalty(NamedTuple):
    key: str
    value: str
    penalty: float
```

Numeric multiplier for OSM ways with specific keys and values. A [named tuple](https://docs.python.org/3/library/typing.html#typing.NamedTuple).

*Attributes*:
- `key: str` - key of an OSM way for which this penalty applies, used for `value` comparison (e.g. "highway" or "railway").
- `value: str` - value under `key` of an OSM way for which this penalty applies.E.g. "motorway", "residential", or "rail".
- `penalty: float` - multiplier of the length, to express preference for a specific way. Must be not less than one and be finite.

### routx.OsmCustomProfile

```
@dataclass
class OsmCustomProfile:
    name: str
    penalties: list[OsmPenalty]
    access: list[str]
    disallow_motorroad: bool = False
    disable_restrictions: bool = False
```

Describes how to convert OSM data into a [Graph](#routxgraph). A [dataclass](https://docs.python.org/3/library/dataclasses.html).

If possible, usage of pre-defined [OsmProfiles](#routxosmprofile) should be preferred.
Using custom profile involves reallocation of all arrays and strings
two times to match ABIs (first from Python to C, then from C to Rust).
This is only a constant cost incurred on call to Graph.add_from_file or Graph.add_from_memory.

*Attributes*:

- `name: str` - human readable name of the routing profile, customary the most specific [access tag](https://wiki.openstreetmap.org/wiki/Key:access).

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

- `penalties: list[OsmPenalty]` - tags of OSM ways which can be used for routing.

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

- `access: list[str]` - list of OSM [access tags](https://wiki.openstreetmap.org/wiki/Key:access#Land-based_transportation) (in order from least to most specific) to consider when checking for road prohibitions.

    This list is used mainly to follow the access tags, but also to follow mode-specific one-way and turn restrictions.

- `disallow_motorroad: bool` - force no routing over [motorroad=yes](https://wiki.openstreetmap.org/wiki/Key:motorroad) ways.

- `disable_restrictions: bool` - force ignoring of [turn restrictions](https://wiki.openstreetmap.org/wiki/Turn_restriction).

### routx.OsmLoadingError

```
class OsmLoadingError(ValueError):
    pass  # attributes and constructor the same as for ValueError
```

Raised with the underlying library has failed to load OSM data data. See logs for details.

### routx.StepLimitExceeded

```
class StepLimitExceeded(ValueError):
    pass  # attributes and constructor the same as for ValueError
```

Raised when Graph.find_route exceeded its step limit.

### routx.earth_distance

```
def earth_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
```

Calculates the great-circle distance between two positions using the [haversine formula](https://en.wikipedia.org/wiki/Haversine_formula).

Returns the result in kilometers.

## License

routx and routx-python are made available under the MIT license.
