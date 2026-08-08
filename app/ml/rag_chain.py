"""
RAG chains for regulatory Q&A and CSRD report generation.

Two chains are built on the same FAISS retriever:
- QA chain: answers questions about CSRD/ESRS regulations with citations
- Report chain: generates ESRS E1 disclosure narratives from emission data

All LangChain imports are lazy so the app works without the RAG stack.
"""
import logging
from typing import AsyncGenerator

from app.core.config import settings
from app.ml.document_processor import load_vector_store

logger = logging.getLogger(__name__)

QA_PROMPT_TEMPLATE = (
    "You are a CSRD compliance expert. Use the following regulatory context "
    "to answer the question. Always cite which part of CSRD/ESRS the answer "
    "comes from. Context: {context}\n\nQuestion: {question}\n\nAnswer:"
)

CSRD_REPORT_SYSTEM_PROMPT = (
    "You are a CSRD report writer. Generate professional ESRS E1 Climate "
    "Change disclosure narrative. Use the emission data provided and "
    "regulatory context. Structure: 1) Overview 2) Scope 1 Analysis "
    "3) Scope 2 Analysis 4) Scope 3 Analysis 5) Reduction Targets "
    "6) Methodology"
)


def get_llm(streaming: bool = True):
    """ChatOpenAI instance with project defaults — low temperature for facts."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0.1,
        streaming=streaming,
        api_key=settings.OPENAI_API_KEY,
    )


def get_retriever(k: int = 5):
    """Load the FAISS store and return a top-k retriever, or None if not built."""
    store = load_vector_store()
    if store is None:
        return None
    return store.as_retriever(search_kwargs={"k": k})


def build_qa_chain():
    """
    Retrieval QA chain: question → retrieve top chunks → answer with citations.
    Returns None if the vector store hasn't been built yet.
    """
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate
    from langchain_core.runnables import RunnablePassthrough

    retriever = get_retriever(k=5)
    if retriever is None:
        return None

    prompt = PromptTemplate.from_template(QA_PROMPT_TEMPLATE)

    def format_docs(docs) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | get_llm(streaming=True)
        | StrOutputParser()
    )
    return chain


def build_csrd_report_chain():
    """
    Report generation chain. Takes a pre-formatted emission data context
    (built by CSRDReportGenerator) plus retrieved regulatory context and
    produces the full ESRS E1 narrative.
    """
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([
        ("system", CSRD_REPORT_SYSTEM_PROMPT),
        (
            "human",
            "Regulatory context:\n{regulatory_context}\n\n"
            "Company emission data:\n{emission_context}\n\n"
            "Write the complete ESRS E1 disclosure narrative now.",
        ),
    ])

    chain = prompt | get_llm(streaming=True) | StrOutputParser()
    return chain


async def stream_rag_response(question: str, chain) -> AsyncGenerator[str, None]:
    """Yield text chunks from a chain for SSE streaming."""
    async for chunk in chain.astream(question):
        if chunk:
            yield chunk
