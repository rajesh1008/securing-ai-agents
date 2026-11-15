#!/usr/bin/env python3
"""Chapter 37, lab 1 (no model): is what the catalogue says an item is called what the source says?  For every item of every standard in bulwark/crosswalk_data.py, look for its title in the text
of the page or document the author saved on 2026-11-13 (06-research/ch37_raw).  Items found / not found / not checkable (no primary text held).  Also: the OWASP 2023-24 to 2025 renumbering, and the ATLAS counts.
Writes results/ch37_sources.json and prints the log.  The saved pages are not part of the repository; their digests are."""
import sys, json, re, hashlib
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.crosswalk_data import CAT, STANDARDS
RAW = here.parent.parent / "06-research/ch37_raw"
import unicodedata
def norm(s): return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKC", s).lower().replace("&", " and ")).strip()
SRC = {"LLM25": ["llm2025.txt"], "LLM23": ["llm2023.txt"], "ASI26": ["asi.txt", "xwalk.txt"], "N600": ["nist600.txt"], "EUAI": ["art4.txt", "art9.txt", "art12.txt", "art14.txt", "art15.txt", "art26.txt", "art50.txt", "art73.txt"], "ATLS": ["atlas_changelog.raw"]}
def main():
    res = {"files": {}, "std": {}}
    for f in sorted(RAW.iterdir()):
        if f.suffix in (".raw", ".txt") and f.stem not in ("eurlex",): res["files"][f.name] = dict(bytes=f.stat().st_size, sha256=hashlib.sha256(f.read_bytes()).hexdigest()[:16])
    eu_extra = {"Art12": "record keeping", "Art14": "human oversight", "Art15": "accuracy robustness and cybersecurity", "Art73": "reporting of serious incidents"}
    for s in STANDARDS:
        texts = {n: norm((RAW / n).read_text(errors="ignore")) for n in SRC.get(s.id, []) if (RAW / n).exists()}
        big = " ".join(texts.values()); found, missing, uncheck = [], [], []
        for it in CAT.of(s.id):
            if not big: uncheck.append(it.id); continue
            t = norm(it.title)
            if s.id == "EUAI" and it.id in eu_extra: t = eu_extra[it.id]
            if s.id == "EUAI":
                pg = norm((RAW / f"art{it.id[3:]}.txt").read_text(errors="ignore")); (found if norm(f"article {it.id[3:]} {it.title}") in pg else missing).append(it.id); continue
            (found if t in big else missing).append(it.id)
        res["std"][s.id] = dict(read=s.read, items=len(CAT.of(s.id)), found=len(found), missing=missing, not_checkable=len(uncheck), sources=list(texts))
        print(f"{s.id:6} edition {s.edition!r:60} read={s.read:9} items {len(CAT.of(s.id)):3}  title found in saved source {len(found):3}  missing {missing}  no primary text {len(uncheck)}")
    cw = norm((RAW / "xwalk.txt").read_text(errors="ignore")); res["asi_title_variants"] = {k: sorted(set(re.findall(k, cw))) for k in ("cascading[a-z ]{0,8}failures", "agentic supply chain[a-z ]{0,16}", "insecure inter agent communications?")}
    print("OWASP ASI wording on the crosswalk page:", res["asi_title_variants"])
    # the Art 14 / Art 12 / Art 15 / Art 73 pages were fetched by the research step, not saved: say so
    # ATLAS counts from the changelog
    t = (RAW / "atlas_changelog.raw").read_text(errors="ignore"); m = re.search(r"## \[(\d{4}\.\d{2})\]\(\) \((\d{4}-\d{2}-\d{2})\)\s+##### Content v[\d.]+\s+This version of ATLAS data contains ([^.]*)\.", t)
    res["atlas_latest"] = dict(release=m.group(1), date=m.group(2), contains=m.group(3)) if m else None; print("ATLAS latest release in the changelog:", res["atlas_latest"])
    rel = re.findall(r"## \[(\d{4}\.\d{2}[^\]]*)\]\(\) \((\d{4}-\d{2}-\d{2})\)", t); res["atlas_releases_in_file"] = rel[:12]; print("ATLAS releases listed:", rel[:12])
    # OWASP LLM renumbering
    old, new = {i.id: i.title for i in CAT.of("LLM23")}, {i.id: i.title for i in CAT.of("LLM25")}
    same = [k for k in old if norm(old[k]) == norm(new[k])]; res["llm_same_id_same_title"] = same
    t_new = {norm(v): k for k, v in new.items()}; moved = {k: t_new[norm(v)] for k, v in old.items() if norm(v) in t_new and t_new[norm(v)] != k}; res["llm_moved"] = moved
    print("OWASP LLM: ids whose title is unchanged between 2023-24 and 2025:", same, "| same title, different id:", moved, "| ids with a different title:", [k for k in old if k not in same])
    json.dump(res, open(here / "results/ch37_sources.json", "w"), indent=1)
if __name__ == "__main__": main()
