# Roadmap di Sviluppo: Scarlet

Questa roadmap traccia le fasi di sviluppo necessarie per prototipare e mettere in produzione l'agente Scarlet.

## Fase 0: Ricerca e Design Architetturale ✅
- [x] Studio stato dell'arte (Motivazione Intrinseca, Frameworks).
- [x] Selezione Letta come framework della memoria.
- [x] Selezione modello PAD per motore emotivo vettoriale.
- [x] Progettazione concettuale dell'Intelligent Heartbeat e divisione Cloud/Locale (RTX 4070 Ti).

## Fase 1: Core Framework Letta (In Corso)
- [x] Setup infrastruttura Docker (Letta v0.16.4 + Ollama GPU + PostgreSQL).
- [x] Integrazione LLM Cloud: MiniMax M2.5 via OpenAI-compatible API.
- [x] Stesura e test dei blocchi Core Memory: `Persona` e `World State`.
- [x] Primo agente `scarlet-core` funzionante con risposta verificata.
- [ ] Arricchimento memory blocks (Persona completa con Aspirational Layer).
- [ ] Test multi-turn e persistenza memoria tra sessioni.
- [ ] Setup `scarlet_config.yaml` per configurazione centralizzata.
*Obiettivo: Validare la memoria a lungo termine e il ciclo agente-LLM.*

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
- [ ] Setup del LLM Locale via Ollama (es. Llama3.1-8b-instruct) sulla RTX 4070 Ti.
- [ ] Sviluppo della logica per demandare task di Sentiment Analysis PAD all'LLM locale.
- [ ] Integrazione del Local LLM per generare riflessioni di background e monologhi per il Buffer Subconscio.
*Obiettivo: Portare online la 4070 Ti e smistare traffico a basso valore.*

## Fase 5: Sincronizzazione e Produzione (Settimane 9-10)
- [ ] Sviluppo dell'architettura publisher/subscriber (es. Redis/RabbitMQ).
- [ ] Creazione pipeline affinché l'LLM locale metta in coda le "Memory Update Proposals" senza scrivere direttamente nel DB.
- [ ] Integrazione con l'istanza core di Letta per il merge serializzato degli stati (evitando Race Conditions).
*Obiettivo: Chiudere il loop ibrido sincronizzando i pensieri subconsci e le interazioni chat.*
