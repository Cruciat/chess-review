"""
Da valutazione a probabilità di vittoria, e da lì all'accuratezza.

Il motivo per cui non si usano direttamente i centipawn: perdere 100
centipawn quando sei a +900 non cambia nulla, perderli quando sei a 0.0
può costarti la partita. La stessa perdita in centipawn ha significati
opposti, mentre la probabilità di vittoria è confrontabile ovunque.

Le formule sono quelle pubblicate da Lichess, ricavate da partite reali.

CONVENZIONE DEL PUNTO DI VISTA, valida per tutto il modulo: ogni
Evaluation che arriva qui è già orientata su CHI HA MOSSO. Chi chiama
si occupa di invertire quella dopo la mossa, che Stockfish restituisce
dal punto di vista dell'avversario. Farlo anche qui la invertirebbe
due volte, ed è esattamente il bug che questa nota esiste per evitare.
"""

from __future__ import annotations

import math

from .engine import Evaluation

#: Pendenza della curva che converte centipawn in probabilità di vittoria.
WIN_PROBABILITY_K = 0.00368208

#: Costanti della curva di accuratezza, sempre di Lichess.
ACCURACY_A = 103.1668
ACCURACY_B = 0.04354
ACCURACY_C = 3.1669


def win_percent(evaluation: Evaluation) -> float:
    """
    Probabilità di vittoria di chi deve muovere, da 0 a 100.

    Un matto non passa per la formula: è una certezza, non una stima.
    """
    if evaluation.mate is not None:
        return 100.0 if evaluation.mate > 0 else 0.0

    cp = evaluation.cp if evaluation.cp is not None else 0
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-WIN_PROBABILITY_K * cp)) - 1.0)


def win_percent_lost(before: Evaluation, after: Evaluation) -> float:
    """
    Punti percentuali di probabilità di vittoria buttati via da una mossa.

    ENTRAMBE le valutazioni devono essere già orientate su chi ha mosso.
    `after` non viene invertita qui: se lo facessimo, e chi chiama l'ha
    già orientata, il punto di vista si ribalterebbe due volte e il
    risultato sarebbe (probabilità prima + probabilità dopo − 100),
    cioè un numero privo di senso che cresce con la forza della posizione.

    Il risultato non è mai negativo: se hai trovato una mossa migliore
    di quella che il motore riteneva migliore, hai giocato in modo
    ottimo, non hai guadagnato probabilità dal nulla.
    """
    return max(0.0, win_percent(before) - win_percent(after))


def move_accuracy(win_percent_drop: float) -> float:
    """
    Accuratezza di una singola mossa, da 0 a 100.

    Una perdita nulla dà circa 100, una perdita grande tende a zero.
    """
    raw = ACCURACY_A * math.exp(-ACCURACY_B * max(0.0, win_percent_drop)) - ACCURACY_C
    return max(0.0, min(100.0, raw))


def game_accuracy(drops: list[float]) -> float:
    """
    Accuratezza di una partita: media delle accuratezze delle mosse.

    Senza mosse restituisce 100: non avere giocato non è un errore.
    """
    if not drops:
        return 100.0
    return sum(move_accuracy(d) for d in drops) / len(drops)


def average_centipawn_loss(losses: list[int]) -> float:
    """
    ACPL, la metrica classica. La teniamo perché è quella che trovi
    ovunque e permette il confronto con altri strumenti, ma il giudizio
    sulle mosse si basa sulla probabilità di vittoria.
    """
    if not losses:
        return 0.0
    return sum(losses) / len(losses)
