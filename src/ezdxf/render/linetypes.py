# Copyright (c) 2020-2022, Manfred Moitzi
# License: MIT License
from typing import Iterable, Iterator
import ezdxf
from ezdxf.math import UVec
from ._linetypes import _LineTypeRenderer, LineSegment

if ezdxf.options.use_c_ext:
    try:
        from ezdxf.acc.linetypes import _LineTypeRenderer  # type: ignore
    except ImportError:
        pass


class LineTypeRenderer(_LineTypeRenderer):
    def line_segments(self, vertices: Iterable[UVec]) -> Iterator[LineSegment]:
        last = None
        count = 0
        limit = 10000
        vertices_list = list(vertices)
        
        for vertex in vertices_list:
            if last is not None:
                for s, e in self.line_segment(last, vertex):
                    yield s, e
                    count += 1
                    if count >= limit:
                        # Fallback: connect to the end and stop
                        yield e, vertices_list[-1]
                        return
            last = vertex
