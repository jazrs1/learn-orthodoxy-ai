"""v2 store verification and directory checks (INGEST_PLAN.md §9.1), without any embedding call."""

import chromadb
from chromadb.config import Settings

from corpus_runtime import ids_sha1, v2_directory_problems, verify_store


def manifest_for(en_ids, ar_ids):
    return {"collections": {
        "en": {"name": "orthodox_pdfs_v2", "chunks": len(en_ids), "chunk_ids_sha1": ids_sha1(en_ids)},
        "ar": {"name": "orthodox_arabic_pdfs_v2", "chunks": len(ar_ids), "chunk_ids_sha1": ids_sha1(ar_ids)},
    }}


def store(tmp_path, en_ids, ar_ids):
    client = chromadb.PersistentClient(path=str(tmp_path / "v2"), settings=Settings(anonymized_telemetry=False))
    for name, ids in (("orthodox_pdfs_v2", en_ids), ("orthodox_arabic_pdfs_v2", ar_ids)):
        if ids:
            client.get_or_create_collection(name).upsert(ids=ids, embeddings=[[0.1, 0.2]] * len(ids), documents=ids)
    return client


def test_matching_store_has_no_problems(tmp_path):
    client = store(tmp_path, ["v2:cat2:q1:c1", "v2:cat2:q2:c1"], ["v2:ar-cat:q1:c1"])
    assert verify_store(client, manifest_for(["v2:cat2:q1:c1", "v2:cat2:q2:c1"], ["v2:ar-cat:q1:c1"])) == []


def test_missing_collection_count_and_id_differences_are_reported(tmp_path):
    client = store(tmp_path, ["v2:cat2:q1:c1", "v2:cat2:q3:c1"], [])
    problems = verify_store(client, manifest_for(["v2:cat2:q1:c1", "v2:cat2:q2:c1"], ["v2:ar-cat:q1:c1"]))
    assert problems == ["orthodox_pdfs_v2: chunk ids differ from the manifest", "orthodox_arabic_pdfs_v2: missing"]


def test_v2_directory_must_exist_and_live_inside_the_volume(tmp_path):
    mount = tmp_path / "chroma_db"
    (mount / "v2").mkdir(parents=True)
    assert v2_directory_problems(str(mount / "v2"), str(mount))[0].endswith("does not exist or is empty")
    (mount / "v2" / "chroma.sqlite3").write_text("x")
    assert v2_directory_problems(str(mount / "v2"), str(mount)) == []
    outside = tmp_path / "chroma_v2"
    outside.mkdir()
    (outside / "chroma.sqlite3").write_text("x")
    assert "is not inside the volume mount" in v2_directory_problems(str(outside), str(mount))[0]
    assert v2_directory_problems(str(outside), None) == []  # locally there is no volume to be inside
