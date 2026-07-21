# -*- coding: utf-8 -*-

import pytest

from pyknic.lib.datalog.proto import DatalogProto


def test_abstract() -> None:
    pytest.raises(TypeError, DatalogProto)
    pytest.raises(NotImplementedError, DatalogProto.append, None, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, DatalogProto.iterate, None)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, DatalogProto.truncate, None, 0)  # type: ignore[call-overload]
    pytest.raises(NotImplementedError, DatalogProto.find, None, 0)  # type: ignore[call-overload]
