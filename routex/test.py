from math import inf
from tempfile import NamedTemporaryFile
from unittest import TestCase

from .wrapper import (
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

OSM_FILE_FIXTURE = (
    "<?xml version='1.0' encoding='UTF-8'?><osm version='0.6'>\n"
    "<node id='-1' lat='0.00' lon='0.02' />\n"
    "<node id='-2' lat='0.00' lon='0.01' />\n"
    "<node id='-3' lat='0.00' lon='0.00' />\n"
    "<node id='-4' lat='0.01' lon='0.01' />\n"
    "<node id='-5' lat='0.01' lon='0.00' />\n"
    "<way id='-10'>\n"
    "  <nd ref='-1' /><nd ref='-2' />\n"
    "  <tag k='highway' v='tertiary' />\n"
    "</way>\n"
    "<way id='-11'>\n"
    "  <nd ref='-2' /><nd ref='-3' />\n"
    "  <tag k='highway' v='tertiary' />\n"
    "</way>\n"
    "<way id='-12'>\n"
    "  <nd ref='-2' /><nd ref='-4' />\n"
    "  <tag k='highway' v='residential' />\n"
    "</way>\n"
    "<way id='-13'>\n"
    "  <nd ref='-4' /><nd ref='-5' /><nd ref='-3' />\n"
    "  <tag k='highway' v='service' />\n"
    "</way>\n"
    "<relation id='-20'>\n"
    "  <member type='way' ref='-10' role='from' />\n"
    "  <member type='node' ref='-2' role='via' />\n"
    "  <member type='way' ref='-12' role='to' />\n"
    "  <tag k='restriction' v='only_left_turn' />\n"
    "  <tag k='type' v='restriction' />\n"
    "</relation>\n"
    "</osm>\n"
)


class TestGraph(TestCase):
    def test_node_manipulation(self) -> None:
        g = Graph()

        # len of empty graph
        self.assertEqual(len(g), 0)

        # node creation
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.01, 0.05)
        g[3] = Node(3, 3, 0.03, 0.09)

        # len of non-empty graph
        self.assertEqual(len(g), 3)

        # node getting on existing node
        n = g[2]
        self.assertEqual(n.id, 2)
        self.assertEqual(n.osm_id, 2)
        self.assertAlmostEqual(n.lat, 0.01)
        self.assertAlmostEqual(n.lon, 0.05)

        # node getting on non-existing node
        self.assertIsNone(g.get(42))
        with self.assertRaises(KeyError):
            g[42]

        # node removal
        del g[3]
        self.assertNotIn(3, g)
        self.assertIsNone(g.get(3))

        # node removal on non-existing node
        self.assertIsNone(g.pop(42, None))
        with self.assertRaises(KeyError):
            del g[42]

    def test_set_node_with_mismatched_id(self) -> None:
        g = Graph()
        with self.assertRaises(ValueError):
            g[0] = Node(1, 1, 0.0, 0.0)

    def test_node_overwrite(self) -> None:
        g = Graph()

        g[1] = Node(1, 1, 0.01, 0.01)
        n = g[1]
        self.assertEqual(n.id, 1)
        self.assertEqual(n.osm_id, 1)
        self.assertAlmostEqual(n.lat, 0.01)
        self.assertAlmostEqual(n.lon, 0.01)

        g[1] = Node(1, 1, -0.02, 0.05)
        n = g[1]
        self.assertEqual(n.id, 1)
        self.assertEqual(n.osm_id, 1)
        self.assertAlmostEqual(n.lat, -0.02)
        self.assertAlmostEqual(n.lon, 0.05)

    def test_node_iteration(self) -> None:
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.01, 0.05)
        g[3] = Node(3, 3, 0.03, 0.09)

        it = iter(g)
        n = next(it)
        self.assertEqual(n, 1)

        n = next(it)
        self.assertEqual(n, 2)

        n = next(it)
        self.assertEqual(n, 3)

        with self.assertRaises(StopIteration):
            next(it)

    def test_find_nearest_node(self) -> None:
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.01, 0.05)
        g[3] = Node(3, 3, 0.03, 0.09)
        g[4] = Node(4, 4, 0.04, 0.03)
        g[5] = Node(5, 5, 0.04, 0.07)
        g[6] = Node(6, 6, 0.07, 0.03)
        g[7] = Node(7, 7, 0.07, 0.01)
        g[8] = Node(8, 8, 0.08, 0.05)
        g[9] = Node(9, 9, 0.08, 0.09)

        self.assertEqual(g.find_nearest_node(0.02, 0.02).id, 1)
        self.assertEqual(g.find_nearest_node(0.05, 0.03).id, 4)
        self.assertEqual(g.find_nearest_node(0.05, 0.08).id, 5)
        self.assertEqual(g.find_nearest_node(0.09, 0.06).id, 8)

    def test_find_nearest_node_on_empty_graph(self) -> None:
        g = Graph()
        with self.assertRaises(KeyError):
            g.find_nearest_node(0.02, 0.02)

    def test_find_nearest_node_canonical(self) -> None:
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[100] = Node(100, 1, 0.01, 0.01)
        g[101] = Node(101, 1, 0.01, 0.01)

        self.assertEqual(g.find_nearest_node(0.02, 0.02).id, 1)

    def test_edge_manipulation(self) -> None:
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.01, 0.05)
        g[3] = Node(3, 3, 0.03, 0.09)

        # get_edge on a graph without edges
        self.assertEqual(g.get_edge(2, 1), inf)
        self.assertEqual(len(g.get_edges(2)), 0)

        # set_edge with new edges
        self.assertFalse(g.set_edge(1, 2, 200.0))
        g.set_edge(2, 1, 200.0)
        g.set_edge(2, 3, 100.0)
        g.set_edge(3, 2, 100.0)

        # get_edge and get_edges
        self.assertAlmostEqual(g.get_edge(2, 1), 200.0)
        edges = g.get_edges(2)
        self.assertEqual(len(edges), 2)
        self.assertEqual(edges[0].to, 1)
        self.assertEqual(edges[0].cost, 200.0)
        self.assertEqual(edges[1].to, 3)
        self.assertEqual(edges[1].cost, 100.0)

        # overwrite edge
        self.assertTrue(g.set_edge(1, 2, 150.0))
        self.assertAlmostEqual(g.get_edge(1, 2), 150.0)

        # delete existing edge
        g.delete_edge(1, 2)
        self.assertEqual(g.get_edge(1, 2), inf)

        # delete non-existing edge
        g.delete_edge(1, 42)
        with self.assertRaises(KeyError):
            g.delete_edge(1, 42, missing_ok=False)

    def test_find_route(self) -> None:
        #   200   200   200
        # 1─────2─────3─────4
        #       └─────5─────┘
        #         100    100
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.02, 0.01)
        g[3] = Node(3, 3, 0.03, 0.01)
        g[4] = Node(4, 4, 0.04, 0.01)
        g[5] = Node(5, 5, 0.03, 0.00)
        g.set_edge(1, 2, 200.0)
        g.set_edge(2, 1, 200.0)
        g.set_edge(2, 3, 200.0)
        g.set_edge(2, 5, 100.0)
        g.set_edge(3, 2, 200.0)
        g.set_edge(3, 4, 200.0)
        g.set_edge(4, 3, 200.0)
        g.set_edge(4, 5, 100.0)
        g.set_edge(5, 2, 100.0)
        g.set_edge(5, 4, 100.0)

        self.assertListEqual(
            g.find_route(1, 4, without_turn_around=False, step_limit=100),
            [1, 2, 5, 4],
        )

        self.assertListEqual(
            g.find_route(1, 4, without_turn_around=True, step_limit=100),
            [1, 2, 5, 4],
        )

    def test_find_route_with_turn_restriction(self) -> None:
        # 1
        # │
        # │10
        # │ 10
        # 2─────4
        # │     │
        # │10   │100
        # │ 10  │
        # 3─────5
        # mandatory 1-2-4
        g = Graph()
        g[1] = Node(1, 1, 0.00, 0.02)
        g[2] = Node(2, 2, 0.00, 0.01)
        g[20] = Node(20, 2, 0.00, 0.01)
        g[3] = Node(3, 3, 0.00, 0.00)
        g[4] = Node(4, 4, 0.01, 0.01)
        g[5] = Node(5, 5, 0.01, 0.00)
        g.set_edge(1, 20, 10.0)
        g.set_edge(2, 1, 10.0)
        g.set_edge(2, 3, 10.0)
        g.set_edge(2, 4, 10.0)
        g.set_edge(20, 4, 10.0)
        g.set_edge(3, 2, 10.0)
        g.set_edge(3, 5, 10.0)
        g.set_edge(4, 2, 10.0)
        g.set_edge(4, 5, 100.0)
        g.set_edge(5, 3, 10.0)
        g.set_edge(5, 4, 100.0)

        self.assertListEqual(
            g.find_route(1, 3, without_turn_around=False, step_limit=100),
            [1, 20, 4, 2, 3],
        )

        self.assertListEqual(
            g.find_route(1, 3, without_turn_around=True, step_limit=100),
            [1, 20, 4, 5, 3],
        )

    def test_find_route_no_route(self) -> None:
        #   200   200   200
        # 1─────2─────3─────4
        #       └─────5─────┘
        #         100    100
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.02, 0.01)
        g[3] = Node(3, 3, 0.03, 0.01)
        g[4] = Node(4, 4, 0.04, 0.01)
        g[5] = Node(5, 5, 0.03, 0.00)
        g.set_edge(1, 2, 200.0)
        g.set_edge(2, 1, 200.0)
        g.set_edge(2, 3, 200.0)
        g.set_edge(2, 5, 100.0)
        g.set_edge(3, 2, 200.0)
        g.set_edge(3, 4, 200.0)
        g.set_edge(4, 3, 200.0)
        g.set_edge(4, 5, 100.0)
        g.set_edge(5, 2, 100.0)
        g.set_edge(5, 4, 100.0)

        with self.assertRaises(StepLimitExceeded):
            g.find_route(1, 4, step_limit=2)

    def test_find_route_invalid_reference(self) -> None:
        g = Graph()
        with self.assertRaises(KeyError):
            g.find_route(1, 2)

    def test_add_from_osm_file(self) -> None:
        with NamedTemporaryFile(mode="w", encoding="utf-8") as temp_file:
            temp_file.write(OSM_FILE_FIXTURE)
            temp_file.flush()

            g = Graph()
            g.add_from_osm_file(temp_file.name, OsmProfile.CAR, OsmFormat.XML)
            self.assertEqual(len(g), 6)

    def test_add_from_osm_file_error(self) -> None:
        g = Graph()

        with self.assertRaises(OsmLoadingError), self.assertLogs("routex") as log_ctx:
            g.add_from_osm_file("non_existing_file.osm", OsmProfile.CAR)

        self.assertListEqual(
            log_ctx.output,
            ["ERROR:routex:non_existing_file.osm: io: No such file or directory (os error 2)"],
        )

    def test_add_from_osm_memory(self) -> None:
        mv = memoryview(bytearray(OSM_FILE_FIXTURE, "utf-8"))

        g = Graph()
        g.add_from_osm_memory(mv, OsmProfile.CAR)
        self.assertEqual(len(g), 6)

    def test_add_from_osm_memory_custom_profile(self) -> None:
        mv = memoryview(bytearray(OSM_FILE_FIXTURE, "utf-8"))

        p = OsmCustomProfile(
            name="car",
            penalties=[
                OsmPenalty("highway", "tertiary", 1.0),
                OsmPenalty("highway", "residential", 2.0),
            ],
            access=["access", "vehicle"],
            disable_restrictions=True,
        )

        g = Graph()
        g.add_from_osm_memory(mv, p, format=OsmFormat.XML)
        self.assertEqual(len(g), 4)


