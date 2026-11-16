import json
import uuid
from pathlib import Path

TICKETS_FILE = Path("data/escalated_tickets.json")

class TicketStore:
    def __init__(self):
        TICKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not TICKETS_FILE.exists():
            TICKETS_FILE.write_text("[]", encoding="utf-8")

    def _load(self):
        return json.loads(TICKETS_FILE.read_text(encoding="utf-8"))

    def _save(self, tickets):
        TICKETS_FILE.write_text(json.dumps(tickets, indent=2), encoding="utf-8")

    def create_ticket(self, tenant_id, customer_question, customer_email, reason):
        tickets = self._load()
        ticket = {
            "ticket_id": str(uuid.uuid4())[:8],
            "tenant_id": tenant_id,
            "customer_question": customer_question,
            "customer_email": customer_email,
            "reason": reason,
            "status": "open",
            "human_answer": None
        }
        tickets.append(ticket)
        self._save(tickets)
        return ticket

    def get_open_tickets(self, tenant_id):
        return [t for t in self._load() if t["tenant_id"] == tenant_id and t["status"] == "open"]

    def resolve_ticket(self, tenant_id, ticket_id, human_answer):
        tickets = self._load()
        for ticket in tickets:
            if ticket["tenant_id"] == tenant_id and ticket["ticket_id"] == ticket_id:
                ticket["status"] = "resolved"
                ticket["human_answer"] = human_answer
                self._save(tickets)
                return ticket
        return None
