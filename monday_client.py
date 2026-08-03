"""
Cliente GraphQL para o board "Orders" no Monday.com.

Board 18424777126 (confirmado via API, colunas obtidas com uma query
`boards(ids: ...) { columns { id title type } }`):

    id                   title                type
    ---------------------------------------------------
    name                 Name                 name
    text_mm5vtbyz        order_id             text
    dropdown_mm5vkamx    brand                dropdown
    color_mm5v4kqv       status               status
    date_mm5vhtg9        estimated_delivery   date
    text_mm5vf5w7        tracking_code        text
    long_text_mm5vwh7k   items                long_text
    text_mm5vxcmz        cliente              text

Se o board mudar (coluna renomeada/recriada), os IDs acima também mudam —
seriam necessários novos IDs.
"""

import os

import requests

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_VERSION = "2024-10"

ORDER_ID_COLUMN = "text_mm5vtbyz"
DETAIL_COLUMNS = [
    "dropdown_mm5vkamx",  # brand
    "color_mm5v4kqv",  # status
    "date_mm5vhtg9",  # estimated_delivery
    "text_mm5vf5w7",  # tracking_code
    "long_text_mm5vwh7k",  # items
    "text_mm5vxcmz",  # cliente
]

BRAND_LABEL_TO_SLUG = {
    "Aurora Cosméticos": "aurora-cosmetics",
    "Nordic Home": "nordic-home",
}

FIND_ORDER_QUERY = """
query FindOrder($boardIds: [ID!], $orderId: CompareValue!, $detailColumns: [String!]) {
  boards(ids: $boardIds) {
    items_page(
      query_params: {
        rules: [
          { column_id: "%s", compare_value: $orderId, operator: any_of }
        ]
      }
    ) {
      items {
        id
        name
        column_values(ids: $detailColumns) {
          id
          text
        }
      }
    }
  }
}
""" % ORDER_ID_COLUMN


class MondayClientError(RuntimeError):
    pass


def _run_query(query: str, variables: dict) -> dict:
    token = os.getenv("MONDAY_API_TOKEN")
    if not token:
        raise MondayClientError("Defina a variável de ambiente MONDAY_API_TOKEN")

    response = requests.post(
        MONDAY_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": MONDAY_API_VERSION,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    if "errors" in payload:
        raise MondayClientError(f"Monday API retornou erro: {payload['errors']}")

    return payload["data"]


def _slugify_status(label: str) -> str:
    return label.strip().lower().replace(" ", "_")


def find_order(order_id: str) -> dict | None:
    """Busca um pedido pelo valor da coluna order_id (não o ID interno do item).

    Retorna um dict no mesmo formato que a antiga ORDERS_DB hardcoded, ou
    None se não encontrado.
    """
    board_id = os.getenv("MONDAY_BOARD_ID")
    if not board_id:
        raise MondayClientError("Defina a variável de ambiente MONDAY_BOARD_ID")

    data = _run_query(
        FIND_ORDER_QUERY,
        {
            "boardIds": [board_id],
            "orderId": [order_id],
            "detailColumns": DETAIL_COLUMNS,
        },
    )

    items = data["boards"][0]["items_page"]["items"]
    if not items:
        return None

    item = items[0]
    values = {cv["id"]: cv["text"] for cv in item["column_values"]}

    brand_label = values.get("dropdown_mm5vkamx") or ""
    tracking_code = values.get("text_mm5vf5w7") or ""
    items_raw = values.get("long_text_mm5vwh7k") or ""

    return {
        "order_id": item["name"],
        "brand": BRAND_LABEL_TO_SLUG.get(brand_label, brand_label),
        "customer_name": values.get("text_mm5vxcmz"),
        "status": _slugify_status(values.get("color_mm5v4kqv") or ""),
        "estimated_delivery": values.get("date_mm5vhtg9"),
        "tracking_code": tracking_code if tracking_code and tracking_code != "—" else None,
        "items": [i.strip() for i in items_raw.split(",") if i.strip()],
    }
