from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from datetime import datetime
from f1_users.decorators import analyst_required
from django.urls import reverse
from django.http import JsonResponse
from f1_users.decorators import team_member_required


def index(request):
    return render(request, 'dashboard/dashboard.html')


def visualization(request):
    return render(request, 'dashboard/visualization.html')


def team_view(request):
    year = request.GET.get('year', '2024')

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT DISTINCT t.team_id,
                                       t.team_name,
                                       t.team_code
                       FROM team t
                                JOIN
                            driver_team dt ON t.team_id = dt.team_id
                                JOIN
                            driver d ON dt.driver_id = d.driver_id
                       WHERE dt.year = %s
                       ORDER BY t.team_name
                       """, [year])
        columns = [col[0] for col in cursor.description]
        teams = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for team in teams:
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT d.driver_code,
                                  d.first_name || ' ' || d.last_name as full_name,
                                  d.number,
                                  d.is_active
                           FROM driver d
                                    JOIN
                                driver_team dt ON d.driver_id = dt.driver_id
                           WHERE dt.team_id = %s
                             AND dt.year = %s
                           ORDER BY d.driver_code
                           """, [team['team_id'], year])
            columns = [col[0] for col in cursor.description]
            team['drivers'] = [dict(zip(columns, row)) for row in cursor.fetchall()]

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT DISTINCT year
                       FROM driver_team
                       ORDER BY year DESC
                       """)
        available_years = [row[0] for row in cursor.fetchall()]

    context = {
        'teams': teams,
        'selected_year': int(year),
        'available_years': available_years
    }

    return render(request, 'dashboard/team_view.html', context)

def driver_view(request):
    year = request.GET.get('year',2024)
    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT d.driver_id,
                              d.driver_code,
                              d.first_name,
                              d.last_name,
                              d.number,
                              d.country,
                              d.date_of_birth,
                              dt.team_id,
                              t.team_name,
                              t.team_code
                       FROM driver d
                                JOIN
                            driver_team dt ON d.driver_id = dt.driver_id
                                JOIN
                            team t ON dt.team_id = t.team_id
                       WHERE dt.year = %s
                       ORDER BY t.team_name, d.last_name
                       """, [year])
        columns = [col[0] for col in cursor.description]
        drivers = [dict(zip(columns, row)) for row in cursor.fetchall()]

        teams_with_drivers = {}
        for driver in drivers:
            team_id = driver['team_id']
            if team_id not in teams_with_drivers:
                teams_with_drivers[team_id] = {
                    'team_id': team_id,
                    'team_name': driver['team_name'],
                    'team_code': driver['team_code'],
                    'drivers': []
                }
            teams_with_drivers[team_id]['drivers'].append({
                'driver_id': driver['driver_id'],
                'driver_code': driver['driver_code'],
                'full_name': f"{driver['first_name']} {driver['last_name']}",
                'number': driver['number'],
                'country': driver['country'],
                'date_of_birth': driver['date_of_birth'],
                'age': calculate_age(driver['date_of_birth']) if driver['date_of_birth'] else None
            })
            cursor.execute("""
                           SELECT DISTINCT year
                           FROM driver_team
                           ORDER BY year DESC
                           """)
            available_years = [row[0] for row in cursor.fetchall()]

        context = {
            'teams': list(teams_with_drivers.values()),
            'selected_year': int(year),
            'available_years': available_years
        }

        return render(request, 'dashboard/driver_view.html', context)

