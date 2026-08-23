from django.shortcuts import render


def debug_home(request):
    return render(request, "debug/debug.html")