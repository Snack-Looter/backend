import logging

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from . import services

logger = logging.getLogger(__name__)


class ChatView(APIView):
    """
    POST /api/chat/
    body: { "message": "..." }
    response: { "reply": "..." } atau { "error": "..." }
    Stateless: tidak menyimpan/menerima riwayat percakapan.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "Pesan tidak boleh kosong"}, status=400)
        try:
            reply = services.ask_gemini(message)
        except Exception:
            logger.exception("Gemini request failed")
            return Response({"error": "Unable to generate response."}, status=502)
        return Response({"reply": reply})
