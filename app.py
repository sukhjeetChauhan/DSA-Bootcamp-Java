import streamlit as st
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import AIMessage, HumanMessage

# --- LOAD .env ---
load_dotenv()

# --- CONFIGURATION ---
# Please set the following environment variables before running the script:
# GOOGLE_API_KEY, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB
st.set_page_config(page_title="DSA AI Tutor", page_icon="🤖")
st.title("DSA AI Tutor")

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
TABLE_NAME = "dsa_tutor_collection"

# --- LOAD API KEY ---
if "GOOGLE_API_KEY" not in os.environ:
    st.error("Please set the GOOGLE_API_KEY environment variable.")
    st.stop()

# --- LOAD DSA TUTOR WORKFLOW ---
@st.cache_data
def load_workflow():
    with open("dsa_tutor_workflow.md", "r") as f:
        return f.read()

dsa_tutor_workflow = load_workflow()

# --- INITIALIZE LANGCHAIN COMPONENTS ---
@st.cache_resource
def initialize_langchain():
    # 1. Configure embeddings
    embedding_function = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
    )

    # 2. Setup vector store
    CONNECTION_STRING = PGVector.connection_string_from_db_params(
        driver="psycopg",
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', 'password'),
        host=os.getenv('POSTGRES_HOST', 'db'),
        port=5432,
        database=os.getenv('POSTGRES_DB', 'postgres'),
    )

    vectorstore = PGVector(
        embeddings=embedding_function,
        collection_name=TABLE_NAME,
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )

    # 3. Create advanced retriever with MMR
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 4,
            "fetch_k": 10,
            "lambda_mult": 0.5
        }
    )

    # 4. Initialize the LLM (keeping the old model as requested)
    llm = ChatGoogleGenerativeAI(
      model="gemini-2.0-flash-thinking-exp-1219",
      temperature=0,
    )

    # 5. Create the prompt template
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    system_prompt = f"{dsa_tutor_workflow}"

    answer_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    # 6. Create the RAG chain
    rag_chain = (
        {
            "context": (lambda x: x['input']) | retriever | format_docs,
            "input": lambda x: x['input'],
            "chat_history": lambda x: x['chat_history']
        }
        | answer_prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain

retrieval_chain = initialize_langchain()

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="How can I help you?")]

for message in st.session_state.messages:
    if isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content)

if prompt := st.chat_input("Ask me about Data Structures and Algorithms..."):
    st.session_state.messages.append(HumanMessage(content=prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_container = st.empty()
        full_response = ""
        
        chain_input = {
            "input": prompt,
            "chat_history": st.session_state.messages
        }

        for chunk in retrieval_chain.stream(chain_input):
            full_response += chunk
            response_container.markdown(full_response + "▌")

        response_container.markdown(full_response)
        st.session_state.messages.append(AIMessage(content=full_response))