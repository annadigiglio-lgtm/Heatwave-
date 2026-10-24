"""Test del RAG: chunking, indice vettoriale e ricerca.

Tutti i test usano un mini-corpus in ``tmp_path`` e l'embedding finto di
``FakeLLM`` (bag-of-words), quindi nessuna rete e nessun Ollama. Solo
``test_indice_reale_domande_di_controllo`` usa l'indice reale e ``bge-m3``:
si salta se l'indice non esiste o Ollama non risponde.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from src.chatbot import rag
from src.chatbot.llm_client import FakeLLM, LLMNonDisponibile, OllamaClient
from src.chatbot.rag import (
    Chunk,
    IndiceVettoriale,
    cerca_documenti,
    costruisci_indice,
    formatta_contesto,
    leggi_corpus,
    spezza_in_chunk,
)

PAGINA_WIKI = """# Fonti dati

**Sorgenti**: script di download e configurazione del progetto Heatwave.

## Open-Meteo

Open-Meteo fornisce una rianalisi storica delle temperature giornaliere
per i comuni del Piemonte, ottenuta combinando un modello fisico con le osservazioni.

<!-- nota interna: segretissimo da non indicizzare -->

## ARPA Piemonte

Le stazioni ARPA misurano direttamente la temperatura dell'aria; il bias
rispetto alla rianalisi Open-Meteo è negativo sulle massime estive.

```yaml
# questo non è un titolo ma un commento YAML dentro un blocco di codice
chiave: valore
```
"""

SCHEDA_FAQ = """# Domande frequenti

## Cos'è il clustering climatico?

Il clustering K-Means raggruppa i comuni con temperature simili in tre
gruppi: alpino fresco, intermedio e pianura calda, usando la silhouette.

### Vuota
"""

TODO = """# To-do per agenti

## T4.1 Knowledge base

Fare il RAG con ondate, cluster, ARPA, Open-Meteo, rianalisi, silhouette.
"""


def _scrivi(percorso: Path, testo: str) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(testo, encoding='utf-8')


@pytest.fixture
def corpus(tmp_path):
    """Mini-progetto con wiki, pagine escluse (operative e manoscritto) e knowledge base."""
    _scrivi(tmp_path / 'docs' / 'pages' / 'data-sources.md', PAGINA_WIKI)
    _scrivi(tmp_path / 'docs' / 'pages' / 'todo-agenti.md', TODO)
    _scrivi(tmp_path / 'docs' / 'pages' / 'roadmap-esame.md', TODO)
    _scrivi(tmp_path / 'paper' / 'manoscritto.md',
            '# Manoscritto\n\n## Abstract\n\nLe ondate di calore in Piemonte aumentano '
            'di frequenza e intensità nelle pianure del sud della regione.\n')
    _scrivi(tmp_path / 'paper' / 'references' / 'documento.pdf', 'non leggere')
    _scrivi(tmp_path / 'data' / 'knowledge_base' / 'faq.md', SCHEDA_FAQ)
    return tmp_path


@pytest.fixture
def fake():
    return FakeLLM(['ok'])


@pytest.fixture(autouse=True)
def cache_pulita():
    rag.svuota_cache()
    yield
    rag.svuota_cache()


# --- Corpus -----------------------------------------------------------------

def test_leggi_corpus_esclude_pagine_operative_e_pdf(corpus):
    fonti = [d.fonte for d in leggi_corpus(corpus)]
    assert fonti == [
        'docs/pages/data-sources.md',
        'data/knowledge_base/faq.md',
    ]
    assert 'paper/manoscritto.md' not in fonti
    assert 'docs/pages/todo-agenti.md' not in fonti
    assert not any(f.endswith('.pdf') for f in fonti)


def test_leggi_corpus_senza_knowledge_base(tmp_path):
    _scrivi(tmp_path / 'docs' / 'pages' / 'a.md', '# A\n\ntesto')
    assert [d.fonte for d in leggi_corpus(tmp_path)] == ['docs/pages/a.md']


def test_documento_ha_hash_e_titolo(corpus):
    documento = leggi_corpus(corpus)[0]
    assert len(documento.sha256) == 64
    assert documento.titolo == 'Fonti dati'


# --- Chunking ---------------------------------------------------------------

def test_chunking_per_titoli(corpus):
    chunks = spezza_in_chunk(PAGINA_WIKI, 'docs/pages/data-sources.md')
    assert [c.sezione for c in chunks] == ['Fonti dati', 'Open-Meteo', 'ARPA Piemonte']
    assert chunks[1].testo.startswith('## Open-Meteo')
    assert 'rianalisi' in chunks[1].testo
    # il commento YAML dentro il blocco di codice non diventa una sezione
    assert 'commento YAML' in chunks[2].testo


def test_chunking_toglie_commenti_html():
    chunks = spezza_in_chunk(PAGINA_WIKI, 'a.md')
    assert all('segretissimo' not in c.testo and '<!--' not in c.testo for c in chunks)


def test_chunking_salta_sezioni_quasi_vuote():
    chunks = spezza_in_chunk(SCHEDA_FAQ, 'faq.md')
    # "# Domande frequenti" e "### Vuota" non hanno testo: restano solo le sezioni piene
    assert [c.sezione for c in chunks] == ["Cos'è il clustering climatico?"]


def test_finestre_con_sovrapposizione():
    parole = [f'parola{i:02d}' for i in range(25)]
    testo = '## Lunga\n\n' + ' '.join(parole)
    chunks = spezza_in_chunk(testo, 'lunga.md', chunk_words=10, overlap_words=3)
    assert len(chunks) == 4
    assert all(c.sezione == 'Lunga' and c.testo.startswith('## Lunga') for c in chunks)
    primo, secondo = chunks[0].testo.split(), chunks[1].testo.split()
    for confine in ('parola07', 'parola08', 'parola09'):
        assert confine in primo and confine in secondo
    assert 'parola06' not in secondo
    # nessuna parola persa
    tutte = {p for c in chunks for p in c.testo.split()}
    assert set(parole) <= tutte


def test_id_stabili_e_fonte_con_slash():
    primi = spezza_in_chunk(PAGINA_WIKI, 'docs\\pages\\data-sources.md')
    secondi = spezza_in_chunk(PAGINA_WIKI, 'docs\\pages\\data-sources.md')
    assert [c.id for c in primi] == [c.id for c in secondi]
    assert [c.id for c in primi] == [f'docs/pages/data-sources.md#{i}' for i in range(3)]
    assert all(c.fonte == 'docs/pages/data-sources.md' for c in primi)


def test_parametri_di_chunking_non_validi():
    with pytest.raises(ValueError):
        spezza_in_chunk('## A\n\ntesto', 'a.md', chunk_words=10, overlap_words=10)


# --- Indice vettoriale ------------------------------------------------------

def test_cerca_restituisce_il_chunk_giusto_per_primo(corpus, fake):
    indice = costruisci_indice(fake, root=corpus)
    risultati = cerca_documenti('stazioni ARPA bias temperatura aria', k=2,
                                client=fake, indice=indice)
    assert risultati[0]['sezione'] == 'ARPA Piemonte'
    assert risultati[0]['fonte'] == 'docs/pages/data-sources.md'
    assert set(risultati[0]) >= {'testo', 'fonte', 'sezione', 'similarita'}
    assert risultati[0]['similarita'] >= risultati[1]['similarita']

    risultati = cerca_documenti('clustering K-Means silhouette', client=fake, indice=indice, k=1)
    assert risultati[0]['fonte'] == 'data/knowledge_base/faq.md'


def test_k_rispettato(corpus, fake):
    indice = costruisci_indice(fake, root=corpus)
    totale = len(indice)
    assert totale >= 3
    assert len(cerca_documenti('ondate di calore', k=2, client=fake, indice=indice)) == 2
    assert len(cerca_documenti('ondate di calore', k=50, client=fake, indice=indice)) == totale
    with pytest.raises(ValueError):
        indice.cerca(fake.embed(['x'])[0], k=0)


def test_round_trip_salva_carica(corpus, fake, tmp_path):
    indice = costruisci_indice(fake, root=corpus)
    cartella = indice.salva(tmp_path / 'vector_store', nome_indice='prova')
    assert {p.name for p in cartella.iterdir()} == {
        'embeddings.npy', 'chunks.parquet', 'manifest.json'
    }
    assert np.load(cartella / 'embeddings.npy').dtype == np.float32
    manifest = json.loads((cartella / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['n_chunk'] == len(indice)
    assert manifest['dimensione'] == 256
    assert manifest['modello_embedding'] == 'FakeLLM'
    assert set(manifest['hash_fonti_sha256']) == {
        'docs/pages/data-sources.md', 'data/knowledge_base/faq.md'
    }

    ricaricato = IndiceVettoriale.carica(cartella)
    assert ricaricato.chunks.equals(indice.chunks)
    domanda = 'rianalisi Open-Meteo modello fisico'
    assert (cerca_documenti(domanda, k=3, client=fake, indice=ricaricato)
            == cerca_documenti(domanda, k=3, client=fake, indice=indice))


def test_carica_indice_usa_la_cache(corpus, fake, tmp_path):
    costruisci_indice(fake, root=corpus).salva(tmp_path / 'vs')
    assert rag.carica_indice(tmp_path / 'vs') is rag.carica_indice(tmp_path / 'vs')


def test_errore_se_indice_manca(tmp_path):
    with pytest.raises(FileNotFoundError, match='build_knowledge_base'):
        IndiceVettoriale.carica(tmp_path / 'non_esiste')


def test_errore_se_dimensioni_incoerenti(corpus, fake):
    indice = costruisci_indice(fake, root=corpus)
    with pytest.raises(ValueError, match='incoerente'):
        indice.cerca([0.1, 0.2, 0.3], k=1)
    nuovo = Chunk(id='x#0', fonte='x', sezione='X', testo='testo nuovo')
    with pytest.raises(ValueError, match='incoerente'):
        indice.aggiungi([nuovo], [[1.0, 0.0]])
    with pytest.raises(ValueError):
        indice.aggiungi([nuovo], np.ones((2, 256)))


def test_errore_su_id_duplicati(corpus, fake):
    indice = costruisci_indice(fake, root=corpus)
    primo = indice.chunks.iloc[0]
    gia_presente = Chunk(id=primo['id'], fonte=primo['fonte'],
                         sezione=primo['sezione'], testo='duplicato')
    with pytest.raises(ValueError, match='duplicati'):
        indice.aggiungi([gia_presente], fake.embed(['duplicato']))


def test_errore_se_modello_diverso(corpus, fake):
    indice = costruisci_indice(fake, root=corpus)
    indice.modello_embedding = 'bge-m3'
    altro = FakeLLM(['ok'])
    altro.embedding_model = 'nomic-embed-text'
    with pytest.raises(ValueError, match='ricostruisci'):
        cerca_documenti('ondate', client=altro, indice=indice)


def test_domanda_vuota(corpus, fake):
    with pytest.raises(ValueError):
        cerca_documenti('   ', client=fake, indice=costruisci_indice(fake, root=corpus))


def test_formatta_contesto_contiene_fonte_e_sezione(corpus, fake):
    indice = costruisci_indice(fake, root=corpus)
    risultati = cerca_documenti('stazioni ARPA', k=2, client=fake, indice=indice)
    contesto = formatta_contesto(risultati)
    assert contesto.startswith(f'[{risultati[0]["fonte"]} — {risultati[0]["sezione"]}]')
    assert '[docs/pages/data-sources.md — ARPA Piemonte]' in contesto
    assert risultati[1]['testo'].strip() in contesto
    assert formatta_contesto([]) == ''


def test_build_senza_ollama_esce_con_messaggio(monkeypatch, capsys):
    from src.chatbot import build_knowledge_base

    class SenzaOllama:
        embedding_model = 'bge-m3'

        def embed(self, testi):
            raise LLMNonDisponibile('Il server Ollama non risponde.')

    monkeypatch.setattr(build_knowledge_base, 'crea_client_embedding', lambda: SenzaOllama())
    assert build_knowledge_base.main() == 1
    errore = capsys.readouterr().err
    assert 'Il server Ollama non risponde.' in errore
    assert 'Traceback' not in errore


# --- Indice reale (cancello F4) ----------------------------------------------

# Domanda → parole che il chunk giusto deve contenere (tutte, senza maiuscole).
DOMANDE_DI_CONTROLLO = [
    ('Perché Open-Meteo e ARPA danno temperature diverse?', ('rianalisi', 'arpa')),
    ("Cos'è un'ondata di calore?", ('3 giorni', '35 °c')),
    ('Cosa significa il cluster 2?', ('cluster 2', 'pianura')),
    ("Cos'è l'indice di Moran?", ('moran', 'vicin')),
    ('Quanti comuni sono coperti dai dati?', ('599', '1180')),
    ('Il chatbot può prevedere il caldo di domani?', ('previsioni', 'allert')),
]
MANIFEST_REALE = rag.cartella_indice() / 'manifest.json'


def _chunk_giusto(risultato: dict, parole: tuple[str, ...]) -> bool:
    testo = risultato['testo'].lower()
    return all(p in testo for p in parole)


@pytest.mark.skipif(not MANIFEST_REALE.exists(), reason='indice reale non costruito')
def test_indice_reale_domande_di_controllo():
    client = OllamaClient()
    try:
        client.embed(['prova'])
    except LLMNonDisponibile as errore:
        pytest.skip(f'Ollama non risponde: {errore}')
    indice = IndiceVettoriale.carica(rag.cartella_indice())
    esiti = []
    for domanda, parole in DOMANDE_DI_CONTROLLO:
        primi_tre = cerca_documenti(domanda, k=3, client=client, indice=indice)
        esiti.append(any(_chunk_giusto(r, parole) for r in primi_tre))
    assert sum(esiti) >= 5, f'Domande riuscite: {sum(esiti)}/6 → {esiti}'
