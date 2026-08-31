"""Alignment tokenow po formie powierzchniowej (T-014, docs/07_TASKS.md).

Porownanie taggera z goldem EQTB nie idzie ``po indeksie``: CAMeL moze
rozbic albo skleic slowo ortograficzne. Needleman-Wunsch na sekwencjach
form powierzchniowych, koszt substytucji = znormalizowany Levenshtein
znakowy. Kolejnosc jest zachowana (to nie jest matching dwudzielny).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlignedPair:
    gold_index: int | None
    pred_index: int | None
    gold_surface: str
    pred_surface: str

    @property
    def is_match(self) -> bool:
        return self.gold_index is not None and self.pred_index is not None


def char_levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    prev = list(range(len(right) + 1))
    for i, lch in enumerate(left, start=1):
        curr = [i]
        for j, rch in enumerate(right, start=1):
            ins = curr[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (lch != rch)
            curr.append(min(ins, delete, sub))
        prev = curr
    return prev[-1]


def normalized_edit_cost(left: str, right: str) -> float:
    """0.0 = identyczne, 1.0 = calkowita zamiana. Pusty vs niepusty = 1.0."""
    denom = max(len(left), len(right), 1)
    return char_levenshtein(left, right) / denom


def align_surfaces(
    gold: list[str],
    pred: list[str],
    *,
    gap_cost: float = 1.0,
) -> list[AlignedPair]:
    """Needleman-Wunsch. ``gap_cost`` jest porownywalny z kosztem substytucji [0, 1]."""
    n_gold = len(gold)
    n_pred = len(pred)
    # dp[i][j] = koszt alignmentu gold[:i] z pred[:j]
    dp = [[0.0] * (n_pred + 1) for _ in range(n_gold + 1)]
    ptr = [[(0, 0)] * (n_pred + 1) for _ in range(n_gold + 1)]
    for i in range(1, n_gold + 1):
        dp[i][0] = i * gap_cost
        ptr[i][0] = (i - 1, 0)
    for j in range(1, n_pred + 1):
        dp[0][j] = j * gap_cost
        ptr[0][j] = (0, j - 1)

    for i in range(1, n_gold + 1):
        for j in range(1, n_pred + 1):
            diag = dp[i - 1][j - 1] + normalized_edit_cost(gold[i - 1], pred[j - 1])
            up = dp[i - 1][j] + gap_cost
            left = dp[i][j - 1] + gap_cost
            # Przy remisie: substytucja, potem gap w pred, potem gap w gold.
            _, _, origin = min(
                (diag, 0, (i - 1, j - 1)),
                (up, 1, (i - 1, j)),
                (left, 2, (i, j - 1)),
            )
            dp[i][j] = min(diag, up, left)
            ptr[i][j] = origin

    pairs: list[AlignedPair] = []
    i, j = n_gold, n_pred
    while i > 0 or j > 0:
        pi, pj = ptr[i][j]
        if pi == i - 1 and pj == j - 1:
            pairs.append(
                AlignedPair(
                    gold_index=i - 1,
                    pred_index=j - 1,
                    gold_surface=gold[i - 1],
                    pred_surface=pred[j - 1],
                )
            )
        elif pi == i - 1 and pj == j:
            pairs.append(
                AlignedPair(
                    gold_index=i - 1,
                    pred_index=None,
                    gold_surface=gold[i - 1],
                    pred_surface="",
                )
            )
        else:
            pairs.append(
                AlignedPair(
                    gold_index=None,
                    pred_index=j - 1,
                    gold_surface="",
                    pred_surface=pred[j - 1],
                )
            )
        i, j = pi, pj
    pairs.reverse()
    return pairs


def boundary_positions(segments: list[str]) -> set[int]:
    """Pozycje ciecia po sklejeniu segmentow, bez 0 i bez konca."""
    cuts: set[int] = set()
    cursor = 0
    for seg in segments[:-1]:
        cursor += len(seg)
        if cursor > 0:
            cuts.add(cursor)
    return cuts


def segmentation_f1(gold_segments: list[str], pred_segments: list[str]) -> float:
    gold_cuts = boundary_positions(gold_segments)
    pred_cuts = boundary_positions(pred_segments)
    if not gold_cuts and not pred_cuts:
        return 1.0
    if not pred_cuts or not gold_cuts:
        return 0.0
    overlap = len(gold_cuts & pred_cuts)
    precision = overlap / len(pred_cuts)
    recall = overlap / len(gold_cuts)
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)
