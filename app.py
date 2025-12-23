import streamlit as st
import os
import asyncio
import base64
import concurrent.futures
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
from elevenlabs.client import AsyncElevenLabs
from code_editor import code_editor


# --- LOAD .env ---
load_dotenv()

# --- CONFIGURATION ---
# Please set the following environment variables before running the script:
# GOOGLE_API_KEY, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB, ELEVENLABS_API_KEY
st.set_page_config(page_title="DSA AI Tutor", page_icon="🤖")
st.title("DSA AI Tutor")

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
TABLE_NAME = "dsa_tutor_collection"
HISTORY_FILE = "user_interactions.md"
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # Default voice ID
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
ELEVENLABS_API_KEY = os.getenv("ELEVEN_LABS_API")

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
      model="gemini-2.5-flash-lite",
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
            # Escape curly braces in history to prevent LangChain from interpreting them as template variables
            escaped_history = history_context.replace("{", "{{").replace("}", "}}")
            history_section = f"\n\n## Previous Conversation History\n\nYou have access to previous conversation history. Use this to understand context and maintain continuity in your teaching:\n\n{escaped_history}\n\n---\n\nNote: Use this history to understand the student's learning journey, but focus on the current conversation in your responses."

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

# --- ELEVENLABS TTS FUNCTIONS ---

async def stream_tts_async(text: str, api_key: str, voice_id: str, model_id: str):
    """Stream TTS audio asynchronously and return audio bytes."""
    if not api_key:
        return None

    audio_chunks = []

    try:
        # Create async client
        client = AsyncElevenLabs(api_key=api_key)

        # Use the async streaming API (returns async generator, no await needed)
        audio_stream = client.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format="mp3_44100_128",
        )

        # Collect all audio chunks asynchronously
        async for chunk in audio_stream:
            if chunk:
                audio_chunks.append(chunk)

        # Combine all chunks into a single bytes object
        return b''.join(audio_chunks)
    except Exception as e:
        # Don't use st.error() in async function - return error info instead
        print(f"Error generating TTS: {e}")
        return None

def generate_tts_audio(text: str, api_key: str, voice_id: str, model_id: str):
    """Wrapper to run async TTS generation in sync context."""
    if not api_key:
        return None

    # Run async function in sync context
    try:
        # Check if there's already a running event loop
        try:
            loop = asyncio.get_running_loop()
            # If there's a running loop, use a thread to run the async function
            def run_in_thread():
                # Create a new event loop in this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        stream_tts_async(text, api_key, voice_id, model_id)
                    )
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                audio_bytes = future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            audio_bytes = asyncio.run(
                stream_tts_async(text, api_key, voice_id, model_id)
            )
        return audio_bytes
    except Exception as e:
        st.error(f"Error in TTS generation: {e}")
        return None




# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("Settings")
    enable_tts = st.checkbox("Enable Text-to-Speech", value=False)
    enable_ide = st.checkbox("Enable Code Editor", value=False )

    # Check for ElevenLabs API key
    elevenlabs_api_key = ELEVENLABS_API_KEY
    if not elevenlabs_api_key:
        st.warning("ELEVENLABS_API_KEY not set. TTS will be disabled.")
        enable_tts = False

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="How can I help you?")]

# Initialize code editor content in session state
if "code_editor_content" not in st.session_state:
    st.session_state.code_editor_content = "# write your code here\n\n"

# Display code editor if enabled
if enable_ide:
    st.subheader("📝 Code Editor")
    st.caption("Write your code below. When you submit a message, your code will be included.")

    code_response = code_editor(
        st.session_state.code_editor_content,
        lang="python"
    )

    # Update session state with latest code from editor
    if code_response and "text" in code_response:
        st.session_state.code_editor_content = code_response["text"]
        # Store code to be used in next prompt
        st.session_state.pending_code = code_response["text"]

for message in st.session_state.messages:
    if isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content)

if prompt := st.chat_input("Ask me about Data Structures and Algorithms..."):
    # Include code in prompt if IDE is enabled and code exists
    if enable_ide and "pending_code" in st.session_state and st.session_state.pending_code.strip():
        code_content = st.session_state.pending_code.strip()
        # Format the prompt to include code
        if code_content and code_content != "# write your code here":
            formatted_prompt = f"Here's my code:\n```python\n{code_content}\n```\n\n"
            if prompt.strip():
                formatted_prompt += f"Question: {prompt}"
            else:
                formatted_prompt += "Please review this code and help me understand it."
            prompt = formatted_prompt
            # Clear pending code after using it
            del st.session_state.pending_code

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

        # Stream response but collect it without displaying (show loading indicator)
        for chunk in retrieval_chain.stream(chain_input):
            full_response += chunk
            # Show loading indicator instead of text
            response_container.markdown("Thinking... ▌")

        # Generate and play TTS audio if enabled (before showing final response)
        audio_bytes = None
        if enable_tts and elevenlabs_api_key and full_response.strip():
            # Show spinner while generating audio
            # response_container.markdown("Generating audio...")
            with st.spinner():
                audio_bytes = generate_tts_audio(
                    full_response,
                    elevenlabs_api_key,
                    ELEVENLABS_VOICE_ID,
                    ELEVENLABS_MODEL_ID
                )

        # Now show the final response only after audio generation completes
        # (or immediately if TTS is disabled)
        response_container.markdown(full_response)
        st.session_state.messages.append(AIMessage(content=full_response))

        # Display audio if it was generated
        if audio_bytes:
            # Encode audio to base64 for HTML data URI
            b64 = base64.b64encode(audio_bytes).decode()

            # Create HTML audio element with JavaScript autoplay attempt
            audio_html = f"""
            <audio id="tts-audio-{id(audio_bytes)}" controls autoplay style="width: 100%; display: none;">
                <source src="data:audio/mpeg;base64,{b64}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <script>
                (function() {{
                    var audio = document.getElementById('tts-audio-{id(audio_bytes)}');
                    if (audio) {{
                        // Try to play immediately (may be blocked by browser)
                        var playPromise = audio.play();
                        if (playPromise !== undefined) {{
                            playPromise.then(function() {{
                                console.log('Audio autoplay started successfully');
                            }}).catch(function(error) {{
                                console.log('Autoplay was blocked:', error.name);
                                // Audio player is visible, user can click play
                            }});
                        }}
                    }}
                }})();
            </script>
            """
            st.markdown(audio_html, unsafe_allow_html=True)

        # Save the interaction to history file
        save_interaction(prompt, full_response)
