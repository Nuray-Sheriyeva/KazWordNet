from kazwn import systems_freeze as F


def test_describe_check_and_pool_counts(tmp_path):
    a, b = tmp_path / "a.tsv", tmp_path / "b.tsv"
    a.write_text("h1\th2\nx\ty\nz\tw\n", encoding="utf-8")
    b.write_text("h1\th2\nx\ty\n", encoding="utf-8")
    paths = {"A": a, "B": b}
    rec = {"files": F.describe(paths, tmp_path)}
    assert rec["files"]["A"]["rows"] == 2 and rec["files"]["A"]["path"] == "a.tsv"
    assert F.check(rec, paths, tmp_path) == []
    b.write_text("h1\th2\nchanged\ty\n", encoding="utf-8")
    assert F.check(rec, paths, tmp_path) == ["B: file changed since the freeze"]
    b.unlink()
    assert F.check(rec, paths, tmp_path) == ["B: file missing"]
    assert F.check({"files": {}}, {"A": a}, tmp_path) == ["A: not in freeze record"]
    c = F.pool_counts({"S": {("d", "x"), ("d", "y"), ("t", "x"), ("r", "z")}}, {"d"}, {"t"}, {"d", "t", "r", "r2"})
    assert c["S"]["dev"] == {"pairs": 2, "synsets": 1, "pool_size": 1}
    assert c["S"]["test"]["pairs"] == 1 and c["S"]["rest"] == {"pairs": 1, "synsets": 1, "pool_size": 2}