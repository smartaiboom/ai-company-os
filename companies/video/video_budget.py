"""Opt-in adapter for NEW video projects; no mission-01 migration or default budget."""


class BudgetedVideoTransport:
    def __init__(self, ledger, project, scope, verify_consent):
        self.ledger, self.project = ledger, project
        self.scope, self.verify_consent = scope, verify_consent

    def send(self, operation_id, resource, transport):
        return self.ledger.execute(self.project, operation_id=operation_id, resource=resource,
            expected_scope=self.scope, verify_consent=self.verify_consent, send=transport)

    def budget_status(self):
        return self.ledger.view(self.project)
