
import streamlit as st
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chains.combine_documents import create_stuff_documents_chain
from langchain_community.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.messages import AIMessage, HumanMessage

# --- LOAD .env ---
load_dotenv()

# --- CONFIGURATION ---
st.set_page_config(page_title="DSA AI Tutor", page_icon="🤖")
st.title("DSA AI Tutor")

# --- LOAD API KEY ---
# It is recommended to set the Google API key as an environment variable.
# For example, in your terminal: export GOOGLE_API_KEY="your_api_key"
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
    # Load the FAISS index
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    faiss_index = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)

    # Create a retriever
    retriever = faiss_index.as_retriever()

    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
      model="gemini-2.0-flash-thinking-exp-1219",
      temperature=0,
    )

    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", dsa_tutor_workflow),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    # Create the chains
    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    return retrieval_chain

retrieval_chain = initialize_langchain()

# --- CHAT INTERFACE ---
# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [AIMessage(content="How can I help you?")]
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display chat messages
for message in st.session_state.messages:
    if isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.write(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.write(message.content)

# User input
if prompt := st.chat_input("Ask me about Data Structures and Algorithms..."):
    st.session_state.messages.append(HumanMessage(content=prompt))
    st.session_state.chat_history.append(HumanMessage(content=prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = retrieval_chain.invoke({
                "input": prompt,
                "chat_history": st.session_state.chat_history
            })
            st.markdown(response["answer"])
            st.session_state.messages.append(AIMessage(content=response["answer"]))
            st.session_state.chat_history.append(AIMessage(content=response["answer"]))
