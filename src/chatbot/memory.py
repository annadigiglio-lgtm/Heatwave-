"""Memoria conversazionale del chatbot: finestra scorrevole (lezione 15-03).

L'LLM non ricorda nulla tra una chiamata e l'altra: la "memoria" è la lista
dei messaggi precedenti che rimandiamo ogni volta. Per non allungare il
prompt (su CPU ogni token in più costa tempo) si tengono solo gli ultimi
``finestra`` scambi, cioè coppie domanda dell'utente / risposta
dell'assistente; ``finestra`` di default è ``chatbot.memory_window``.

La memoria vive solo in ``st.session_state`` (``to_list()`` / ``from_list()``)
e non viene mai salvata su disco (wiki/pages/etica-e-limiti.md). Il riassunto
automatico degli scambi vecchi (lezione 15-04) non serve: le domande del
chatbot sono brevi e quasi indipendenti tra loro.
"""

from __future__ import annotations

from src.utils.config import config

FINESTRA_PREDEFINITA = 6
RUOLI_AMMESSI = ('user', 'assistant')


class MemoriaConversazione:
    """Storia della chat con finestra scorrevole sugli ultimi ``finestra`` scambi."""

    def __init__(self, finestra: int | None = None) -> None:
        """Crea una memoria vuota; ``finestra`` deve essere un intero >= 0."""
        if finestra is None:
            finestra = int(config.get('chatbot.memory_window', FINESTRA_PREDEFINITA))
        if int(finestra) < 0:
            raise ValueError('La finestra della memoria deve essere >= 0')
        self.finestra = int(finestra)
        self._messaggi: list[dict] = []

    def aggiungi(self, ruolo: str, testo: str) -> None:
        """Aggiunge un messaggio (``user`` o ``assistant``) alla storia."""
        if ruolo not in RUOLI_AMMESSI:
            raise ValueError(f'Ruolo "{ruolo}" non ammesso: usa {" o ".join(RUOLI_AMMESSI)}')
        self._messaggi.append({'role': ruolo, 'content': str(testo)})

    def messaggi(self) -> list[dict]:
        """Ultimi ``finestra`` scambi nel formato ``{"role", "content"}`` per l'LLM.

        La finestra parte sempre da un messaggio dell'utente, così l'LLM non
        riceve una risposta senza la sua domanda.
        """
        if self.finestra == 0:
            return []
        ultimi = self._messaggi[-2 * self.finestra:]
        while ultimi and ultimi[0]['role'] != 'user':
            ultimi = ultimi[1:]
        return [dict(m) for m in ultimi]

    def svuota(self) -> None:
        """Cancella la storia (pulsante "Nuova conversazione")."""
        self._messaggi.clear()

    def to_list(self) -> list[dict]:
        """Copia completa della storia, da salvare in ``st.session_state``."""
        return [dict(m) for m in self._messaggi]

    @classmethod
    def from_list(cls, messaggi: list[dict], finestra: int | None = None) -> 'MemoriaConversazione':
        """Ricostruisce la memoria da ``to_list()`` (ignora messaggi malformati)."""
        memoria = cls(finestra)
        for messaggio in messaggi or []:
            if isinstance(messaggio, dict) and messaggio.get('role') in RUOLI_AMMESSI:
                memoria.aggiungi(messaggio['role'], messaggio.get('content', ''))
        return memoria

    def __len__(self) -> int:
        return len(self._messaggi)
