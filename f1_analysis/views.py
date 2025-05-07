from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from django.http import JsonResponse
from f1_users.decorators import team_member_required
from f1_analysis.analyzers.db_qualifying_analyzer import DBF1QualifyingAnalyzer
import json
from django.urls import reverse
from f1_analysis.analyzers.db_race_analyzer import DBF1RaceAnalyzer 

def execute_query(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

@team_member_required
def qualifying_analysis(request):
    events = execute_query("""
        SELECT DISTINCT e.event_id, e.event_name, e.year, e.event_date 
        FROM event e
        JOIN session s ON e.event_id = s.event_id
        WHERE s.session_type = 'Q'
        ORDER BY e.year DESC, e.event_date DESC
    """)
    
    context = {'events': events}
    return render(request, 'analysis/qualifying_form.html', context)

@team_member_required
def get_qualifying_drivers(request):
    event_id = request.GET.get('event_id')
    if not event_id:
        return JsonResponse({'drivers': []})
    
    session = execute_query("""
        SELECT session_id FROM session 
        WHERE event_id = %s AND session_type = 'Q'
    """, [event_id])
    
    if not session:
        return JsonResponse({'drivers': []})
    
    session_id = session[0]['session_id']
    
    drivers = execute_query("""
        SELECT DISTINCT d.driver_id, d.driver_code, 
               d.first_name || ' ' || d.last_name as driver_name
        FROM driver d
        JOIN telemetry t ON d.driver_id = t.driver_id
        WHERE t.session_id = %s
        ORDER BY d.driver_code
    """, [session_id])
    
    if not drivers:
        drivers = execute_query("""
            SELECT DISTINCT d.driver_id, d.driver_code, 
                   d.first_name || ' ' || d.last_name as driver_name
            FROM driver d
            JOIN event_entry ee ON d.driver_id = ee.driver_id
            WHERE ee.event_id = %s
            ORDER BY d.driver_code
        """, [event_id])
    
    return JsonResponse({'drivers': drivers})

@team_member_required
def create_qualifying_analysis(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        driver1_id = request.POST.get('driver1_id')
        driver2_id = request.POST.get('driver2_id')
        
        if not event_id or not driver1_id or not driver2_id:
            messages.error(request, "All fields are required")
            return redirect('f1_analysis:qualifying')
            
        if driver1_id == driver2_id:
            messages.error(request, "Please select two different drivers")
            return redirect('f1_analysis:qualifying')
        
        event_data = execute_query("""
            SELECT event_name, year FROM event WHERE event_id = %s
        """, [event_id])
        
        if not event_data:
            messages.error(request, "Event not found")
            return redirect('f1_analysis:qualifying')
            
        event_name = event_data[0]['event_name']
        year = event_data[0]['year']
        
        driver1_data = execute_query("SELECT driver_code FROM driver WHERE driver_id = %s", [driver1_id])
        driver2_data = execute_query("SELECT driver_code FROM driver WHERE driver_id = %s", [driver2_id])
        
        if not driver1_data or not driver2_data:
            messages.error(request, "One or both drivers not found")
            return redirect('f1_analysis:qualifying')
            
        driver1_code = driver1_data[0]['driver_code']
        driver2_code = driver2_data[0]['driver_code']
        
        try:
            db_params = {
                'host': 'localhost',
                'database': 'f1_telemetry',
                'user': 'madalin',
                'password': 'madalin',
                'port': 5432
            }
            
            analyzer = DBF1QualifyingAnalyzer(db_params)
            results = analyzer.run_quali_analysis(
                event_name=event_name,
                year=year,
                drivers=[driver1_code, driver2_code],
                save_to_db=True
            )
            
            if results:
                analysis_id = None
                
                if 'existing_analysis' in results and results['existing_analysis']:
                    analysis_id = results.get('analysis_id')
                else:
                    session = execute_query("""
                        SELECT session_id FROM session 
                        WHERE event_id = %s AND session_type = 'Q'
                    """, [event_id])
                    
                    if session:
                        session_id = session[0]['session_id']
                        
                        recent_analysis = execute_query("""
                            SELECT a.analysis_id 
                            FROM analysis a
                            JOIN race_analysis ra ON a.analysis_id = ra.analysis_id
                            WHERE a.session_id = %s 
                            AND ra.drivers_json::jsonb @> %s
                            ORDER BY a.created_at DESC LIMIT 1
                        """, [
                            session_id, 
                            json.dumps([driver1_code, driver2_code])
                        ])
                        
                        if recent_analysis:
                            analysis_id = recent_analysis[0]['analysis_id']
                
                messages.success(request, f"Qualifying analysis for {driver1_code} vs {driver2_code} at {event_name} {year} created successfully!")
                
                redirect_url = reverse('f1_dashboard:qualifying_analysis_view')
                if analysis_id:
                    redirect_url += f"?event_id={event_id}&analysis_id={analysis_id}"
                else:
                    redirect_url += f"?event_id={event_id}"
                    
                return redirect(redirect_url)
        except Exception as e:
            messages.error(request, f"Analysis error: {str(e)}")
            return redirect('f1_analysis:qualifying')
    
    return redirect('f1_analysis:qualifying')

@team_member_required
def race_analysis(request):
    events = execute_query("""
        SELECT DISTINCT e.event_id, e.event_name, e.year, e.event_date 
        FROM event e
        JOIN session s ON e.event_id = s.event_id
        WHERE s.session_type = 'R'
        ORDER BY e.year DESC, e.event_date DESC
    """)
    
    context = {'events': events}
    return render(request, 'analysis/race_form.html', context)

@team_member_required
def get_race_drivers(request):
    event_id = request.GET.get('event_id')
    if not event_id:
        return JsonResponse({'drivers': []})
    
    session = execute_query("""
        SELECT session_id FROM session 
        WHERE event_id = %s AND session_type = 'R'
    """, [event_id])
    
    if not session:
        return JsonResponse({'drivers': []})
    
    session_id = session[0]['session_id']
    
    drivers = execute_query("""
        SELECT DISTINCT d.driver_id, d.driver_code, 
               d.first_name || ' ' || d.last_name as driver_name
        FROM driver d
        JOIN telemetry t ON d.driver_id = t.driver_id
        WHERE t.session_id = %s
        ORDER BY d.driver_code
    """, [session_id])
    
    if not drivers:
        drivers = execute_query("""
            SELECT DISTINCT d.driver_id, d.driver_code, 
                   d.first_name || ' ' || d.last_name as driver_name
            FROM driver d
            JOIN event_entry ee ON d.driver_id = ee.driver_id
            WHERE ee.event_id = %s
            ORDER BY d.driver_code
        """, [event_id])
    
    return JsonResponse({'drivers': drivers})

@team_member_required
def create_race_analysis(request):
    if request.method == 'POST':
        event_id = request.POST.get('event_id')
        driver1_id = request.POST.get('driver1_id')
        driver2_id = request.POST.get('driver2_id')
        
        if not event_id or not driver1_id or not driver2_id:
            messages.error(request, "All fields are required")
            return redirect('f1_analysis:race')
            
        if driver1_id == driver2_id:
            messages.error(request, "Please select two different drivers")
            return redirect('f1_analysis:race')
        
        event_data = execute_query("""
            SELECT event_name, year FROM event WHERE event_id = %s
        """, [event_id])
        
        if not event_data:
            messages.error(request, "Event not found")
            return redirect('f1_analysis:race')
            
        event_name = event_data[0]['event_name']
        year = event_data[0]['year']
        
        driver1_data = execute_query("SELECT driver_code FROM driver WHERE driver_id = %s", [driver1_id])
        driver2_data = execute_query("SELECT driver_code FROM driver WHERE driver_id = %s", [driver2_id])
        
        if not driver1_data or not driver2_data:
            messages.error(request, "One or both drivers not found")
            return redirect('f1_analysis:race')
            
        driver1_code = driver1_data[0]['driver_code']
        driver2_code = driver2_data[0]['driver_code']
        
        try:
            db_params = {
                'host': 'localhost',
                'database': 'f1_telemetry',
                'user': 'madalin',
                'password': 'madalin',
                'port': 5432
            }
            
            analyzer = DBF1RaceAnalyzer(db_params)
            results = analyzer.run_race_analysis(
                event_name=event_name,
                year=year,
                drivers=[driver1_code, driver2_code],
                save_to_db=True
            )
            
            if results:
                analysis_id = None
                
                if 'existing_analysis' in results and results['existing_analysis']:
                    analysis_id = results.get('analysis_id')
                else:
                    session = execute_query("""
                        SELECT session_id FROM session 
                        WHERE event_id = %s AND session_type = 'R'
                    """, [event_id])
                    
                    if session:
                        session_id = session[0]['session_id']
                        recent_analysis = execute_query("""
                            SELECT a.analysis_id 
                            FROM analysis a
                            JOIN race_analysis ra ON a.analysis_id = ra.analysis_id
                            WHERE a.session_id = %s 
                            AND ra.drivers_json @> %s::jsonb
                            AND jsonb_array_length(ra.drivers_json) = 2
                            ORDER BY a.created_at DESC LIMIT 1
                        """, [session_id, json.dumps([driver1_code, driver2_code])])
                        
                        if recent_analysis:
                            analysis_id = recent_analysis[0]['analysis_id']
                
                messages.success(request, f"Race analysis for {driver1_code} vs {driver2_code} at {event_name} {year} created successfully!")
                
                redirect_url = reverse('f1_dashboard:race_analysis_view')
                if analysis_id:
                    redirect_url += f"?event_id={event_id}&analysis_id={analysis_id}"
                else:
                    redirect_url += f"?event_id={event_id}"
                    
                return redirect(redirect_url)
            else:
                messages.error(request, "Analysis failed. Please check if there is sufficient telemetry data.")
                return redirect('f1_analysis:race')
        except Exception as e:
            messages.error(request, f"Analysis error: {str(e)}")
            return redirect('f1_analysis:race')
    
    return redirect('f1_analysis:race')