def event_view(request):
    year = request.GET.get('year', '2024')

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT e.event_id,
                              e.event_name,
                              e.year,
                              e.circuit_name,
                              e.location,
                              e.country,
                              e.event_date,
                              (SELECT COUNT(*)
                               FROM event_entry ee
                               WHERE ee.event_id = e.event_id) as driver_count
                       FROM event e
                       WHERE e.year = %s
                       ORDER BY e.event_date
                       """, [year])
        columns = [col[0] for col in cursor.description]
        events = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for event in events:
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT s.session_id,
                                  s.session_type,
                                  s.session_date
                           FROM session s
                           WHERE s.event_id = %s
                           ORDER BY s.session_date
                           """, [event['event_id']])
            columns = [col[0] for col in cursor.description]
            event['sessions'] = [dict(zip(columns, row)) for row in cursor.fetchall()]

            for session in event['sessions']:
                if session['session_type'] == 'Q':
                    session['type_display'] = 'Qualifying'
                elif session['session_type'] == 'R':
                    session['type_display'] = 'Race'

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT DISTINCT year
                       FROM event
                       ORDER BY year DESC
                       """)
        available_years = [row[0] for row in cursor.fetchall()]

    context = {
        'events': events,
        'selected_year': int(year),
        'available_years': available_years
    }

    return render(request, 'dashboard/event_view.html', context)


def entry_view(request):
    event_id = request.GET.get('event_id')
    year = request.GET.get('year', '2024')

    if not event_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT event_id
                           FROM event
                           WHERE year = %s
                           ORDER BY event_date
                               LIMIT 1
                           """, [year])
            result = cursor.fetchone()
            if result:
                event_id = result[0]

    event_info = None
    if event_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT *
                           FROM event
                           WHERE event_id = %s
                           """, [event_id])
            columns = [col[0] for col in cursor.description]
            event_info = dict(zip(columns, cursor.fetchone())) if cursor.rowcount else None

    entries = []
    if event_id:
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT ee.entry_id,
                                  d.driver_code,
                                  d.first_name || ' ' || d.last_name as driver_name,
                                  d.number,
                                  t.team_name,
                                  t.team_id
                           FROM event_entry ee
                                    JOIN
                                driver d ON ee.driver_id = d.driver_id
                                    JOIN
                                team t ON ee.team_id = t.team_id
                           WHERE ee.event_id = %s
                           ORDER BY d.number
                           """, [event_id])
            columns = [col[0] for col in cursor.description]
            entries = [dict(zip(columns, row)) for row in cursor.fetchall()]

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT event_id,
                              event_name,
                              circuit_name,
                              event_date
                       FROM event
                       WHERE
                           year = %s
                       ORDER BY
                           event_date
                       """, [year])
        columns = [col[0] for col in cursor.description]
        events = [dict(zip(columns, row)) for row in cursor.fetchall()]

    with connection.cursor() as cursor:
        cursor.execute("""
                       SELECT DISTINCT year
                       FROM event
                       ORDER BY year DESC
                       """)
        available_years = [row[0] for row in cursor.fetchall()]

    context = {
        'event_info': event_info,
        'entries': entries,
        'events': events,
        'selected_event': int(event_id) if event_id else None,
        'selected_year': int(year),
        'available_years': available_years
    }

    return render(request, 'dashboard/entry_view.html', context)


def telemetry_view(request):

    event_id = request.GET.get('event_id')
    session_id = request.GET.get('session_id')
    driver_id = request.GET.get('driver_id')
    lap_number = request.GET.get('lap_number')

    events = execute_query("""
                           SELECT e.event_id, e.event_name, e.event_date
                           FROM event e
                           WHERE EXISTS (SELECT 1
                                         FROM session s
                                         WHERE s.event_id = e.event_id
                                           AND EXISTS (SELECT 1
                                                       FROM telemetry t
                                                       WHERE t.session_id = s.session_id))
                           ORDER BY e.event_date
                           """)

    if not event_id and events:
        event_id = events[0]['event_id']

    sessions = []
    if event_id:
        sessions = execute_query("""
                                 SELECT s.session_id, s.session_type, s.session_date
                                 FROM session s
                                 WHERE s.event_id = %s
                                   AND EXISTS (SELECT 1
                                               FROM telemetry t
                                               WHERE t.session_id = s.session_id)
                                 ORDER BY s.session_date
                                 """, [event_id])

        for session in sessions:
            if session['session_type'] == 'Q':
                session['display_type'] = 'Qualifying'
            elif session['session_type'] == 'R':
                session['display_type'] = 'Race'

    if not session_id and sessions:
        session_id = sessions[0]['session_id']

    drivers = []
    if session_id:
        drivers = execute_query("""
                                SELECT DISTINCT d.driver_id,
                                                d.driver_code,
                                                d.first_name || ' ' || d.last_name as driver_name
                                FROM telemetry t
                                         JOIN driver d ON t.driver_id = d.driver_id
                                WHERE t.session_id = %s
                                ORDER BY d.driver_code
                                """, [session_id])

    if not driver_id and drivers:
        driver_id = drivers[0]['driver_id']

    laps = []
    if session_id and driver_id:
        laps = execute_query("""
                             SELECT DISTINCT CAST(lap_number AS INTEGER) as lap_number
                             FROM telemetry
                             WHERE session_id = %s
                               AND driver_id = %s
                               AND lap_number IS NOT NULL
                               AND lap_number > 0
                               AND lap_number = lap_number
                               AND lap_number <= 200 
                             ORDER BY lap_number
                             """, [session_id, driver_id])

    telemetry_data = []
    message = None

    if session_id and driver_id:
        query = """
                SELECT telemetry_id,
                       time_str,
                       speed, 
                       throttle, 
                       brake, 
                       rpm, 
                       drs, 
                       lap_number, 
                       lap_time, 
                       position,
                       is_fastest_lap,
                       tire_compound,
                       tyre_life,
                       sector1_time,
                       sector2_time,
                       sector3_time
                FROM telemetry
                WHERE session_id = %s
                  AND driver_id = %s
                """
        params = [session_id, driver_id]

        if lap_number:
            query += " AND lap_number = %s"
            params.append(lap_number)

        query += " ORDER BY lap_number, time_str"

        telemetry_data = execute_query(query, params)

        if not telemetry_data:
            message = "No telemetry data found for the selected filters."
    else:
        message = "Please select an event, session, and driver to view telemetry data."

    event_info = None
    session_info = None
    driver_info = None

    if event_id:
        event_results = execute_query("SELECT * FROM event WHERE event_id = %s", [event_id])
        if event_results:
            event_info = event_results[0]

    if session_id:
        session_results = execute_query("SELECT * FROM session WHERE session_id = %s", [session_id])
        if session_results:
            session_info = session_results[0]
            if session_info['session_type'] == 'Q':
                session_info['display_type'] = 'Qualifying'
            elif session_info['session_type'] == 'R':
                session_info['display_type'] = 'Race'

    if driver_id:
        driver_results = execute_query("""
                                       SELECT driver_id,
                                              driver_code,
                                              first_name || ' ' || last_name as full_name,
                                              number
                                       FROM driver
                                       WHERE driver_id = %s
                                       """, [driver_id])
        if driver_results:
            driver_info = driver_results[0]

    context = {
        'events': events,
        'sessions': sessions,
        'drivers': drivers,
        'laps': laps,
        'telemetry_data': telemetry_data,
        'selected_event': int(event_id) if event_id else None,
        'selected_session': int(session_id) if session_id else None,
        'selected_driver': int(driver_id) if driver_id else None,
        'selected_lap': int(float(lap_number)) if lap_number else None,
        'message': message,
        'event_info': event_info,
        'session_info': session_info,
        'driver_info': driver_info
    }

    return render(request, 'dashboard/telemetry_view.html', context)


def qualifying_analysis_view(request):

    event_id = request.GET.get('event_id')
    analysis_id = request.GET.get('analysis_id')
    
    auto_select = event_id and not analysis_id

    events = execute_query("""
                           SELECT DISTINCT e.event_id, e.event_name, e.year, e.event_date
                           FROM event e
                                    JOIN session s ON e.event_id = s.event_id
                                    JOIN analysis a ON s.session_id = a.session_id
                                    JOIN quali_analysis qa ON a.analysis_id = qa.analysis_id
                           WHERE a.analysis_type = 'qualifying'
                           ORDER BY e.year DESC, e.event_date DESC
                           """)

    if not event_id and events:
        event_id = events[0]['event_id']

    analyses = []
    if event_id:
        analyses = execute_query("""
                                 SELECT a.analysis_id,
                                        a.analysis_name,
                                        a.created_at,
                                        qa.driver1_code,
                                        qa.driver2_code
                                 FROM analysis a
                                          JOIN session s ON a.session_id = s.session_id
                                          JOIN quali_analysis qa ON a.analysis_id = qa.analysis_id
                                 WHERE s.event_id = %s
                                   AND a.analysis_type = 'qualifying'
                                 ORDER BY a.created_at DESC
                                 """, [event_id])

    if auto_select and analyses:
        first_analysis_id = analyses[0]['analysis_id']
        return redirect(f"{request.path}?event_id={event_id}&analysis_id={first_analysis_id}")
    
    if not analysis_id and analyses:
        analysis_id = analyses[0]['analysis_id']

    analysis_details = None
    if analysis_id:
        analysis_results = execute_query("""
                                         SELECT a.analysis_id,
                                                a.analysis_name,
                                                a.event_name,
                                                a.year,
                                                qa.driver1_code,
                                                qa.driver2_code,
                                                qa.markdown_insights,
                                                qa.delta_plot_path,
                                                qa.speed_plot_path
                                         FROM analysis a
                                                  JOIN quali_analysis qa ON a.analysis_id = qa.analysis_id
                                         WHERE a.analysis_id = %s
                                         """, [analysis_id])

        if analysis_results:
            analysis_details = analysis_results[0]

    context = {
        'events': events,
        'analyses': analyses,
        'analysis_details': analysis_details,
        'selected_event': int(event_id) if event_id else None,
        'selected_analysis': int(analysis_id) if analysis_id else None
    }

    return render(request, 'dashboard/qualifying_analysis_view.html', context)


def race_analysis_view(request):
    import json
    event_id = request.GET.get('event_id')
    analysis_id = request.GET.get('analysis_id')
    
    auto_select = event_id and not analysis_id

    events = execute_query("""
                           SELECT DISTINCT e.event_id, e.event_name, e.year, e.event_date
                           FROM event e
                                    JOIN session s ON e.event_id = s.event_id
                                    JOIN analysis a ON s.session_id = a.session_id
                                    JOIN race_analysis ra ON a.analysis_id = ra.analysis_id
                           WHERE a.analysis_type = 'race'
                           ORDER BY e.year DESC, e.event_date DESC
                           """)

    if not event_id and events:
        event_id = events[0]['event_id']

    analyses = []
    if event_id:
        analyses = execute_query("""
                                 SELECT a.analysis_id, ra.drivers_json
                                 FROM analysis a
                                          JOIN race_analysis ra ON a.analysis_id = ra.analysis_id
                                          JOIN session s ON a.session_id = s.session_id
                                 WHERE a.analysis_type = 'race'
                                   AND s.event_id = %s
                                 ORDER BY a.created_at DESC
                                 """, [event_id])
        
        for analysis in analyses:
            if 'drivers_json' in analysis and analysis['drivers_json']:
                drivers = json.loads(analysis['drivers_json'])
                if len(drivers) >= 2:
                    analysis['driver1_code'] = drivers[0]
                    analysis['driver2_code'] = drivers[1]
    
    if auto_select and analyses:
        first_analysis_id = analyses[0]['analysis_id']
        return redirect(f"{request.path}?event_id={event_id}&analysis_id={first_analysis_id}")

    if not analysis_id and analyses:
        analysis_id = analyses[0]['analysis_id']

    analysis_details = None
    if analysis_id:
        results = execute_query("""
                                SELECT a.*,
                                       ra.drivers_json,
                                       ra.markdown_insights,
                                       ra.lap_times_plot_path,
                                       ra.tire_strategy_plot_path,
                                       ra.position_plot_path
                                FROM analysis a
                                         JOIN race_analysis ra ON a.analysis_id = ra.analysis_id
                                WHERE a.analysis_id = %s
                                """, [analysis_id])

        if results:
            analysis_details = results[0]
            if 'drivers_json' in analysis_details and analysis_details['drivers_json']:
                drivers = json.loads(analysis_details['drivers_json'])
                if len(drivers) >= 2:
                    analysis_details['driver1_code'] = drivers[0]
                    analysis_details['driver2_code'] = drivers[1]

    context = {
        'events': events,
        'analyses': analyses,
        'analysis_details': analysis_details,
        'selected_event': int(event_id) if event_id else None,
        'selected_analysis': int(analysis_id) if analysis_id else None
    }

    return render(request, 'dashboard/race_analysis_view.html', context)

@analyst_required
def driver_create(request):
    teams = execute_query("SELECT team_id, team_name FROM team ORDER BY team_name")
    years = range(2022,2025)
    
    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                driver_code = request.POST.get('driver_code').upper()
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                number = request.POST.get('number')
                country = request.POST.get('country')
                date_of_birth = request.POST.get('date_of_birth')
                is_active = 'is_active' in request.POST
                
                team_id = request.POST.get('team_id')
                year = request.POST.get('year')
                
                cursor.execute("BEGIN")
                
                cursor.execute("""
                    INSERT INTO driver 
                    (driver_code, first_name, last_name, number, country, date_of_birth, is_active) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING driver_id
                """, [driver_code, first_name, last_name, number, country, date_of_birth, is_active])
                
                driver_id = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO driver_team
                    (driver_id, team_id, year)
                    VALUES (%s, %s, %s)
                """, [driver_id, team_id, year])
                
                cursor.execute("COMMIT")
                
                messages.success(request, f'Driver {driver_code} ({first_name} {last_name}) added successfully!')
                return redirect('f1_dashboard:driver_view')
                
        except Exception as e:
            with connection.cursor() as cursor:
                cursor.execute("ROLLBACK")
            messages.error(request, f'Error adding driver: {str(e)}')
    
    context = {
        'teams': teams,
        'years': years,
        'action': 'Add'
    }
    
    return render(request, 'dashboard/driver_form.html', context)

