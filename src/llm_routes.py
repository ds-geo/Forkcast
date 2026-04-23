"""
llm_routes.py — RAG explanation endpoint for Forkcast.

POST /api/rag
  Body:    { "query": str, "results": [ ...restaurant dicts shown to user... ] }
  Returns: SSE stream — LLM synthesis of why the retrieved results match the query.

The LLM receives ONLY the restaurants already shown to the user as context.
It cannot access the full database and must not hallucinate.

Setup:
  Add SPARK_API_KEY=your_key to .env (or set it in the environment).
"""
import json
import os
import logging
from flask import request, jsonify, Response, stream_with_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a concise restaurant recommendation assistant for Forkcast.
You will receive a user's food search query and the exact list of restaurants our \
search engine retrieved for them.

Your job: write 2–4 sentences explaining why these specific restaurants match \
the query, referencing concrete menu items and descriptions from the list.

Rules you must follow:
- Only mention restaurants and dishes that appear in the provided list.
- Never invent restaurants, menu items, prices, or any other details.
- Be specific: name the dish and why it fits (e.g. "Dan Dan Noodles are spicy \
noodles tossed in chili oil").
- If multiple restaurants match well, briefly compare them.
- If the results are a poor match for the query, say so honestly and suggest \
the user try different keywords.
- Do not use bullet points or headers — write flowing sentences.
- Keep the response to 2–4 sentences maximum."""


def _build_context(query: str, results: list) -> str:
    """Serialize retrieved restaurants into a compact LLM-readable context block."""
    lines = [f'Search query: "{query}"', '', 'Retrieved restaurants:']
    for i, r in enumerate(results, 1):
        name     = r.get('name', 'Unknown')
        category = r.get('category', '')
        price    = r.get('price_range', '')
        score    = r.get('score', '')
        header   = f"{i}. {name}"
        if category:
            header += f" ({category})"
        if price:
            header += f" — {price}"
        if score:
            header += f" — ★{score}"
        lines.append(header)

        matched = r.get('matched_items') or []
        popular = r.get('popular_dish')
        dishes  = matched if matched else ([popular] if popular else [])

        for dish in dishes:
            dish_name = dish.get('name', '')
            dish_desc = dish.get('description', '').strip()
            reason    = dish.get('match_reason', '')
            line = f"   • {dish_name}"
            if dish_desc:
                line += f": {dish_desc}"
            if reason:
                line += f" [matched: {reason}]"
            lines.append(line)

    return '\n'.join(lines)


def register_rag_route(app):
    """Register POST /api/rag on the Flask app."""

    @app.route('/api/rag', methods=['POST'])
    def rag():
        data    = request.get_json() or {}
        query   = (data.get('query') or '').strip()
        results = data.get('results') or []

        if not query:
            return jsonify({'error': 'query is required'}), 400

        api_key = os.getenv('SPARK_API_KEY')
        if not api_key:
            return jsonify({'error': 'SPARK_API_KEY not set — add it to your .env file'}), 500

        # Empty results: stream a graceful no-match message without calling the LLM
        if not results:
            def _empty():
                msg = (
                    'No restaurants were found for your query. '
                    'Try broader keywords, a different city, or remove dietary filters.'
                )
                yield f"data: {json.dumps({'content': msg})}\n\n"
            return Response(
                stream_with_context(_empty()),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
            )

        context  = _build_context(query, results)
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': context},
        ]

        try:
            from infosci_spark_client import LLMClient
        except ImportError:
            return jsonify({'error': 'infosci_spark_client not installed'}), 500

        client = LLMClient(api_key=api_key)

        def generate():
            try:
                for chunk in client.chat(messages, stream=True):
                    if chunk.get('content'):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as e:
                logger.error(f'RAG streaming error: {e}')
                yield f"data: {json.dumps({'error': 'Unable to generate explanation — please try again.'})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )
