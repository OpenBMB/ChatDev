# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""
Data object model, as per https://docs.python.org/3/reference/datamodel.html.

This module describes, at least partially, a data object model for some
of astroid's nodes. The model contains special attributes that nodes such
as functions, classes, modules etc have, such as __doc__, __class__,
__module__ etc, being used when doing attribute lookups over nodes.

For instance, inferring `obj.__class__` will first trigger an inference
of the `obj` variable. If it was successfully inferred, then an attribute
`__class__ will be looked for in the inferred object. This is the part
where the data model occurs. The model is attached to those nodes
and the lookup mechanism will try to see if attributes such as
`__class__` are defined by the model or not. If they are defined,
the model will be requested to return the corresponding value of that
attribute. Thus the model can be viewed as a special part of the lookup
mechanism.
"""

from __future__ import annotations

import itertools
import os
import pprint
import sys
import types
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import astroid
from astroid import bases, nodes, util
from astroid.context import InferenceContext, copy_context
from astroid.exceptions import AttributeInferenceError, InferenceError, NoDefault
from astroid.manager import AstroidManager
from astroid.nodes import node_classes

objects = util.lazy_import("objects")
builder = util.lazy_import("builder")

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

if TYPE_CHECKING:
    from astroid import builder
    from astroid.objects import Property

IMPL_PREFIX = "attr_"
LEN_OF_IMPL_PREFIX = len(IMPL_PREFIX)


def _dunder_dict(instance, attributes):
    obj = node_classes.Dict(parent=instance)

    # Convert the keys to node strings
    keys = [
        node_classes.Const(value=value, parent=obj) for value in list(attributes.keys())
    ]

    # The original attribute has a list of elements for each key,
    # but that is not useful for retrieving the special attribute's value.
    # In this case, we're picking the last value from each list.
    values = [elem[-1] for elem in attributes.values()]

    obj.postinit(list(zip(keys, values)))
    return obj


def _get_bound_node(model: ObjectModel) -> Any:
    # TODO: Use isinstance instead of try ... except after _instance has typing
    try:
        return model._instance._proxied
    except AttributeError:
        return model._instance


class ObjectModel:
    def __init__(self):
        self._instance = None

    def __repr__(self):
        result = []
        cname = type(self).__name__
        string = "%(cname)s(%(fields)s)"
        alignment = len(cname) + 1
        for field in sorted(self.attributes()):
            width = 80 - len(field) - alignment
            lines = pprint.pformat(field, indent=2, width=width).splitlines(True)

            inner = [lines[0]]
            for line in lines[1:]:
                inner.append(" " * alignment + line)
            result.append(field)

        return string % {
            "cname": cname,
            "fields": (",\n" + " " * alignment).join(result),
        }

    def __call__(self, instance):
        self._instance = instance
        return self

    def __get__(self, instance, cls=None):
        # ObjectModel needs to be a descriptor so that just doing
        # `special_attributes = SomeObjectModel` should be enough in the body of a node.
        # But at the same time, node.special_attributes should return an object
        # which can be used for manipulating the special attributes. That's the reason
        # we pass the instance through which it got accessed to ObjectModel.__call__,
        # returning itself afterwards, so we can still have access to the
        # underlying data model and to the instance for which it got accessed.
        return self(instance)

    def __contains__(self, name) -> bool:
        return name in self.attributes()

    @lru_cache()  # noqa
    def attributes(self) -> list[str]:
        """Get the attributes which are exported by this object model."""
        return [o[LEN_OF_IMPL_PREFIX:] for o in dir(self) if o.startswith(IMPL_PREFIX)]

    def lookup(self, name):
        """Look up the given *name* in the current model.

        It should return an AST or an interpreter object,
        but if the name is not found, then an AttributeInferenceError will be raised.
        """
        if name in self.attributes():
            return getattr(self, IMPL_PREFIX + name)
        raise AttributeInferenceError(target=self._instance, attribute=name)

    @property
    def attr___new__(self) -> bases.BoundMethod:
        """Calling cls.__new__(type) on an object returns an instance of 'type'."""
        node: nodes.FunctionDef = builder.extract_node(
            """def __new__(self, cls): return cls()"""
        )
        # We set the parent as being the ClassDef of 'object' as that
        # triggers correct inference as a call to __new__ in bases.py
        node.parent = AstroidManager().builtins_module["object"]

        return bases.BoundMethod(proxy=node, bound=_get_bound_node(self))

    @property
    def attr___init__(self) -> bases.BoundMethod:
        """Calling cls.__init__() normally returns None."""
        # The *args and **kwargs are necessary not to trigger warnings about missing
        # or extra parameters for '__init__' methods we don't infer correctly.
        # This BoundMethod is the fallback value for those.
        node: nodes.FunctionDef = builder.extract_node(
            """def __init__(self, *args, **kwargs): return None"""
        )
        # We set the parent as being the ClassDef of 'object' as that
        # is where this method originally comes from
        node.parent = AstroidManager().builtins_module["object"]

        return bases.BoundMethod(proxy=node, bound=_get_bound_node(self))


class ModuleModel(ObjectModel):
    def _builtins(self):
        builtins_ast_module = AstroidManager().builtins_module
        return builtins_ast_module.special_attributes.lookup("__dict__")

    @property
    def attr_builtins(self):
        return self._builtins()

    @property
    def attr___path__(self):
        if not self._instance.package:
            raise AttributeInferenceError(target=self._instance, attribute="__path__")

        path_objs = [
            node_classes.Const(
                value=path
                if not path.endswith("__init__.py")
                else os.path.dirname(path),
                parent=self._instance,
            )
            for path in self._instance.path
        ]

        container = node_classes.List(parent=self._instance)
        container.postinit(path_objs)

        return container

    @property
    def attr___name__(self):
        return node_classes.Const(value=self._instance.name, parent=self._instance)

    @property
    def attr___doc__(self):
        return node_classes.Const(
            value=getattr(self._instance.doc_node, "value", None),
            parent=self._instance,
        )

    @property
    def attr___file__(self):
        return node_classes.Const(value=self._instance.file, parent=self._instance)

    @property
    def attr___dict__(self):
        return _dunder_dict(self._instance, self._instance.globals)

    @property
    def attr___package__(self):
        if not self._instance.package:
            value = ""
        else:
            value = self._instance.name

        return node_classes.Const(value=value, parent=self._instance)

    # These are related to the Python 3 implementation of the
    # import system,
    # https://docs.python.org/3/reference/import.html#import-related-module-attributes

    @property
    def attr___spec__(self):
        # No handling for now.
        return node_classes.Unknown()

    @property
    def attr___loader__(self):
        # No handling for now.
        return node_classes.Unknown()

    @property
    def attr___cached__(self):
        # No handling for now.
        return node_classes.Unknown()


class FunctionModel(ObjectModel):
    @property
    def attr___name__(self):
        return node_classes.Const(value=self._instance.name, parent=self._instance)

    @property
    def attr___doc__(self):
        return node_classes.Const(
            value=getattr(self._instance.doc_node, "value", None),
            parent=self._instance,
        )

    @property
    def attr___qualname__(self):
        return node_classes.Const(value=self._instance.qname(), parent=self._instance)

    @property
    def attr___defaults__(self):
        func = self._instance
        if not func.args.defaults:
            return node_classes.Const(value=None, parent=func)

        defaults_obj = node_classes.Tuple(parent=func)
        defaults_obj.postinit(func.args.defaults)
        return defaults_obj

    @property
    def attr___annotations__(self):
        obj = node_classes.Dict(parent=self._instance)

        if not self._instance.returns:
            returns = None
        else:
            returns = self._instance.returns

        args = self._instance.args
        pair_annotations = itertools.chain(
            zip(args.args or [], args.annotations),
            zip(args.kwonlyargs, args.kwonlyargs_annotations),
            zip(args.posonlyargs or [], args.posonlyargs_annotations),
        )

        annotations = {
            arg.name: annotation for (arg, annotation) in pair_annotations if annotation
        }
        if args.varargannotation:
            annotations[args.vararg] = args.varargannotation
        if args.kwargannotation:
            annotations[args.kwarg] = args.kwargannotation
        if returns:
            annotations["return"] = returns

        items = [
            (node_classes.Const(key, parent=obj), value)
            for (key, value) in annotations.items()
        ]

        obj.postinit(items)
        return obj

    @property
    def attr___dict__(self):
        return node_classes.Dict(parent=self._instance)

    attr___globals__ = attr___dict__

    @property
    def attr___kwdefaults__(self):
        def _default_args(args, parent):
            for arg in args.kwonlyargs:
                try:
                    default = args.default_value(arg.name)
                except NoDefault:
                    continue

                name = node_classes.Const(arg.name, parent=parent)
                yield name, default

        args = self._instance.args
        obj = node_classes.Dict(parent=self._instance)
        defaults = dict(_default_args(args, obj))

        obj.postinit(list(defaults.items()))
        return obj

    @property
    def attr___module__(self):
        return node_classes.Const(self._instance.root().qname())

    @property
    def attr___get__(self):
        func = self._instance

        class DescriptorBoundMethod(bases.BoundMethod):
            """Bound method which knows how to understand calling descriptor
            binding.
            """

            def implicit_parameters(self) -> Literal[0]:
                # Different than BoundMethod since the signature
                # is different.
                return 0

            def infer_call_result(
                self, caller, context: InferenceContext | None = None
            ):
                if len(caller.args) > 2 or len(caller.args) < 1:
                    raise InferenceError(
                        "Invalid arguments for descriptor binding",
                        target=self,
                        context=context,
                    )

                context = copy_context(context)
                try:
                    cls = next(caller.args[0].infer(context=context))
                except StopIteration as e:
                    raise InferenceError(context=context, node=caller.args[0]) from e

                if isinstance(cls, util.UninferableBase):
                    raise InferenceError(
                        "Invalid class inferred", target=self, context=context
                    )

                # For some reason func is a Node that the below
                # code is not expecting
                if isinstance(func, bases.BoundMethod):
                    yield func
                    return

                # Rebuild the original value, but with the parent set as the
                # class where it will be bound.
                new_func = func.__class__(
                    name=func.name,
                    lineno=func.lineno,
                    col_offset=func.col_offset,
                    parent=func.parent,
                )
                # pylint: disable=no-member
                new_func.postinit(
                    func.args,
                    func.body,
                    func.decorators,
                    func.returns,
                    doc_node=func.doc_node,
                )

                # Build a proper bound method that points to our newly built function.
                proxy = bases.UnboundMethod(new_func)
                yield bases.BoundMethod(proxy=proxy, bound=cls)

            @property
            def args(self):
                """Overwrite the underlying args to match those of the underlying func.

                Usually the underlying *func* is a function/method, as in:

                    def test(self):
                        pass

                This has only the *self* parameter but when we access test.__get__
                we get a new object which has two parameters, *self* and *type*.
                """
                nonlocal func
                positional_or_keyword_params = func.args.args.copy()
                positional_or_keyword_params.append(astroid.AssignName(name="type"))

                positional_only_params = func.args.posonlyargs.copy()

                arguments = astroid.Arguments(parent=func.args.parent)
                arguments.postinit(
                    args=positional_or_keyword_params,
                    posonlyargs=positional_only_params,
                    defaults=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    annotations=[],
                )
                return arguments

        return DescriptorBoundMethod(proxy=self._instance, bound=self._instance)

    # These are here just for completion.
    @property
    def attr___ne__(self):
        return node_classes.Unknown()

    attr___subclasshook__ = attr___ne__
    attr___str__ = attr___ne__
    attr___sizeof__ = attr___ne__
    attr___setattr___ = attr___ne__
    attr___repr__ = attr___ne__
    attr___reduce__ = attr___ne__
    attr___reduce_ex__ = attr___ne__
    attr___lt__ = attr___ne__
    attr___eq__ = attr___ne__
    attr___gt__ = attr___ne__
    attr___format__ = attr___ne__
    attr___delattr___ = attr___ne__
    attr___getattribute__ = attr___ne__
    attr___hash__ = attr___ne__
    attr___dir__ = attr___ne__
    attr___call__ = attr___ne__
    attr___class__ = attr___ne__
    attr___closure__ = attr___ne__
    attr___code__ = attr___ne__


class ClassModel(ObjectModel):
    def __init__(self):
        # Add a context so that inferences called from an instance don't recurse endlessly
        self.context = InferenceContext()

        super().__init__()

    @property
    def attr___module__(self):
        return node_classes.Const(self._instance.root().qname())

    @property
    def attr___name__(self):
        return node_classes.Const(self._instance.name)

    @property
    def attr___qualname__(self):
        return node_classes.Const(self._instance.qname())

    @property
    def attr___doc__(self):
        return node_classes.Const(getattr(self._instance.doc_node, "value", None))

    @property
    def attr___mro__(self):
        if not self._instance.newstyle:
            raise AttributeInferenceError(target=self._instance, attribute="__mro__")

        mro = self._instance.mro()
        obj = node_classes.Tuple(parent=self._instance)
        obj.postinit(mro)
        return obj

    @property
    def attr_mro(self):
        if not self._instance.newstyle:
            raise AttributeInferenceError(target=self._instance, attribute="mro")

        other_self = self

        # Cls.mro is a method and we need to return one in order to have a proper inference.
        # The method we're returning is capable of inferring the underlying MRO though.
        class MroBoundMethod(bases.BoundMethod):
            def infer_call_result(
                self, caller, context: InferenceContext | None = None
            ):
                yield other_self.attr___mro__

        implicit_metaclass = self._instance.implicit_metaclass()
        mro_method = implicit_metaclass.locals["mro"][0]
        return MroBoundMethod(proxy=mro_method, bound=implicit_metaclass)

    @property
    def attr___bases__(self):
        obj = node_classes.Tuple()
        context = InferenceContext()
        elts = list(self._instance._inferred_bases(context))
        obj.postinit(elts=elts)
        return obj

    @property
    def attr___class__(self):
        # pylint: disable=import-outside-toplevel; circular import
        from astroid import helpers

        return helpers.object_type(self._instance)

    @property
    def attr___subclasses__(self):
        """Get the subclasses of the underlying class.

        This looks only in the current module for retrieving the subclasses,
        thus it might miss a couple of them.
        """
        if not self._instance.newstyle:
            raise AttributeInferenceError(
                target=self._instance, attribute="__subclasses__"
            )

        qname = self._instance.qname()
        root = self._instance.root()
        classes = [
            cls
            for cls in root.nodes_of_class(nodes.ClassDef)
            if cls != self._instance and cls.is_subtype_of(qname, context=self.context)
        ]

        obj = node_classes.List(parent=self._instance)
        obj.postinit(classes)

        class SubclassesBoundMethod(bases.BoundMethod):
            def infer_call_result(
                self, caller, context: InferenceContext | None = None
            ):
                yield obj

        implicit_metaclass = self._instance.implicit_metaclass()
        subclasses_method = implicit_metaclass.locals["__subclasses__"][0]
        return SubclassesBoundMethod(proxy=subclasses_method, bound=implicit_metaclass)

    @property
    def attr___dict__(self):
        return node_classes.Dict(parent=self._instance)

    @property
    def attr___call__(self):
        """Calling a class A() returns an instance of A."""
        return self._instance.instantiate_class()


class SuperModel(ObjectModel):
    @property
    def attr___thisclass__(self):
        return self._instance.mro_pointer

    @property
    def attr___self_class__(self):
        return self._instance._self_class

    @property
    def attr___self__(self):
        return self._instance.type

    @property
    def attr___class__(self):
        return self._instance._proxied


class UnboundMethodModel(ObjectModel):
    @property
    def attr___class__(self):
        # pylint: disable=import-outside-toplevel; circular import
        from astroid import helpers

        return helpers.object_type(self._instance)

    @property
    def attr___func__(self):
        return self._instance._proxied

    @property
    def attr___self__(self):
        return node_classes.Const(value=None, parent=self._instance)

    attr_im_func = attr___func__
    attr_im_class = attr___class__
    attr_im_self = attr___self__


class ContextManagerModel(ObjectModel):
    """Model for context managers.

    Based on 3.3.9 of the Data Model documentation:
    https://docs.python.org/3/reference/datamodel.html#with-statement-context-managers
    """

    @property
    def attr___enter__(self) -> bases.BoundMethod:
        """Representation of the base implementation of __enter__.

        As per Python documentation:
        Enter the runtime context related to this object. The with statement
        will bind this method's return value to the target(s) specified in the
        as clause of the statement, if any.
        """
        node: nodes.FunctionDef = builder.extract_node("""def __enter__(self): ...""")
        # We set the parent as being the ClassDef of 'object' as that
        # is where this method originally comes from
        node.parent = AstroidManager().builtins_module["object"]

        return bases.BoundMethod(proxy=node, bound=_get_bound_node(self))

    @property
    def attr___exit__(self) -> bases.BoundMethod:
        """Representation of the base implementation of __exit__.

        As per Python documentation:
        Exit the runtime context related to this object. The parameters describe the
        exception that caused the context to be exited. If the context was exited
        without an exception, all three arguments will be None.
        """
        node: nodes.FunctionDef = builder.extract_node(
            """def __exit__(self, exc_type, exc_value, traceback): ..."""
        )
        # We set the parent as being the ClassDef of 'object' as that
        # is where this method originally comes from
        node.parent = AstroidManager().builtins_module["object"]

        return bases.BoundMethod(proxy=node, bound=_get_bound_node(self))


class BoundMethodModel(FunctionModel):
    @property
    def attr___func__(self):
        return self._instance._proxied._proxied

    @property
    def attr___self__(self):
        return self._instance.bound


class GeneratorModel(FunctionModel, ContextManagerModel):
    def __new__(cls, *args, **kwargs):
        # Append the values from the GeneratorType unto this object.
        ret = super().__new__(cls, *args, **kwargs)
        generator = AstroidManager().builtins_module["generator"]
        for name, values in generator.locals.items():
            method = values[0]

            def patched(cls, meth=method):
                return meth

            setattr(type(ret), IMPL_PREFIX + name, property(patched))

        return ret

    @property
    def attr___name__(self):
        return node_classes.Const(
            value=self._instance.parent.name, parent=self._instance
        )

    @property
    def attr___doc__(self):
        return node_classes.Const(
            value=getattr(self._instance.parent.doc_node, "value", None),
            parent=self._instance,
        )


class AsyncGeneratorModel(GeneratorModel):
    def __new__(cls, *args, **kwargs):
        # Append the values from the AGeneratorType unto this object.
        ret = super().__new__(cls, *args, **kwargs)
        astroid_builtins = AstroidManager().builtins_module
        generator = astroid_builtins.get("async_generator")
        if generator is None:
            # Make it backward compatible.
            generator = astroid_builtins.get("generator")

        for name, values in generator.locals.items():
            method = values[0]

            def patched(cls, meth=method):
                return meth

            setattr(type(ret), IMPL_PREFIX + name, property(patched))

        return ret


class InstanceModel(ObjectModel):
    @property
    def attr___class__(self):
        return self._instance._proxied

    @property
    def attr___module__(self):
        return node_classes.Const(self._instance.root().qname())

    @property
    def attr___doc__(self):
        return node_classes.Const(getattr(self._instance.doc_node, "value", None))

    @property
    def attr___dict__(self):
        return _dunder_dict(self._instance, self._instance.instance_attrs)


# Exception instances


class ExceptionInstanceModel(InstanceModel):
    @property
    def attr_args(self) -> nodes.Tuple:
        return nodes.Tuple(parent=self._instance)

    @property
    def attr___traceback__(self):
        builtins_ast_module = AstroidManager().builtins_module
        traceback_type = builtins_ast_module[types.TracebackType.__name__]
        return traceback_type.instantiate_class()


class SyntaxErrorInstanceModel(ExceptionInstanceModel):
    @property
    def attr_text(self):
        return node_classes.Const("")


class OSErrorInstanceModel(ExceptionInstanceModel):
    @property
    def attr_filename(self):
        return node_classes.Const("")

    @property
    def attr_errno(self):
        return node_classes.Const(0)

    @property
    def attr_strerror(self):
        return node_classes.Const("")

    attr_filename2 = attr_filename


class ImportErrorInstanceModel(ExceptionInstanceModel):
    @property
    def attr_name(self):
        return node_classes.Const("")

    @property
    def attr_path(self):
        return node_classes.Const("")


class UnicodeDecodeErrorInstanceModel(ExceptionInstanceModel):
    @property
    def attr_object(self):
        return node_classes.Const("")


BUILTIN_EXCEPTIONS = {
    "builtins.SyntaxError": SyntaxErrorInstanceModel,
    "builtins.ImportError": ImportErrorInstanceModel,
    "builtins.UnicodeDecodeError": UnicodeDecodeErrorInstanceModel,
    # These are all similar to OSError in terms of attributes
    "builtins.OSError": OSErrorInstanceModel,
    "builtins.BlockingIOError": OSErrorInstanceModel,
    "builtins.BrokenPipeError": OSErrorInstanceModel,
    "builtins.ChildProcessError": OSErrorInstanceModel,
    "builtins.ConnectionAbortedError": OSErrorInstanceModel,
    "builtins.ConnectionError": OSErrorInstanceModel,
    "builtins.ConnectionRefusedError": OSErrorInstanceModel,
    "builtins.ConnectionResetError": OSErrorInstanceModel,
    "builtins.FileExistsError": OSErrorInstanceModel,
    "builtins.FileNotFoundError": OSErrorInstanceModel,
    "builtins.InterruptedError": OSErrorInstanceModel,
    "builtins.IsADirectoryError": OSErrorInstanceModel,
    "builtins.NotADirectoryError": OSErrorInstanceModel,
    "builtins.PermissionError": OSErrorInstanceModel,
    "builtins.ProcessLookupError": OSErrorInstanceModel,
    "builtins.TimeoutError": OSErrorInstanceModel,
}


class DictModel(ObjectModel):
    @property
    def attr___class__(self):
        return self._instance._proxied

    def _generic_dict_attribute(self, obj, name):
        """Generate a bound method that can infer the given *obj*."""

        class DictMethodBoundMethod(astroid.BoundMethod):
            def infer_call_result(
                self, caller, context: InferenceContext | None = None
            ):
                yield obj

        meth = next(self._instance._proxied.igetattr(name), None)
        return DictMethodBoundMethod(proxy=meth, bound=self._instance)

    @property
    def attr_items(self):
        elems = []
        obj = node_classes.List(parent=self._instance)
        for key, value in self._instance.items:
            elem = node_classes.Tuple(parent=obj)
            elem.postinit((key, value))
            elems.append(elem)
        obj.postinit(elts=elems)

        obj = objects.DictItems(obj)
        return self._generic_dict_attribute(obj, "items")

    @property
    def attr_keys(self):
        keys = [key for (key, _) in self._instance.items]
        obj = node_classes.List(parent=self._instance)
        obj.postinit(elts=keys)

        obj = objects.DictKeys(obj)
        return self._generic_dict_attribute(obj, "keys")

    @property
    def attr_values(self):
        values = [value for (_, value) in self._instance.items]
        obj = node_classes.List(parent=self._instance)
        obj.postinit(values)

        obj = objects.DictValues(obj)
        return self._generic_dict_attribute(obj, "values")


class PropertyModel(ObjectModel):
    """Model for a builtin property."""

    def _init_function(self, name):
        function = nodes.FunctionDef(name=name, parent=self._instance)

        args = nodes.Arguments(parent=function)
        args.postinit(
            args=[],
            defaults=[],
            kwonlyargs=[],
            kw_defaults=[],
            annotations=[],
            posonlyargs=[],
            posonlyargs_annotations=[],
            kwonlyargs_annotations=[],
        )

        function.postinit(args=args, body=[])
        return function

    @property
    def attr_fget(self):
        func = self._instance

        class PropertyFuncAccessor(nodes.FunctionDef):
            def infer_call_result(
                self, caller=None, context: InferenceContext | None = None
            ):
                nonlocal func
                if caller and len(caller.args) != 1:
                    raise InferenceError(
                        "fget() needs a single argument", target=self, context=context
                    )

                yield from func.function.infer_call_result(
                    caller=caller, context=context
                )

        property_accessor = PropertyFuncAccessor(name="fget", parent=self._instance)
        property_accessor.postinit(args=func.args, body=func.body)
        return property_accessor

    @property
    def attr_fset(self):
        func = self._instance

        def find_setter(func: Property) -> astroid.FunctionDef | None:
            """
            Given a property, find the corresponding setter function and returns it.

            :param func: property for which the setter has to be found
            :return: the setter function or None
            """
            for target in [
                t for t in func.parent.get_children() if t.name == func.function.name
            ]:
                for dec_name in target.decoratornames():
                    if dec_name.endswith(func.function.name + ".setter"):
                        return target
            return None

        func_setter = find_setter(func)
        if not func_setter:
            raise InferenceError(
                f"Unable to find the setter of property {func.function.name}"
            )

        class PropertyFuncAccessor(nodes.FunctionDef):
            def infer_call_result(
                self, caller=None, context: InferenceContext | None = None
            ):
                nonlocal func_setter
                if caller and len(caller.args) != 2:
                    raise InferenceError(
                        "fset() needs two arguments", target=self, context=context
                    )
                yield from func_setter.infer_call_result(caller=caller, context=context)

        property_accessor = PropertyFuncAccessor(name="fset", parent=self._instance)
        property_accessor.postinit(args=func_setter.args, body=func_setter.body)
        return property_accessor

    @property
    def attr_setter(self):
        return self._init_function("setter")

    @property
    def attr_deleter(self):
        return self._init_function("deleter")

    @property
    def attr_getter(self):
        return self._init_function("getter")

    # pylint: enable=import-outside-toplevel