@analyst_required
def driver_edit(request, driver_id):
    teams = execute_query("SELECT team_id, team_name FROM team ORDER BY team_name")
    years = range(2022,2025)
    
    try:
        driver_data = execute_query("SELECT * FROM driver WHERE driver_id = %s", [driver_id])
        if not driver_data:
            messages.error(request, f"Driver with ID {driver_id} not found")
            return redirect('f1_dashboard:driver_view')
            
        driver = driver_data[0]
        
        driver_team_data = execute_query("""
            SELECT dt.* FROM driver_team dt 
            WHERE dt.driver_id = %s
            ORDER BY dt.year DESC
            LIMIT 1
        """, [driver_id])
        
        driver_team = driver_team_data[0] if driver_team_data else {'team_id': '', 'year': datetime.now().year}
        
        if request.method == 'POST':
            try:
                with connection.cursor() as cursor:
                    first_name = request.POST.get('first_name')
                    last_name = request.POST.get('last_name')
                    number = request.POST.get('number')
                    country = request.POST.get('country')
                    date_of_birth = request.POST.get('date_of_birth')
                    is_active = 'is_active' in request.POST
                    
                    team_id = request.POST.get('team_id')
                    year = request.POST.get('year')
                    
                    cursor.execute("BEGIN")
                    
                    cursor.execute("""
                        UPDATE driver 
                        SET first_name = %s, last_name = %s, number = %s, country = %s, 
                            date_of_birth = %s, is_active = %s
                        WHERE driver_id = %s
                    """, [first_name, last_name, number, country, date_of_birth, is_active, driver_id])
                    
                    cursor.execute("""
                        SELECT driver_team_id FROM driver_team
                        WHERE driver_id = %s AND year = %s
                    """, [driver_id, year])
                    
                    existing_entry = cursor.fetchone()
                    
                    if existing_entry:
                        cursor.execute("""
                            UPDATE driver_team
                            SET team_id = %s
                            WHERE driver_id = %s AND year = %s
                        """, [team_id, driver_id, year])
                    else:
                        cursor.execute("""
                            INSERT INTO driver_team
                            (driver_id, team_id, year)
                            VALUES (%s, %s, %s)
                        """, [driver_id, team_id, year])
                    
                    cursor.execute("COMMIT")
                    
                    messages.success(request, f'Driver {driver["driver_code"]} updated successfully!')
                    return redirect('f1_dashboard:driver_view')
                    
            except Exception as e:
                with connection.cursor() as cursor:
                    cursor.execute("ROLLBACK")
                messages.error(request, f'Error updating driver: {str(e)}')
        
        context = {
            'driver': driver,
            'driver_team': driver_team,
            'teams': teams,
            'years': years,
            'action': 'Edit'
        }
        
        return render(request, 'dashboard/driver_form.html', context)
        
    except Exception as e:
        messages.error(request, f'Error retrieving driver data: {str(e)}')
        return redirect('f1_dashboard:driver_view')

