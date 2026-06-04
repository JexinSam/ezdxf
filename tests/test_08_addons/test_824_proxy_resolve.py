#  Copyright (c) 2026, ezdxf contributors
#  License: MIT License

import pytest
import struct
import ezdxf
from ezdxf.entities import factory
from ezdxf.lldxf.tags import Tags
from ezdxf.lldxf.types import DXFTag
from ezdxf.addons.proxy_resolve import resolve_proxy_entities, reconstruct_annotations


def test_resolve_proxy_entities_layout():
    doc = ezdxf.new()
    msp = doc.modelspace()
    psp = doc.layout("Layout1")

    # Create dummy viewport in paper space layout with required args
    vp = psp.add_viewport(
        center=(5.0, 5.0),
        size=(10.0, 10.0),
        view_center_point=(10.0, 10.0),
        view_height=10.0
    )

    # Create a block record for resolution target
    blk = doc.blocks.new("*I12")
    blk.add_circle((0.0, 0.0), 10.0)
    blk_handle = blk.block_record.dxf.handle

    # Add proxy entity to layout
    proxy = factory.new("ACAD_PROXY_ENTITY", doc=doc)
    proxy.acdb_proxy_entity = Tags([
        DXFTag(340, blk_handle),
        DXFTag(330, vp.dxf.handle)
    ])
    proxy.dxf.layer = "TestLayer"
    msp.add_entity(proxy)

    assert len(list(msp)) == 1
    count = resolve_proxy_entities(doc)
    assert count == 1

    # Check replacements
    entities = list(msp)
    assert len(entities) == 1
    assert entities[0].dxftype() == "INSERT"
    assert entities[0].dxf.name == "*I12"
    assert entities[0].dxf.layer == "TestLayer"
    # Spaced coordinates should start at (0, 0, 0)
    assert entities[0].dxf.insert == (0.0, 0.0, 0.0)
    assert vp.dxf.view_center_point == (0.0, 0.0)


def test_reconstruct_annotations():
    doc = ezdxf.new()
    blk = doc.blocks.new("TEST_BLOCK")
    circle = blk.add_circle((100.0, 200.0), 15.0)

    # Add a proxy centerline entity
    proxy = factory.new("ACAD_PROXY_ENTITY", doc=doc)
    proxy.dxf.layer = "Mittelpunktmarkierung"
    
    # Pack coordinates for center mark matching (100.0, 200.0)
    binary_data = struct.pack("<d", 100.0) + struct.pack("<d", 200.0)
    proxy.acdb_proxy_entity = Tags([
        DXFTag(310, binary_data)
    ])
    blk.add_entity(proxy)

    reconstruct_annotations(doc)

    # Proxy entity should be deleted and replaced with two crosshair lines
    entities = list(blk)
    assert len(entities) == 3  # Circle + 2 Lines
    assert circle in entities

    lines = [e for e in entities if e.dxftype() == "LINE"]
    assert len(lines) == 2
    for line in lines:
        assert line.dxf.layer == "Mittelpunktmarkierung"

    # Line 1: (cx - r - 2, cy) to (cx + r + 2, cy) -> (100 - 15 - 2, 200) to (100 + 15 + 2, 200)
    # Line 2: (cx, cy - r - 2) to (cx, cy + r + 2) -> (100, 200 - 15 - 2) to (100, 200 + 15 + 2)
    coords = [(line.dxf.start, line.dxf.end) for line in lines]
    expected_horizontal = ((83.0, 200.0, 0.0), (117.0, 200.0, 0.0))
    expected_vertical = ((100.0, 183.0, 0.0), (100.0, 217.0, 0.0))

    has_horizontal = any(abs(c[0][0] - expected_horizontal[0][0]) < 0.1 for c in coords)
    has_vertical = any(abs(c[0][1] - expected_vertical[0][1]) < 0.1 for c in coords)
    assert has_horizontal
    assert has_vertical
