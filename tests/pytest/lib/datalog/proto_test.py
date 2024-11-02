# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.datalog.proto import DatalogProto


def test_abstract() -> None:
    pytest.raises(TypeError, DatalogProto)
    pytest.raises(NotImplementedError, DatalogProto.append, None, None)
    pytest.raises(NotImplementedError, DatalogProto.iterate, None)
    pytest.raises(NotImplementedError, DatalogProto.truncate, None, 0)
