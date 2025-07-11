from django.http import HttpResponse
from prometheus_client import generate_latest
from django.conf import settings


def healthz(request):
    return HttpResponse("OK", status=200)


def readyz(request):
    return HttpResponse("OK" if settings.READY else "NOT READY", status=200 if settings.READY else 503)


def metrics(request):
    return HttpResponse(generate_latest(), content_type='text/plain')
