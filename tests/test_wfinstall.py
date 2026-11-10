# -*- coding: utf-8 -*-
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nd_wfinstall as W


def node(t, cnr=None, aux=None, ver=None, **extra):
    p = {}
    if cnr:
        p["cnr_id"] = cnr
    if aux:
        p["aux_id"] = aux
    if ver:
        p["ver"] = ver
    d = {"id": 1, "type": t, "properties": p}
    d.update(extra)
    return d


def wf(nodes, subgraph_nodes=(), notes=()):
    ns = list(nodes) + [node("MarkdownNote", widgets_values=[n]) for n in notes]
    data = {"nodes": ns, "links": []}
    if subgraph_nodes:
        data["definitions"] = {"subgraphs": [{"id": "11111111-2222-3333-4444-555555555555", "name": "sg", "nodes": list(subgraph_nodes)}]}
        data["nodes"].append(node("11111111-2222-3333-4444-555555555555", "comfy-core"))
    return data


class PackageTests(unittest.TestCase):
    def test_core_and_frontend_skipped(self):
        r = W.analyze_workflow(wf([node("KSampler", "comfy-core", ver="0.3"), node("Reroute"), node("Note")]))
        self.assertEqual(r["packages"], [])
        self.assertEqual(r["unknown_types"], [])

    def test_subgraph_nodes_are_scanned(self):
        data = wf([node("KSampler", "comfy-core")], [node("VedaX", "veda-sparse-attention", "veda-sparse/Veda-on-ComfyUI", "0.3.0")])
        r = W.analyze_workflow(data)
        self.assertEqual([p["repo"] for p in r["packages"]], ["veda-sparse/Veda-on-ComfyUI"])
        self.assertEqual(r["packages"][0]["ver_kind"], "tag")

    def test_cnr_only_joins_aux_package_by_name(self):
        data = wf([node("A", "comfyui-kjnodes", "kijai/ComfyUI-KJNodes", "a" * 40), node("B", "comfyui-kjnodes", None, "a" * 40)])
        pk = W.analyze_workflow(data)["packages"]
        self.assertEqual(len(pk), 1)
        self.assertEqual(pk[0]["nodes"], 2)

    def test_wrong_cnr_id_uses_aux(self):
        data = wf([node("L", "comfyui-workflow-encrypt", "TripleHeadedMonkey/ComfyUI-MiniMaxH3_LatentUpscaler", "b" * 40)])
        p = W.analyze_workflow(data)["packages"][0]
        self.assertEqual(p["repo"], "TripleHeadedMonkey/ComfyUI-MiniMaxH3_LatentUpscaler")
        self.assertEqual(p["status"], "install")

    def test_note_picks_fork_and_offers_alternative(self):
        nodes = [node("A", "comfyui-promptbuilder", "Adudeguyman/ComfyUI-PromptBuilder", "1" * 40), node("B", "comfyui-promptbuilder", "neural-dreamer/ComfyUI-PromptBuilder", "2" * 40)]
        note = "git clone [x](https://github.com/neural-dreamer/ComfyUI-PromptBuilder)"
        p = W.analyze_workflow(wf(nodes, notes=[note]))["packages"][0]
        self.assertEqual(p["repo"], "neural-dreamer/ComfyUI-PromptBuilder")
        self.assertEqual(p["alternatives"], ["Adudeguyman/ComfyUI-PromptBuilder"])
        self.assertEqual(p["status"], "choose")
        self.assertEqual(p["ver"], "2" * 40)   # версия именно выбранного форка

    def test_note_only_match_by_cnr_name(self):
        data = wf([node("S", "comfyui-spectrum-minimax-h3", None, "c" * 40)], notes=["[r](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3)"])
        p = W.analyze_workflow(data)["packages"][0]
        self.assertEqual((p["repo"], p["source"]), ("xmarre/ComfyUI-Spectrum-MiniMax-H3", "заметка"))

    def test_registry_then_manager_fallback(self):
        data = wf([node("X", "comfyui-easy-use", None, "1.3.6"), node("Y")])
        calls = []
        r = W.analyze_workflow(data, registry=lambda c: calls.append(c) or "https://github.com/yolain/ComfyUI-Easy-Use")
        self.assertEqual(r["packages"][0]["repo"], "yolain/ComfyUI-Easy-Use")
        self.assertEqual(r["packages"][0]["source"], "Comfy Registry")
        self.assertEqual(r["unknown_types"], ["Y"])
        r = W.analyze_workflow(data, registry=lambda c: None, manager=lambda t: ["https://github.com/yolain/ComfyUI-Easy-Use"] if t == "X" else [])
        self.assertEqual(r["packages"][0]["source"], "база ComfyUI-Manager")
        r = W.analyze_workflow(data)
        self.assertEqual(r["packages"][0]["status"], "notfound")

    def test_extra_note_repos(self):
        data = wf([node("A", None, "o/r1")], notes=["https://github.com/o/r1 и https://github.com/o/other https://boosty.to/x https://github.com/o"])
        r = W.analyze_workflow(data)
        self.assertEqual([e["repo"] for e in r["extra_notes"]], ["o/other"])

    def test_parse_repo(self):
        self.assertEqual(W.parse_repo("https://github.com/a/b.git")["repo"], "b")
        self.assertEqual(W.parse_repo("https://github.com/a/b/tree/dev")["branch"], "dev")
        for bad in ("https://huggingface.co/a/b", "https://github.com/a", "https://github.com/a/b/blob/main/x.md", "https://youtube.com/@x"):
            self.assertIsNone(W.parse_repo(bad), bad)

    def test_ver_kind(self):
        self.assertEqual(W.ver_kind("d7c70b548e145cc0e687f3c45a748aa9311c01e6"), "commit")
        self.assertEqual(W.ver_kind("1.5.1"), "tag")
        self.assertEqual(W.ver_kind("v2.0"), "tag")
        self.assertIsNone(W.ver_kind("nightly"))
        self.assertIsNone(W.ver_kind(None))

    def test_merge_analyses(self):
        a = W.analyze_workflow(wf([node("A", None, "o/r", "1" * 40)]))
        b = W.analyze_workflow(wf([node("B", None, "O/R", "1" * 40), node("C", None, "o/s")]))
        m = W.merge_analyses([a, b])
        self.assertEqual(sorted(p["repo"].lower() for p in m["packages"]), ["o/r", "o/s"])


