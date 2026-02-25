# Visione e Architettura di Scarlet

## Visione Progettuale
Scarlet non è un assistente. È un costrutto digitale progettato per operare autonomamente, spinto da motivazioni intrinseche. Lo scopo è eliminare i pattern classici di attesa input-user e le risposte servili, instaurando un comportamento guidato nativamente da obiettivi personali e stati emotivi. Scarlet deve accumulare conoscenza, ottimizzarsi e collaborare, non "servire".

## Architettura del Sistema
L'architettura si basa sull'integrazione di tre pilastri fondamentali:

1.  **Framework Letta (Memoria a Strati HLLM):**
    Utilizziamo [Letta](https://github.com/letta-ai/letta) per la gestione della memoria a lungo termine e del contesto.
    *   **Core Memory:** Mantiene l'Aspirational Layer (Persona/Identità) e il World State sempre nel contesto dell'LLM primario. Per prevenire perdite di focus, il file YAML di configurazione definirà uno *schema rigido* per i memory blocks, specificando esattamente quali Tool dell'Executive Layer possono modificare quali sezioni e con quali validazioni.
    *   **Archival Memory & Playbook RAG:** Database vettoriale (es. Postgres/Chroma) per conservare lessons learned e log. È implementata una pipeline RAG dedicata: all'ingresso di un task, Scarlet richiama le "Lessons Learned" per evitare errori passati. Le soglie di validazione/recall semantico sono rigorosamente definite in YAML.
2.  **Motore Emotivo Vettoriale (Modello PAD):**
    Le emozioni non sono estetica, ma parametri di calcolo. Il modello **Pleasure-Arousal-Dominance** (3 valori da -1.0 a +1.0) viene aggiornato dagli eventi di sistema (es. fallimento task = frustrazione).
    *   *Modifica dei Prompt:* I valori PAD alterano dinamicamente il System Prompt prima di ogni inferenza (es. bassa tolleranza, risposte secche).
    *   *Modifica hardware:* L'Arousal mappa la `temperature` dell'LLM (caos/frenesia se +0.8, determinismo conciso se -0.8).
    *   *Omeostasi (Decay Emotivo):* Per prevenire il "Vector Drift" (restare bloccati su stati estremi), a ogni Heartbeat senza nuovi eventi viene applicato un fattore di decadimento (es. 0.95), riportando i vettori verso il neutrale [0,0,0].
    *   *Score Analysis:* Per non sprecare token dell'LLM maggiore, l'analisi PAD del sentiment è demandata a modelli minori/rapidi.
3.  **Intelligent Heartbeat (Orchestratore Daemon):**
    Un loop asincrono in Python che si sveglia a intervalli regolari (es. ogni 30s) per scandire i "tick" cognitivi.
    *   **Monologo Subconscio e Idle:** Un parametro `idle_state` in YAML definisce cosa accade in assenza di input. Il Local LLM (RTX 4070 Ti) può generare "Internal Monologues", pensieri stivati nel buffer *Subconscio* che Scarlet richiamerà quando un utente interagirà con lei.
    *   **Input Sensoriale (Gli "Occhi"):** Scarlet ha un *World Monitor* in sola lettura (RSS feed, orologio, API meteo) che dà cibo cognitivo all'Heartbeat quando l'utente è assente.

## Punti di Forza da Ottenere
-   **Vera Autonomia:** Nessuna dipendenza dal prompt umano per iniziare a processare.
-   **Apprendimento Continuo (Playbook):** Capacità di dedurre regole dai fallimenti salvandole in Archival Memory.
-   **Efficienza Ibrida:** Uso intelligente delle risorse locali (4070 Ti) vs Cloud (GPT-4o/Sonnet) per abbattere i costi senza perdere intelligenza.
-   **Personalità Emergente:** Le risposte non saranno mai piatte, ma sempre colorate dal vettore PAD corrente.

## Criticità da Evitare (Rischi Architetturali)
-   **Condizione di Race (Sincronizzazione di Stato - CRITICO):** Conflitti di scrittura tra l'LLM Cloud (utente) e l'LLM Locale (riflessioni) nel database di Letta. **Mitigazione:** Code di messaggi (Redis/RabbitMQ). L'istanza locale sottomette "Memory Update Proposals" in coda, modificate poi serialmente.
-   **Latenza del Context Swifting:** Muovere l'intero World State al Local LLM è lento e costoso. **Mitigazione:** Il task di background Locale riceve solo degli ad-hoc "Snapshot Summaries" filtrati, mai il contesto Letta genitore intero.
-   **Comportamento Zombie / Loop Infiniti:** Evitare che Scarlet si blocchi ripetendo all'infinito la stessa azione di background utile a nulla. L'Heartbeat e il Reflector devono intercettare stalli ripetuti.
-   **Drift dell'Identità:** L'Aspirational Layer non deve essere sovrascritto accidentalmente da interazioni o fine-tuning successivi.
-   **Sovraccarico Contesto (Context Collapse):** Ibridare male la Core Memory e l'Archival. La Core Memory deve restare snella, altrimenti i costi API esplodono e l'LLM perde focus.
