from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.agentic.observability import OrchestrationRecorder, safe_audit_data
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.tools import CommerceToolRegistry
from app.models import Category, OrchestrationRun, Product, ProductStatus, Seller, SellerStatus, User


class FakeChatModel:
    async def ainvoke(self, input, **kwargs):
        return AIMessage(content='{"mission_type":"build_setup","goal":"gaming setup","budget":4000,"preferences":[],"constraints":[],"owned_items":[],"priorities":["value"]}')


@pytest.mark.anyio
async def test_orchestration_run_and_ordered_events_are_persisted(db_session):
    user = User(email="agent-log@example.com", full_name="Agent Logger")
    seller = Seller(name="Log Seller", slug="log-seller", status=SellerStatus.ACTIVE)
    category = Category(name="Gaming", slug="gaming")
    product = Product(seller=seller, category=category, sku="LOG-001", slug="log-product", name="Gaming Setup", brand="Shopy", description="Catalog item.", price=Decimal("100"), status=ProductStatus.ACTIVE, inventory_quantity=5)
    db_session.add_all([user, product])
    db_session.commit()

    recorder = OrchestrationRecorder(db_session, request_id="runlog123", user=user)
    registry = CommerceToolRegistry(db_session, request_id="runlog123", recorder=recorder)
    result = await ShoppingOrchestrator(FakeChatModel(), tool_registry=registry, recorder=recorder).ainvoke("Build a gaming setup")
    run = db_session.scalar(select(OrchestrationRun).where(OrchestrationRun.request_id == "runlog123"))

    assert run is not None
    assert run.status == "completed"
    assert run.final_response == result["final_response"]
    assert [event.event_type for event in run.events] == ["run_started", "node_completed", "node_completed", "tool_completed", "node_completed", "node_completed", "run_finished"]
    assert [event.sequence for event in run.events] == list(range(1, 8))
    assert run.events[1].node_name == "intent_agent"
    assert run.events[3].tool_name == "search_products"
    assert run.events[-1].output_data["audit_result"]["status"] == "pass"


def test_sensitive_audit_fields_are_redacted():
    data = safe_audit_data({"api_key": "private", "card_number": "4111111111111111", "safe": "visible"})
    assert data == {"api_key": "[redacted]", "card_number": "[redacted]", "safe": "visible"}
