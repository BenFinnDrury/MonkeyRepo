from pathlib import Path
from click.testing import CliRunner

from monkey_registry.cli import cli


def test_cli_crud_smoke(tmp_path: Path):
    # use an isolated temp json file so we don't touch real data
    dbfile = tmp_path / "monkeys.json"
    env = {"MONKEY_DB_PATH": str(dbfile)}

    runner = CliRunner()

    # create
    res = runner.invoke(cli, ["create", "--name", "luna", "--species", "marmoset", "--age", "2", "--fruit", "mango"], env=env)
    assert res.exit_code == 0, res.output

    # duplicate should fail (same name within same species)
    res2 = runner.invoke(cli, ["create", "--name", "luna", "--species", "marmoset", "--age", "3", "--fruit", "banana"], env=env)
    assert res2.exit_code != 0
    assert "duplicate name" in res2.output.lower()

    # different species with same name should succeed
    res3 = runner.invoke(cli, ["create", "--name", "luna", "--species", "macaque", "--age", "3", "--fruit", "banana"], env=env)
    assert res3.exit_code == 0, res3.output

    # list and search should find items
    res_list = runner.invoke(cli, ["list"], env=env)
    assert res_list.exit_code == 0 and "luna" in res_list.output

    res_search = runner.invoke(cli, ["search", "marmo"], env=env)
    assert res_search.exit_code == 0 and "found" in res_search.output.lower()