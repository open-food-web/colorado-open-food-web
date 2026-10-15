"""The site data is built from a release and the supply network, and only ever carries safe, public fields."""
import importlib.util
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
spec = importlib.util.spec_from_file_location("build_site", os.path.join(REPO, "scripts", "build_site.py"))
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)


def test_web_json_links_edges_to_nodes_and_adds_websites(tmp_path, monkeypatch):
    rel = tmp_path / "rel"
    rel.mkdir()
    (rel / "MANIFEST.json").write_text('{"version": "v2026.10.1"}', encoding="utf-8")
    (rel / "directory.csv").write_text("Business Name,City,Website\nRootstalk,Breckenridge,https://rootstalk.example\n", encoding="utf-8")
    (rel / "supply-network-nodes.csv").write_text("name,type,city\nRootstalk,restaurant,Breckenridge\nA Farm,farm,Salida\n", encoding="utf-8")
    (rel / "supply-network-edges.csv").write_text(
        "supplier,buyer,date,confidence,source,note,status\nA Farm,Rootstalk,unknown,high,https://x.example,private note,\n"
        "Nobody,Rootstalk,unknown,high,https://y.example,,\n", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(bs, "OUT", str(out))
    monkeypatch.setattr("sys.argv", ["build_site.py", "--release-dir", str(rel)])
    bs.main()
    web = json.load(open(out / "web.json", encoding="utf-8"))
    assert [n["name"] for n in web["nodes"]] == ["Rootstalk", "A Farm"]
    assert web["nodes"][0]["site"] == "https://rootstalk.example"
    assert web["edges"] == [{"s": 1, "t": 0, "src": "https://x.example", "ok": True, "conf": "high"}]   # unknown supplier dropped
    assert "private note" not in (out / "web.json").read_text(encoding="utf-8")
