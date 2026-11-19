# AEGIS AI Architecture

## Responsibility
The AI service provides security intelligence to the AEGIS platform. It is separate from the customer/engineer UI and the core API.

## Logical layers
1. Orchestrator and workflow manager.
2. Specialist agents with declared capabilities and typed contracts.
3. Provider-independent model gateway.
4. Tenant-isolated knowledge and retrieval.
5. Permissioned security tools and integrations.
6. Policy, authorization and human approval gates.
7. Evaluation, feedback and observability.

## Execution path
Authorized telemetry is normalized by ingestion services and delivered to detection workflows. The orchestrator dispatches scoped tasks to agents. Agents retrieve permitted evidence and call only registered tools. Findings and recommendations are returned to the API and SOC console with trace IDs and provenance. Any consequential action is revalidated and approved before execution, then verified and audited.

## Model strategy
Use interchangeable cloud and self-hosted providers behind one gateway. Route by task capability, quality, latency, privacy and budget. Do not train a foundation model from scratch for the initial release.

## Data boundaries
Tenant context is established server-side. Every retrieval, cache, queue, tool and report operation must enforce tenant scope. Customer information is not used for shared model training without explicit contractual authorization and privacy review.

## Knowledge persistence status

The backend migration `0010_tenant_knowledge_store` defines tenant-owned
documents, chunks and embedding spaces in PostgreSQL/pgvector. Forced RLS,
composite tenant-consistent foreign keys, model/revision/dimension compatibility
and audit-triggered ingestion writes are included. The pgvector extension must
be enabled by a database administrator before migrations run.

This schema is not yet an active retrieval service. The PostgreSQL adapter,
embedding orchestration, exact tenant-and-space-filtered vector query, hybrid
ranking and retention workflow remain pending. The in-memory KnowledgeStore is
still the only active adapter.

## Deployment
Run the AI service and background workers as separately deployable services. Use Neon for transactional metadata and tenant-scoped knowledge metadata; use suitable event/object storage for high-volume raw telemetry.
