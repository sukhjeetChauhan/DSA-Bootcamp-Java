import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_postgres import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages import AIMessage, HumanMessage
from langfuse.langchain import CallbackHandler


# --- LOAD .env ---
load_dotenv()

# --- CONFIGURATION ---
# Please set the following environment variables before running the script:
# GOOGLE_API_KEY, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB
st.set_page_config(page_title="DSA AI Tutor", page_icon="🤖")
st.title("DSA AI Tutor")

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
TABLE_NAME = "dsa_tutor_collection"
HISTORY_FILE = "user_interactions.md"

# --- CONVERSATION HISTORY FUNCTIONS ---
def load_conversation_history():
    """Load previous conversation history from markdown file."""
    if not os.path.exists(HISTORY_FILE):
        return ""

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        # Only return recent history (last 5 sessions) to avoid token limits
        # You can adjust this based on your needs
        sessions = content.split("## Session")
        if len(sessions) > 6:  # Keep header + last 5 sessions
            recent_sessions = "## Session".join(sessions[-6:])
            return recent_sessions
        return content
    except Exception as e:
        st.warning(f"Could not load conversation history: {e}")
        return ""

def save_interaction(user_message: str, ai_response: str):
    """Save a user-AI interaction to the markdown file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")

    # Create or append to the history file
    file_exists = os.path.exists(HISTORY_FILE)
    needs_new_session = False

    # Check if we need a new session (new day)
    if file_exists:
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as read_f:
                content = read_f.read()
                # Check if today's session header exists
                if f"## Session ({today})" not in content:
                    needs_new_session = True
        except Exception:
            needs_new_session = True

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("# User Interaction History\n\n")
            f.write("This file contains the conversation history between users and the DSA AI Tutor.\n\n")
            f.write("---\n\n")
            needs_new_session = True

        # Add session header if needed
        if needs_new_session:
            f.write(f"\n## Session ({today})\n\n")

        f.write(f"**Timestamp:** {timestamp}\n\n")
        f.write(f"**User:** {user_message}\n\n")
        f.write(f"**Assistant:** {ai_response}\n\n")
        f.write("---\n\n")

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

    # 3. Create advanced retriever with MMR
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 4,
            "fetch_k": 10,
            "lambda_mult": 0.5
        }
    )

    handler = CallbackHandler()

    # 4. Initialize the LLM (keeping the old model as requested)
    llm = ChatGoogleGenerativeAI(
      callbacks=[handler],
      model="gemini-2.5-flash",
      temperature=0.7,
    )

    # 5. Create the prompt template
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Base system prompt (history will be added dynamically)
    base_system_prompt = dsa_tutor_workflow

    # 6. Create the RAG chain
    # Note: We'll create a dynamic prompt wrapper that includes history
    def create_chain_with_history():
        """Create a chain with current conversation history."""
        # Load fresh history
        history_context = load_conversation_history()
        history_section = ""
        if history_context:
            history_section = f"\n\n## Previous Conversation History\n\nYou have access to previous conversation history. Use this to understand context and maintain continuity in your teaching:\n\n{history_context}\n\n---\n\nNote: Use this history to understand the student's learning journey, but focus on the current conversation in your responses."

        # Create prompt with history
        system_prompt = f"{base_system_prompt}{history_section}"
        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])

        # Create the RAG chain
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

    # Return a function that creates the chain with current history
    return create_chain_with_history

create_chain = initialize_langchain()

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

        # Create chain with current history (loads fresh history each time)
        retrieval_chain = create_chain()

        chain_input = {
            "input": prompt,
            "chat_history": st.session_state.messages
        }

        for chunk in retrieval_chain.stream(chain_input):
            full_response += chunk
            response_container.markdown(full_response + "▌")

        response_container.markdown(full_response)
        st.session_state.messages.append(AIMessage(content=full_response))

        # Save the interaction to history file
        save_interaction(prompt, full_response)
