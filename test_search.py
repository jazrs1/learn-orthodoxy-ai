import os
from dotenv import load_dotenv
from chromadb.utils import embedding_functions
from chroma_store import COLLECTION_NAME, get_chroma_collection, log_chroma_configuration

load_dotenv()

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    log_chroma_configuration("test_search")
    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )

    _, collection = get_chroma_collection(
        embedding_function=embed_fn,
    )

    query = "What does Orthodox teaching say about fasting and why we do it?"
    results = collection.query(query_texts=[query], n_results=5)

    print("QUERY:", query)
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), start=1):
        print("\n" + "-" * 80)
        print(f"Result {i} — {meta['pdf']} page {meta['page']}")
        print(doc[:600].replace("\n", " ") + " ...")


if __name__ == "__main__":
    main()