class InstalledTests(unittest.TestCase):
    def make(self, root, folder, remote=None, pyname=None):
        d = Path(root) / folder
        (d / ".git").mkdir(parents=True)
        if remote:
            (d / ".git" / "config").write_text(f'[remote "origin"]\n\turl = {remote}\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n')
        if pyname:
            (d / "pyproject.toml").write_text(f'[project]\nname = "{pyname}"\n')

    def test_detect_same_other_and_disabled(self):
        with tempfile.TemporaryDirectory() as t:
            self.make(t, "ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git")
            self.make(t, "ComfyUI-PromptBuilder", "git@github.com:Adudeguyman/ComfyUI-PromptBuilder.git")
            self.make(t, "veda.disabled", None, "veda-sparse-attention")
            inst = W.scan_installed(t)
            self.assertTrue(any(i["disabled"] for i in inst))
            r = W.analyze_workflow(wf([node("A", "comfyui-kjnodes", "kijai/ComfyUI-KJNodes")]), installed=inst)
            self.assertEqual(r["packages"][0]["status"], "installed")
            r = W.analyze_workflow(wf([node("B", None, "neural-dreamer/ComfyUI-PromptBuilder")]), installed=inst)
            p = r["packages"][0]
            self.assertEqual(p["installed_kind"], "other")   # папка есть, но это другой репозиторий (оригинал вместо форка)
            self.assertEqual(p["status"], "install")


