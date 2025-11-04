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

## License

routx and routx-python are made available under the MIT license.
