"""
Provisiona um agente ElevenLabs por linha de um CSV de marcas/clientes.

Resolve o problema de "a empresa tem N marcas, não dá pra configurar uma
por uma na mão no dashboard" — self-service tool que padroniza e escala a
criação de agentes.

Uso:
    python provision_agents.py --csv brands.csv --dry-run     # só mostra o payload, não chama a API
    python provision_agents.py --csv brands.csv                # cria de verdade (precisa de ELEVENLABS_API_KEY)

Requer:
    ELEVENLABS_API_KEY no .env (não precisa em --dry-run)
    MOCK_API_BASE_URL no .env apontando pra URL pública da API
    (ex: a URL do ngrok, algo como https://xxxx.ngrok-free.app) — em
    produção seria o endpoint real do backend do cliente.
"""

import argparse
import csv
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

MOCK_API_BASE_URL = os.getenv("MOCK_API_BASE_URL", "http://localhost:8000")


def build_agent_payload(brand: dict) -> dict:
    """
    Monta o conversation_config do agente para uma marca específica.
    Schema baseado na doc oficial da ElevenLabs (POST /v1/convai/agents/create).
    """
    system_prompt = (
        f"Você é o assistente de atendimento da {brand['brand_name']}. "
        f"Seu tom deve ser {brand['tone_description']}. "
        f"Use as ferramentas disponíveis para consultar status de pedido e "
        f"elegibilidade de troca antes de responder — nunca invente informação "
        f"sobre pedidos. Se não conseguir resolver, ofereça transferir para um humano."
    )

    tools = [
        {
            "type": "webhook",
            "name": "lookup_order_status",
            "description": (
                "Consulta o status de um pedido pelo código (ex: ORD-1001). "
                "Use sempre que o cliente perguntar 'cadê meu pedido' ou similar."
            ),
            "api_schema": {
                "url": f"{MOCK_API_BASE_URL}/tools/lookup-order-status",
                "method": "POST",
                "request_body_schema": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Código do pedido informado pelo cliente, ex: ORD-1001",
                        }
                    },
                    "required": ["order_id"],
                },
            },
        },
        {
            "type": "webhook",
            "name": "check_return_eligibility",
            "description": (
                "Verifica se um pedido é elegível para troca/devolução, "
                "de acordo com a política da marca."
            ),
            "api_schema": {
                "url": f"{MOCK_API_BASE_URL}/tools/check-return-eligibility",
                "method": "POST",
                "request_body_schema": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Código do pedido a verificar",
                        }
                    },
                    "required": ["order_id"],
                },
            },
        },
    ]

    return {
        "name": f"{brand['brand_name']} - Atendimento",
        "conversation_config": {
            "agent": {
                "language": brand["language"],
                "prompt": {
                    "prompt": system_prompt,
                    "tools": tools,
                    "built_in_tools": {
                        "end_call": {
                            "name": "end_call",
                            "params": {"system_tool_type": "end_call"},
                        },
                        "language_detection": {
                            "name": "language_detection",
                            "params": {"system_tool_type": "language_detection"},
                        },
                    },
                },
                "first_message": brand["first_message"],
            },
            "tts": {
                "model_id": "eleven_turbo_v2_5",
                "voice_id": brand["voice_id"],
            },
        },
    }


def provision_from_csv(csv_path: str, dry_run: bool) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        brands = list(reader)

    if not brands:
        print(f"Nenhuma marca encontrada em {csv_path}")
        return

    client = None
    if not dry_run:
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            sys.exit("Instale o SDK: pip install elevenlabs")

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            sys.exit("Defina a variável de ambiente ELEVENLABS_API_KEY antes de rodar sem --dry-run")
        client = ElevenLabs(api_key=api_key)

    for brand in brands:
        payload = build_agent_payload(brand)

        if dry_run:
            print(f"\n{'=' * 60}")
            print(f"[DRY RUN] Payload que seria enviado para: {brand['brand_name']}")
            print(f"{'=' * 60}")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            try:
                agent = client.conversational_ai.agents.create(
                    name=payload["name"],
                    conversation_config=payload["conversation_config"],
                )
                print(f"✅ Agente criado para {brand['brand_name']}: agent_id={agent.agent_id}")
            except Exception as e:
                print(f"❌ Erro ao criar agente para {brand['brand_name']}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provisiona agentes ElevenLabs a partir de um CSV")
    parser.add_argument("--csv", default="brands.csv", help="Caminho do CSV de marcas")
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o payload, não chama a API")
    args = parser.parse_args()

    provision_from_csv(args.csv, args.dry_run)
