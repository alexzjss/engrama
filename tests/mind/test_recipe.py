import numpy as np
import pytest
from engrama.mind.contracts import Module
from engrama.mind.recipe import ModuleSpec, load_recipe
from engrama.mind import registry


def write(tmp_path, text):
    p = tmp_path / "r.toml"; p.write_text(text, encoding="utf-8"); return p


def test_load_recipe_ok_and_errors(tmp_path):
    r = load_recipe(write(tmp_path, """
[recipe]
name = "x"
version = 2
[[module]]
type = "drives.needs"
gain = 3
[[module]]
type = "policy.utility"
name = "pol"
weight = 2.0
[[shadow]]
type = "policy.qlearning"
[arbiter]
temperature = 0.7
"""))
    assert (r.name, r.version) == ("x", 2)
    assert [m.name for m in r.modules] == ["drives.needs", "pol", "policy.qlearning"]
    assert r.modules[0].params == {"gain": 3} and r.modules[1].weight == 2.0
    assert [m.shadow for m in r.modules] == [False, False, True]
    assert r.arbiter == {"temperature": 0.7, "trait_temperature": True}

    with pytest.raises(ValueError, match="bogus"):
        load_recipe(write(tmp_path, '[recipe]\nname="x"\nbogus=1\n'))
    with pytest.raises(ValueError, match="dup"):
        load_recipe(write(tmp_path, '[recipe]\nname="x"\n[[module]]\ntype="a"\nname="dup"\n[[module]]\ntype="b"\nname="dup"\n'))


def test_build_unknown_type_lists_known():
    with pytest.raises(KeyError) as e:
        registry.build(ModuleSpec("nope", "nope", {}), np.random.default_rng(0))
    assert "drives.needs" in str(e.value)


class Fake(Module):
    pass


def test_build_registered_module_sets_name():
    registry.register("test.fake", f"{__name__}:Fake")
    m = registry.build(ModuleSpec("test.fake", "inst", {"k": 1}), np.random.default_rng(0))
    assert isinstance(m, Fake) and m.name == "inst" and m.params == {"k": 1}


def test_build_missing_import_is_unavailable():
    registry.register("test.missing", "engrama.no_such_pkg_xyz:Thing")
    with pytest.raises(registry.ModuleUnavailable):
        registry.build(ModuleSpec("test.missing", "m", {}), np.random.default_rng(0))
