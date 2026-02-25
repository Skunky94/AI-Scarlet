# Regole di Sviluppo per Agenti AI (LLM)

Questo file contiene le direttive fondamentali che **tutti gli agenti AI (LLM) devono seguire** quando lavorano sulla stesura di codice o documentazione per il Progetto Scarlet. Lo scopo è prevenire il degrado architetturale (drift), mantenere la codebase pulita e assicurare che la documentazione funga da singola fonte di verità (Single Source of Truth - SSOT).

---

## 1. Documentazione come Base Singola di Verità (SSOT)
- **Mantieni l'Indice:** Qualsiasi nuovo modulo, documento o servizio creato deve essere linkato nel file `index.md` o nei sotto-indici in `docs/`. Non lasciare file orfani.
- **Aggiorna contestualmente:** **MAI** modificare la logica di sistema (es. cambiare come funziona l'Heartbeat o il modello PAD) senza aggiornare *immediatamente* la relativa documentazione in `docs/visione_architettura.md`. Esegui l'aggiornamento di documentazione e codice nello stesso prompt/pull request.
- **Aggiorna il Changelog:** Usa `docs/changelog.md` per segnare l'aggiunta di funzionalità principali. Evita un logging eccessivo di refactor minori, concentrati sulla logica e sulle architetture.

## 2. Principi di Architettura (Prevenire il Drift)
- **Nessuna Duplicazione:** Prima di creare funzioni di utility o strumenti, verifica accuratamente il sorgente (es. con `grep_search` o lettura moduli) per assicurarti che non esista già. Se esiste, migliorala; non scriverne un'altra simile.
- **Rispetta il Design HLLM:** Letta è il gestore della memoria. **Non** inventare file `.json` "passanti" o SQLite separati per salvare lo stato persistente dell'agente se questa informazione appartiene per competenza alla Core o all'Archival Memory di Letta.
- **Sincronizzazione di Stato (Code di Messaggi):** Per evitare Race Conditions tra LLM Cloud e LLM Locale, l'istanza Locale **NON** deve mai scrivere direttamente sul database di Letta. Deve obbligatoriamente pubblicare una "Memory Update Proposal" su un sistema di code (es. Redis/RabbitMQ) che l'istanza Core smaltirà serialmente.
- **Delega Hardware Corretta:** Istruisci sempre le funzioni pesanti per usare il Cloud LLM e le operazioni binarie/estrazioni semplici (es. embeddings, PAD Sentiment Analysis) per usare il server locale sulla tua RTX 4070 Ti (Ollama/Llama3). Disaccoppia la Sentiment Analysis dal loop principale Cloud per ottimizzare i token.

## 3. Pratiche di Scrittura Codice
- **Codice "Self-Documenting" e Docstring:** Usa Type Hints (`def function(param: type) -> type:`) per **ogni** singola funzione Python. Includi brevi docstring chiare sul *perché* (il ragionamento di design o business logic), non sul *cosa* (che dovrebbe essere autoevidente dal nome e dal tipo).
- **Clean Code & Modularity:** Niente file "monolite". Se un file supera le 300 linee o le 3 responsabilità, fai refactoring e separalo logicamente in nuovi moduli. Separa nettamente la logica del Modello (PAD), il Controller (Heartbeat) e le Viste/Integrazioni (Letta Tools).

## 4. Metodologia di Testing (No Mock Inutili)
- **Test in Produzione Diretti:** Nel contesto dello sviluppo di agenti AI, i mock eccessivi dei ritorni LLM non esplorano il comportamento cognitivo imprevisto. Preferisci test di integrazione veloci *che effettuano reali chiamate API o invocano realmente ollama/locale* con prompt corti per validare l'end-to-end (es. check che uno stato PAD influisca sull'output testuale).
- **Test Omeostasi e "Edge Case" Emozionali:** Quando si programma il motore PAD, è essenziale creare test specifici che iniettano valori emotivi estremi (es. P=-1.0, A=-1.0, D=-1.0) validando che il *System Prompt risultante* o la logica di fallback si attivino correttamente senza distruggere i prompt tag necessari. Testare obbligatoriamente il ciclo di "Decay" (Omeostasi) a intervalli senza eventi.
- **Validazione RAG (Playbook):** I test del "Reflector" devono verificare empiricamente che le soglie minime di similarità per recuperare le regole passate in Letta impediscano "allucinazioni" (recall di regole irrilevanti per il task in ingresso).

## 5. Processo Operativo (Come lavorare ai Task)
Quando ti (AI) viene assegnato un task:
1.  **Leggi:** Verifica e leggi `docs/visione_architettura.md` e la codebase rilevante usando i tool disponibili.
2.  **Pensa & Pianifica:** Definisci un piano chiaro.
3.  **Proponi (se impattante):** Se fai design di alto livello, confrontati con l'utente (tramite `notify_user` e `task_boundary`) per stabilire modifiche architetturali, **prima** di scrivere tonnellate di codice in isolamento.
4.  **Esegui:** Scrivi codice *insieme* ai commenti docstring pertinenti.
5.  **Verifica / SSOT:** Alla fine del task, se l'architettura o le features sono variate anche solo un po' dalla visione o roadmap iniziale, procedi all'aggiornamento automatico dell'Index, della Roadmap o dell'architettura in `docs/` prima di ritenere concluso il lavoro.
