# Roadmap di Sviluppo: Scarlet

Questa roadmap traccia le fasi di sviluppo necessarie per prototipare e mettere in produzione l'agente Scarlet.

## Fase 1: Ricerca e Design Architetturale (Completata)
- [x] Studio stato dell'arte (Motivazione Intrinseca, Frameworks).
- [x] Selezione Letta come framework della memoria.
- [x] Selezione modello PAD per motore emotivo vettoriale.
- [x] Progettazione concettuale dell'Intelligent Heartbeat e divisione Cloud/Locale (RTX 4070 Ti).

## Fase 1: Core Framework Letta (Settimane 1-2)
- [ ] Inizializzazione repository (Python, Poetry, pre-commit hooks) e `scarlet_config.yaml`.
- [ ] Implementazione di Letta con il solo LLM Cloud Primario (GPT-4o/Sonnet).
- [ ] Stesura e test dei blocchi Core Memory: `Persona` (Aspirational Layer) e `World State`. 
*Obiettivo: Validare la memoria a lungo termine senza le complessità ibride.*

## Fase 2: Motore Emotivo e PAD (Settimane 3-4)
- [ ] Sviluppo della classe `PadEngine` con vettori `[P, A, D]` e sistema di decadimento periodico (Omeostasi) verso `[0,0,0]`.
- [ ] Integrazione del PAD nel System Prompt iniezione dinamica pre-chiamata API.
- [ ] Mappatura del parametro dell'Arousal sulla `temperature` dell'LLM (caos/frenesia se alto, determinismo se basso).
*Obiettivo: Testare la modulazione emotiva con scenari controllati che simulano successi o errori ripetuti.*

## Fase 3: Intelligent Heartbeat ("Vita") (Settimane 5-6)
- [ ] Sviluppo del ciclo asincrono Python (Orchestratore) con intervalli regolari.
- [ ] Creazione mock dell'Input Sensoriale (connessione a data/ora, RSS feeds).
- [ ] Gestione stati di `idle_state`.
*Obiettivo: Validare il timing e i cicli di attivazione/disattivazione stampando inizialmente solo log di transizione.*

## Fase 4: Esecuzione Ibrida ("Il Cervello") (Settimane 7-8)
- [ ] Setup del server LLM Locale (Ollama + Llama3-8b-Instruct) ottimizzato per 16GB VRAM (su RTX 4070 Ti).
- [ ] Sviluppo della logica per demandare task di Sentiment Analysis PAD all'LLM locale.
- [ ] Integrazione del Local LLM per generare riflessioni di background e monologhi per il Buffer Subconscio.
*Obiettivo: Portare online la 4070 Ti e smistare traffico a basso valore.*

## Fase 5: Sincronizzazione e Produzione (Settimane 9-10)
- [ ] Sviluppo dell'architettura publisher/subscriber (es. Redis/RabbitMQ).
- [ ] Creazione pipeline affinché l'LLM locale metta in coda le "Memory Update Proposals" senza scrivere direttamente nel DB.
- [ ] Integrazione con l'istanza core di Letta per il merge serializzato degli stati (evitando Race Conditions).
*Obiettivo: Chiudere il loop ibrido sincronizzando i pensieri subconsci e le interazioni chat.*
