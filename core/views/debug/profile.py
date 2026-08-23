import os
import tempfile

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from agents.profile.graph import profile_graph


MAX_PDF_SIZE = 10 * 1024 * 1024


@require_POST
def debug_profile(request):
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
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp_file:

            for chunk in pdf.chunks():
                temp_file.write(chunk)

            temp_path = temp_file.name

        result = profile_graph.invoke({
            "pdf_path": temp_path,
            "raw_text": "",
            "profile": None
        })

        profile = result.get("profile")

        return JsonResponse({
            "success": True,
            "filename": pdf.name,
            "profile": (
                profile.model_dump()
                if profile is not None
                else None
            ),
            "raw_text": result.get("raw_text", "")
        })

    except Exception as error:
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