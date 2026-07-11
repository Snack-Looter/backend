import logging

from requests.exceptions import HTTPError, RequestException
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
        except HTTPError as err:
            response = err.response
            if response is not None and response.status_code == 429:
                logger.warning("Gemini quota exhausted: %s", response.text[:500])
                return Response(
                    {
                        "error": (
                            "Gemini sedang sibuk atau kuota free tier sementara habis. "
                            "Coba lagi sebentar ya."
                        )
                    },
                    status=429,
                    headers={"Retry-After": "60"},
                )
            logger.exception("Gemini request failed with HTTP error")
            return Response({"error": "Unable to generate response."}, status=502)
        except RequestException:
            logger.exception("Gemini request failed")
            return Response({"error": "Unable to generate response."}, status=502)
        except Exception:
            logger.exception("Gemini request failed")
            return Response({"error": "Unable to generate response."}, status=502)
        return Response({"reply": reply})
