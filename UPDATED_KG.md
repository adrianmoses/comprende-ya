┌──────────────────────────────────────────────────────┐
│                   Knowledge Graph                     │
│                                                       │
│  Static edges:    (Concept)-[REQUIRES]->(Concept)     │
│                   (Concept)-[RELATED_TO]->(Concept)   │
│                                                       │
│  Dynamic edges:   (Learner)-[STUDIES]->(Concept)      │
│                   (Concept)-[CONFUSES_WITH]->(Concept) │
│                   (Learner)-[RESPONDS_WELL_TO]->(Context)│
└──────────────┬──────────────────────┬────────────────┘
               │                      │
          reads graph            mutates graph
               │                      │
        ┌──────▼──────────────────────▼──────┐
        │           Learner Model            │
        │                                     │
        │  • Reads STUDIES edges to assess    │
        │    current state                    │
        │  • Writes STUDIES edges when        │
        │    evidence comes in                │
        │  • Creates CONFUSES_WITH edges      │
        │    when interference detected       │
        │  • Handles decay, confidence,       │
        │    cross-concept propagation        │
        └──────────────┬─────────────────────┘
                       │
                  reads state
                       │
        ┌──────────────▼─────────────────────┐
        │        Curriculum Planner           │
        │                                     │
        │  • Queries learner model for        │
        │    priorities, gaps, trends         │
        │  • Produces SessionPlan             │
        │  • Parameterizes voice agent        │
        └──────────────┬─────────────────────┘
                       │
              session plan + instructions
                       │
        ┌──────────────▼─────────────────────┐
        │          Voice Agent                │
        │                                     │
        │  • Teaches according to plan        │
        │  • Produces transcript              │
        │  • Emits raw interaction events     │
        └──────────────┬─────────────────────┘
                       │
              raw events (utterances, outcomes)
                       │
        ┌──────────────▼─────────────────────┐
        │        Assessment Layer             │
        │  (LLM-as-judge on transcript)       │
        │                                     │
        │  • Scores against concept signals   │
        │  • Detects misconceptions           │
        │  • Identifies context patterns      │
        │  • Emits EvidenceEvents             │
        └──────────────┬─────────────────────┘
                       │
              EvidenceEvents
                       │
                       ▼
               Learner Model (writes to graph)
The cycle is: plan → teach → observe → assess → update graph → plan again.
The learner model is the only thing that writes to the graph. The planner only reads. The voice agent doesn't touch the graph at all — it just follows instructions and produces a transcript. The assessment layer is the bridge that converts messy speech into structured evidence events.
This separation matters because it means the voice agent can stay simple and conversational. It doesn't need to know about mastery scores or decay curves. It just gets a system prompt that says "focus on aunque + subjunctive, use contrastive examples, the learner confuses it with como si" and does its thing. All the intelligence about what to teach when lives in the planner, and all the intelligence about what did the learner actually demonstrate lives in the assessment layer.
The one nuance: the planner operates at two timescales. Between sessions it produces a full session plan. Within a session it can do lightweight replanning — if the assessment layer reports that the learner just nailed the current concept in 3 minutes instead of the planned 10, the planner can advance to the next activity early. That intra-session loop is faster and simpler, basically just checking thresholds rather than doing full priority scoring.
