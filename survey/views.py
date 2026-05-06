from django.shortcuts import render
import json
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import SurveyResponse


@method_decorator(csrf_exempt, name='dispatch')
class SurveyResponseCreateView(View):

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido.'}, status=400)

        likelihood = body.get('likelihood')
        role       = body.get('role')

        if likelihood not in SurveyResponse.Likelihood.values:
            return JsonResponse({'error': f'likelihood inválido. Opciones: {SurveyResponse.Likelihood.values}'}, status=400)

        if role not in SurveyResponse.Role.values:
            return JsonResponse({'error': f'role inválido. Opciones: {SurveyResponse.Role.values}'}, status=400)

        willing_to_pay = body.get('willing_to_pay')
        if role == SurveyResponse.Role.PRO and willing_to_pay is None:
            return JsonResponse({'error': 'willing_to_pay es requerido cuando role es "pro".'}, status=400)

        ip  = _get_client_ip(request)
        ua  = request.META.get('HTTP_USER_AGENT', '')

        survey = SurveyResponse(
            name           = body.get('name') or None,
            email          = body.get('email') or None,
            likelihood     = likelihood,
            role           = role,
            willing_to_pay = willing_to_pay if role == SurveyResponse.Role.PRO else None,
            source         = body.get('source', 'landing_page'),
            ip_address     = ip,
            user_agent     = ua,
        )

        try:
            survey.full_clean()
            survey.save()
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

        return JsonResponse({
            'id':           str(survey.id),
            'submitted_at': survey.submitted_at.isoformat(),
        }, status=201)


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')