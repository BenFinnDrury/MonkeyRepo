import pytest

from monkey_registry.models import Monkey, Species


def test_marmoset_age_cap_rejected():
    # marmoset older than 22 should raise
    with pytest.raises(ValueError):
        Monkey(name="oldie", species=Species.MARMOSET, age_years=23, favourite_fruit="banana")


def test_valid_monkey_constructs():
    m = Monkey(name="luna", species="marmoset", age_years=2, favourite_fruit="mango")
    d = m.to_dict()
    assert d["name"] == "luna"
    assert d["species"] == "marmoset"
    assert d["age_years"] == 2