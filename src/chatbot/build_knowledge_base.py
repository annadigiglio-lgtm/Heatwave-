"""Ricostruisce da zero l'indice RAG del chatbot.

Uso::

    python -m src.chatbot.build_knowledge_base

Legge il corpus (wiki, manoscritto, schede di ``data/knowledge_base``),
calcola gli embedding con Ollama (``chatbot.rag.embedding_model``, di
default ``bge-m3``) e salva l'indice in ``chatbot.rag.persist_dir``. Ogni
esecuzione riparte da zero e sovrascrive i file: è idempotente.
"""

from __future__ import annotations

import sys
import time

from src.chatbot.llm_client import LLMNonDisponibile
from src.chatbot.rag import (
    FILE_CHUNKS,
    FILE_EMBEDDINGS,
    FILE_MANIFEST,
    cartella_indice,
    costruisci_indice,
    crea_client_embedding,
    nome_indice,
    svuota_cache,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    """Costruisce e salva l'indice; restituisce il codice di uscita (0 = ok)."""
    inizio = time.perf_counter()
    cartella = cartella_indice()
    try:
        client = crea_client_embedding()
        indice = costruisci_indice(client)
    except LLMNonDisponibile as errore:
        print(f'Indice non costruito: {errore}', file=sys.stderr)
        return 1

    for nome in (FILE_EMBEDDINGS, FILE_CHUNKS, FILE_MANIFEST):
        (cartella / nome).unlink(missing_ok=True)
    indice.salva(cartella, nome_indice=nome_indice())
    svuota_cache()

    conteggi = indice.chunks['fonte'].value_counts().sort_index()
    print(f'Indice "{nome_indice()}" — modello {indice.modello_embedding}, '
          f'dimensione {indice.dimensione}')
    print('Chunk per fonte:')
    for fonte, numero in conteggi.items():
        print(f'  {numero:4d}  {fonte}')
    print(f'Totale: {len(indice)} chunk da {len(conteggi)} fonti')
    print(f'Salvato in: {cartella}')
    print(f'Tempo impiegato: {time.perf_counter() - inizio:.1f} s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
