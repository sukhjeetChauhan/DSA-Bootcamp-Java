# Development History

This file tracks the development conversation about building a DSA teaching AI.

**User's Goal:** Build an AI system on top of the `DSA-Bootcamp-Java` repository to teach data structures and algorithms.

**Initial Plan:**
1.  **Content Analysis:** Parse PDFs, Markdown, Java code, and images.
2.  **AI Model:** Fine-tune an LLM on the extracted data.
3.  **Application:** Build a chat interface for students.
4.  **Backend:** Host the model and handle logic.
5.  **Evaluation:** Test and refine the AI.

**Refined Plan with LangChain and Streamlit:**
*   **LangChain:** Use for data ingestion (`DocumentLoaders`), creating a RAG pipeline (`ConversationalRetrievalChain`), and managing interaction with the LLM. This is the core of the backend.
*   **Streamlit:** Use to build the interactive web-based chat UI for the frontend.

**Pydantic's Role:**
*   **Data Consistency:** Use Pydantic models to define a clear, validated schema for structured data.
*   **Structured Output from LLM:** Use LangChain's `PydanticOutputParser` to get structured data back from the model.
*   **API Layer:** Define request and response models for a potential FastAPI backend.

**Agent Rules Created:**
*   `setup.md`: General agent protocols.
*   `gemini.md` & `claude.md`: Specific rules for agents, including read-only access to core material and a pedagogical focus on gap identification.

---

## Next Steps (To be resumed)

**User:** ok what should be our next step?

**Assistant's Proposal:** Begin **Phase 1: Content Ingestion and Processing**.

1.  **Set Up the Environment:** Create a `requirements.txt` file for libraries (`langchain`, `streamlit`, `pypdf`, `faiss-cpu`, etc.).
2.  **Create an Ingestion Script (`ingest.py`):** This script will use LangChain to:
    *   Load all educational materials.
    *   Split them into chunks.
    *   Create vector embeddings.
    *   Store the embeddings in a local FAISS vector database.

**User's Response:** ok save this in development history. we will pick it up from here tomorrow

---

## Session Summary (2025-10-31)

**Goal:** Complete Phase 1: Content Ingestion and Processing.

**Accomplishments:**
1.  **Environment Setup:**
    *   Created a `requirements.txt` file with all necessary libraries.
    *   Set up a Python virtual environment using `uv`.
    *   Installed all dependencies.
2.  **Ingestion Script (`ingest.py`):**
    *   Created the `ingest.py` script to handle document loading, splitting, and embedding.
    *   Successfully ran the script, creating the `faiss_index` vector store.

**Next Steps:**
*   **Phase 2: Building the User Interface:**
    *   Create a Streamlit application (`app.py`) to serve as the front-end for the AI tutor.
    *   Implement the logic to receive user input, query the vector store, and display the AI's response.

---

## Session Summary (2025-11-01)

**Goal:** Begin Phase 2: Building the User Interface, focusing on the AI's core logic and prompt engineering.

**Accomplishments:**
1.  **AI Tutor Workflow Defined:** Collaboratively designed a detailed `dsa_tutor_workflow.md` file outlining the AI's behavior in two modes:
    *   **Curriculum Mode:** Guiding students topic-by-topic, tracking progress, and adapting to preferred programming languages.
    *   **Problem-Solving Mode:** Diagnosing knowledge gaps, using Socratic questioning, and leveraging multimedia from core materials.
2.  **`dsa_tutor_workflow.md` Created:** The workflow document was written to `/Users/sukhchauhan/DevAcademy/DSA-Bootcamp-Java/dsa_tutor_workflow.md`.
3.  **LLM and Prompt Setup Discussed:** Identified key LangChain components (`ChatGoogleGenerativeAI`, `ChatPromptTemplate`, `MessagesPlaceholder`) and discussed their roles.
4.  **System Message Constructed:** Planned how to integrate the `dsa_tutor_workflow.md` content into the `ChatPromptTemplate` as a system message.
5.  **RAG Chain Components Explored:** Discussed the need for a Retrieval-Augmented Generation (RAG) chain, including:
    *   Loading the FAISS vector store.
    *   Creating a retriever.
    *   Using a document chain (`create_stuff_documents_chain`).
    *   Combining them into a retrieval chain (`create_retrieval_chain`).
