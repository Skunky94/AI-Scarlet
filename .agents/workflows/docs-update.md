---
description: Checklist per aggiornare tutta la documentazione del progetto dopo una modifica
---

# Aggiornamento Documentazione

Dopo qualsiasi modifica architetturale, nuova feature, o cambiamento importante, esegui questa checklist:

## 1. Changelog
- Apri `docs/changelog.md`
- Aggiungi una entry datata sotto la sezione corrente con `### Added`, `### Changed`, o `### Fixed`

## 2. Roadmap
- Apri `docs/roadmap.md`
- Marca come `[x]` gli item completati
- Marca come `[/]` quelli in corso
- Aggiungi nuovi item se necessario

## 3. Indice
- Apri `index.md`
- Verifica che ogni file in `docs/` sia linkato
- Verifica che i link funzionino e le descrizioni siano corrette

## 4. Riferimenti Tecnici
- Se hai modificato configurazioni di un componente (Letta, MiniMax, Ollama), aggiorna il relativo file in `docs/letta/` o `docs/modelli/`

## 5. AI Rules
- Se l'architettura o lo stack tecnologico e' cambiato, aggiorna la sezione 0 di `AI_DEVELOPMENT_RULES.md`

## 6. Cleanup
- Elimina script temporanei/debug da `scripts/`
- Mantieni solo codice di produzione o utility riutilizzabili