@analyst_required
def driver_delete(request, driver_id):
    try:
        driver_data = execute_query("""
            SELECT driver_id, driver_code, first_name, last_name
            FROM driver WHERE driver_id = %s
        """, [driver_id])
        
        if not driver_data:
            messages.error(request, f"Driver with ID {driver_id} not found")
            return redirect('f1_dashboard:driver_view')
            
        driver = driver_data[0]
        
        if request.method == 'POST':
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                
                cursor.execute("DELETE FROM driver WHERE driver_id = %s", [driver_id])
                
                cursor.execute("COMMIT")
                
                messages.success(request, f'Driver {driver["driver_code"]} deleted successfully!')
                return redirect('f1_dashboard:driver_view')
                
        return render(request, 'dashboard/driver_confirm_delete.html', {'driver': driver})
        
    except Exception as e:
        with connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
        messages.error(request, f'Error deleting driver: {str(e)}')
        return redirect('f1_dashboard:driver_view')
 
@analyst_required
def telemetry_create(request):
    sessions = execute_query("""
        SELECT s.session_id, 
               e.event_name, 
               s.session_type, 
               s.session_date
        FROM session s
        JOIN event e ON s.event_id = e.event_id
        ORDER BY s.session_date DESC
    """)
    
    for session in sessions:
        if session['session_type'] == 'Q':
            session['display_name'] = f"{session['event_name']} - Qualifying"
        elif session['session_type'] == 'R':
            session['display_name'] = f"{session['event_name']} - Race"
        else:
            session['display_name'] = f"{session['event_name']} - {session['session_type']}"
    
    drivers = execute_query("""
        SELECT driver_id, driver_code, first_name, last_name
        FROM driver
        ORDER BY driver_code
    """)
    
    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                
                session_id = request.POST.get('session_id')
                driver_id = request.POST.get('driver_id')
                lap_number = request.POST.get('lap_number')
                time_str = request.POST.get('time_str')
                
                speed = request.POST.get('speed')
                speed = None if speed == '' else speed
                
                throttle = request.POST.get('throttle')
                throttle = None if throttle == '' else throttle
                
                rpm = request.POST.get('rpm')
                rpm = None if rpm == '' else rpm
                
                position = request.POST.get('position')
                position = None if position == '' else position
                
                tyre_life = request.POST.get('tyre_life')
                tyre_life = None if tyre_life == '' else tyre_life
                
                brake = True if 'brake' in request.POST else False
                drs = 1 if 'drs' in request.POST else 0
                is_fastest_lap = True if 'is_fastest_lap' in request.POST else False
                
                tire_compound = request.POST.get('tire_compound')
                
                lap_time = request.POST.get('lap_time')
                lap_time = None if lap_time == '' else lap_time
                
                sector1_time = request.POST.get('sector1_time')
                sector1_time = None if sector1_time == '' else sector1_time
                
                sector2_time = request.POST.get('sector2_time')
                sector2_time = None if sector2_time == '' else sector2_time
                
                sector3_time = request.POST.get('sector3_time')
                sector3_time = None if sector3_time == '' else sector3_time
                tyre_life = request.POST.get('tyre_life') or None
                is_fastest_lap = True if 'is_fastest_lap' in request.POST else False
                
                cursor.execute("""
                    INSERT INTO telemetry 
                    (session_id, driver_id, lap_number, time_str, speed, throttle, 
                     brake, rpm, drs, position, lap_time, sector1_time, sector2_time, 
                     sector3_time, tire_compound, tyre_life, is_fastest_lap)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING telemetry_id
                """, [session_id, driver_id, lap_number, time_str, speed, throttle, 
                     brake, rpm, drs, position, lap_time, sector1_time, sector2_time, 
                     sector3_time, tire_compound, tyre_life, is_fastest_lap])
                
                telemetry_id = cursor.fetchone()[0]

                cursor.execute("COMMIT")
                
                messages.success(request, f'Telemetry data point added successfully (ID: {telemetry_id})')
                
                url = reverse('f1_dashboard:telemetry_view')
            return redirect(f"{url}?session_id={session_id}&driver_id={driver_id}&lap_number={lap_number}")
                
        except Exception as e:
            with connection.cursor() as cursor:
                cursor.execute("ROLLBACK")
            messages.error(request, f'Error adding telemetry data: {str(e)}')
    
    context = {
        'sessions': sessions,
        'drivers': drivers,
        'action': 'Add'
    }
    
    return render(request, 'dashboard/telemetry_form.html', context)