6.  **Embedding Model Confirmed:** Reconfirmed that `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")` is the correct embedding model to use for loading the FAISS index.

**Next Steps:**
*   Load the FAISS index using `FAISS.load_local()`.
*   Create a retriever from the loaded FAISS index using the confirmed `HuggingFaceEmbeddings` model.

---

## Session Summary (2025-11-02)

**Goal:** Resolve `ModuleNotFoundError` and `ImportError` related to `langchain` imports in `app.py`.

**Issues Faced:**
*   Persistent `ModuleNotFoundError` and `ImportError` issues related to `langchain` imports, despite multiple re-installations and environment checks.

**User's Deduction:** The user correctly deduced that the problem is not with package installation but with the `langchain` API itself. Specifically, that the old way of importing retriever and document chaining functions has been deprecated due to the modularization of the `langchain` library.

**Next Steps:**
*   Investigate the correct, current import paths for `create_stuff_documents_chain` and `create_retrieval_chain` based on the latest `langchain` documentation and package structure.
*   Update `app.py` with the correct import statements.

---

## Session Summary (2025-11-04)

**Goal:** Analyze and summarize the user's changes to `app.py`.

**Accomplishments:**
1.  **Code Analysis:** The user made significant changes to `app.py` to fix the import errors and improve the application.
2.  **Summary of Changes:**
    *   **Modernized LangChain Implementation:**
        *   Corrected imports to reflect the latest `langchain` package structure.
        *   Replaced deprecated chains with a more explicit and composable chain using `RunnablePassthrough`.
        *   Enhanced the system prompt to explicitly combine the `dsa_tutor_workflow.md` with the retrieved context.
    *   **Improved Chat Experience:**
        *   Implemented streaming responses for a more interactive feel.
        *   Simplified chat history management.
        *   Used `st.markdown` for better formatting of AI responses.

**Next Steps:**
*   Continue building and refining the DSA AI Tutor.

---

## Session Summary (2025-11-18)

**Goal:** Migrate from FAISS to PGVector for the RAG model and containerize the application.

**Accomplishments:**
1.  **Updated `requirements.txt`:**
    *   Added `langchain-postgres`, `psycopg`, `transformers`, and `langfuse`.
    *   Removed `faiss-cpu`.
2.  **Updated `ingest.py`:**
    *   Modified to use `PGVector` for the vector store.
    *   Switched to `BAAI/bge-small-en-v1.5` for embeddings.
    *   Implemented advanced chunking using `AutoTokenizer` and added rich metadata to document chunks.
    *   Integrated `SQLRecordManager` for index management.
3.  **Updated `app.py`:**
    *   Modified to connect to `PGVector` instead of loading a local FAISS index.
    *   Updated embedding function to `BAAI/bge-small-en-v1.5`.
    *   Configured the retriever to use Maximal Marginal Relevance (MMR) search.
    *   Retained the original LLM model (`gemini-2.0-flash-thinking-exp-1219` with `temperature=0`) as per user request.
    *   Adjusted the RAG chain structure for explicit context and chat history handling.
4.  **Containerization:**
    *   Created a `Dockerfile` for the Python application.
    *   Created a `docker-compose.yml` file to orchestrate a PostgreSQL service with PGVector and the Python application service.
    *   Created a `.env.example` file listing all necessary environment variables (PostgreSQL, Google API Key, Langfuse).
5.  **Explanation Provided:**
    *   Explained the functionality of `HF_HOME`, `SENTENCE_TRANSFORMERS_HOME` environment variables, and the `huggingface_cache` Docker volume for persisting downloaded embedding models.

**Next Steps:**
*   **Install new dependencies:** Run `source .venv/bin/activate && uv pip install -r requirements.txt`.
*   **Set up environment variables:** Create a `.env` file based on `.env.example` and populate it with actual values, especially for PostgreSQL connection and `GOOGLE_API_KEY`.
*   **Build and run Docker containers:** Use `docker-compose up --build` to start the services.
*   **Ingest data:** Run `python ingest.py` (or `docker-compose exec app python ingest.py`) to populate the PGVector database.
*   **Test application:** Access the Streamlit application in the browser (usually `http://localhost:8501`).

