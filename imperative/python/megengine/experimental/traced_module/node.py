# -*- coding: utf-8 -*-
# MegEngine is Licensed under the Apache License, Version 2.0 (the "License")
#
# Copyright (c) 2014-2021 Megvii Inc. All rights reserved.
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT ARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
import abc
import weakref
from typing import Any, Dict, List, Tuple, Type

import numpy

from ...core._imperative_rt.core2 import Tensor as RawTensor
from ...module import Module
from ...tensor import Tensor
from .pytree import TreeDef


class Node:
    """
    ``Node`` represents the variables （Tensor/Module/other python object) used in Module's forward method. They are inputs/outputs of Expr(the operations on variables).

    param expr: the Expr which produces the node
    param name: the name of the node
    """

    expr = None
    __total_id = 0
    _id = None
    _name = None

    def __init__(self, expr: "Expr", name: str = None):
        self.expr = expr
        self.users = []  # List[Expr]
        self._id = Node.__total_id
        Node.__total_id += 1
        self._name = name

    def __setstate__(self, d):
        self.__dict__ = d
        Node.__total_id = max(Node.__total_id, self._id) + 1

    def __repr__(self):
        if self._name is None:
            return "%{}".format(self._id)
        else:
            return "%{}".format(self._name)


class ModuleNode(Node):
    """
    ``ModuleNode`` represents the Module objects.

    Attributes:
        module_type: type of the Module correspending to the ModuleNode
        graph: the InternalGraph which will be interpreted when call Module's forward method
        attr_type_map: record the type of Module's attributes
    """

    module_type = Module  # type: Type[Module]
    _owner = None  # type: weakref.ReferenceType

    def __init__(self, expr: "Expr", name: str = None):
        super().__init__(expr, name)

    def __repr__(self):
        if self._name is None:
            return "%{}({})".format(self._id, self.module_type.__name__)
        else:
            return "%{}({})".format(self._name, self.module_type.__name__)

    def __getstate__(self):
        d = self.__dict__
        d.pop("_owner", None)
        return d

    @property
    def owner(self):
        return self._owner()


class TensorNode(Node):
    """
    ``TensorNode`` represents the Tensor objects.
    """

    shape = None  # type: Tuple[int]
    dtype = None  # type: numpy.dtype

    def __repr__(self):
        if self._name is None:
            return "%{}(Tensor)".format(self._id)
        else:
            return "%{}(Tensor)".format(self._name)


class NodeMixin(abc.ABC):
    __node = None

    @abc.abstractmethod
    def _record_wrapped_nodes(self, node):
        # record the nodes which had been bound to this NodeMixin
        pass

    @classmethod
    def wrap(cls, value, node):
        if isinstance(value, (NodeMixin, RawTensor)):
            if isinstance(node, Node):
                if isinstance(value, RawTensor):
                    node.dtype = value.dtype
                    node.shape = (
                        value._tuple_shape if isinstance(value, Tensor) else value.shape
                    )
                if isinstance(value, NodeMixin):
                    value._record_wrapped_nodes(node)
                setattr(value, "_NodeMixin__node", node)
            else:
                assert callable(node)
                n = node()
                assert isinstance(n, Node)
                if isinstance(value, RawTensor):
                    n.dtype = value.dtype
                    n.shape = (
                        value._tuple_shape if isinstance(value, Tensor) else value.shape
                    )
                if isinstance(value, NodeMixin):
                    value._record_wrapped_nodes(n)
                setattr(value, "_NodeMixin__node", n)

    @classmethod
    def wrap_safe(cls, value, node):
        assert isinstance(value, (NodeMixin, RawTensor))
        if isinstance(value, RawTensor):
            node.dtype = value.dtype
            node.shape = (
                value._tuple_shape if isinstance(value, Tensor) else value.shape
            )
        setattr(value, "_NodeMixin__node", node)
        if isinstance(value, NodeMixin):
            value._record_wrapped_nodes(node)

    @classmethod
    def get(cls, value, *default):
        return getattr(value, "_NodeMixin__node", *default)

    @classmethod
    def get_wrapped_type(cls, value):
        if isinstance(value, RawTensor):
            return TensorNode
        if isinstance(value, (Module, NodeMixin)):
            return ModuleNode
        return Node