@analyst_required
def telemetry_edit(request, telemetry_id):
    sessions = execute_query("""
        SELECT s.session_id, 
               e.event_name, 
               s.session_type, 
               s.session_date
        FROM session s
        JOIN event e ON s.event_id = e.event_id
        ORDER BY s.session_date DESC
    """)
    
    for session in sessions:
        if session['session_type'] == 'Q':
            session['display_name'] = f"{session['event_name']} - Qualifying"
        elif session['session_type'] == 'R':
            session['display_name'] = f"{session['event_name']} - Race"
        else:
            session['display_name'] = f"{session['event_name']} - {session['session_type']}"
    
    drivers = execute_query("""
        SELECT driver_id, driver_code, first_name, last_name
        FROM driver
        ORDER BY driver_code
    """)
    
    try:
        telemetry_data = execute_query("SELECT * FROM telemetry WHERE telemetry_id = %s", [telemetry_id])
        
        if not telemetry_data:
            messages.error(request, f"Telemetry data with ID {telemetry_id} not found")
            return redirect('f1_dashboard:telemetry_view')
        
        telemetry = telemetry_data[0]
        
        if request.method == 'POST':
            try:
                with connection.cursor() as cursor:
                    cursor.execute("BEGIN")
                    
                    session_id = request.POST.get('session_id')
                    driver_id = request.POST.get('driver_id')
                    lap_number = request.POST.get('lap_number')
                    time_str = request.POST.get('time_str')
                    
                    speed = request.POST.get('speed')
                    speed = None if speed == '' else speed
                    
                    throttle = request.POST.get('throttle')
                    throttle = None if throttle == '' else throttle
                    
                    rpm = request.POST.get('rpm')
                    rpm = None if rpm == '' else rpm
                    
                    position = request.POST.get('position')
                    position = None if position == '' else position
                    
                    tyre_life = request.POST.get('tyre_life')
                    tyre_life = None if tyre_life == '' else tyre_life
                    
                    brake = True if 'brake' in request.POST else False
                    drs = 1 if 'drs' in request.POST else 0
                    is_fastest_lap = True if 'is_fastest_lap' in request.POST else False
                    
                    tire_compound = request.POST.get('tire_compound')
                    
                    lap_time = request.POST.get('lap_time')
                    lap_time = None if lap_time == '' else lap_time
                    
                    sector1_time = request.POST.get('sector1_time')
                    sector1_time = None if sector1_time == '' else sector1_time
                    
                    sector2_time = request.POST.get('sector2_time')
                    sector2_time = None if sector2_time == '' else sector2_time
                    
                    sector3_time = request.POST.get('sector3_time')
                    sector3_time = None if sector3_time == '' else sector3_time
                    
                    cursor.execute("""
                        UPDATE telemetry
                        SET session_id = %s, driver_id = %s, lap_number = %s, time_str = %s,
                            speed = %s, throttle = %s, brake = %s, rpm = %s, drs = %s,
                            position = %s, lap_time = %s, sector1_time = %s, sector2_time = %s,
                            sector3_time = %s, tire_compound = %s, tyre_life = %s, is_fastest_lap = %s
                        WHERE telemetry_id = %s
                    """, [session_id, driver_id, lap_number, time_str, speed, throttle, 
                        brake, rpm, drs, position, lap_time, sector1_time, sector2_time, 
                        sector3_time, tire_compound, tyre_life, is_fastest_lap, telemetry_id])
                        
                    cursor.execute("COMMIT")
                    
                    messages.success(request, f'Telemetry data updated successfully')
                    
                url = reverse('f1_dashboard:telemetry_view')
                return redirect(f"{url}?session_id={session_id}&driver_id={driver_id}&lap_number={lap_number}")
                
                    
            except Exception as e:
                with connection.cursor() as cursor:
                    cursor.execute("ROLLBACK")
                messages.error(request, f'Error updating telemetry data: {str(e)}')
        
        context = {
            'telemetry': telemetry,
            'sessions': sessions,
            'drivers': drivers,
            'action': 'Edit'
        }
        
        return render(request, 'dashboard/telemetry_form.html', context)
        
    except Exception as e:
        messages.error(request, f'Error retrieving telemetry data: {str(e)}')
        return redirect('f1_dashboard:telemetry_view')

@analyst_required
def telemetry_delete(request, telemetry_id):
    try:
        telemetry_data = execute_query("""
            SELECT t.telemetry_id, t.time_str, t.lap_number, 
                   d.driver_code, e.event_name, s.session_type
            FROM telemetry t
            JOIN driver d ON t.driver_id = d.driver_id
            JOIN session s ON t.session_id = s.session_id
            JOIN event e ON s.event_id = e.event_id
            WHERE t.telemetry_id = %s
        """, [telemetry_id])
        
        if not telemetry_data:
            messages.error(request, f"Telemetry data with ID {telemetry_id} not found")
            return redirect('f1_dashboard:telemetry_view')
        
        telemetry = telemetry_data[0]
        
        if telemetry['session_type'] == 'Q':
            telemetry['session_display'] = 'Qualifying'
        elif telemetry['session_type'] == 'R':
            telemetry['session_display'] = 'Race'
        else:
            telemetry['session_display'] = telemetry['session_type']
        
        if request.method == 'POST':
            try:
                with connection.cursor() as cursor:
                    cursor.execute("BEGIN")
                    
                    cursor.execute("DELETE FROM telemetry WHERE telemetry_id = %s", [telemetry_id])
                    
                    cursor.execute("COMMIT")
                    
                    messages.success(request, f'Telemetry data deleted successfully')
                    return redirect('f1_dashboard:telemetry_view')
                    
            except Exception as e:
                with connection.cursor() as cursor:
                    cursor.execute("ROLLBACK")
                messages.error(request, f'Error deleting telemetry data: {str(e)}')
        
        context = {
            'telemetry': telemetry
        }
        
        return render(request, 'dashboard/telemetry_confirm_delete.html', context)
        
    except Exception as e:
        messages.error(request, f'Error retrieving telemetry data: {str(e)}')
        return redirect('f1_dashboard:telemetry_view')


