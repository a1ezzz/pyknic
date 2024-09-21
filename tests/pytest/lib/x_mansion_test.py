# -*- coding: utf-8 -*-

from pyknic.lib.x_mansion import CapabilitiesAndSignalsMeta, CapabilitiesAndSignals

from pyknic.lib.signals.proto import Signal
from pyknic.lib.signals.source import SignalSourceMeta, SignalSource
from pyknic.lib.capability import CapabilitiesHolderMeta, CapabilitiesHolder, capability, iscapable


class TestCapabilitiesAndSignalsMeta:

    class Sample(metaclass=CapabilitiesAndSignalsMeta):
        pass

    def test(self) -> None:
        assert(isinstance(TestCapabilitiesAndSignalsMeta.Sample, SignalSourceMeta))
        assert(isinstance(TestCapabilitiesAndSignalsMeta.Sample, CapabilitiesHolderMeta))


class TestCapabilitiesAndSignals:

    class BaseCls(CapabilitiesAndSignals):
        signal = Signal()

        @capability
        def foo(self) -> None:
            pass

    class DerivedCls(BaseCls):

        def foo(self) -> None:
            pass

    def test(self) -> None:
        base_cls = TestCapabilitiesAndSignals.BaseCls()

        assert(isinstance(TestCapabilitiesAndSignals.BaseCls, CapabilitiesAndSignalsMeta))
        assert(isinstance(base_cls, SignalSource))
        assert(isinstance(base_cls, CapabilitiesHolder))

        base_cls.emit(base_cls.signal)
        assert(iscapable(base_cls, TestCapabilitiesAndSignals.BaseCls.foo) is False)
        assert(iscapable(TestCapabilitiesAndSignals.DerivedCls(), TestCapabilitiesAndSignals.BaseCls.foo) is True)
