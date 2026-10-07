import logging
import os
import tempfile
import hashlib

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from agents.profile.pdf_reader import EmptyPDFTextError
from agents.profile.graph import profile_graph
from core.models import Profile


MAX_PDF_SIZE = 10 * 1024 * 1024

logger = logging.getLogger(__name__)


@login_required
@require_POST
def process_profile(request):
    pdf = request.FILES.get("pdf")

    if not pdf:
        return JsonResponse(
            {
                "success": False,
                "error": "Debes seleccionar un archivo PDF."
            },
            status=400
        )

    if not pdf.name.lower().endswith(".pdf"):
        return JsonResponse(
            {
                "success": False,
                "error": "El archivo debe ser un PDF."
            },
            status=400
        )

    if pdf.size > MAX_PDF_SIZE:
        return JsonResponse(
            {
                "success": False,
                "error": "El archivo PDF no puede superar los 10 MB."
            },
            status=400
        )

    temp_path = None

    try:
        document_hasher = hashlib.sha256()

        with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
        ) as temp_file:
            for chunk in pdf.chunks():
                temp_file.write(chunk)
                document_hasher.update(chunk)

            temp_path = temp_file.name

        result = profile_graph.invoke({
            "pdf_path": temp_path,
            "raw_text": "",
            "profile": None
        })

        raw_text = result["raw_text"]

        profile_data = result.get("profile")

        if profile_data is None:
            raise ValueError(
                "No fue posible extraer el perfil del CV."
            )

        profile_dict = profile_data.model_dump()

        profile, created = Profile.objects.update_or_create(
            user=request.user,
            defaults={
                "data": profile_dict,
                "raw_text": raw_text,
                "document_hash": document_hasher.hexdigest(),
                "career_data": {},
            },
        )

        return JsonResponse({
            "success": True,
            "profile": profile.data,
            "created": created
        })

    except EmptyPDFTextError as error:
        logger.exception(error)

        return JsonResponse(
            {
                "success": False,
                "error": str(error),
            },
            status=422,
        )

    except Exception as error:
        logger.exception(error)

        return JsonResponse(
            {
                "success": False,
                "error": str(error)
            },
            status=500
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)