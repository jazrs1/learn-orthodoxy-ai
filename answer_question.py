import os
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

load_dotenv()

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "orthodox_pdfs"

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY.")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small",
    )
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
    )

    question = "What does Orthodox teaching say about fasting and why we do it?"
    retrieved = collection.query(query_texts=[question], n_results=6)

    docs = retrieved["documents"][0]
    metas = retrieved["metadatas"][0]

    context_blocks = []
    for d, m in zip(docs, metas):
        context_blocks.append(f"[Source: {m['pdf']} p.{m['page']}]\n{d}")

    context = "\n\n".join(context_blocks)

    client_oai = OpenAI(api_key=api_key)

    system_prompt = """
You are an Orthodox theology assistant.
Answer ONLY using the provided sources.
If the sources do not contain the answer, say:
"I don't know based on the provided sources."
Always include citations like (saints1.pdf p.12).
"""

    user_prompt = f"""
QUESTION:
{question}

SOURCES:
{context}
"""

    response = client_oai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    print("\nQUESTION:", question)
    print("\nANSWER:\n")
    print(response.choices[0].message.content)

    print("\nTOP SOURCES USED:")
    for m in metas[:3]:
        print(f"- {m['pdf']} p.{m['page']}")

if __name__ == "__main__":
    main()
