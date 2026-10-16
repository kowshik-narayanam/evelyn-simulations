import pytest

from evsim_calc import OPERANDS, __version__, calculate


@pytest.mark.parametrize(
    "integer_1, integer_2, operand, result",
    [
        (12, 30, "add", 42),
        (-5, 8, "add", 3),
        (100, 58, "subtract", 42),
        (3, 10, "subtract", -7),
        (7, 6, "multiply", 42),
        (-4, 25, "multiply", -100),
        (84, 4, "divide", 21),
        (0, 5, "divide", 0),
    ],
)
def test_each_operand(integer_1, integer_2, operand, result):
    assert calculate(integer_1, integer_2, operand) == result


@pytest.mark.parametrize(
    "integer_1, integer_2, result",
    [(7, 2, 3), (-7, 2, -3), (7, -2, -3), (-7, -2, 3)],
)
def test_divide_truncates_toward_zero_like_java(integer_1, integer_2, result):
    # Python's // gives -4 for -7 // 2. Java's int division gives -3, and so must this library.
    assert calculate(integer_1, integer_2, "divide") == result


def test_divide_by_zero_fails():
    with pytest.raises(ZeroDivisionError, match="9 divide 0"):
        calculate(9, 0, "divide")


def test_an_unknown_operand_lists_the_allowed_ones():
    with pytest.raises(ValueError, match="'power'; allowed: add, subtract, multiply, divide"):
        calculate(2, 3, "power")


@pytest.mark.parametrize("bad", [True, 2.5, "2"])
def test_only_integers_are_accepted(bad):
    with pytest.raises(TypeError):
        calculate(bad, 1, "add")


def test_the_version_comes_from_the_installed_package():
    assert __version__ == "1.0.0" and OPERANDS == ("add", "subtract", "multiply", "divide")