class ModelTests(unittest.TestCase):
    def test_models_from_node_and_notes(self):
        note = ("**diffusion_models**\n\n- [a.safetensors](https://huggingface.co/o/r/resolve/main/diffusion_models/a.safetensors)\n"
                "- [Civit](https://civitai.com/models/1/x)\n\n# Другое\n- [m.gguf](https://huggingface.co/o/r/resolve/main/m.gguf)\n"
                "- [page](https://huggingface.co/models?other=x)\n")
        data = wf([node("V", None, None, None, properties={"models": [{"name": "v.safetensors", "url": "https://h/v", "directory": "vae"}]})], notes=[note])
        ms = {m["name"]: m for m in W.collect_models(data)}
        self.assertEqual(ms["v.safetensors"]["folder"], "vae")
        self.assertEqual(ms["a.safetensors"]["folder"], "diffusion_models")
        self.assertTrue(ms["Civit"]["manual"])
        self.assertEqual(ms["m.gguf"]["folder"], "LLM")   # заголовок не про папку моделей сбросил папку; .gguf → LLM
        self.assertNotIn("page", ms)

    def test_model_present(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "vae" / "sub" / "x.safetensors"
            f.parent.mkdir(parents=True)
            f.write_bytes(b"1")
            self.assertTrue(W.model_present({"name": "sub/x.safetensors", "folder": "vae"}, [t]))
            self.assertFalse(W.model_present({"name": "y.safetensors", "folder": "vae"}, [t]))
            self.assertFalse(W.model_present({"name": "x", "folder": "vae", "manual": True}, [t]))


def zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


WF = json.dumps({"nodes": [], "links": []}).encode()


class BundleTests(unittest.TestCase):
    def test_zip_contents_and_safety(self):
        data = zip_bytes({"A.json": WF, "Sub/B.json": WF, "prompts/p.txt": "hi", "x/prompts/deep/q.txt": "q",
                          "../evil.json": WF, "/abs.json": WF, "tool.py": "print(1)", "pkg.json": '{"name": 1}',
                          "__MACOSX/._A.json": "x", "prompts/../outside.txt": "x"})
        b = W.Bundle()
        W.read_zip(b, io.BytesIO(data), "t.zip")
        self.assertEqual(sorted(w["rel"] for w in b.workflows), ["A.json", "Sub/B.json"])
        self.assertEqual(sorted(p["rel"] for p in b.prompts), ["deep/q.txt", "p.txt"])
        names = [n for n, _ in b.ignored]
        self.assertIn("tool.py", names)
        self.assertIn("pkg.json", names)
        self.assertIn("../evil.json", names)

    def test_api_format_detected(self):
        b = W.Bundle()
        W._add_json(b, "api.json", json.dumps({"1": {"class_type": "KSampler", "inputs": {}}}).encode())
        self.assertTrue(b.workflows[0]["api"])

    def test_bad_zip(self):
        b = W.Bundle()
        W.read_zip(b, io.BytesIO(b"not a zip"), "x.zip")
        self.assertTrue(b.errors)

    def test_read_inputs_mixed(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "one.json").write_bytes(WF)
            (Path(t) / "z.zip").write_bytes(zip_bytes({"Two.json": WF}))
            (Path(t) / "n.txt").write_text("x")
            b = W.read_inputs([Path(t) / "one.json", Path(t) / "z.zip", Path(t) / "n.txt"])
            self.assertEqual(sorted(w["rel"] for w in b.workflows), ["Two.json", "one.json"])
            self.assertEqual(len(b.ignored), 1)


class PlanTests(unittest.TestCase):
    def test_conflicts_replace_keep_both(self):
        with tempfile.TemporaryDirectory() as t:
            wd, pd = Path(t) / "wf", Path(t) / "prompts"
            wd.mkdir()
            (wd / "A.json").write_bytes(b"old")
            (wd / "B.json").write_bytes(b"oldB")
            (wd / "C.json").write_bytes(b"oldC")
            b = W.Bundle()
            for n in ("A", "B", "C", "New"):
                b.workflows.append(dict(rel=f"{n}.json", raw=f"new{n}".encode(), data={}, api=False))
            b.prompts.append(dict(rel="p.txt", raw=b"P"))
            plan = W.plan_files(b, wd, pd)
            self.assertEqual({p["rel"]: p["action"] for p in plan}, {"A.json": "ask", "B.json": "ask", "C.json": "ask", "New.json": "write", "p.txt": "write"})
            res = W.apply_plan(plan, {str(wd / "A.json"): "replace", str(wd / "B.json"): "keep", str(wd / "C.json"): "both"})
            self.assertEqual((wd / "A.json").read_bytes(), b"newA")
            self.assertEqual((wd / "B.json").read_bytes(), b"oldB")
            self.assertEqual((wd / "C.json").read_bytes(), b"oldC")
            self.assertEqual((wd / "C (2).json").read_bytes(), b"newC")
            self.assertEqual((pd / "p.txt").read_bytes(), b"P")
            self.assertEqual(len(res["written"]), 4)
            self.assertEqual(res["errors"], [])
            self.assertFalse(list(wd.glob("*.nd_tmp")))


SAMPLE = Path("/mnt/user-data/uploads/28833806-ND_MiniMax_H3_Director_v1.2_NDUI.json")


@unittest.skipUnless(SAMPLE.is_file(), "нет примера воркфлоу")
class RealSampleTests(unittest.TestCase):
    def test_director_resolves_everything_from_metadata_and_notes(self):
        d = json.loads(SAMPLE.read_text(encoding="utf-8"))
        r = W.analyze_workflow(d)
        repos = {p["repo"] for p in r["packages"] if p["repo"]}
        for need in ("xmarre/ComfyUI-Spectrum-MiniMax-H3", "veda-sparse/Veda-on-ComfyUI", "Larryvrh/ComfyUI-MiniMax-H3-Turbo",
                     "Zironic/H3-Optimizations", "neural-dreamer/ComfyUI-Fantastic-MiniMaxH3-PromptBuilder"):
            self.assertIn(need, repos)
        fork = next(p for p in r["packages"] if "PromptBuilder" in (p["repo"] or ""))
        self.assertEqual(fork["status"], "choose")


if __name__ == "__main__":
    unittest.main()


class VersionsTest(unittest.TestCase):
    """Узлы одной ноды могут нести разные версии (часть узлов обновили позже): все должны попасть в список,
    включая узлы без aux_id."""

    def test_all_versions_collected_with_noaux_nodes(self):
        def node(i, t, aux, ver):
            pr = {"cnr_id": "comfyui-foo", "ver": ver}
            if aux:
                pr["aux_id"] = aux
            return {"id": i, "type": t, "properties": pr}
        wf = {"nodes": [node(1, "A", "o/comfyui-foo", "a" * 40), node(2, "B", "o/comfyui-foo", "a" * 40),
                        node(3, "C", None, "b" * 40)], "links": []}
        res = W.analyze_workflow(wf, [], None, None)
        pk = res["packages"][0]
        self.assertEqual(pk["vers"], ["a" * 40, "b" * 40])
        self.assertEqual(pk["vers_by_repo"]["o/comfyui-foo"], ["a" * 40, "b" * 40])
