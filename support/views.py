import anthropic
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .chat import MAX_HISTORY_MESSAGES, MAX_MESSAGE_CHARS, run_chat


def _validated_history(raw):
    """Client-held transcript; untrusted, so shape-check hard."""
    if not isinstance(raw, list) or len(raw) > MAX_HISTORY_MESSAGES:
        return None
    history = []
    for entry in raw:
        if not isinstance(entry, dict):
            return None
        role, content = entry.get('role'), entry.get('content')
        if role not in ('user', 'assistant') or not isinstance(content, str):
            return None
        if len(content) > MAX_MESSAGE_CHARS:
            return None
        history.append({'role': role, 'content': content})
    return history


class ChatView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'chat'  # every request costs real money

    def post(self, request):
        if not settings.ANTHROPIC_API_KEY:
            return Response({'detail': 'support chat is not configured'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        message = request.data.get('message')
        if not isinstance(message, str) or not message.strip() \
                or len(message) > MAX_MESSAGE_CHARS:
            return Response({'detail': 'message required'},
                            status=status.HTTP_400_BAD_REQUEST)
        history = _validated_history(request.data.get('history', []))
        if history is None:
            return Response({'detail': 'malformed history'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            reply = run_chat(history, message.strip(), user=request.user)
        except anthropic.RateLimitError:
            return Response({'detail': 'assistant is busy, try again shortly'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except (anthropic.APIStatusError, anthropic.APIConnectionError):
            return Response({'detail': 'assistant unavailable'},
                            status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'reply': reply,
            'history': history + [{'role': 'user', 'content': message.strip()},
                                  {'role': 'assistant', 'content': reply}],
        })
