"""Exception classes raised by both implementations of arithkit.

Both implementations raise exactly these classes, under exactly the same
conditions. Error messages may differ between the implementations.

Besides these, both implementations raise the builtin :class:`TypeError` for
arguments of the wrong Python type (for instance a float where an integer is
expected) and for operations between objects of different implementations
(toy and native objects never interact).
"""


class ArithkitError(Exception):
    """Base class of all arithkit exceptions."""


class InvalidParameterError(ArithkitError, ValueError):
    """Invalid parameters for constructing a parent, e.g. a non-squarefree ``N``."""


class NotInGroupError(ArithkitError, ValueError):
    """The given data does not describe an element of the group."""


class ParentMismatchError(ArithkitError, TypeError):
    """An operation combined objects of the same implementation but different parents."""


class JsonFormatError(ArithkitError, ValueError):
    """A JSON text is malformed or does not have the documented shape."""


class JsonIntTooLargeError(JsonFormatError):
    """A JSON text contains, or would contain, an integer with too many digits.

    Integers with at least :data:`arithkit_api._json.MAX_DIGITS` decimal digits
    are refused when reading and when writing JSON.
    """
