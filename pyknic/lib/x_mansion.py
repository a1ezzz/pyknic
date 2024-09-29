# -*- coding: utf-8 -*-
# pyknic/lib/mutant.py
#
# Copyright (C) 2024 the pyknic authors and contributors
# <see AUTHORS file>
#
# This file is part of pyknic.
#
# pyknic is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyknic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pyknic.  If not, see <http://www.gnu.org/licenses/>.

import typing

from pyknic.lib.signals.source import SignalSourceMeta, SignalSource
from pyknic.lib.capability import CapabilitiesHolderMeta, CapabilitiesHolder


class CapabilitiesAndSignalsMeta(SignalSourceMeta, CapabilitiesHolderMeta):
    """ This metaclass is for classes that may send signals and may have capabilities
    """

    def __init__(cls, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """ Initialize class with this metaclass

        :param name: same as 'name' in :meth:`.WSignalSourceMeta.__init__` method
        :param bases: same as 'bases' in :meth:`.WSignalSourceMeta.__init__` method
        :param namespace: same as 'namespace' in :meth:`.WSignalSourceMeta.__init__` method
        """
        SignalSourceMeta.__init__(cls, name, bases, namespace)
        CapabilitiesHolderMeta.__init__(cls, name, bases, namespace)


class CapabilitiesAndSignals(SignalSource, CapabilitiesHolder, metaclass=CapabilitiesAndSignalsMeta):
    """ This is a base class for classes that may send signals and may have capabilities
    """
    pass
