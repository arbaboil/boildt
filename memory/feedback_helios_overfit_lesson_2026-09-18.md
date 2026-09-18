---
name: Helios overfit lesson — fitness must penalize inactive folds
description: GA v1 gamed median-Calmar by firing in only 2/5 folds; enforce active-fold coverage
type: feedback
---

**Rule.** A GA fitness function computed only over folds where trades fire is exploitable — the search will collapse to parameters that only fire in the easy folds. Always require a coverage threshold and a minimum aggregate trade count before Calmar/Sharpe is even computed.

**Why.** First HELIOS GA run (`bot_v1_seed42.json`) achieved fitness +44 by producing 12 trades total across 2 of 5 folds. Median Calmar was misleadingly high because the 3 empty folds contributed nothing. Zero honesty.

**How to apply.** Every GA fitness for a rare-signal strategy must include:
1. Minimum active-fold fraction (Helios uses 0.8)
2. Minimum aggregate trade count (Helios uses 30)
3. Coverage penalty per missing fold (Helios uses -8 per missing fold)
4. Aggregate metric = MIN or worst-fold, not median (median hides sparsity)

Also: `MIN_TRADES_PER_FOLD` should be at least 3, else fold-Calmar is dominated by a single trade's PnL.

Applies to all future FAR bots (Argus, Sable, Rook, Knox) that use fold-aggregated fitness.
