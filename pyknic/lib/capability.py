# -*- coding: utf-8 -*-
# pyknic/lib/capability.py
#
# Copyright (C) 2018-2024 the pyknic authors and contributors
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

# TODO: document the code
# TODO: write tests for the code

import typing

from abc import ABCMeta
from inspect import isfunction

from pyknic.lib.verify import verify_value


class CapabilityDescriptor:
    """ This class describes a single capability. Every capability (function) has its own descriptor
    """

    @verify_value(capability_name=lambda x: len(x) > 0)
    def __init__(self, capability_cls: type, capability_name: str):
        """ TODO: docs

        :param capability_cls: class that defines a capability
        :param capability_name: function name
        """
        self.__cls = capability_cls
        self.__name = capability_name

    def cls(self) -> type:
        """ Return origin class
        """
        return self.__cls

    def name(self) -> str:
        """ Return capability name
        """
        return self.__name


def capability(f: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
    """ Mark a decorated function as a capability

    :param f: function that is defined as a capability
    """
    f.__pyknic_capability__ = None  # type: ignore[attr-defined] # we are force the attribute to be
    return f


class CapabilitiesHolderMeta(ABCMeta):
    """ This metaclass sets capability descriptor for every newly marked capabilities
    """

    def __init__(cls, name: str, bases: typing.Tuple[type], namespace: typing.Dict[str, typing.Any]):
        """ Generate new class with this metaclass

        :param name: same as 'name' in :meth:`.ABCMeta.__init__` method
        :param bases: same as 'bases' in :meth:`.ABCMeta.__init__` method
        :param namespace: same as 'namespace' in :meth:`.ABCMeta.__init__` method
        """
        ABCMeta.__init__(cls, name, bases, namespace)

        for n in dir(cls):
            i = ABCMeta.__getattribute__(cls, n)
            if callable(i) and hasattr(i, '__pyknic_capability__'):
                if isfunction(i) is False:
                    raise TypeError(
                        'Only functions may be a "capability". "classmethod" or "staticmethod" '
                        'are not supported'
                    )
                if i.__pyknic_capability__ is None:
                    i.__pyknic_capability__ = CapabilityDescriptor(cls, i.__name__)


@verify_value(obj_capability_fn=lambda x: isinstance(x.__pyknic_capability__, CapabilityDescriptor))
def iscapable(obj: object, obj_capability_fn: typing.Callable[..., typing.Any]) -> bool:
    """ Check if the specified object (or type) is capable of something. I.e. check if a function from a descriptor
    has been overridden in the derived class. Return True if function has been overridden and False otherwise

    :param obj: object to check
    :param obj_capability_fn: capability descriptor
    """

    obj_capability = obj_capability_fn.__pyknic_capability__  # type: ignore[attr-defined] # metaclass/decorators issues

    obj_method = None
    if isinstance(obj, type):
        if issubclass(obj, obj_capability.cls()) is True:
            obj_method = getattr(obj, obj_capability.name())
    elif isinstance(obj, obj_capability.cls()) is True:
        obj_method = getattr(obj, obj_capability.name())

    if obj_method:
        return not hasattr(obj_method, '__pyknic_capability__')  # overridden methods will not have
        # the __pyknic_capability__ attribute

    return False


class CapabilitiesHolder(metaclass=CapabilitiesHolderMeta):
    """ Simple base class for defining capabilities. Besides that this class uses :class:`.CapabilitiesHolderMeta`
    metaclass already. This class overrides '__contains__' method, so 'in' operator may be used for checking
    whether a class has a capability
    """

    def __contains__(self, item: typing.Callable[..., typing.Any]) -> bool:
        """ Check whether this object has a capability

        :param item: capability to check
        """
        return iscapable(self, item)

    def append_capability(
        self, obj_capability_fn: typing.Callable[..., typing.Any], func: typing.Callable[..., typing.Any]
    ) -> None:
        """ Append capability implementation to the object

        :param obj_capability_fn: capability to implement
        :param func: capability implementation
        """
        cap_name = obj_capability_fn.__pyknic_capability__.name()  # type: ignore[attr-defined] # metaclass/decorators
        # issues

        if iscapable(self, obj_capability_fn):
            raise ValueError(f'An object already has the "{cap_name}" capability')

        setattr(self, cap_name, func)
