# Vector Databases (Assignment 2, Question 3)

> Verification note: feature statements below come from the author's general knowledge as of
> mid-2026 and were **not** re-checked against current vendor documentation while building this
> project. No benchmark numbers are claimed. Re-verify against official docs before submission.

## Concepts (short)
* **Embedding**: a model maps text to a fixed-length vector so that similar meaning gives nearby vectors.
* **Cosine similarity**: compares the *angle* between vectors (ignores length). Common for text embeddings. `cos = (a·b)/(|a||b|)`.
* **Euclidean (L2) distance**: straight-line distance; sensitive to vector length. For L2-normalised vectors, ranking by cosine and by L2 is equivalent.
* **Approximate nearest neighbour (ANN)**: exact search compares the query with every vector (O(N)). ANN indexes (e.g. HNSW graphs, IVF clusters) trade a little recall for much lower latency.
* **Indexing**: HNSW = fast, memory-hungry, good recall; IVF = cluster-then-search, needs training and tuning `nprobe`.
* **Metadata filtering**: restrict results by attributes (department, ACL group). Filtering *with* ANN is hard: filtering after the search can return too few results; good systems filter during traversal.
* **RAG**: embed the question, retrieve top-k chunks, put them in the prompt, and let the LLM answer from them with citations.

## Candidates

| | FAISS | Chroma | Qdrant | pgvector |
|---|---|---|---|---|
| What it is | C++/Python **library** for similarity search | Open-source vector DB, embedded or client-server | Dedicated vector DB service (Rust) | **Postgres extension** adding a vector type and indexes |
| Persistence / server | You build it (save/load index files, no server) | Built in | Built in | Postgres |
| Metadata filtering | Minimal; you implement it around the index | Supported | Strong, payload filtering integrated in search | Full SQL `WHERE`, joins with ACL tables |
| ANN indexes | Many (flat, IVF, HNSW, PQ), including GPU | HNSW-based | HNSW-based, quantisation options | HNSW and IVFFlat; exact search by default |
| Scale | Very large in-memory/GPU, but you manage sharding | Small to medium | Medium to very large, clustering supported | Small to medium-large; depends on Postgres sizing |
| Security features | None (library) | Check current auth/TLS options for the deployment mode | API keys, TLS, access control options on self-hosted; managed option | Inherits Postgres: roles, TLS, row-level security, backups, audit extensions |
| Operations | Lowest dependencies, highest DIY | Low | Another service to run and monitor | Reuses existing Postgres operations |
| Cost | Free | Free (self-host) | Free self-host; paid managed tier optional | Free extension; managed Postgres cost if used |

## Decision matrix
Score 1 (poor) to 5 (good) **for this hypothetical use case**: ~2 million chunks, per-document ACLs,
corporate Postgres already in use, small platform team, on-premises or private-cloud requirement.
Weights reflect that access control and operability matter most. Scores are the author's judgement, not measurements.

| Criterion (weight) | FAISS | Chroma | Qdrant | pgvector |
|---|---|---|---|---|
| Deployment fit, self-hosted (2) | 3 | 4 | 4 | 5 |
| Cost (1) | 5 | 5 | 4 | 5 |
| Scalability (2) | 4 | 2 | 5 | 3 |
| Filtering and ACLs (3) | 1 | 3 | 5 | 5 |
| Operational complexity (2) | 3 | 4 | 3 | 5 |
| Security and compliance (3) | 1 | 2 | 4 | 5 |
| Integration with existing stack (2) | 2 | 3 | 3 | 5 |
| **Weighted total (max 75)** | **35** | **46** | **61** | **71** |

(Computation: sum of weight x score per column.)

## Recommendation for this scenario: **pgvector**
Reasons grounded in the requirements: ACL filtering is the central security need, and a SQL `WHERE`
on the same database that already stores users, groups and document permissions keeps permissions and
vectors in one transactional, auditable system with existing backup, TLS and role management. Two
million chunks is well within what Postgres with HNSW can serve for an internal assistant.

## Trade-offs and when the answer changes
* **Choose Qdrant instead** if vectors grow to tens of millions, you need very low latency under heavy filtered load, or the vector workload should scale independently from the transactional database.
* **Choose FAISS** for research, offline batch jobs, or when you need GPU-scale raw search and will build the serving and security layer yourself. It is a library, not a database.
* **Choose Chroma** for prototypes and small deployments; verify its current security and scaling features before a production decision.
* pgvector limits: heavy vector load competes with transactional load on the same instance; ANN with restrictive filters can return fewer than k results unless tuned (newer versions add iterative index scans; check the installed version); index builds and memory use need planning.
* Whatever is chosen, **ACL enforcement must still be tested** (e.g. a user must never retrieve a chunk from a group they lack) and re-checked after retrieval.
