"""evsim-calc: a tiny calculator library, shipped to a function as a wheel.

It stands in for a jar that Evelyn bundles, such as fircosoft-trust or address-lookup-jnw: a
project of its own, with its own version and tests, built once and consumed as a binary.
"""

from importlib.metadata import version

__version__ = version("evsim-calc")

OPERANDS = ("add", "subtract", "multiply", "divide")


def calculate(integer_1: int, integer_2: int, operand: str) -> int:
    """Apply `operand` to two integers and return an integer.

    `divide` truncates toward zero, the way Java's int division does: -7 divide 2 is -3. Python's
    `//` rounds down instead and gives -4, the trap a Java-to-Python port falls into.
    """
    # bool is a subclass of int in Python, so True + True would quietly give 2.
    if type(integer_1) is not int or type(integer_2) is not int:
        raise TypeError(f"two integers expected, got {integer_1!r} and {integer_2!r}")
    if operand == "add":
        return integer_1 + integer_2
    if operand == "subtract":
        return integer_1 - integer_2
    if operand == "multiply":
        return integer_1 * integer_2
    if operand == "divide":
        if integer_2 == 0:
            raise ZeroDivisionError(f"{integer_1} divide 0: division by zero")
        quotient = abs(integer_1) // abs(integer_2)
        return quotient if (integer_1 < 0) == (integer_2 < 0) else -quotient
    raise ValueError(f"unknown operand {operand!r}; allowed: {', '.join(OPERANDS)}")
