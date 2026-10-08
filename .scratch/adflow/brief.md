# Project: AdFlow — Real-Time Personalized Advertising Recommendation and Experimentation Platform

You are building a production-style full-stack software engineering project called **AdFlow**.

The purpose of this project is to demonstrate strong software engineering skills relevant to a Meta Software Engineering Internship, especially:

- backend engineering
- scalable system design
- recommendation systems
- ranking algorithms
- API development
- databases
- caching
- experimentation / A/B testing
- performance optimization
- testing
- monitoring
- clean code
- engineering tradeoffs

This should NOT be a simple AI demo.

The project should resemble a simplified real-world advertising recommendation platform capable of retrieving, ranking, and serving personalized ads efficiently.

I want the project to be impressive enough for a software engineering internship resume but still realistic for one developer to complete with AI assistance.

---

# 1. Main Project Goal

Build a system where a user requests an advertisement and AdFlow:

1. Receives a user request.
2. Retrieves relevant advertising candidates.
3. Reduces a large pool of ads into a smaller candidate set.
4. Predicts how likely the user is to click each ad.
5. Combines relevance, predicted CTR, and advertiser bid into a ranking score.
6. Selects the best ad.
7. Returns the selected ad through an API.
8. Records impressions, clicks, and conversions.
9. Supports A/B testing between ranking algorithms.
10. Displays system performance and experiment results on a dashboard.

The system should emphasize **software engineering and system design**, not just machine learning.

---

# 2. Preferred Technology Stack

Use the following stack unless there is a strong technical reason not to.

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy

## Database

- PostgreSQL

## Cache

- Redis

## Recommendation / ML

Start simple.

Use:

- scikit-learn
- NumPy
- FAISS for approximate nearest-neighbor retrieval

For the CTR prediction model, begin with Logistic Regression.

Structure the code so the model can later be replaced with:

- XGBoost
- neural network
- another ranking model

without rewriting the entire system.

## Frontend

Use:

- React
- TypeScript
- Vite

Keep the UI modern, minimal, and professional.

## Infrastructure

Use:

- Docker
- Docker Compose

## Testing

Use:

- pytest
- FastAPI TestClient

## Load Testing

Use either:

- Locust

or

- k6

Prefer Locust if it is easier to integrate with Python.

---

# 3. Core Architecture

Organize the backend into separate components.

Target architecture:

User Request

→ FastAPI API

→ User Profile Service

→ Candidate Retrieval

→ Ranking Engine

→ Auction / Final Scoring

→ Ad Selection

→ Response

At the same time:

Ad Impression

→ Event Logging

→ Database

→ Analytics

→ A/B Experiment Dashboard

Redis should be available for caching frequently accessed data.

---

# 4. Main Data Models

Create at least the following entities.

## User

Fields:

- id
- age_group
- interests
- country
- device_type
- created_at

Example:

```json
{
  "id": 1001,
  "age_group": "18-24",
  "interests": [
    "technology",
    "gaming",
    "fitness"
  ],
  "country": "US",
  "device_type": "mobile"
}
```

---

## Advertiser

Fields:

- id
- name
- total_budget
- active

---

## Ad

Fields:

- id
- advertiser_id
- title
- description
- category
- target_interests
- bid
- active
- embedding
- created_at

Example:

```json
{
  "id": 5021,
  "advertiser_id": 14,
  "title": "New Gaming Laptop",
  "category": "technology",
  "target_interests": [
    "gaming",
    "technology"
  ],
  "bid": 1.25,
  "active": true
}
```

---

## AdEvent

Fields:

- id
- user_id
- ad_id
- event_type
- timestamp
- experiment_id
- experiment_variant

Supported events:

- impression
- click
- conversion

---

## Experiment

Fields:

- id
- name
- description
- control_algorithm
- variant_algorithm
- traffic_split
- active
- created_at

---

# 5. Synthetic Dataset

Do not depend on proprietary or external user data.

Create a script that generates realistic synthetic data.

Generate approximately:

- 10,000 users
- 100,000 ads
- 100 advertisers
- 1,000,000 historical interaction events

Allow these values to be configured.

Generate realistic interests such as:

- technology
- gaming
- fitness
- travel
- food
- fashion
- sports
- finance
- education
- music
- movies
- photography
- cars

Create logical relationships.

For example:

Users interested in gaming should be more likely to click gaming advertisements.

The data generator should create enough signal for a CTR prediction model to learn useful relationships.

---

# 6. Candidate Retrieval System

Do NOT rank every advertisement for every request.

Implement a candidate retrieval stage.

The retrieval system should reduce:

100,000 ads

to approximately:

500 candidate ads.

Use FAISS approximate nearest-neighbor search.

Generate or construct embeddings representing:

- users
- advertisements

A simple embedding approach is acceptable initially.

