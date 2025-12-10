import os
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.indexes import SQLRecordManager
from langchain_core.indexing import index
from transformers import AutoTokenizer

# --- CONFIGURATION ---
# Please set the following environment variables before running the script:
# POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB
# Example:
# export POSTGRES_USER="myuser"
# export POSTGRES_PASSWORD="mypassword"
# export POSTGRES_HOST="localhost"
# export POSTGRES_DB="mydatabase"

DATA_PATH = "core material/"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
TABLE_NAME = "dsa_tutor_collection"

def main():
    """
    This function orchestrates the ingestion of documents into the PGVector store.
    """
    # 1. Load documents
    documents = []
    for root, _, files in os.walk(DATA_PATH):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
            elif file.endswith(".md"):
                loader = UnstructuredMarkdownLoader(file_path)
                documents.extend(loader.load())
            elif file.endswith(".txt"):
                loader = TextLoader(file_path)
                documents.extend(loader.load())

    print(f"Loaded {len(documents)} documents.")

    # 2. Modern chunking with tokenizer
    tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=lambda text: len(tokenizer.tokenize(text, truncation=True)),
        is_separator_regex=False,
    )
    chunks = text_splitter.split_documents(documents)

    # 3. Add rich metadata
    for i, chunk in enumerate(chunks):
        chunk.metadata.update({
            "source": chunk.metadata.get("source", "Unknown"),
            "chunk_index": i,
            "total_chunks": len(chunks),
            "indexed_at": datetime.now().isoformat(),
        })

    print(f"Created {len(chunks)} chunks with rich metadata.")

    # 4. Configure embeddings
    embedding_function = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
    )

    # 5. Setup vector store
    CONNECTION_STRING = PGVector.connection_string_from_db_params(
        driver="psycopg",
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', 'password'),
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=5432,
        database=os.getenv('POSTGRES_DB', 'postgres'),
    )

    vectorstore = PGVector(
        embeddings=embedding_function,
        collection_name=TABLE_NAME,
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )

    # 6. Setup index management
    namespace = f"pgvector/{TABLE_NAME}"
    RECORD_MANAGER_URL = f"postgresql+psycopg://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'password')}@{os.getenv('POSTGRES_HOST', 'localhost')}:5432/{os.getenv('POSTGRES_DB', 'postgres')}"

    record_manager = SQLRecordManager(namespace, db_url=RECORD_MANAGER_URL)
    record_manager.create_schema()

    # 7. Index documents
    result = index(
        chunks,
        record_manager,
        vectorstore,
        cleanup="incremental",
        source_id_key="source",
    )
    print(f"Indexing result: {result}")

if __name__ == "__main__":
    main()
