import os
import tempfile

from django.shortcuts import render

from agents.profile.graph import profile_graph

def profile_debug(request):
    context = {}

    if request.method == "POST":
        pdf = request.FILES.get("pdf")

        if not pdf:
            context["error"] = "Debes seleccionar un archivo PDF."
            return render(request, "core/profile_debug.html", context)

        if not pdf.name.lower().endswith(".pdf"):
            context["error"] = "El archivo debe ser un PDF."
            return render(request, "core/profile_debug.html", context)

        temp_path = None

        try:
            # El grafo actualmente recibe una ruta,
            # entonces
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

            context["profile"] = result["profile"].model_dump()
            context["raw_text"] = result["raw_text"]
            context["filename"] = pdf.name

        except Exception as error:
            context["error"] = str(error)

        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    return render(request, "profile_debug.html", context)