For example, represent interests and categories as vectors.

Structure the retrieval interface like:

```python
class CandidateRetriever:
    def retrieve(
        self,
        user,
        limit: int = 500
    ):
        ...
```

Make the retrieval system modular so another retrieval algorithm can replace FAISS later.

Track retrieval latency.

---

# 7. CTR Prediction Model

Build a simple machine-learning model that predicts:

P(click | user, ad)

Start with Logistic Regression.

Possible input features:

- number of shared interests
- ad category matches user interest
- advertiser bid
- age group
- device type
- historical ad CTR
- historical category CTR
- user activity level

Create:

```python
class CTRModel:
    def predict_ctr(
        self,
        user,
        ad
    ) -> float:
        ...
```

Include:

- training script
- evaluation script
- model serialization
- model loading

Report metrics such as:

- ROC-AUC
- accuracy if useful
- log loss

Do not overcomplicate the ML.

The software architecture is more important.

---

# 8. Ranking Engine

After retrieving approximately 500 candidates, rank them.

Create multiple ranking algorithms.

## Ranking V1

Simple relevance-based ranking.

Example:

```text
score =
    interest_similarity
    + advertiser_bid
```

## Ranking V2

Use CTR prediction.

Example:

```text
score =
    predicted_ctr * advertiser_bid
```

## Ranking V3

Optional advanced version.

Example:

```text
score =
    predicted_ctr * advertiser_bid
    + relevance_weight * similarity_score
```

Create a common ranking interface.

Example:

```python
class RankingStrategy:
    def rank(
        self,
        user,
        candidates
    ):
        ...
```

Ranking strategies should be interchangeable.

Use the Strategy design pattern if appropriate.

---

# 9. Advertisement Auction

Add a simplified advertising auction.

The winner should not simply be the advertisement with the highest advertiser bid.

Calculate expected value using something like:

```text
expected_value =
predicted_click_probability × advertiser_bid
```

Potential final score:

```text
final_score =
0.65 × normalized_expected_value
+
0.25 × relevance_score
+
0.10 × quality_score
```

Keep the scoring configurable.

Document the tradeoff between:

- advertiser revenue
- user relevance
- advertisement quality

---

# 10. Main Recommendation API

Create:

```http
GET /api/v1/recommendations/{user_id}
```

Return:

```json
{
  "user_id": 1001,
  "ad": {
    "id": 5021,
    "title": "New Gaming Laptop",
    "category": "technology"
  },
  "score": 0.842,
  "predicted_ctr": 0.071,
  "experiment": {
    "name": "ranking-v2",
    "variant": "B"
  },
  "latency_ms": 24.8
}
```

The API flow should be:

1. Fetch user.
2. Check cache if applicable.
3. Retrieve ad candidates.
4. Run ranking algorithm.
5. Run auction.
6. Select winning ad.
7. Record impression.
8. Return response.

Handle errors correctly.

Examples:

- invalid user
- no active advertisements
- database unavailable
- Redis unavailable
- ranking model unavailable

Use graceful fallbacks when reasonable.

---

# 11. Event Tracking APIs

Create endpoints such as:

```http
POST /api/v1/events/click
```

and

```http
POST /api/v1/events/conversion
```

Request:

```json
{
  "user_id": 1001,
  "ad_id": 5021
}
```

Record timestamps and experiment information.

Prevent obviously invalid events.

---

# 12. A/B Experimentation Platform

This is a major feature.

Build an experimentation system capable of comparing ranking algorithms.

Example experiment:

```text
Name:
ranking-v2-test

Control:
Ranking V1

Variant:
Ranking V2

Traffic:
50 / 50
```

Assign users deterministically.

For example:

```python
hash(user_id + experiment_name)
```

The same user should remain in the same experiment group.

Do NOT randomly switch the user between variants on every request.

Track metrics including:

- impressions
- clicks
- conversions
- CTR
- conversion rate
- revenue
- average recommendation latency

Create an experiment results API.

Example:

```http
GET /api/v1/experiments/{experiment_id}/results
```

Response:

```json
{
  "experiment": "ranking-v2-test",
  "control": {
    "users": 5000,
    "ctr": 0.041,
    "conversion_rate": 0.012,
    "revenue_per_user": 0.31,
    "p95_latency_ms": 21
  },
  "variant": {
    "users": 5000,
    "ctr": 0.048,
    "conversion_rate": 0.014,
    "revenue_per_user": 0.37,
    "p95_latency_ms": 27
  },
  "ctr_lift_percent": 17.07
}
```

If practical, calculate basic statistical significance.

Do not pretend results are statistically significant if they are not.

---

# 13. Redis Caching

Use Redis for appropriate caching.

Possible examples:

- user profiles
- frequently accessed ads
- recommendation results
- advertisement metadata

Do not blindly cache everything.

