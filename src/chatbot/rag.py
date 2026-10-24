"""RAG del chatbot: corpus, chunking, indice vettoriale numpy e ricerca.

Segue lo schema della lezione 21-03 (indicizzazione → recupero → generazione):
qui ci sono le prime due fasi. La generazione la fa l'agente "Ricercatore",
che riceve il contesto preparato da ``formatta_contesto()`` e cita le fonti.

**Perché non ChromaDB.** Sul PC di sviluppo Smart App Control di Windows
blocca le librerie compilate di ChromaDB (``orjson``) e di
sentence-transformers (``torch``, ``regex``). L'indice è quindi scritto a
mano con la stessa interfaccia concettuale di una collection ChromaDB
(lezione 21-02): ``aggiungi()``, ``cerca()``, ``salva()``, ``carica()``. Gli
embedding stanno in una matrice numpy, la similarità è
``sklearn.metrics.pairwise.cosine_similarity`` (lezione 19). Con qualche
centinaio di chunk la ricerca esatta richiede pochi millisecondi.

Gli embedding arrivano sempre da un client di ``llm_client`` (``embed()``):
in produzione Ollama con ``bge-m3``, nei test ``FakeLLM`` (bag-of-words).
Il modulo non dipende da Streamlit.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from src.chatbot.llm_client import ClientLLM, crea_client
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

RADICE_PROGETTO = Path(__file__).resolve().parents[2]

FILE_EMBEDDINGS = 'embeddings.npy'
FILE_CHUNKS = 'chunks.parquet'
FILE_MANIFEST = 'manifest.json'
COMANDO_BUILD = 'python -m src.chatbot.build_knowledge_base'

CHUNK_WORDS_PREDEFINITO = 300
OVERLAP_WORDS_PREDEFINITO = 50
TOP_K_PREDEFINITO = 4
MIN_PAROLE_CHUNK = 8
SEZIONE_INIZIALE = 'Introduzione'

# Fonti del corpus, relative alla radice del progetto (niente PDF).
PATTERN_CORPUS = (
    'wiki/pages/*.md',
    'paper/references/README.md',
    'data/knowledge_base/*.md',
)

# Pagine operative escluse: sono liste di lavoro per gli agenti di sviluppo
# (task, dipendenze, comandi di verifica, ondate della pipeline d'esame), non
# spiegazioni per i cittadini. Contengono molte parole chiave del progetto
# ("ondate", "cluster", "RAG", "ARPA") e finirebbero spesso in cima al
# retrieval al posto delle pagine che spiegano davvero i concetti.
FONTI_ESCLUSE = frozenset({
    'wiki/pages/todo-agenti.md',
    'wiki/pages/roadmap-esame.md',
})
# `paper/manoscritto.md` non fa parte del corpus: è una bozza dell'articolo
# scientifico, fuori dall'ambito d'esame, e contiene numeri di versioni
# precedenti del campione (es. 44 o 177 comuni) che il Ricercatore potrebbe
# citare al posto di quelli attuali. La bibliografia (`paper/references/README.md`)
# resta inclusa.

_RE_COMMENTO_HTML = re.compile(r'<!--.*?-->', re.DOTALL)
_RE_TITOLO = re.compile(r'^(#{1,3})\s+(.+?)\s*#*\s*$')
_RE_RECINTO_CODICE = re.compile(r'^\s*(```|~~~)')


@dataclass(frozen=True)
class Documento:
    """Un file del corpus: path relativo con ``/``, testo e hash SHA-256."""

    fonte: str
    testo: str
    sha256: str

    @property
    def titolo(self) -> str:
        """Primo titolo ``#`` del documento, oppure il nome del file."""
        for riga in self.testo.splitlines():
            trovato = _RE_TITOLO.match(riga)
            if trovato and len(trovato.group(1)) == 1:
                return _pulisci_titolo(trovato.group(2))
        return Path(self.fonte).stem


@dataclass(frozen=True)
class Chunk:
    """Pezzo di documento da indicizzare, con i metadati per citare la fonte."""

    id: str
    fonte: str
    sezione: str
    testo: str


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

def _radice(root: str | Path | None) -> Path:
    """Radice del corpus: quella indicata oppure la radice del progetto."""
    return Path(root).resolve() if root is not None else RADICE_PROGETTO


def _percorso_progetto(percorso: str | Path) -> Path:
    """Risolve un percorso relativo rispetto alla radice del progetto."""
    percorso = Path(percorso)
    return percorso if percorso.is_absolute() else (RADICE_PROGETTO / percorso).resolve()


def leggi_corpus(root: str | Path | None = None) -> list[Documento]:
    """Legge i documenti Markdown del corpus RAG.

    Fonti: ``wiki/pages/*.md``,
    ``paper/references/README.md`` e ``data/knowledge_base/*.md`` (se la
    cartella esiste). Sono escluse le pagine operative in ``FONTI_ESCLUSE``
    (``todo-agenti.md``, ``roadmap-esame.md``): servono agli agenti che
    sviluppano il progetto, non a rispondere agli utenti, e confonderebbero
    il retrieval perché ripetono tutte le parole chiave senza spiegarle.
    I file vuoti vengono saltati.
    """
    radice = _radice(root)
    documenti: list[Documento] = []
    visti: set[str] = set()
    for pattern in PATTERN_CORPUS:
        for percorso in sorted(radice.glob(pattern)):
            fonte = percorso.relative_to(radice).as_posix()
            if fonte in FONTI_ESCLUSE or fonte in visti or not percorso.is_file():
                continue
            contenuto = percorso.read_bytes()
            testo = contenuto.decode('utf-8')
            if not testo.strip():
                continue
            visti.add(fonte)
            documenti.append(Documento(
                fonte=fonte,
                testo=testo,
                sha256=hashlib.sha256(contenuto).hexdigest(),
            ))
    logger.info(f'Corpus RAG: {len(documenti)} documenti letti da {radice}')
    return documenti


# ---------------------------------------------------------------------------
# Chunking (lezione 21-03)
# ---------------------------------------------------------------------------

def _pulisci_titolo(titolo: str) -> str:
    """Toglie la formattazione Markdown (``**``, `` ` ``) da un titolo."""
    return re.sub(r'\s+', ' ', titolo.replace('*', '').replace('`', '')).strip()


def _sezioni(testo: str) -> list[tuple[str, str, list[str]]]:
    """Divide il testo per titoli ``#``/``##``/``###``.

    Restituisce ``(titolo pulito, riga del titolo, righe del corpo)``. I
    titoli dentro i blocchi di codice (es. commenti ``# ...`` in YAML) non
    contano. Il testo prima del primo titolo forma la sezione iniziale.
    """
    sezioni: list[tuple[str, str, list[str]]] = []
    titolo, riga_titolo, corpo = SEZIONE_INIZIALE, '', []
    in_codice = False
    for riga in testo.splitlines():
        if _RE_RECINTO_CODICE.match(riga):
            in_codice = not in_codice
        trovato = None if in_codice else _RE_TITOLO.match(riga)
        if trovato:
            sezioni.append((titolo, riga_titolo, corpo))
            titolo, riga_titolo, corpo = _pulisci_titolo(trovato.group(2)), riga.strip(), []
        else:
            corpo.append(riga)
    sezioni.append((titolo, riga_titolo, corpo))
    return sezioni


def _finestre(parole: list[str], chunk_words: int, overlap_words: int) -> list[list[str]]:
    """Finestre di ``chunk_words`` parole che si sovrappongono di ``overlap_words``."""
    if len(parole) <= chunk_words:
        return [parole]
    passo = chunk_words - overlap_words
    finestre = []
    for inizio in range(0, len(parole), passo):
        finestre.append(parole[inizio:inizio + chunk_words])
        if inizio + chunk_words >= len(parole):
            break
    return finestre


def spezza_in_chunk(
    testo: str,
    fonte: str,
    chunk_words: int = CHUNK_WORDS_PREDEFINITO,
    overlap_words: int = OVERLAP_WORDS_PREDEFINITO,
) -> list[Chunk]:
    """Spezza un documento Markdown in chunk con metadati.

    1. Rimuove i commenti HTML ``<!-- ... -->``.
    2. Divide per titoli ``#``, ``##``, ``###``: la riga del titolo resta in
       testa al chunk e il titolo pulito va nei metadati (``sezione``).
    3. Le sezioni più lunghe di ``chunk_words`` parole diventano finestre di
       parole con ``overlap_words`` parole in comune tra finestre vicine
       (lezione 21-03); ogni finestra ripete la riga del titolo, così resta
       comprensibile anche da sola.
    4. Salta le sezioni quasi vuote (meno di ``MIN_PAROLE_CHUNK`` parole oltre
       al titolo, per esempio un titolo seguito subito da un sottotitolo).

    L'``id`` è ``fonte#indice`` (indice progressivo nel documento): a parità
    di testo e parametri è stabile tra una ricostruzione e l'altra.
    """
    if chunk_words <= 0:
        raise ValueError('chunk_words deve essere positivo')
    if not 0 <= overlap_words < chunk_words:
        raise ValueError('overlap_words deve essere tra 0 e chunk_words - 1')

    fonte = fonte.replace('\\', '/')
    pulito = _RE_COMMENTO_HTML.sub('', testo)
    chunks: list[Chunk] = []
    for titolo, riga_titolo, righe in _sezioni(pulito):
        corpo = '\n'.join(righe).strip()
        parole = corpo.split()
        if len(parole) < MIN_PAROLE_CHUNK:
            continue
        if len(parole) <= chunk_words:
            pezzi = [corpo]
        else:
            pezzi = [' '.join(f) for f in _finestre(parole, chunk_words, overlap_words)]
        for pezzo in pezzi:
            testo_chunk = f'{riga_titolo}\n{pezzo}' if riga_titolo else pezzo
            chunks.append(Chunk(
                id=f'{fonte}#{len(chunks)}',
                fonte=fonte,
                sezione=titolo,
                testo=testo_chunk,
            ))
    return chunks


def testo_per_embedding(chunk: Chunk, titolo_documento: str = '') -> str:
    """Testo da passare al modello di embedding.

    Aggiunge davanti il titolo del documento: una sezione breve come
    "Limiti" è ambigua da sola, "Machine Learning — Limiti" no.
    """
    if titolo_documento and titolo_documento != chunk.sezione:
        return f'{titolo_documento} — {chunk.testo}'
    return chunk.testo


# ---------------------------------------------------------------------------
# Indice vettoriale (interfaccia simile a una collection ChromaDB)
# ---------------------------------------------------------------------------

def _normalizza(matrice: np.ndarray) -> np.ndarray:
    """Normalizza ogni riga a norma L2 = 1 (le righe nulle restano nulle)."""
    norme = np.linalg.norm(matrice, axis=1, keepdims=True)
    norme[norme == 0] = 1.0
    return (matrice / norme).astype(np.float32)


class IndiceVettoriale:
    """Indice vettoriale in memoria: matrice numpy + tabella dei chunk."""

    COLONNE = ('id', 'fonte', 'sezione', 'testo')

    def __init__(self, modello_embedding: str = '', dimensione: int | None = None) -> None:
        """Crea un indice vuoto; ``dimensione`` si fissa al primo ``aggiungi``."""
        self.modello_embedding = modello_embedding
        self.dimensione = dimensione
        self.hash_fonti: dict[str, str] = {}
        self._vettori = np.zeros((0, dimensione or 0), dtype=np.float32)
        self._chunks: list[dict] = []

    def __len__(self) -> int:
        """Numero di chunk nell'indice."""
        return len(self._chunks)

    @property
    def chunks(self) -> pd.DataFrame:
        """Copia della tabella dei chunk (``id``, ``fonte``, ``sezione``, ``testo``)."""
        return pd.DataFrame(self._chunks, columns=list(self.COLONNE))

    def _controlla_dimensione(self, dimensione: int) -> None:
        """Solleva ``ValueError`` se ``dimensione`` non è quella dell'indice."""
        if self.dimensione is not None and dimensione != self.dimensione:
            raise ValueError(
                f'Dimensione dei vettori incoerente: {dimensione} invece di {self.dimensione}. '
                "Usa lo stesso modello di embedding dell'indice "
                f'({self.modello_embedding or "sconosciuto"}) oppure ricostruiscilo con '
                f'`{COMANDO_BUILD}`.'
            )

    def aggiungi(self, chunks: list[Chunk], vettori) -> None:
        """Aggiunge i chunk con i loro vettori (uno per chunk, stessa dimensione)."""
        matrice = np.asarray(vettori, dtype=np.float32)
        if not chunks:
            return
        if matrice.ndim != 2 or matrice.shape[0] != len(chunks):
            raise ValueError(
                f'Servono {len(chunks)} vettori (uno per chunk), ricevuta forma {matrice.shape}'
            )
        self._controlla_dimensione(matrice.shape[1])
        id_presenti = {c['id'] for c in self._chunks}
        nuovi_id = [c.id for c in chunks]
        doppi = sorted((id_presenti & set(nuovi_id)) | {i for i in nuovi_id if nuovi_id.count(i) > 1})
        if doppi:
            raise ValueError(f'Id di chunk duplicati: {", ".join(doppi[:5])}')

        self.dimensione = int(matrice.shape[1])
        if self._vettori.shape[1] != self.dimensione:
            self._vettori = np.zeros((0, self.dimensione), dtype=np.float32)
        self._vettori = np.vstack([self._vettori, _normalizza(matrice)])
        self._chunks.extend(
            {'id': c.id, 'fonte': c.fonte, 'sezione': c.sezione, 'testo': c.testo} for c in chunks
        )

    def cerca(self, vettore_domanda, k: int = TOP_K_PREDEFINITO) -> list[dict]:
        """I ``k`` chunk più simili al vettore, dal più simile al meno simile.

        Ogni risultato è un dizionario con ``testo``, ``fonte``, ``sezione``,
        ``similarita`` (coseno, tra −1 e 1) e ``id``.
        """
        if k <= 0:
            raise ValueError('k deve essere positivo')
        domanda = np.asarray(vettore_domanda, dtype=np.float32).reshape(1, -1)
        self._controlla_dimensione(domanda.shape[1])
        if not self._chunks:
            return []
        similarita = cosine_similarity(domanda, self._vettori)[0]
        migliori = np.argsort(-similarita, kind='stable')[:k]
        return [
            {
                'testo': self._chunks[i]['testo'],
                'fonte': self._chunks[i]['fonte'],
                'sezione': self._chunks[i]['sezione'],
                'similarita': float(similarita[i]),
                'id': self._chunks[i]['id'],
            }
            for i in migliori
        ]

    def salva(self, cartella: str | Path, nome_indice: str = '') -> Path:
        """Salva ``embeddings.npy`` (float32), ``chunks.parquet`` e ``manifest.json``."""
        cartella = Path(cartella)
        cartella.mkdir(parents=True, exist_ok=True)
        np.save(cartella / FILE_EMBEDDINGS, self._vettori.astype(np.float32))
        self.chunks.to_parquet(cartella / FILE_CHUNKS, index=False)
        chunk_per_fonte = self.chunks['fonte'].value_counts().sort_index()
        manifest = {
            'nome_indice': nome_indice,
            'modello_embedding': self.modello_embedding,
            'dimensione': self.dimensione,
            'n_chunk': len(self),
            'creato_il_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'chunk_per_fonte': {f: int(n) for f, n in chunk_per_fonte.items()},
            'hash_fonti_sha256': dict(sorted(self.hash_fonti.items())),
        }
        (cartella / FILE_MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        logger.info(f'Indice RAG salvato in {cartella} ({len(self)} chunk)')
        return cartella

    @classmethod
    def carica(cls, cartella: str | Path) -> 'IndiceVettoriale':
        """Ricarica un indice salvato; errore chiaro se manca o è incoerente."""
        cartella = Path(cartella)
        mancanti = [
            nome for nome in (FILE_EMBEDDINGS, FILE_CHUNKS, FILE_MANIFEST)
            if not (cartella / nome).is_file()
        ]
        if mancanti:
            raise FileNotFoundError(
                f'Indice RAG non trovato in {cartella} (mancano: {", ".join(mancanti)}). '
                f'Costruiscilo con `{COMANDO_BUILD}`.'
            )
        manifest = json.loads((cartella / FILE_MANIFEST).read_text(encoding='utf-8'))
        vettori = np.load(cartella / FILE_EMBEDDINGS).astype(np.float32)
        tabella = pd.read_parquet(cartella / FILE_CHUNKS)

        dimensione = manifest.get('dimensione')
        if vettori.ndim != 2 or len(vettori) != len(tabella) or (
            len(tabella) and dimensione is not None and vettori.shape[1] != dimensione
        ):
            raise ValueError(
                f'Indice RAG in {cartella} incoerente (vettori {vettori.shape}, '
                f'{len(tabella)} chunk, dimensione dichiarata {dimensione}). '
                f'Ricostruiscilo con `{COMANDO_BUILD}`.'
            )

        indice = cls(manifest.get('modello_embedding', ''), dimensione)
        indice.hash_fonti = dict(manifest.get('hash_fonti_sha256', {}))
        indice._vettori = vettori
        indice._chunks = tabella.loc[:, list(cls.COLONNE)].to_dict('records')
        return indice


# ---------------------------------------------------------------------------
# Costruzione e ricerca
# ---------------------------------------------------------------------------

def cartella_indice() -> Path:
    """Cartella dell'indice (``chatbot.rag.persist_dir``), assoluta."""
    return _percorso_progetto(str(config.get('chatbot.rag.persist_dir', './data/vector_store')))


def nome_indice() -> str:
    """Nome dell'indice (``chatbot.rag.index_name``), scritto nel manifest."""
    return str(config.get('chatbot.rag.index_name', 'heatwave_docs'))


def crea_client_embedding() -> ClientLLM:
    """Client per gli embedding: sempre Ollama (o ``FakeLLM`` con ``HEATWAVE_FAKE_LLM=1``).

    Anche se la chat usa Anthropic, gli embedding del progetto restano su
    Ollama (``bge-m3``), quindi qui il provider è fissato.
    """
    return crea_client('ollama')


def _nome_modello(client: ClientLLM) -> str:
    """Nome del modello di embedding del client (o il nome della classe)."""
    return str(getattr(client, 'embedding_model', '') or type(client).__name__)


def costruisci_indice(
    client: ClientLLM,
    root: str | Path | None = None,
    chunk_words: int | None = None,
    overlap_words: int | None = None,
) -> IndiceVettoriale:
    """Legge il corpus, lo spezza in chunk e calcola gli embedding con ``client``.

    I parametri mancanti si leggono da ``chatbot.rag`` in ``config.yaml``.
    Solleva ``LLMNonDisponibile`` se il client non riesce a calcolare gli embedding.
    """
    chunk_words = int(chunk_words or config.get('chatbot.rag.chunk_words', CHUNK_WORDS_PREDEFINITO))
    if overlap_words is None:
        overlap_words = int(config.get('chatbot.rag.overlap_words', OVERLAP_WORDS_PREDEFINITO))

    indice = IndiceVettoriale(modello_embedding=_nome_modello(client))
    for documento in leggi_corpus(root):
        chunks = spezza_in_chunk(documento.testo, documento.fonte, chunk_words, overlap_words)
        indice.hash_fonti[documento.fonte] = documento.sha256
        if not chunks:
            continue
        testi = [testo_per_embedding(c, documento.titolo) for c in chunks]
        indice.aggiungi(chunks, client.embed(testi))
        logger.info(f'{documento.fonte}: {len(chunks)} chunk indicizzati')
    return indice


_CACHE_INDICI: dict[Path, IndiceVettoriale] = {}


def carica_indice(cartella: str | Path | None = None, ricarica: bool = False) -> IndiceVettoriale:
    """Carica l'indice una volta sola e lo riusa (cache a livello di modulo)."""
    percorso = _percorso_progetto(cartella) if cartella is not None else cartella_indice()
    if ricarica or percorso not in _CACHE_INDICI:
        _CACHE_INDICI[percorso] = IndiceVettoriale.carica(percorso)
    return _CACHE_INDICI[percorso]


def svuota_cache() -> None:
    """Dimentica gli indici caricati (per esempio dopo una ricostruzione)."""
    _CACHE_INDICI.clear()


def cerca_documenti(
    domanda: str,
    k: int | None = None,
    client: ClientLLM | None = None,
    indice: IndiceVettoriale | None = None,
) -> list[dict]:
    """Recupera i ``k`` chunk più pertinenti alla domanda (come ``cerca_contesto``, lezione 21-03).

    L'embedding della domanda va calcolato con lo stesso modello usato per
    l'indice: se il client dichiara un modello diverso da quello del
    manifest si solleva ``ValueError``.

    Returns:
        Lista di dizionari ``testo``, ``fonte``, ``sezione``, ``similarita``, ``id``.
    """
    if not domanda or not domanda.strip():
        raise ValueError('La domanda è vuota')
    k = int(k or config.get('chatbot.rag.top_k', TOP_K_PREDEFINITO))
    indice = indice if indice is not None else carica_indice()
    client = client if client is not None else crea_client_embedding()

    modello_client = getattr(client, 'embedding_model', None)
    if modello_client and indice.modello_embedding and modello_client != indice.modello_embedding:
        raise ValueError(
            f'Indice costruito con "{indice.modello_embedding}" ma il client usa '
            f'"{modello_client}": ricostruisci l\'indice con `{COMANDO_BUILD}`.'
        )
    vettore = client.embed([domanda.strip()])[0]
    return indice.cerca(vettore, k)


def formatta_contesto(risultati: list[dict]) -> str:
    """Prepara il contesto per l'LLM: ogni chunk preceduto da ``[fonte — sezione]``.

    Il Ricercatore riceve questo testo nel prompt (come ``rispondi_con_rag``
    della lezione 21-03) e cita le fonti con la stessa etichetta. Con nessun
    risultato restituisce una stringa vuota.
    """
    blocchi = [
        f'[{r["fonte"]} — {r["sezione"]}]\n{str(r["testo"]).strip()}' for r in risultati
    ]
    return '\n\n'.join(blocchi)