class TestEarthDistance(TestCase):
    def test(self) -> None:
        centrum = 52.23024, 21.01062
        stadion = 52.23852, 21.0446
        falenica = 52.16125, 21.21147

        self.assertAlmostEqual(earth_distance(*centrum, *stadion), 2.49049, places=5)
        self.assertAlmostEqual(earth_distance(*centrum, *falenica), 15.692483, places=5)


class TestKDTree(TestCase):
    def test(self) -> None:
        g = Graph()
        g[1] = Node(1, 1, 0.01, 0.01)
        g[2] = Node(2, 2, 0.01, 0.05)
        g[3] = Node(3, 3, 0.03, 0.09)
        g[4] = Node(4, 4, 0.04, 0.03)
        g[5] = Node(5, 5, 0.04, 0.07)
        g[6] = Node(6, 6, 0.07, 0.03)
        g[7] = Node(7, 7, 0.07, 0.01)
        g[8] = Node(8, 8, 0.08, 0.05)
        g[9] = Node(9, 9, 0.08, 0.09)

        kd = KDTree.build(g)
        self.assertEqual(kd.find_nearest_node(0.02, 0.02).id, 1)
        self.assertEqual(kd.find_nearest_node(0.05, 0.03).id, 4)
        self.assertEqual(kd.find_nearest_node(0.05, 0.08).id, 5)
        self.assertEqual(kd.find_nearest_node(0.09, 0.06).id, 8)