def execute_query(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def calculate_age(birth_date):
    from datetime import date
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))



#------------------------------------------#
@team_member_required
def data_quality_view(request):
    events = execute_query("""
        SELECT e.event_id, e.event_name, e.year, e.circuit_name, e.event_date
        FROM event e
        JOIN session s ON e.event_id = s.event_id
        WHERE EXISTS (
            SELECT 1 
            FROM telemetry t 
            WHERE t.session_id = s.session_id
        )
        GROUP BY e.event_id, e.event_name, e.year, e.circuit_name, e.event_date
        ORDER BY e.year DESC, e.event_date DESC
    """)
    
    context = {
        'events': events
    }
    
    return render(request, 'dashboard/data_quality.html', context)


@team_member_required
def event_data_quality(request):
    import math
    
    event_id = request.GET.get('event_id')
    
    if not event_id:
        return JsonResponse({'error': 'Event ID is required'}, status=400)
    
    event_info = execute_query("""
        SELECT event_id, event_name, year, circuit_name
        FROM event
        WHERE event_id = %s
    """, [event_id])
    
    if not event_info:
        return JsonResponse({'error': 'Event not found'}, status=404)
    
    overall_stats = execute_query("""
        SELECT 
            COUNT(*) as total_data_points,
            SUM(CASE 
                WHEN (speed IS NULL OR speed::text = 'NaN' OR
                     throttle IS NULL OR throttle::text = 'NaN' OR
                     brake IS NULL OR
                     rpm IS NULL OR rpm::text = 'NaN' OR
                     drs IS NULL OR
                     lap_number IS NULL OR lap_number::text = 'NaN' OR
                     lap_time IS NULL OR lap_time = 'No time' OR
                     position IS NULL OR
                     tire_compound IS NULL OR tire_compound = '' OR
                     tyre_life IS NULL OR tyre_life::text = 'NaN' OR
                     sector1_time IS NULL OR sector1_time::text = 'NaN' OR
                     sector2_time IS NULL OR sector2_time::text = 'NaN' OR
                     sector3_time IS NULL OR sector3_time::text = 'NaN')
                THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as valid_data_pct,
            
            SUM(CASE WHEN speed IS NULL OR speed::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as speed_complete_pct,
            SUM(CASE WHEN throttle IS NULL OR throttle::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as throttle_complete_pct,
            SUM(CASE WHEN brake IS NULL THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as brake_complete_pct,
            SUM(CASE WHEN rpm IS NULL OR rpm::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as rpm_complete_pct,
            SUM(CASE WHEN drs IS NULL THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as drs_complete_pct,
            SUM(CASE WHEN lap_number IS NULL OR lap_number::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as lap_number_complete_pct,
            SUM(CASE WHEN lap_time IS NULL OR lap_time = 'No time' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as lap_time_complete_pct,
            SUM(CASE WHEN position IS NULL THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as position_complete_pct,
            SUM(CASE WHEN tire_compound IS NULL OR tire_compound = '' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as tire_compound_complete_pct,
            SUM(CASE WHEN tyre_life IS NULL OR tyre_life::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as tyre_life_complete_pct,
            SUM(CASE WHEN sector1_time IS NULL OR sector1_time::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as sector1_complete_pct,
            SUM(CASE WHEN sector2_time IS NULL OR sector2_time::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as sector2_complete_pct,
            SUM(CASE WHEN sector3_time IS NULL OR sector3_time::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as sector3_complete_pct
        FROM telemetry t
        JOIN session s ON t.session_id = s.session_id
        WHERE s.event_id = %s
    """, [event_id])
    
    if not overall_stats or overall_stats[0]['total_data_points'] == 0:
        return JsonResponse({'error': 'No telemetry data found for this event'}, status=404)
    
    stats = overall_stats[0]
    all_metrics = [
        'valid_data_pct', 'speed_complete_pct', 'throttle_complete_pct', 'brake_complete_pct', 
        'rpm_complete_pct', 'drs_complete_pct', 'lap_number_complete_pct', 
        'lap_time_complete_pct', 'position_complete_pct', 
        'tire_compound_complete_pct', 'tyre_life_complete_pct',
        'sector1_complete_pct', 'sector2_complete_pct', 'sector3_complete_pct'
    ]
    
    for key in all_metrics:
        if key in stats and (stats[key] is None or (isinstance(stats[key], float) and math.isnan(stats[key]))):
            stats[key] = 0
    
    driver_stats = execute_query("""
        SELECT 
            d.driver_id,
            d.driver_code,
            COUNT(*) as total_points,
            SUM(CASE 
                WHEN (t.speed IS NULL OR t.speed::text = 'NaN' OR
                     t.throttle IS NULL OR t.throttle::text = 'NaN' OR
                     t.brake IS NULL OR
                     t.rpm IS NULL OR t.rpm::text = 'NaN' OR
                     t.drs IS NULL OR
                     t.lap_number IS NULL OR t.lap_number::text = 'NaN' OR
                     t.lap_time IS NULL OR t.lap_time = 'No time' OR
                     t.position IS NULL OR
                     t.tire_compound IS NULL OR t.tire_compound = '' OR
                     t.tyre_life IS NULL OR t.tyre_life::text = 'NaN' OR
                     t.sector1_time IS NULL OR t.sector1_time::text = 'NaN' OR
                     t.sector2_time IS NULL OR t.sector2_time::text = 'NaN' OR
                     t.sector3_time IS NULL OR t.sector3_time::text = 'NaN')
                THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as valid_data_pct,
            
            SUM(CASE WHEN t.speed IS NULL OR t.speed::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as speed_complete_pct,
            SUM(CASE WHEN t.throttle IS NULL OR t.throttle::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as throttle_complete_pct,
            SUM(CASE WHEN t.brake IS NULL THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as brake_complete_pct,
            SUM(CASE WHEN t.rpm IS NULL OR t.rpm::text = 'NaN' THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as rpm_complete_pct,
            COUNT(DISTINCT CASE WHEN t.lap_number IS NOT NULL AND t.lap_number::text != 'NaN' THEN t.lap_number END) as lap_count,
            MAX(CASE WHEN t.lap_number::text != 'NaN' THEN t.lap_number END) as max_lap
        FROM telemetry t
        JOIN session s ON t.session_id = s.session_id
        JOIN driver d ON t.driver_id = d.driver_id
        WHERE s.event_id = %s
        GROUP BY d.driver_id, d.driver_code
        ORDER BY d.driver_code
    """, [event_id])
    
    for driver in driver_stats:
        if 'valid_data_pct' in driver and (driver['valid_data_pct'] is None or 
                                          (isinstance(driver['valid_data_pct'], float) and math.isnan(driver['valid_data_pct']))):
            driver['valid_data_pct'] = 0
        
        driver['usable_data_percentage'] = round(driver.get('valid_data_pct', 0), 2)
        driver['erroneous_data_percentage'] = round(100 - driver['usable_data_percentage'], 2)
        
        max_lap = driver.get('max_lap')
        lap_count = driver.get('lap_count', 0) or 0
        
        if max_lap is None or (isinstance(max_lap, float) and math.isnan(max_lap)):
            driver['max_lap'] = None
            driver['incomplete_laps'] = 0
        else:
            driver['incomplete_laps'] = max(0, max_lap - lap_count)
    
    return JsonResponse({
        'event': event_info[0],
        'overall_stats': {
            'total_data_points': stats['total_data_points'],
            'usable_data_percentage': round(stats['valid_data_pct'], 2),
            'erroneous_data_percentage': round(100 - stats['valid_data_pct'], 2),
            'metrics': {
                'speed': round(stats['speed_complete_pct'], 2),
                'throttle': round(stats['throttle_complete_pct'], 2),
                'brake': round(stats['brake_complete_pct'], 2),
                'rpm': round(stats['rpm_complete_pct'], 2),
                'drs': round(stats['drs_complete_pct'], 2),
                'lap_number': round(stats['lap_number_complete_pct'], 2),
                'lap_time': round(stats['lap_time_complete_pct'], 2),
                'position': round(stats['position_complete_pct'], 2),
                'tire_compound': round(stats['tire_compound_complete_pct'], 2),
                'tyre_life': round(stats['tyre_life_complete_pct'], 2),
                'sector1': round(stats['sector1_complete_pct'], 2),
                'sector2': round(stats['sector2_complete_pct'], 2),
                'sector3': round(stats['sector3_complete_pct'], 2)
            }
        },
        'drivers': driver_stats
    })

