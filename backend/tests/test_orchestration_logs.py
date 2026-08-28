import json
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.agentic.observability import OrchestrationRecorder, safe_audit_data
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.tools import CommerceToolRegistry
from app.models import Category, Conversation, OrchestrationRun, Product, ProductStatus, Seller, SellerStatus, User


class FakeChatModel:
    async def ainvoke(self, input, **kwargs):
        if "response-writing agent" in str(input[0].content):
            payload = json.loads(str(input[1].content))
            products = payload["verified_catalog_products"]
            response = "I can help with this request." if not products else "\n".join(
                f"{product['name']} — RM {product['price']}" for product in products
            )
            return AIMessage(content=json.dumps({"response": response, "product_ids": [product["id"] for product in products]}))
        return AIMessage(content=(
            '{"mission_type":"product_search","recommendation_mode":"single",'
            '"goal":"gaming setup","requires_catalog":true,"catalog_query":"gaming setup",'
            '"catalog_queries":["gaming setup"],"requested_actions":["search_products"],'
            '"budget":4000,"preferences":[],"constraints":[],"owned_items":[],"priorities":["value"],'
            '"fulfillment_requirements":[{"kind":"category","value":"gaming setup","quantity":1}]}'
        ))


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
    assert run.events[0].event_type == "run_started"
    assert run.events[-1].event_type == "run_finished"
    assert [event.sequence for event in run.events] == list(range(1, len(run.events) + 1))
    assert run.events[1].node_name == "intent_agent"
    assert any(event.tool_name == "search_products" for event in run.events)
    assert any(event.node_name == "manager" for event in run.events)
    assert [event.node_name for event in run.events if event.event_type == "node_completed"][-4:] == [
        "response_draft", "audit", "brand_voice", "final_audit",
    ]
    assert run.events[-1].output_data["audit_result"]["status"] == "pass"


def test_sensitive_audit_fields_are_redacted():
    data = safe_audit_data({"api_key": "private", "card_number": "4111111111111111", "safe": "visible"})
    assert data == {"api_key": "[redacted]", "card_number": "[redacted]", "safe": "visible"}


def test_llm_token_usage_is_recorded_per_call_and_aggregated(db_session):
    recorder = OrchestrationRecorder(db_session, request_id="token-run-123")
    recorder.start({"user_request": "Find a desk"})
    recorder.record_llm_call(input_tokens=120, output_tokens=35, total_tokens=155)
    recorder.record_llm_call(input_tokens=80, output_tokens=20, total_tokens=100)

    assert recorder.run is not None
    assert (recorder.run.input_tokens, recorder.run.output_tokens, recorder.run.total_tokens) == (200, 55, 255)
    events = [event for event in recorder.run.events if event.event_type == "llm_call"]
    assert [(event.input_tokens, event.output_tokens, event.total_tokens) for event in events] == [(120, 35, 155), (80, 20, 100)]


def test_orchestration_run_can_be_linked_to_a_conversation(db_session):
    conversation = Conversation(session_token="camera-session", context={"channel": "web_camera"})
    recorder = OrchestrationRecorder(db_session, request_id="camera-run-123", conversation=conversation)
    recorder.start({"user_request": "Shop this image", "vision_input": {"image_bytes": b"raw-image", "mode": "shop_object"}})

    run = db_session.scalar(select(OrchestrationRun).where(OrchestrationRun.request_id == "camera-run-123"))
    assert run is not None
    assert run.conversation_id == conversation.id
    assert run.initial_state["vision_input"]["image_bytes"] == "[binary payload omitted: 9 bytes]"
