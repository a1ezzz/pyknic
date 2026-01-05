# -*- coding: utf-8 -*-

import math
import pytest
import time

from pyknic.lib.io.stats import GeneratorStats
from pyknic.lib.io.aio_wrapper import cg


class TestGeneratorStats:

    def test(self) -> None:
        source_gen = (x for x in ((b'b' * 100, ) * 100))

        stats = GeneratorStats()
        start_time = time.monotonic()
        cg(stats.process(source_gen))
        duration = time.monotonic() - start_time

        assert(stats.bytes() == 10000)
        assert(1 < math.fabs(stats.rate() / (stats.bytes() / duration)) < 1.5)

    def test_exception(self) -> None:
        source_gen = (x for x in ((b'b' * 100, ) * 100))

        stats = GeneratorStats()
        stats_gen = stats.process(source_gen)
        next(stats_gen)

        with pytest.raises(RuntimeError):
            stats.bytes()

        with pytest.raises(RuntimeError):
            stats.rate()

        cg(stats_gen)
        assert(stats.bytes() == 10000)
        assert(stats.rate() > 0)
