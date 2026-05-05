from dotenv import load_dotenv

from chroma_store import COLLECTION_NAME, get_chroma_dir_env, get_chroma_path, get_collection_count

load_dotenv()


def main() -> None:
    count = get_collection_count()
    print(f"verify_chroma: collection={COLLECTION_NAME}")
    print(f"verify_chroma: chroma_dir_env={get_chroma_dir_env()}")
    print(f"verify_chroma: resolved_chroma_dir={get_chroma_path()}")
    print(f"verify_chroma: document_count={count}")


if __name__ == "__main__":
    main()
