"""Chatbot "Assistente climatico": il modello si usa solo tramite ``llm_client``."""

from src.chatbot.llm_client import (
    AnthropicClient,
    ClientLLM,
    FakeLLM,
    LLMNonDisponibile,
    OllamaClient,
    chiedi_llm,
    crea_client,
    embedding_bag_of_words,
    stato_llm,
)
from src.chatbot.memory import MemoriaConversazione
from src.chatbot.rag import (
    Chunk,
    Documento,
    IndiceVettoriale,
    carica_indice,
    cerca_documenti,
    costruisci_indice,
    formatta_contesto,
    leggi_corpus,
    spezza_in_chunk,
)
from src.chatbot.prompts import RIFIUTI, SYSTEM_PROMPTS, versione_prompt
from src.chatbot.agent import (
    RispostaAgente,
    esegui_agente,
    instrada,
    numeri_non_supportati,
    parse_tool_request,
    rileva_injection,
)

__all__ = [
    'AnthropicClient',
    'ClientLLM',
    'FakeLLM',
    'LLMNonDisponibile',
    'OllamaClient',
    'chiedi_llm',
    'crea_client',
    'embedding_bag_of_words',
    'stato_llm',
    # RAG (rag.py)
    'Chunk',
    'Documento',
    'IndiceVettoriale',
    'carica_indice',
    'cerca_documenti',
    'costruisci_indice',
    'formatta_contesto',
    'leggi_corpus',
    'spezza_in_chunk',
    # Memoria, prompt e agente (memory.py, prompts.py, agent.py)
    'MemoriaConversazione',
    'RIFIUTI',
    'SYSTEM_PROMPTS',
    'versione_prompt',
    'RispostaAgente',
    'esegui_agente',
    'instrada',
    'numeri_non_supportati',
    'parse_tool_request',
    'rileva_injection',
]
