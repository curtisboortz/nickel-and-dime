"""AI Advisor API — chat with SSE streaming, conversation management."""

import json
import logging
from datetime import date, datetime, timezone

from flask import (
    Blueprint, Response, current_app, jsonify,
    request as flask_request, stream_with_context,
)
from flask_login import login_required, current_user
from openai import OpenAI

from ..extensions import db, csrf
from ..models.ai import AIConversation, AIMessage, AIUsage
from ..services.ai_context_service import build_system_messages
from ..services.ai_tools import TOOL_DEFINITIONS, execute_tool
from ..utils.auth import requires_pro

log = logging.getLogger("nd")

api_ai_bp = Blueprint("api_ai", __name__)


def _check_rate_limit(user_id):
    """Return (allowed: bool, remaining: int, limit: int)."""
    limit = current_app.config.get("AI_DAILY_LIMIT", 25)
    today = date.today()
    usage = (
        AIUsage.query
        .filter_by(user_id=user_id, date=today)
        .first()
    )
    count = usage.query_count if usage else 0
    return count < limit, limit - count, limit


def _increment_usage(user_id):
    today = date.today()
    usage = (
        AIUsage.query
        .filter_by(user_id=user_id, date=today)
        .first()
    )
    if usage:
        usage.query_count += 1
    else:
        usage = AIUsage(user_id=user_id, date=today, query_count=1)
        db.session.add(usage)
    db.session.commit()


# ── Chat endpoint (SSE streaming) ──────────────────────────────


@api_ai_bp.route("/ai/chat", methods=["POST"])
@login_required
@requires_pro
def ai_chat():
    """Stream an AI advisor response via Server-Sent Events."""
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "AI not configured"}), 503

    allowed, remaining, limit = _check_rate_limit(current_user.id)
    if not allowed:
        return jsonify({
            "error": f"Daily AI limit reached ({limit} queries). Resets at midnight.",
            "rate_limited": True,
        }), 429

    data = flask_request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    conversation_id = data.get("conversation_id")

    conversation = _get_or_create_conversation(
        current_user.id, conversation_id, user_message,
    )

    user_msg = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.session.add(user_msg)
    db.session.commit()

    openai_messages = _build_openai_messages(conversation)

    _increment_usage(current_user.id)

    user_id = current_user.id

    @stream_with_context
    def generate():
        client = OpenAI(api_key=api_key)
        full_response = ""

        try:
            messages = list(openai_messages)
            max_tool_rounds = 5

            for _ in range(max_tool_rounds):
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    temperature=0.7,
                    max_tokens=800,
                    stream=True,
                )

                tool_calls_acc = {}
                finished_with_content = False

                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    if delta.content:
                        full_response += delta.content
                        yield f"data: {json.dumps({'token': delta.content})}\n\n"
                        finished_with_content = True

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_acc[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

                if not tool_calls_acc:
                    break

                assistant_msg = {
                    "role": "assistant",
                    "content": full_response or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                        for tc in tool_calls_acc.values()
                    ],
                }
                messages.append(assistant_msg)

                for tc in tool_calls_acc.values():
                    tool_result = execute_tool(
                        tc["name"], tc["arguments"], user_id,
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    })

                full_response = ""

            assistant_record = AIMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response,
            )
            db.session.add(assistant_record)
            conversation.updated_at = datetime.now(timezone.utc)
            db.session.commit()

        except Exception as e:
            log.exception("AI chat stream error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    headers = {
        "X-Conversation-Id": str(conversation.id),
        "X-AI-Remaining": str(max(0, remaining - 1)),
    }
    resp = Response(
        generate(),
        mimetype="text/event-stream",
        headers=headers,
    )
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# Exempt from CSRF since this is an API endpoint using SSE
csrf.exempt(api_ai_bp)


def _get_or_create_conversation(user_id, conversation_id, first_message):
    """Load existing conversation or create a new one."""
    if conversation_id:
        conv = (
            AIConversation.query
            .filter_by(id=conversation_id, user_id=user_id)
            .first()
        )
        if conv:
            return conv

    title = first_message[:80] + ("..." if len(first_message) > 80 else "")
    conv = AIConversation(user_id=user_id, title=title)
    db.session.add(conv)
    db.session.flush()

    system_msgs = build_system_messages(user_id)
    for sm in system_msgs:
        db.session.add(AIMessage(
            conversation_id=conv.id,
            role="system",
            content=sm["content"],
        ))

    db.session.commit()
    return conv


def _build_openai_messages(conversation):
    """Convert DB messages to OpenAI message format."""
    messages = []
    for msg in conversation.messages:
        messages.append({
            "role": msg.role,
            "content": msg.content,
        })
    return messages


# ── Conversation management ─────────────────────────────────────


@api_ai_bp.route("/ai/conversations", methods=["GET"])
@login_required
@requires_pro
def list_conversations():
    """Return the user's AI conversations, most recent first."""
    convs = (
        AIConversation.query
        .filter_by(user_id=current_user.id)
        .order_by(AIConversation.updated_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in convs
        ],
    })


@api_ai_bp.route("/ai/conversations/<int:conv_id>", methods=["GET"])
@login_required
@requires_pro
def get_conversation(conv_id):
    """Return the full message history for a conversation."""
    conv = (
        AIConversation.query
        .filter_by(id=conv_id, user_id=current_user.id)
        .first()
    )
    if not conv:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in conv.messages
            if m.role in ("user", "assistant")
        ],
    })


@api_ai_bp.route("/ai/conversations/<int:conv_id>", methods=["DELETE"])
@login_required
@requires_pro
def delete_conversation(conv_id):
    """Delete a conversation and all its messages."""
    conv = (
        AIConversation.query
        .filter_by(id=conv_id, user_id=current_user.id)
        .first()
    )
    if not conv:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(conv)
    db.session.commit()
    return jsonify({"ok": True})


@api_ai_bp.route("/ai/usage", methods=["GET"])
@login_required
@requires_pro
def ai_usage():
    """Return current daily usage stats."""
    allowed, remaining, limit = _check_rate_limit(current_user.id)
    return jsonify({
        "remaining": remaining,
        "limit": limit,
        "date": date.today().isoformat(),
    })
