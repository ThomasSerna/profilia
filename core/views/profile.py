import logging
import os
import tempfile
import hashlib

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from agents.profile.pdf_reader import EmptyPDFTextError
from agents.profile.graph import profile_graph
from agents.profile.schemas import ProfileData
from agents.career.cache import StaleProfileError, get_profile_revision, get_profile_state, persist_career_data
from core.models import Profile
from core.profile_updates import update_profile


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
        previous = Profile.objects.filter(user=request.user).first()
        previous_revision = get_profile_revision(previous) if previous else None
        requested_revision = request.POST.get("profile_revision")
        if requested_revision and requested_revision != previous_revision:
            return JsonResponse({"success": False, "error": "El perfil cambió. Recarga la página."}, status=409)
        document_hasher = hashlib.sha256()

        with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
        ) as temp_file:
            for chunk in pdf.chunks():
                temp_file.write(chunk)
                document_hasher.update(chunk)

            temp_path = temp_file.name

        document_hash = document_hasher.hexdigest()
        if previous and previous.document_hash == document_hash and previous.raw_text.strip():
            previous.refresh_from_db()
            if get_profile_revision(previous) != previous_revision:
                raise StaleProfileError("El perfil cambió mientras revisábamos el archivo. Recarga la página antes de continuar.")
            try:
                ProfileData.model_validate(previous.data)
            except ValidationError:
                pass
            else:
                return JsonResponse({"success": True, "created": False, "reused": True,
                                     **get_profile_state(previous)})

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

        if previous:
            current = Profile.objects.get(pk=previous.pk, user=request.user)
            if get_profile_revision(current) != previous_revision:
                return JsonResponse({"success": False, "error": "El perfil cambió mientras se procesaba el CV. Recarga la página."}, status=409)
            # shortcut: preserve edited lists as a whole; use stable item IDs before adding item-level CV merging.
            for field in current.manual_fields:
                profile_dict[field] = current.data[field]
            profile = update_profile(current, previous_revision, profile_dict,
                                     manual_fields=current.manual_fields, raw_text=raw_text,
                                     document_hash=document_hash)
            created = False
        else:
            profile = update_profile(Profile(user=request.user), "", profile_dict, manual_fields=[],
                                     raw_text=raw_text, document_hash=document_hash)
            created = True

        profile = persist_career_data(profile, get_profile_revision(profile), inference_runs=[{
            "provider": "groq", "model": "openai/gpt-oss-20b", "stage": "profile_extraction",
            "status": "ready", "usage": result.get("extraction_usage", {}),
            "latency_ms": result.get("extraction_latency_ms"),
        }])

        return JsonResponse({
            "success": True,
            **get_profile_state(profile),
            "created": created,
            "reused": False,
        })

    except StaleProfileError as error:
        return JsonResponse({"success": False, "error": str(error)}, status=409)

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
        logger.error("No se pudo procesar el CV (%s).", type(error).__name__)

        return JsonResponse(
            {
                "success": False,
                "error": "No fue posible procesar el CV. Comprueba el archivo e inténtalo de nuevo.",
            },
            status=500
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
