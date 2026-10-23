"""The RAE engine: retrieve -> de-abstract -> situate -> instrument -> mark joints -> store.

The engine handles retrieval, provenance, assembly, and registration.
The agent supplies the judgment at each transform via the `fill` callbacks.
This division is deliberate: the machine never invents substance, and the
agent never has to do bookkeeping.
"""
import datetime
from pathlib import Path

from . import db
from . import patterns

ARTIFACT_DIR = Path.home() / "workspace" / "your_files" / "rae-artifacts"


def retrieve(ref):
    el = db.get_element(ref)
    kind = patterns.detect_kind(el)
    return {
        "id": el["id"],
        "title": el["title"],
        "content": el.get("content") or "",
        "layer": el.get("layer"),
        "status": el.get("status"),
        "verification_source": el.get("verification_source"),
        "verification_date": el.get("verification_date"),
        "notes": el.get("notes"),
        "source_title": el.get("source_title"),
        "source_url": el.get("source_url"),
        "kind": kind,
        "pattern": patterns.PATTERNS[kind],
    }


def assemble(element, context, fills):
    """Build the reified artifact markdown from the agent's fills.

    fills: dict with keys per the pattern's slots + instrument sections.
    Each fill value is (text, provenance) where provenance is 'verified' or 'scaffolded'.
    """
    mark = patterns.joint_mark
    L = []
    L.append(f"# {element['title']} — reified for {context}")
    L.append("")
    L.append(f"*RAE artifact · {datetime.date.today().isoformat()} · "
             f"source element #{element['id']} ({element['status']})*")
    L.append("")
    L.append("## Source element")
    L.append("")
    L.append(f"**{element['title']}** {mark(element['status'])}")
    if element["content"]:
        L.append(f"> {element['content']}")
    if element["verification_source"]:
        L.append(f"Verification: {element['verification_source']}")
    if element["source_title"]:
        L.append(f"Via: {element['source_title']}")
    L.append("")
    L.append("## Reified structure")
    L.append("")
    for slot in element["pattern"]["slots"]:
        text, prov = fills.get(slot, ("_(not filled)_", "scaffolded"))
        L.append(f"### {slot.replace('_', ' ').title()} {mark(prov)}")
        L.append("")
        L.append(text)
        L.append("")
    L.append("## Operational instruments")
    L.append("")
    for inst in element["pattern"]["instrument"]:
        text, prov = fills.get(inst, ("_(not filled)_", "scaffolded"))
        L.append(f"### {inst.replace('_', ' ').title()} {mark(prov)}")
        L.append("")
        L.append(text)
        L.append("")
    L.append("## Joint markings")
    L.append("")
    L.append("Parts marked [verified] come from the source element's verified content. "
             "Parts marked [scaffolded — candidate] were added during reification to make "
             "the artifact wieldable — they are new claims, not inherited certainty. "
             "The combination is a fresh unknown at its seams; test it in use.")
    L.append("")
    return "\n".join(L)


def store(title, markdown, element_ids, context, summary=""):
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")[:60]
    path = ARTIFACT_DIR / f"{slug}.md"
    path.write_text(markdown, encoding="utf-8")
    wp_id = db.register_work_product(
        title=f"RAE: {title}",
        file_path=str(path),
        knowledge_ids=element_ids,
        summary=summary or f"Reified '{title}' for context: {context}",
        kind="reified artifact",
    )
    return path, wp_id


def reify(ref, context, fills, title=None):
    """Full six-stage run. `fills` comes from the agent's judgment."""
    element = retrieve(ref)                       # 1. retrieve
    # 2-4. de-abstract / situate / instrument happen inside fills (agent's work)
    markdown = assemble(element, context, fills)  # 5. mark joints (in assemble)
    path, wp_id = store(                          # 6. store
        title or f"{element['title']} ({context})",
        markdown, [element["id"]], context,
    )
    return {"element": element, "path": str(path), "work_product_id": wp_id}
