"""
pkgdata is a simple, extensible way for a package to acquire data file
resources.

The getResource function is equivalent to the standard idioms, such as
the following minimal implementation:

    import sys, os

    def getResource(identifier, pkgname=__name__):
        pkgpath = os.path.dirname(sys.modules[pkgname].__file__)
        path = os.path.join(pkgpath, identifier)
        return file(os.path.normpath(path), mode='rb')

When a __loader__ is present on the module given by __name__, it will defer
getResource to its get_data implementation and return it as a file-like
object (such as StringIO).
"""

__all__ = ["getResource"]
import sys
import os

try:
    from pkg_resources import resource_stream, resource_exists
except ImportError:

    def resource_exists(_package_or_requirement, _resource_name):
        """
        A stub for when we fail to import this function.

        :return: Always returns False
        """
        return False

    def resource_stream(_package_of_requirement, _resource_name):
        """
        A stub for when we fail to import this function.

        Always raises a NotImplementedError when called.
        """
        raise NotImplementedError


def getResource(identifier, pkgname=__name__):
    """
    Acquire a readable object for a given package name and identifier.
    An IOError will be raised if the resource can not be found.

    For example:
        mydata = getResource('mypkgdata.jpg').read()

    Note that the package name must be fully qualified, if given, such
    that it would be found in sys.modules.

    In some cases, getResource will return a real file object.  In that
    case, it may be useful to use its name attribute to get the path
    rather than use it as a file-like object.  For example, you may
    be handing data off to a C API.
    """

    # When pyinstaller (or similar tools) are used, resource_exists may raise
    # NotImplemented error
    try:
        if resource_exists(pkgname, identifier):
            return resource_stream(pkgname, identifier)
    except NotImplementedError:
        pass

    mod = sys.modules[pkgname]
    path_to_file = getattr(mod, "__file__", None)
    if path_to_file is None:
        raise OSError(f"{repr(mod)} has no __file__!")
    path = os.path.join(os.path.dirname(path_to_file), identifier)

    # pylint: disable=consider-using-with
    return open(os.path.normpath(path), "rb")
