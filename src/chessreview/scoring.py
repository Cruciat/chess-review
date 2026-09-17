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
from typing import Sequence

from .engine import Evaluation

#: Pendenza della curva che converte centipawn in probabilità di vittoria.
WIN_PROBABILITY_K = 0.00368208

#: Costanti della curva di accuratezza, sempre di Lichess.
ACCURACY_A = 103.1668
ACCURACY_B = 0.04354
ACCURACY_C = 3.1669

#: Limiti al peso di una mossa nella media pesata sulla volatilità:
#: sotto 0,5 una posizione immobile non conterebbe quasi nulla, sopra 12
#: un solo momento caotico dominerebbe la partita.
VOLATILITY_MIN = 0.5
VOLATILITY_MAX = 12.0


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


def game_accuracy(
    white_win_percents: Sequence[float],
    drops: Sequence[float],
    white_moves: Sequence[bool],
) -> tuple[float, float]:
    """
    Accuratezza di bianco e nero in una partita, col metodo di Lichess.

    Una media aritmetica delle accuratezze delle mosse è troppo indulgente:
    trenta mosse quasi perfette annegano un errore che ha deciso la partita.
    Lichess combina due correzioni, e il risultato è la media delle due.

    1. Media pesata sulla volatilità: ogni mossa pesa quanto è agitata la
       partita intorno a lei, cioè la deviazione standard della win% in una
       finestra di posizioni. Sbagliare in un momento critico conta di più
       che sbagliare in una posizione tranquilla.
    2. Media armonica: è dominata dai valori bassi, quindi un blunder abbassa
       il risultato molto più di quanto una mossa perfetta lo alzi.

    `white_win_percents` è la win% del bianco nella posizione iniziale e dopo
    ogni mossa (una posizione in più delle mosse). `drops` è la perdita di
    ogni mossa dal punto di vista di chi l'ha giocata, `white_moves` dice se
    l'ha giocata il bianco. Un colore senza mosse vale 100.
    """
    n = len(drops)
    if len(white_win_percents) != n + 1 or len(white_moves) != n:
        raise ValueError("Servono una win% per posizione e una perdita e un colore per mossa")
    if n == 0:
        return 100.0, 100.0

    # Finestre come in Lichess: larghe un decimo della partita, fra 2 e 8
    # posizioni; le prime mosse riusano la prima finestra, così ogni mossa
    # ne ha una.
    size = max(2, min(8, len(white_win_percents) // 10))
    first = list(white_win_percents[:size])
    sliding = [
        list(white_win_percents[i : i + size]) for i in range(len(white_win_percents) - size + 1)
    ]
    windows = ([first] * (size - 2) + sliding)[:n]
    weights = [min(VOLATILITY_MAX, max(VOLATILITY_MIN, _stdev(w))) for w in windows]

    result: list[float] = []
    for color in (True, False):
        pairs = [
            (move_accuracy(drop), weight)
            for drop, weight, is_white in zip(drops, weights, white_moves)
            if is_white is color
        ]
        if not pairs:
            result.append(100.0)
            continue
        weighted = sum(a * w for a, w in pairs) / sum(w for _, w in pairs)
        # Un'accuratezza zero renderebbe infinita la somma dei reciproci:
        # si limita a 1, che per la media armonica è già il caso peggiore.
        harmonic = len(pairs) / sum(1.0 / max(a, 1.0) for a, _ in pairs)
        result.append((weighted + harmonic) / 2.0)

    return result[0], result[1]


def _stdev(values: Sequence[float]) -> float:
    """Deviazione standard della popolazione."""
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def average_centipawn_loss(losses: list[int]) -> float:
    """
    ACPL, la metrica classica. La teniamo perché è quella che trovi
    ovunque e permette il confronto con altri strumenti, ma il giudizio
    sulle mosse si basa sulla probabilità di vittoria.
    """
    if not losses:
        return 0.0
    return sum(losses) / len(losses)