@team_member_required
def driver_data_quality(request):
    """API endpoint pentru datele de calitate la nivel de pilot"""
    import math
    
    event_id = request.GET.get('event_id')
    driver_id = request.GET.get('driver_id')
    
    if not event_id or not driver_id:
        return JsonResponse({'error': 'Event ID and Driver ID are required'}, status=400)
    
    event_info = execute_query("""
        SELECT event_id, event_name, year, circuit_name
        FROM event
        WHERE event_id = %s
    """, [event_id])
    
    driver_info = execute_query("""
        SELECT driver_id, driver_code, first_name || ' ' || last_name as full_name
        FROM driver
        WHERE driver_id = %s
    """, [driver_id])
    
    if not event_info or not driver_info:
        return JsonResponse({'error': 'Event or driver not found'}, status=404)
    
    detailed_stats = execute_query("""
        SELECT 
            COUNT(*) as total_points,
            SUM(CASE 
                WHEN (speed IS NULL OR speed::text = 'NaN' OR
                     throttle IS NULL OR throttle::text = 'NaN' OR
                     brake IS NULL OR
                     rpm IS NULL OR rpm::text = 'NaN' OR
                     drs IS NULL OR
                     lap_number IS NULL OR lap_number::text = 'NaN' OR
                     lap_time IS NULL OR lap_time = 'No time' OR
                     position IS NULL OR
                     tire_compound IS NULL OR tire_compound = '' OR
                     tyre_life IS NULL OR tyre_life::text = 'NaN' OR
                     sector1_time IS NULL OR sector1_time::text = 'NaN' OR
                     sector2_time IS NULL OR sector2_time::text = 'NaN' OR
                     sector3_time IS NULL OR sector3_time::text = 'NaN')
                THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as valid_data_pct,
            
            SUM(CASE WHEN speed IS NULL OR speed::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_speed_pct,
            SUM(CASE WHEN throttle IS NULL OR throttle::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_throttle_pct,
            SUM(CASE WHEN brake IS NULL THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_brake_pct,
            SUM(CASE WHEN rpm IS NULL OR rpm::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_rpm_pct,
            SUM(CASE WHEN drs IS NULL THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_drs_pct,
            SUM(CASE WHEN lap_time IS NULL OR lap_time = 'No time' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_lap_time_pct,
            SUM(CASE WHEN lap_number IS NULL OR lap_number::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_lap_number_pct,
            SUM(CASE WHEN position IS NULL THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_position_pct,
            SUM(CASE WHEN tire_compound IS NULL OR tire_compound = '' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_tire_compound_pct,
            SUM(CASE WHEN tyre_life IS NULL OR tyre_life::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_tyre_life_pct,
            SUM(CASE WHEN sector1_time IS NULL OR sector1_time::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_sector1_pct,
            SUM(CASE WHEN sector2_time IS NULL OR sector2_time::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_sector2_pct,
            SUM(CASE WHEN sector3_time IS NULL OR sector3_time::text = 'NaN' THEN 1 ELSE 0 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as null_sector3_pct,
            COUNT(DISTINCT CASE WHEN lap_number IS NOT NULL AND lap_number::text != 'NaN' THEN lap_number END) as lap_count,
            MAX(CASE WHEN lap_number::text != 'NaN' THEN lap_number END) as max_lap
        FROM telemetry t
        JOIN session s ON t.session_id = s.session_id
        WHERE s.event_id = %s AND t.driver_id = %s
    """, [event_id, driver_id])
    
    if not detailed_stats or detailed_stats[0]['total_points'] == 0:
        return JsonResponse({'error': 'No telemetry data found for this driver in this event'}, status=404)
    
    session_stats = execute_query("""
        SELECT 
            s.session_id,
            s.session_type,
            COUNT(*) as total_points,
            SUM(CASE 
                WHEN (t.speed IS NULL OR t.speed::text = 'NaN' OR
                     t.throttle IS NULL OR t.throttle::text = 'NaN' OR
                     t.brake IS NULL OR
                     t.rpm IS NULL OR t.rpm::text = 'NaN' OR
                     t.drs IS NULL OR
                     t.lap_number IS NULL OR t.lap_number::text = 'NaN' OR
                     t.lap_time IS NULL OR t.lap_time = 'No time' OR
                     t.position IS NULL OR
                     t.tire_compound IS NULL OR t.tire_compound = '' OR
                     t.tyre_life IS NULL OR t.tyre_life::text = 'NaN' OR
                     t.sector1_time IS NULL OR t.sector1_time::text = 'NaN' OR
                     t.sector2_time IS NULL OR t.sector2_time::text = 'NaN' OR
                     t.sector3_time IS NULL OR t.sector3_time::text = 'NaN')
                THEN 0 ELSE 1 END) * 100.0 / 
                NULLIF(COUNT(*), 0) as valid_data_pct,
            COUNT(DISTINCT CASE WHEN t.lap_number IS NOT NULL AND t.lap_number::text != 'NaN' THEN t.lap_number END) as lap_count
        FROM telemetry t
        JOIN session s ON t.session_id = s.session_id
        WHERE s.event_id = %s AND t.driver_id = %s
        GROUP BY s.session_id, s.session_type
    """, [event_id, driver_id])
    
    if 'valid_data_pct' in detailed_stats[0] and (detailed_stats[0]['valid_data_pct'] is None or 
                                               (isinstance(detailed_stats[0]['valid_data_pct'], float) and 
                                                math.isnan(detailed_stats[0]['valid_data_pct']))):
        detailed_stats[0]['valid_data_pct'] = 0
        
    metrics = [
        {'name': 'Speed', 'usable_percentage': round(100 - detailed_stats[0]['null_speed_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_speed_pct'], 2)},
        {'name': 'Throttle', 'usable_percentage': round(100 - detailed_stats[0]['null_throttle_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_throttle_pct'], 2)},
        {'name': 'Brake', 'usable_percentage': round(100 - detailed_stats[0]['null_brake_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_brake_pct'], 2)},
        {'name': 'RPM', 'usable_percentage': round(100 - detailed_stats[0]['null_rpm_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_rpm_pct'], 2)},
        {'name': 'DRS', 'usable_percentage': round(100 - detailed_stats[0]['null_drs_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_drs_pct'], 2)},
        {'name': 'Lap Time', 'usable_percentage': round(100 - detailed_stats[0]['null_lap_time_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_lap_time_pct'], 2)},
        {'name': 'Lap Number', 'usable_percentage': round(100 - detailed_stats[0]['null_lap_number_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_lap_number_pct'], 2)},
        {'name': 'Position', 'usable_percentage': round(100 - detailed_stats[0]['null_position_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_position_pct'], 2)},
        {'name': 'Tire Compound', 'usable_percentage': round(100 - detailed_stats[0]['null_tire_compound_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_tire_compound_pct'], 2)},
        {'name': 'Tire Life', 'usable_percentage': round(100 - detailed_stats[0]['null_tyre_life_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_tyre_life_pct'], 2)},
        {'name': 'Sector 1', 'usable_percentage': round(100 - detailed_stats[0]['null_sector1_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_sector1_pct'], 2)},
        {'name': 'Sector 2', 'usable_percentage': round(100 - detailed_stats[0]['null_sector2_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_sector2_pct'], 2)},
        {'name': 'Sector 3', 'usable_percentage': round(100 - detailed_stats[0]['null_sector3_pct'], 2), 
         'error_percentage': round(detailed_stats[0]['null_sector3_pct'], 2)},
    ]
    
    for session in session_stats:
        if session['session_type'] == 'Q':
            session['display_type'] = 'Qualifying'
        elif session['session_type'] == 'R':
            session['display_type'] = 'Race'
        else:
            session['display_type'] = 'Practice'
            
        if 'valid_data_pct' in session and (session['valid_data_pct'] is None or 
                                         (isinstance(session['valid_data_pct'], float) and 
                                          math.isnan(session['valid_data_pct']))):
            session['valid_data_pct'] = 0
            
        session['usable_percentage'] = round(session['valid_data_pct'], 2)
        session['error_percentage'] = round(100 - session['valid_data_pct'], 2)
    
    incomplete_laps = max(0, detailed_stats[0]['max_lap'] - detailed_stats[0]['lap_count']) if detailed_stats[0]['max_lap'] else 0
    
    return JsonResponse({
        'event': event_info[0],
        'driver': driver_info[0],
        'overall_stats': {
            'total_points': detailed_stats[0]['total_points'],
            'usable_percentage': round(detailed_stats[0]['valid_data_pct'], 2),
            'error_percentage': round(100 - detailed_stats[0]['valid_data_pct'], 2),
            'lap_count': detailed_stats[0]['lap_count'],
            'incomplete_laps': incomplete_laps
        },
        'metrics': metrics,
        'sessions': session_stats
    })