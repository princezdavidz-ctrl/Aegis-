# Domain layer

Place framework-independent entities, value objects, state transitions, and domain policies here. Domain code must not call models, databases, or external tools directly. Validate tenant ownership and resource relationships at service boundaries; do not trust tenant IDs supplied by clients.
