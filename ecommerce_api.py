"""
API de e-commerce que o agente ElevenLabs chama via tool-calling — agora
consultando o Monday.com (board real, GraphQL) em vez de dados hardcoded.

Rodar: uvicorn ecommerce_api:app --reload --port 8000
Docs interativas: http://localhost:8000/docs
"""

from datetime import date, datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import monday_client

load_dotenv()

app = FastAPI(title="E-commerce API (Monday.com backend)", version="1.0")

RETURN_POLICIES = {
    "aurora-cosmetics": {
        "window_days": 7,
        "condition": "produto lacrado, exceto reação alérgica comprovada",
    },
    "nordic-home": {
        "window_days": 30,
        "condition": "produto sem sinais de uso",
    },
}


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    estimated_delivery: str
    tracking_code: str | None
    items: list[str]


class ReturnEligibilityResponse(BaseModel):
    eligible: bool
    reason: str
    window_days: int


def _get_order_or_404(order_id: str) -> dict:
    order = monday_client.find_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} não encontrado")
    return order


@app.get("/orders/{order_id}/status", response_model=OrderStatusResponse)
def get_order_status(order_id: str):
    """Endpoint que o agente chama via tool-calling para responder 'cadê meu pedido'."""
    order = _get_order_or_404(order_id)
    return OrderStatusResponse(
        order_id=order["order_id"],
        status=order["status"],
        estimated_delivery=order["estimated_delivery"],
        tracking_code=order["tracking_code"],
        items=order["items"],
    )


@app.get("/orders/{order_id}/return-eligibility", response_model=ReturnEligibilityResponse)
def check_return_eligibility(order_id: str):
    """Endpoint que o agente chama para responder sobre política de troca/devolução."""
    order = _get_order_or_404(order_id)

    if order["status"] != "delivered":
        return ReturnEligibilityResponse(
            eligible=False,
            reason="Pedido ainda não foi entregue, troca só é possível após a entrega.",
            window_days=0,
        )

    policy = RETURN_POLICIES.get(order["brand"], {"window_days": 0, "condition": "sem política definida"})

    # O board não tem uma coluna de "data de entrega real" — usamos
    # estimated_delivery como proxy da data de entrega para a demo.
    delivered_date = datetime.strptime(order["estimated_delivery"], "%Y-%m-%d").date()
    days_since = (date.today() - delivered_date).days
    eligible = days_since <= policy["window_days"]

    return ReturnEligibilityResponse(
        eligible=eligible,
        reason=f"Janela de troca: {policy['window_days']} dias. Condição: {policy['condition']}.",
        window_days=policy["window_days"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Endpoints POST, formatados para o padrão de webhook tool da ElevenLabs ---
# (o schema de tool confirmado na doc usa POST + request_body_schema; suporte
# a path params em GET não foi confirmado com certeza, por isso POST é o
# padrão usado na integração real)

class OrderLookupRequest(BaseModel):
    order_id: str


@app.post("/tools/lookup-order-status", response_model=OrderStatusResponse)
def tool_lookup_order_status(payload: OrderLookupRequest):
    return get_order_status(payload.order_id)


@app.post("/tools/check-return-eligibility", response_model=ReturnEligibilityResponse)
def tool_check_return_eligibility(payload: OrderLookupRequest):
    return check_return_eligibility(payload.order_id)
