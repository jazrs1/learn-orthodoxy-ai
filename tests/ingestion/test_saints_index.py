"""The ingest-time saints index (INGEST_PLAN.md §7)."""

import json
from pathlib import Path

import pytest

from ingestion.saints_index import (
    ar_tokens,
    commemoration_dates,
    is_cross_reference,
    match_one_to_one,
    name_tokens,
    ordinals_agree,
)
from ingestion.structure import Block, Unit

INDEX = Path("data/corpus/v2/saints_index.json")


@pytest.mark.parametrize("references, expected", [
    (["[The Synaxarion: 4 Paona]"], ("4 Paona", "")),
    (["[Butler: March 3]"], ("", "March 3")),
    (["[The Synaxariun: 29 Baramouda] [Butler's Lives of Saints; Nov. 4]"], ("29 Baramouda", "Nov 4")),
    (["[The Synaxariun: Abib 16 & Toba 20]"], ("16 Abib", "")),
    (["[Butler: 2 December]"], ("", "December 2")),
    (["[Rev. Baring-Gould: The Lives of Saints, Vol. 7; p. 351 (July 15)]"], ("", "July 15")),
    (["[A Dictionary of Christian Biography, Vol. II, p. 454]"], ("", "")),
    (["[Baring-Gould: The Lives of Saints; 1914; Vol. 5; p. 52]"], ("", "")),
])
def test_commemoration_dates(references, expected):
    assert commemoration_dates(references) == expected


def test_name_tokens_drop_titles_and_descriptors():
    assert name_tokens("ABE-FAM (Bifam) EL-TAHAWY (The martyr)") == ["ABE", "FAM", "BIFAM", "ALTAHAWY"]
    assert name_tokens("LOT, FATHER") == name_tokens("LOT, FR")


def test_regnal_numbers_must_agree():
    assert ordinals_agree(name_tokens("JOHN 13th, The 94th POPE"), name_tokens("JOHN XIII, the 94th POPE"))
    assert not ordinals_agree(name_tokens("CYRIL IV"), name_tokens("CYRIL V"))
    assert not ordinals_agree(ar_tokens("كيرلس الرابع البابا"), ar_tokens("كيرلس الخامس البابا"))


def test_matching_is_one_to_one_and_best_first():
    left = [name_tokens("ABANOUB EL-NEHISSY (The martyr)"), name_tokens("ABANOUB, THE CONFESSOR, ST.")]
    right = [name_tokens("ABANOUB, THE CONFESSOR, ST"), name_tokens("ABANOUB AL-NEHESSY")]
    assert {i: k for i, (k, _) in match_one_to_one(left, right).items()} == {0: 1, 1: 0}


def test_cross_references():
    def unit(body, language="en"):
        u = Unit("sts1", language, "saints", "saint_entry", "x", "X")
        u.blocks.append(Block(body, 1, 1))
        return u
    assert is_cross_reference(unit("See the biography of St. Aphraates."))
    assert is_cross_reference(unit("Cf. Gregory of Nyssa, St."))
    assert is_cross_reference(unit("راجع دوسيثوس الهرطوقي.", "ar"))
    assert not is_cross_reference(unit("He was a priest who was martyred in Persia."))


@pytest.mark.skipif(not INDEX.exists(), reason="run python -m ingestion build --corpus v2 --dry-run")
def test_committed_index_is_consistent():
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    saints = data["saints"]
    ids = [s["id"] for s in saints]
    assert len(ids) == len(set(ids))
    by_id = {s["id"]: s for s in saints}
    names = {n for s in saints for n in [s.get("name_en", ""), *s.get("aliases_en", [])]}
    for famous in ("St. George", "St. Mark", "St. Athanasius", "St. Anthony the Great", "St. Demiana"):
        assert famous in names, famous
    george = next(s for s in saints if "St. George" in s.get("aliases_en", []))
    assert george["id"] == "george-the-capaducian"
    assert {e["lang"] for e in george["entries"]} == {"en", "ar"}
    for saint in saints:
        if saint.get("see_id"):
            assert saint["see_id"] in by_id