Implement cache expiration.

Track:

- cache hits
- cache misses
- hit ratio

Create a clear fallback if Redis is unavailable.

The API should still function using PostgreSQL where practical.

---

# 14. Performance Metrics

Measure API latency.

At minimum track:

- P50 latency
- P95 latency
- P99 latency
- average latency
- requests per second

Measure individual pipeline stages:

- user lookup
- candidate retrieval
- CTR prediction
- ranking
- database logging
- overall request

Create a small metrics service or endpoint.

Example:

```http
GET /api/v1/metrics
```

---

# 15. Load Testing

Create load testing scripts.

Test at least:

- 10 concurrent users
- 100 concurrent users
- 500 concurrent users

Measure:

- throughput
- P50 latency
- P95 latency
- P99 latency
- error rate

Document the results.

Do NOT fabricate benchmark numbers.

Create a script or instructions so I can reproduce benchmarks locally.

---

# 16. Analytics Dashboard

Create a React dashboard.

Pages:

## Overview

Display:

- total advertisements
- total users
- active advertisers
- total impressions
- total clicks
- overall CTR
- total conversions
- revenue

---

## Recommendation Performance

Display:

- average latency
- P50
- P95
- P99
- cache hit rate
- requests per second

---

## Experiments

Display active A/B tests.

Example table:

| Experiment | Control | Variant | CTR Lift | Revenue Lift | Status |
|---|---|---|---|---|---|

Allow clicking an experiment to view detailed results.

---

## Advertisers

Display advertiser information such as:

- spend
- impressions
- clicks
- CTR
- conversions

---

# 17. Frontend Design

Use a professional engineering-dashboard style.

Keep it clean.

Use:

- cards
- charts
- tables
- responsive layout

Do not spend excessive time on animations.

Prioritize usability and technical credibility.

---

# 18. Testing Requirements

Create meaningful tests.

Include:

## Unit Tests

Test:

- candidate retrieval
- ranking algorithms
- experiment assignment
- auction scoring
- CTR feature generation
- cache behavior

## API Tests

Test:

- recommendation endpoint
- click endpoint
- conversion endpoint
- experiment endpoints
- error cases

## Edge Cases

Test:

- user with no interests
- advertiser with zero bid
- no available ads
- inactive ad
- inactive advertiser
- duplicated event
- Redis failure
- missing model file
- unknown user

Aim for clean and meaningful test coverage.

Do not create useless tests just to increase the percentage.

---

# 19. Logging

Use structured logging.

Log important fields such as:

- request_id
- user_id
- selected_ad_id
- ranking_algorithm
- experiment_variant
- retrieval_latency
- ranking_latency
- total_latency

Do NOT log sensitive information unnecessarily.

---

# 20. Error Handling

Create centralized error handling.

Return proper HTTP error codes.

Examples:

```text
404
User not found

503
Recommendation service unavailable

400
Invalid event
```

Avoid leaking stack traces to the frontend.

---

# 21. Docker

Create a Docker setup that starts:

- backend
- frontend
- PostgreSQL
- Redis

using:

```bash
docker compose up
```

Make setup easy for another engineer reviewing the GitHub repository.

---

# 22. Configuration

Use environment variables.

Create:

```text
.env.example
```

Include settings such as:

- DATABASE_URL
- REDIS_URL
- MODEL_PATH
- CANDIDATE_LIMIT
- CACHE_TTL
- LOG_LEVEL

Do NOT commit secrets.

---

# 23. Folder Structure

Use approximately this structure:

```text
adflow/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── retrieval/
│   │   ├── ranking/
│   │   ├── experiments/
│   │   ├── analytics/
│   │   ├── ml/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── scripts/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── load-tests/
│
├── data/
│
├── docs/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

You may improve the structure if necessary.

---

# 24. README

Write an excellent GitHub README.

The README should include:

## Project overview

Explain what AdFlow does.

## Architecture

Include a Mermaid architecture diagram.

## Request flow

Show:

```text
User
↓
API
↓
Candidate Retrieval
↓
Ranking
↓
Auction
↓
Advertisement
```

## Technologies

List the stack.

## Setup

Give exact installation instructions.

## Running the system

Explain Docker and local development.

## API endpoints

Document important endpoints.

## Recommendation algorithm

Explain candidate retrieval and ranking.

## Experimentation

Explain deterministic A/B assignment.

## Performance

Create a section where actual benchmark results can be inserted.

For example:

| Optimization | P95 Latency |
|---|---:|
| Baseline | TBD |
| FAISS Retrieval | TBD |
| Redis Cache | TBD |

Never invent results.

## Engineering decisions

Explain important tradeoffs.

For example:

- Why FAISS?
- Why Redis?
- Why PostgreSQL?
- Why Logistic Regression first?
- Why separate retrieval from ranking?

## Future improvements

Include realistic possibilities:

- Kafka event pipeline
- XGBoost ranking
- neural ranking model
- distributed cache
- Kubernetes deployment
- real feature store
- streaming analytics

---

# 25. Resume-Oriented Engineering Goals

The finished project should make it possible to truthfully write resume bullets similar to:

- Built a multi-stage personalized advertising recommendation platform using FastAPI, PostgreSQL, Redis, and FAISS.

- Designed an approximate nearest-neighbor retrieval pipeline that reduced ranking candidates from 100,000 advertisements to 500 per request.

- Developed an A/B experimentation framework using deterministic user assignment to compare ranking strategies across CTR, revenue, conversion, and latency.

- Load tested the recommendation service and optimized caching and retrieval to improve P95 latency by a measurable amount.

Do NOT fabricate performance improvements.

Only use numbers produced by actual benchmarks.

---

# 26. Engineering Quality Requirements

Follow these principles:

- clean architecture
- separation of concerns
- modular code
- clear naming
- reusable interfaces
- type hints
- concise comments
- minimal duplication
- meaningful tests
- defensive error handling

Do not generate giant files.

Do not place all backend logic inside API route handlers.

Prefer dependency injection where reasonable.

Do not over-engineer the MVP.

---

# 27. Scope Control

The project should be impressive but achievable.

Build the project in stages.

Do NOT attempt advanced distributed infrastructure before the core system works.

Follow this order.

---

# PHASE 1 — Core Backend

Build:

- FastAPI setup
- PostgreSQL integration
- User model
- Advertiser model
- Ad model
- Event model
- synthetic data generator
- basic recommendation endpoint

For the first version, a simple ranking algorithm is acceptable.

Verify everything works before moving forward.

---

# PHASE 2 — Candidate Retrieval

Add:

- advertisement embeddings
- user embeddings
- FAISS index
- top-500 candidate retrieval
- retrieval benchmarking

Add tests.

---

# PHASE 3 — CTR Model

Add:

- ML feature generation
- training dataset
- logistic regression
- model evaluation
- model serialization
- prediction service

Integrate predictions into ranking.

---

# PHASE 4 — Ranking and Auction

Implement:

- Ranking V1
- Ranking V2
- modular ranking strategies
- expected-value auction
- configurable scoring

Add tests.

---

# PHASE 5 — A/B Testing

Implement:

- experiment model
- deterministic assignment
- control vs variant
- metric tracking
- experiment results API

Add tests.

---

# PHASE 6 — Redis

Add:

- caching
- TTL
- graceful fallback
- hit/miss metrics

Benchmark before and after.

---

# PHASE 7 — Dashboard

Build React dashboard pages for:

- overview
- experiments
- system performance
- advertisers

Connect to backend APIs.

---

# PHASE 8 — Load Testing and Optimization

Create load tests.

Measure:

- P50
- P95
- P99
- throughput
- errors

Find actual bottlenecks.

Optimize only after measuring.

Document results.

---

# PHASE 9 — Final Polish

Finish:

- Docker
- README
- architecture diagrams
- screenshots
- setup instructions
- tests
- linting
- type checking
- documentation

---

# 28. How You Should Work

Do not dump the entire application at once.

Work iteratively.

For every phase:

1. Explain what you are about to implement.
2. Inspect the existing repository.
3. Create or modify the necessary files.
4. Keep changes focused.
5. Run relevant tests.
6. Fix failures before moving forward.
7. Tell me what was completed.
8. Tell me what command I can use to test it myself.
9. Identify the next logical step.

Do not rewrite working code unnecessarily.

Preserve existing architecture unless there is a clear improvement.

---

# 29. Important Constraint

I am using this project to prepare for software engineering internship interviews.

Whenever you implement an important technical decision, add a short explanation of:

- why this approach was chosen
- its time complexity where relevant
- its space complexity where relevant
- potential bottlenecks
- tradeoffs
- how it could scale further

I need to understand the implementation well enough to explain it in an interview.

Do not hide complicated logic behind libraries without explaining what the library is doing conceptually.

---

# 30. Start Here

Begin with PHASE 1 only.

First:

1. Inspect the repository.
2. Propose the exact initial folder structure.
3. Set up the FastAPI backend.
4. Configure PostgreSQL with SQLAlchemy.
5. Implement the initial database models.
6. Add configuration management.
7. Create the synthetic data generation script.
8. Add a basic health endpoint.
9. Add a first simple recommendation endpoint that does NOT yet require FAISS or machine learning.
10. Write initial tests.
11. Run all tests.
12. Create setup instructions.

Do not start PHASE 2 until PHASE 1 is working cleanly.

When Phase 1 is complete, summarize:

- files created
- architecture decisions
- how to run it
- how to test it
- known limitations
- what Phase 2 will add