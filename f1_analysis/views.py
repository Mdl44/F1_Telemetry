# Handler pentru procesarea url-urilor
#clase view sau functii care gestioneaza cererile
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from f1_users.decorators import team_member_required
from django.contrib import messages
from django.shortcuts import redirect

@team_member_required #doar membrul echipei poate accesa
def qualifying_analysis(request):
    years = list(range(2022, 2025))
    context = {'years': years}
    return render(request, 'dashboard/qualifying_analysis.html', context) 

@team_member_required
def race_analysis(request):
    years = list(range(2022, 2025))
    context = {'years': years}
    return render(request, 'dashboard/race_analysis.html', context)