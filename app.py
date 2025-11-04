
import streamlit as st
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
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
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Prompt template includes a {context} variable
    # The system prompt combines your original workflow with the retrieved context.
    system_prompt = f"""{dsa_tutor_workflow}

Answer the user's question based on the following context:
{{context}}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    # Create the chains
    retrieval_chain = (
        # This part creates a dictionary with 'context' and 'input'
        # 'context' is created by taking the input, passing it to the retriever, and then formatting the docs
        # 'input' and 'chat_history' are passed through from the original input dictionary
        RunnablePassthrough.assign(
            context=(lambda x: x['input']) | retriever | format_docs
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return retrieval_chain

retrieval_chain = initialize_langchain()
# --- CHAT INTERFACE ---

# 1. Initialize a SINGLE chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="How can I help you?")]

# 2. Display all messages from history
# Use st.markdown() for better formatting of AI responses (like code blocks)
for message in st.session_state.messages:
    if isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content)

# 3. Handle new user input
if prompt := st.chat_input("Ask me about Data Structures and Algorithms..."):

    # 4. Add user message to the SINGLE history and display it
    st.session_state.messages.append(HumanMessage(content=prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    # 5. Get and display AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):

            # 6. Create the input dictionary for the chain
            #    We pass the ENTIRE 'messages' list as the chat_history
            chain_input = {
                "input": prompt,
                "chat_history": st.session_state.messages
            }

          #  Response from the retrieval chain
            response_string = retrieval_chain.invoke(chain_input)

            # 7. Display the string response
            st.markdown(response_string)

            # 8. Add the AI's string response to the SINGLE history
            st.session_state.messages.append(
                AIMessage(content=response_string))