---

## Session Summary (2025-11-23)

**Goal:** Add conversation history persistence and enable model to read previous interactions.

**Accomplishments:**
1. **Conversation History System:**
   * Created `save_interaction()` function to automatically save user-AI exchanges to `user_interactions.md`
   * Created `load_conversation_history()` function to load previous conversations
   * Implemented automatic session organization by date
   * Added token limit management (loads last 5 sessions to avoid exceeding limits)

2. **Model Integration:**
   * Modified RAG chain to dynamically load conversation history before each interaction
   * Integrated history into system prompt for context awareness
   * Model can now reference previous conversations to maintain continuity

3. **Model Configuration Updates:**
   * Updated LLM model from `gemini-2.0-flash-thinking-exp-1219` to `gemini-2.5-flash`
   * Changed temperature from `0` to `0.7` for more varied responses

4. **New File Created:**
   * `user_interactions.md` - Stores actual user-AI conversation history (separate from development history)

**Technical Details:**
* History is loaded dynamically via `create_chain_with_history()` function
* Each interaction is automatically saved after AI response
* History file uses markdown format with timestamps and session headers
* System prompt includes history section when available

**Next Steps:**
* Test the history persistence across multiple sessions
* Monitor token usage with history integration
* Consider adding history management UI (clear history, export, etc.)

---

## Session Summary (2025-12-23)

**Goal:** Add Text-to-Speech (TTS) functionality using ElevenLabs API and implement auto-play audio.

**Accomplishments:**
1. **ElevenLabs Integration:**
   * Added `elevenlabs` package to `requirements.txt`
   * Imported `AsyncElevenLabs` client from `elevenlabs.client`
   * Configured ElevenLabs constants (voice ID, model ID, API key) in `app.py`

2. **TTS Functions Implemented:**
   * Created `stream_tts_async()` function to asynchronously stream TTS audio from ElevenLabs API
   * Created `generate_tts_audio()` wrapper function with improved async handling
   * Implemented `concurrent.futures.ThreadPoolExecutor` to properly handle event loop conflicts in Streamlit
   * Changed error handling in async function from `st.error()` to `print()` for better async compatibility

3. **User Interface Updates:**
   * Added sidebar checkbox to enable/disable TTS functionality
   * Integrated TTS audio generation into the chat response flow
   * Replaced `st.audio()` with custom HTML audio element using base64 encoding
   * Implemented JavaScript autoplay attempt with fallback handling for browser autoplay policies
   * Added spinner feedback during audio generation

4. **Configuration:**
   * Set default voice ID: `JBFqnCBsd6RMkjVDRZzb`
   * Set model ID: `eleven_multilingual_v2`
   * Configured output format: `mp3_44100_128`
   * Added environment variable support for `ELEVEN_LABS_API` key

5. **Bug Fixes:**
   * Fixed history context escaping issue: Added curly brace escaping (`{` → `{{`, `}` → `}}`) in `create_chain_with_history()` to prevent LangChain from interpreting history content as template variables

**Technical Details:**
* TTS generation happens after AI response is complete
* Audio is generated only when TTS is enabled and API key is available
* Uses async streaming API for efficient audio generation
* Improved event loop handling: Uses `ThreadPoolExecutor` when a running event loop is detected, otherwise uses `asyncio.run()`
* Audio is base64-encoded and embedded in HTML data URI for playback
* JavaScript attempts autoplay but may be blocked by browser policies (user can still click play if blocked)
* Audio element currently shows controls (next step: hide controls for true background playback)

**New Imports:**
* Added `base64` for encoding audio bytes to base64 string
* Added `concurrent.futures` for ThreadPoolExecutor in async handling

**Next Steps:**
* **Hide audio player controls:** Modify HTML audio element to remove visible controls (`controls` attribute) while maintaining autoplay functionality. This will enable true background audio playback without showing any player interface to the user.
