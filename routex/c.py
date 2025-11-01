# (c) Copyright 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

import logging
import sys
from ctypes import (
    cdll,
    CFUNCTYPE,
    POINTER,
    c_void_p,
    c_int,
    c_char_p,
    Structure,
    c_int64,
    c_float,
    c_size_t,
    c_bool,
    c_uint32,
    Union,
    c_ubyte,
)
from pathlib import Path
from typing import Any

c_char_p_p = POINTER(c_char_p)
c_int64_p = POINTER(c_int64)
c_ubyte_p = POINTER(c_ubyte)


if sys.platform.startswith("win32"):
    lib_filename = "libroutex.dll"
elif sys.platform.startswith("darwin"):
    lib_filename = "libroutex.dylib"
else:
    lib_filename = "libroutex.so"

lib_path = Path(__file__).with_name(lib_filename)
lib = cdll.LoadLibrary(str(lib_path))

LoggingCallback = CFUNCTYPE(None, c_void_p, c_int, c_char_p, c_char_p)
LoggingFlushCallback = CFUNCTYPE(None, c_void_p)


class Node(Structure):
    _fields_ = [
        ("id", c_int64),
        ("osm_id", c_int64),
        ("lat", c_float),
        ("lon", c_float),
    ]


class Edge(Structure):
    _fields_ = [
        ("to", c_int64),
        ("cost", c_float),
    ]


Graph_p = c_void_p
GraphIterator_p = c_void_p
KDTree_p = c_void_p


class OsmProfilePenalty(Structure):
    _fields_ = [("key", c_char_p), ("value", c_char_p), ("penalty", c_float)]


class OsmProfile(Structure):
    _fields_ = [
        ("name", c_char_p),
        ("penalties", POINTER(OsmProfilePenalty)),
        ("penalties_len", c_size_t),
        ("access", c_char_p_p),
        ("access_len", c_size_t),
        ("disallow_motorroad", c_bool),
        ("disable_restrictions", c_bool),
    ]


OsmProfile_p = POINTER(OsmProfile)
OsmFormat = c_int
BBox = c_float * 4


class OsmOptions(Structure):
    _fields_ = [
        ("profile", OsmProfile_p),
        ("file_format", OsmFormat),
        ("bbox", BBox),
    ]


OsmOptions_p = POINTER(OsmOptions)

RouteResultType = c_int


class RouteResultAsOk(Structure):
    _fields_ = [
        ("nodes", c_int64_p),
        ("len", c_uint32),
        ("capacity", c_uint32),
    ]


class RouteResultAsInvalidReference(Structure):
    _fields_ = [
        ("invalid_node_id", c_int64),
    ]


class RouteResultUnion(Union):
    _fields_ = [
        ("as_ok", RouteResultAsOk),
        ("as_invalid_reference", RouteResultAsInvalidReference),
    ]


class RouteResult(Structure):
    _fields_ = [
        ("union", RouteResultUnion),
        ("type_", RouteResultType),
    ]


@LoggingCallback
def builtin_log_handler(_: Any, level: int, target_b: bytes, message_b: bytes) -> None:
    target = target_b.decode("utf-8").replace("::", ".")
    message = message_b.decode("utf-8")
    logging.getLogger(target).log(level, message)


lib.routex_set_logging_callback.argtypes = [LoggingCallback, LoggingFlushCallback, c_void_p, c_int]
lib.routex_set_logging_callback.restype = None
lib.routex_set_logging_callback(builtin_log_handler, None, None, 10)

lib.routex_graph_new.argtypes = []
lib.routex_graph_new.restype = Graph_p

lib.routex_graph_delete.argtypes = [Graph_p]
lib.routex_graph_delete.restype = None

lib.routex_graph_get_nodes.argtypes = [Graph_p, POINTER(GraphIterator_p)]
lib.routex_graph_get_nodes.restype = c_size_t

lib.routex_graph_iterator_next.argtypes = [GraphIterator_p]
lib.routex_graph_iterator_next.restype = Node

lib.routex_graph_iterator_delete.argtypes = [GraphIterator_p]
lib.routex_graph_iterator_delete.restype = None

lib.routex_graph_get_node.argtypes = [Graph_p, c_int64]
lib.routex_graph_get_node.restype = Node

lib.routex_graph_set_node.argtypes = [Graph_p, Node]
lib.routex_graph_set_node.restype = bool

lib.routex_graph_delete_node.argtypes = [Graph_p, c_int64]
lib.routex_graph_delete_node.restype = bool

lib.routex_graph_find_nearest_node.argtypes = [Graph_p, c_float, c_float]
lib.routex_graph_find_nearest_node.restype = Node

lib.routex_graph_get_edges.argtypes = [Graph_p, c_int64, POINTER(POINTER(Edge))]
lib.routex_graph_get_edges.restype = c_size_t

lib.routex_graph_get_edge.argtypes = [Graph_p, c_int64, c_int64]
lib.routex_graph_get_edge.restype = c_float

lib.routex_graph_set_edge.argtypes = [Graph_p, c_int64, Edge]
lib.routex_graph_set_edge.restype = c_bool

lib.routex_graph_delete_edge.argtypes = [Graph_p, c_int64, c_int64]
lib.routex_graph_delete_edge.restype = c_bool

lib.routex_graph_add_from_osm_file.argtypes = [Graph_p, OsmOptions_p, c_char_p]
lib.routex_graph_add_from_osm_file.restype = c_bool

lib.routex_graph_add_from_osm_memory.argtypes = [Graph_p, OsmOptions_p, c_ubyte_p, c_size_t]
lib.routex_graph_add_from_osm_memory.restype = c_bool

lib.routex_find_route.argtypes = [Graph_p, c_int64, c_int64, c_size_t]
lib.routex_find_route.restype = RouteResult

lib.routex_find_route_without_turn_around.argtypes = [Graph_p, c_int64, c_int64, c_size_t]
lib.routex_find_route_without_turn_around.restype = RouteResult

lib.routex_route_result_delete.argtypes = [RouteResult]
lib.routex_route_result_delete.restype = None

lib.routex_kd_tree_new.argtypes = [Graph_p]
lib.routex_kd_tree_new.restype = KDTree_p

lib.routex_kd_tree_delete.argtypes = [KDTree_p]
lib.routex_kd_tree_delete.restype = None

lib.routex_kd_tree_find_nearest_node.argtypes = [KDTree_p, c_float, c_float]
lib.routex_kd_tree_find_nearest_node.restype = c_int64

lib.routex_earth_distance.argtypes = [c_float, c_float, c_float, c_float]
lib.routex_earth_distance.restype = c_float
