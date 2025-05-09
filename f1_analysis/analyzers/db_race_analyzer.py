import os
import json
import argparse
import numpy as np
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
from datetime import datetime
import traceback


class DBF1RaceAnalyzer:

    def __init__(self, db_params):
        self.db_params = db_params
        self.conn = None

        plt.style.use('dark_background')
        plt.rcParams['axes.edgecolor'] = '#FFFFFF'
        plt.rcParams['axes.linewidth'] = 1
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3

        self.team_colors = {
            'red_bull': '#0600EF',
            'ferrari': '#DC0000',
            'mercedes': '#00D2BE',
            'mclaren': '#FF8700',
            'alpine': '#0090FF',
            'aston_martin': '#006F62',
            'alphatauri': '#2B4562',
            'alfa': '#900000',
            'haas': '#FFFFFF',
            'williams': '#005AFF',
            'rb': '#1E41FF',
            'sauber': '#900000'
        }

    def get_driver_styling(self, drivers, year):
        if not self.conn:
            self.connect()

        driver_teams = {}
        for driver in drivers:
            team_id = self.get_team_for_driver(driver, year)
            driver_teams[driver] = team_id

        team_driver_counts = {}
        for driver, team in driver_teams.items():
            if team not in team_driver_counts:
                team_driver_counts[team] = []
            team_driver_counts[team].append(driver)

        driver_styles = {}
        for team, team_drivers in team_driver_counts.items():
            team_color = self.team_colors.get(team, 'gray')

            if len(team_drivers) > 1:
                for i, driver in enumerate(sorted(team_drivers)):
                    if i == 0:
                        driver_styles[driver] = {
                            'color': team_color,
                            'linestyle': '-'
                        }
                    else:
                        driver_styles[driver] = {
                            'color': '#FF00FF',
                            'linestyle': '--'
                        }
            else:
                driver_styles[team_drivers[0]] = {
                    'color': team_color,
                    'linestyle': '-'
                }

        return driver_styles

    def get_team_for_driver(self, driver_code, year):
        if not self.conn:
            self.connect()

        query = """
                SELECT t.team_id
                FROM driver d
                         JOIN driver_team dt ON d.driver_id = dt.driver_id
                         JOIN team t ON dt.team_id = t.team_id
                WHERE d.driver_code = %s \
                  AND dt.year = %s \
                """

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (driver_code, year))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error getting team for {driver_code}: {e}")
            return None

    def connect(self):
        self.conn = psycopg2.connect(
            host=self.db_params['host'],
            database=self.db_params['database'],
            user=self.db_params['user'],
            password=self.db_params['password'],
            port=self.db_params.get('port', 5432)
        )
        return self.conn

    def get_driver_race_laps(self, event_name, year, driver):
        if not self.conn:
            self.connect()

        query = """
                SELECT lap_number, \
                       MIN(NULLIF(NULLIF(lap_time, ''), 'No time')) as lap_time, \
                       MIN(position)                                as position, \
                       MIN(tire_compound)                           as tire_compound, \
                       MIN(time_seconds)                            as time_seconds, \
                       MIN(sector1_time)                            as sector1_time, \
                       MIN(sector2_time)                            as sector2_time, \
                       MIN(sector3_time)                            as sector3_time
                FROM telemetry t \
                         JOIN \
                     driver d ON t.driver_id = d.driver_id \
                         JOIN \
                     session s ON t.session_id = s.session_id \
                         JOIN \
                     event e ON s.event_id = e.event_id
                WHERE e.event_name LIKE %s
                  AND e.year = %s
                  AND d.driver_code = %s
                  AND s.session_type = 'R'
                GROUP BY lap_number
                ORDER BY lap_number \
                """

        try:
            df = pd.read_sql(query, self.conn, params=(f'%{event_name}%', year, driver))

            if not df.empty and 'lap_time' in df.columns:
                print(f"Sample lap time format for {driver}: {df['lap_time'].iloc[0]}")

            if not df.empty and 'lap_time' in df.columns:
                def parse_lap_time(time_str):
                    if pd.isna(time_str) or time_str == '':
                        return None
                    try:
                        if isinstance(time_str, str):
                            if ':' in time_str and '.' in time_str:
                                minutes, rest = time_str.split(':')
                                seconds = float(rest)
                                return int(minutes) * 60 + seconds
                            elif ':' in time_str:
                                minutes, seconds = time_str.split(':')
                                return int(minutes) * 60 + float(seconds)
                            else:
                                return float(time_str)
                        return float(time_str)
                    except Exception as e:
                        print(f"Could not parse lap time '{time_str}': {e}")
                        return None

                df['lap_time'] = df['lap_time'].apply(parse_lap_time)

            if not df.empty and 'tire_compound' in df.columns:
                df['prev_compound'] = df['tire_compound'].shift(1)
                df['pit_stop'] = (df['tire_compound'] != df['prev_compound']) | df['prev_compound'].isna()
                df.drop('prev_compound', axis=1, inplace=True)

            return df
        except Exception as e:
            print(f"Error retrieving race lap data for {driver}: {e}")
            traceback.print_exc()
            return None

    def get_safety_car_periods(self, event_name, year):
        if not self.conn:
            self.connect()

        query = """
                WITH lap_status AS (SELECT lap_number, \
                                           track_status, \
                                           -- Detect status changes \
                                           LAG(track_status) OVER (ORDER BY lap_number) AS prev_status \
                                    FROM telemetry t \
                                             JOIN \
                                         session s ON t.session_id = s.session_id \
                                             JOIN \
                                         event e ON s.event_id = e.event_id \
                                    WHERE e.event_name LIKE %s \
                                      AND e.year = %s \
                                      AND s.session_type = 'R' \
                                      AND track_status IS NOT NULL \
                                    GROUP BY lap_number, track_status \
                                    ORDER BY lap_number)
                SELECT MIN(lap_number) as start_lap, \
                       MAX(lap_number) as end_lap
                FROM (SELECT lap_number,
                             track_status,
                             SUM(CASE \
                                     WHEN track_status = '4' AND (prev_status != '4' OR prev_status IS NULL) THEN 1 \
                                     ELSE 0 END)
                             OVER (ORDER BY lap_number) as sc_group \
                      FROM lap_status) grouped
                WHERE track_status = '4'
                GROUP BY sc_group
                ORDER BY start_lap \
                """

        try:
            conn = self.connect()
            conn.set_session(autocommit=True)
            cursor = conn.cursor()
            cursor.execute("SET statement_timeout = 30000")

            df = pd.read_sql(query, self.conn, params=(f'%{event_name}%', year))

            cursor.execute("RESET statement_timeout")
            cursor.close()

            if df.empty:
                return []
            return [(row['start_lap'], row['end_lap']) for _, row in df.iterrows()]
        except Exception as e:
            print(f"Error retrieving safety car periods: {e}")
            return []

    def get_pit_stop_data(self, event_name, year, driver):
        if not self.conn:
            self.connect()

        query = """
        WITH prev_compounds AS (
            SELECT 
                lap_number,
                tire_compound,
                LAG(tire_compound) OVER (ORDER BY lap_number) as prev_compound
            FROM 
                telemetry t
            JOIN 
                driver d ON t.driver_id = d.driver_id
            JOIN 
                session s ON t.session_id = s.session_id
            JOIN 
                event e ON s.event_id = e.event_id
            WHERE 
                e.event_name LIKE %s
                AND e.year = %s
                AND d.driver_code = %s
                AND s.session_type = 'R'
        )
        SELECT 
            lap_number,
            tire_compound as new_compound
        FROM 
            prev_compounds
        WHERE 
            prev_compound != tire_compound OR prev_compound IS NULL
        ORDER BY 
            lap_number
                """

        try:
            df = pd.read_sql(query, self.conn, params=(f'%{event_name}%', year, driver))
            return df
        except Exception as e:
            print(f"Error retrieving pit stop data for {driver}: {e}")
            return None

    def visualize_lap_times(self, event_name, year, drivers, save_path=None):
        fig, ax = plt.subplots(figsize=(12, 6))

        safety_car_periods = self.get_safety_car_periods(event_name, year)

        driver_styles = self.get_driver_styling(drivers, year)

        for driver in drivers:
            driver_laps = self.get_driver_race_laps(event_name, year, driver)

            if driver_laps is None or driver_laps.empty:
                print(f"No lap data found for {driver}")
                continue

            if len(driver_laps) > 5:
                q1 = driver_laps['lap_time'].quantile(0.25)
                q3 = driver_laps['lap_time'].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                filtered_laps = driver_laps[
                    (driver_laps['lap_time'] >= lower_bound) &
                    (driver_laps['lap_time'] <= upper_bound)
                    ]
            else:
                filtered_laps = driver_laps

            if not filtered_laps.empty:
                style = driver_styles.get(driver, {'color': 'gray', 'linestyle': '-'})

                ax.plot(filtered_laps['lap_number'],
                        filtered_laps['lap_time'],
                        color=style['color'],
                        linestyle=style['linestyle'],
                        label=driver,
                        linewidth=2,
                        marker='o',
                        markersize=3)

        for sc_start, sc_end in safety_car_periods:
            ax.axvspan(sc_start, sc_end, color='orange', alpha=0.3)
            ax.text((sc_start + sc_end) / 2, ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.05,
                    "SC", ha='center', va='bottom', rotation=90,
                    bbox=dict(facecolor='white', alpha=0.7, color='black'))

        def format_time(x, pos):
            minutes = int(x // 60)
            seconds = x % 60
            return f"{minutes:01d}:{seconds:05.2f}"

        ax.yaxis.set_major_formatter(plt.FuncFormatter(format_time))

        ax.set_title(f"Lap Time Comparison - {' vs '.join(drivers)}\n{event_name} {year}", fontsize=16)
        ax.set_xlabel('Lap Number', fontsize=12)
        ax.set_ylabel('Lap Time', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Lap time comparison visualization saved to {save_path}")

        return fig

    def visualize_tire_strategy(self, event_name, year, drivers, save_path=None):
        fig, ax = plt.subplots(figsize=(12, len(drivers) * 0.7 + 2))

        driver_styles = self.get_driver_styling(drivers, year)

        compound_colors = {
            'SOFT': '#FF3333',
            'MEDIUM': '#FFDD33',
            'HARD': '#FFFFFF',
            'INTERMEDIATE': '#33CC33',
            'WET': '#3366FF',
            'UNKNOWN': '#AAAAAA'
        }

        displayed_compounds = set()

        for i, driver in enumerate(drivers):
            driver_laps = self.get_driver_race_laps(event_name, year, driver)

            if driver_laps is None or driver_laps.empty:
                print(f"No lap data found for {driver}")
                continue

            driver_laps = driver_laps.sort_values('lap_number')

            current_compound = None
            stint_start = None
            stints = []

            for _, row in driver_laps.iterrows():
                lap = row['lap_number']
                compound = row['tire_compound']

                if pd.isna(compound) or compound == 'UNKNOWN':
                    continue

                if current_compound is None or compound != current_compound:
                    if current_compound is not None and stint_start is not None:
                        stints.append({
                            'compound': current_compound,
                            'start': stint_start,
                            'end': lap - 1
                        })

                    current_compound = compound
                    stint_start = lap

            if current_compound is not None and stint_start is not None:
                stints.append({
                    'compound': current_compound,
                    'start': stint_start,
                    'end': driver_laps['lap_number'].max()
                })

            style = driver_styles.get(driver, {'color': 'gray'})

            edge_color = 'white' if style['color'] == '#2B4562' else 'black'

            for stint in stints:
                compound = stint['compound']
                start = stint['start']
                end = stint['end']
                width = end - start + 1

                color = compound_colors.get(compound, 'gray')
                ax.barh(driver, width=width, left=start, height=0.6,
                        color=color, edgecolor=edge_color, alpha=0.9)

                displayed_compounds.add(compound)

        handles = []
        labels = []
        for compound in displayed_compounds:
            color = compound_colors.get(compound, 'gray')
            handles.append(plt.Rectangle((0, 0), 1, 1, color=color, ec="black"))
            labels.append(compound)

        ax.legend(handles=handles, labels=labels, loc='lower left',
                  bbox_to_anchor=(0.01, -0.25), ncol=len(handles))

        ax.set_title(f"Tire Strategy - {event_name} {year}", fontsize=16)
        ax.set_xlabel("Lap Number", fontsize=12)
        ax.grid(False)
        ax.invert_yaxis()

        plt.tight_layout()
        plt.subplots_adjust(bottom=0.2)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Tire strategy visualization saved to {save_path}")

        return fig

    def visualize_position_changes(self, event_name, year, drivers, save_path=None):
        fig, ax = plt.subplots(figsize=(12, 7))

        driver_styles = self.get_driver_styling(drivers, year)

        for driver in drivers:
            driver_laps = self.get_driver_race_laps(event_name, year, driver)

            if driver_laps is None or driver_laps.empty:
                print(f"No lap data found for {driver}")
                continue

            driver_laps = driver_laps.dropna(subset=['position'])

            style = driver_styles.get(driver, {'color': 'gray', 'linestyle': '-'})

            ax.plot(driver_laps['lap_number'], driver_laps['position'],
                    color=style['color'],
                    linestyle=style['linestyle'],
                    label=driver,
                    linewidth=2)

            pit_stops = driver_laps[driver_laps['pit_stop'] == True]
            if not pit_stops.empty:
                ax.scatter(pit_stops['lap_number'], pit_stops['position'],
                           marker='v', s=100, color=style['color'], edgecolor='black')

        for driver in drivers:
            driver_laps = self.get_driver_race_laps(event_name, year, driver)
            if driver_laps is None or driver_laps.empty:
                continue

            driver_laps = driver_laps.sort_values('lap_number')
            driver_laps['prev_pos'] = driver_laps['position'].shift(1)
            driver_laps['pos_change'] = driver_laps['prev_pos'] - driver_laps['position']

            overtakes = driver_laps[(driver_laps['pos_change'] > 0) & (driver_laps['pit_stop'] != True)]

            if not overtakes.empty:
                style = driver_styles.get(driver, {'color': 'gray', 'linestyle': '-'})
                ax.scatter(overtakes['lap_number'], overtakes['position'],
                           marker='*', s=120, color=style['color'], edgecolor='white')

        safety_car_periods = self.get_safety_car_periods(event_name, year)
        for sc_start, sc_end in safety_car_periods:
            ax.axvspan(sc_start, sc_end, color='orange', alpha=0.3)
            ax.text((sc_start + sc_end) / 2, ax.get_ylim()[0] * 0.9,
                    "SC", ha='center', va='bottom', rotation=90,
                    bbox=dict(facecolor='white', alpha=0.7, color='black'))

        ax.set_ylim(20.5, 0.5)
        ax.set_yticks(range(1, 21))

        handles, labels = ax.get_legend_handles_labels()

        ax.legend(loc='upper right')

        event_handles = []
        event_labels = []

        pit_marker = plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='gray', markersize=10)
        overtake_marker = plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='gray', markersize=10)

        event_handles.extend([pit_marker, overtake_marker])
        event_labels.extend(["Pit Stop", "Overtake"])

        legend2 = ax.legend(event_handles, event_labels, loc='lower right', title="Events")
        ax.add_artist(legend2)

        ax.set_xlabel('Lap Number', fontsize=12)
        ax.set_ylabel('Position', fontsize=12)
        ax.set_title(f"Position Changes - {' vs '.join(drivers)}\n{event_name} {year}", fontsize=16)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Position changes visualization saved to {save_path}")

        return fig

    def analyze_tire_compounds(self, event_name, year, drivers):
        tire_data = {driver: {'stints': []} for driver in drivers}

        for driver in drivers:
            driver_laps = self.get_driver_race_laps(event_name, year, driver)

            if driver_laps is None or driver_laps.empty:
                print(f"No lap data found for {driver}")
                continue

            driver_laps = driver_laps.sort_values('lap_number')

            current_compound = None
            stint_start = None
            stint_laps = []

            for _, row in driver_laps.iterrows():
                lap = row['lap_number']
                compound = row['tire_compound']

                if pd.isna(compound) or compound == 'UNKNOWN':
                    continue

                if current_compound is None or compound != current_compound:
                    if current_compound is not None and stint_start is not None and stint_laps:
                        stint_lap_times = [l['lap_time'] for l in stint_laps if pd.notna(l['lap_time'])]

                        if len(stint_lap_times) >= 3:
                            avg_time = sum(stint_lap_times) / len(stint_lap_times)

                            x = np.arange(len(stint_lap_times))
                            y = np.array(stint_lap_times)

                            try:
                                slope, intercept = np.polyfit(x, y, 1)

                                tire_data[driver]['stints'].append({
                                    'compound': current_compound,
                                    'start': stint_start,
                                    'end': lap - 1,
                                    'laps': len(stint_lap_times),
                                    'avg_time': avg_time,
                                    'degradation': slope
                                })
                            except Exception as e:
                                print(f"Error calculating degradation for {driver}'s {current_compound} stint: {e}")

                    current_compound = compound
                    stint_start = lap
                    stint_laps = []

                stint_laps.append(row)

            if current_compound is not None and stint_start is not None and stint_laps:
                stint_lap_times = [l['lap_time'] for l in stint_laps if pd.notna(l['lap_time'])]

                if len(stint_lap_times) >= 3:
                    avg_time = sum(stint_lap_times) / len(stint_lap_times)

                    x = np.arange(len(stint_lap_times))
                    y = np.array(stint_lap_times)

                    try:
                        slope, intercept = np.polyfit(x, y, 1)

                        tire_data[driver]['stints'].append({
                            'compound': current_compound,
                            'start': stint_start,
                            'end': driver_laps['lap_number'].max(),
                            'laps': len(stint_lap_times),
                            'avg_time': avg_time,
                            'degradation': slope
                        })
                    except Exception as e:
                        print(f"Error calculating final stint degradation for {driver}: {e}")

        return tire_data

    def generate_race_insights(self, event_name, year, drivers, tire_data):
        insights = [f"# Tire Strategy Analysis - {' vs '.join(drivers)} at {event_name} {year}"]

        insights.append("\n## Overall Strategy Comparison")

        for driver in drivers:
            driver_data = tire_data[driver]

            if not driver_data or 'stints' not in driver_data or not driver_data['stints']:
                insights.append(f"\n### {driver}: Insufficient data for analysis")
                continue

            stints = driver_data['stints']
            total_stops = len(stints) - 1

            strategy_summary = []
            for stint in stints:
                strategy_summary.append(f"{stint['compound']}({stint['laps']} laps)")

            insights.append(f"\n### {driver}: {total_stops} stop strategy")
            insights.append(f"* Strategy: {' → '.join(strategy_summary)}")

            compounds_summary = {}
            for stint in stints:
                compound = stint['compound']
                if compound not in compounds_summary:
                    compounds_summary[compound] = {
                        'laps': 0,
                        'avg_time': 0,
                        'degradation_sum': 0,
                        'stints': 0
                    }

                compounds_summary[compound]['laps'] += stint['laps']
                compounds_summary[compound]['avg_time'] += stint['avg_time'] * stint['laps']
                compounds_summary[compound]['degradation_sum'] += stint['degradation']
                compounds_summary[compound]['stints'] += 1

            for compound in compounds_summary:
                if compounds_summary[compound]['laps'] > 0:
                    compounds_summary[compound]['avg_time'] /= compounds_summary[compound]['laps']
                    compounds_summary[compound]['avg_degradation'] = compounds_summary[compound]['degradation_sum'] / \
                                                                     compounds_summary[compound]['stints']

            insights.append("\n#### Compound Performance:")
            for compound, data in compounds_summary.items():
                avg_time = data['avg_time']
                minutes = int(avg_time // 60)
                seconds = avg_time % 60
                formatted_time = f"{minutes}:{seconds:.3f}"

                avg_deg = data.get('avg_degradation', 0)
                insights.append(f"* {compound}: Avg lap time {formatted_time}, Degradation {avg_deg:.4f}s/lap")

        if len(drivers) > 1:
            insights.append("\n"
                            "# Tire Management Comparison")

            common_compounds = set()

            driver_compounds = {}
            for driver in drivers:
                if not tire_data[driver] or 'stints' not in tire_data[driver]:
                    continue

                driver_compounds[driver] = set(stint['compound'] for stint in tire_data[driver]['stints'])

            if len(driver_compounds) > 1:
                common_compounds = set.intersection(*driver_compounds.values())

            for compound in common_compounds:
                insights.append(f"\n### {compound} Compound Comparison")

                driver_perf = {}
                for driver in drivers:
                    if not tire_data[driver] or 'stints' not in tire_data[driver]:
                        continue

                    driver_compound_stints = [s for s in tire_data[driver]['stints'] if s['compound'] == compound]

                    if not driver_compound_stints:
                        continue

                    avg_deg = sum(s['degradation'] for s in driver_compound_stints) / len(driver_compound_stints)
                    total_laps = sum(s['laps'] for s in driver_compound_stints)

                    driver_perf[driver] = {
                        'avg_degradation': avg_deg,
                        'total_laps': total_laps
                    }

                if len(driver_perf) > 1:
                    sorted_drivers = sorted(driver_perf.items(), key=lambda x: x[1]['avg_degradation'])

                    for i, (driver, data) in enumerate(sorted_drivers):
                        if i == 0:
                            insights.append(
                                f"* {driver} managed the {compound} tires better with {data['avg_degradation']:.4f}s/lap degradation")
                        else:
                            insights.append(f"* {driver} experienced {data['avg_degradation']:.4f}s/lap degradation")

                    best_driver = sorted_drivers[0][0]
                    best_deg = sorted_drivers[0][1]['avg_degradation']
                    worst_driver = sorted_drivers[-1][0]
                    worst_deg = sorted_drivers[-1][1]['avg_degradation']

                    advantage = worst_deg - best_deg
                    insights.append(f"* Tire management advantage: {advantage:.4f}s/lap to {best_driver}")

        return "\n".join(insights)

    def _create_analysis_index(self, folder_path, metadata):
        index_path = os.path.join(folder_path, "index.json")
        metadata['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(index_path, 'w') as f:
            json.dump(metadata, f, indent=4)

    def save_to_database(self, event_name, year, drivers, insights, lap_times_path, tire_strategy_path, position_path,
                         tire_data):
        if not self.conn:
            self.connect()

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                           SELECT s.session_id
                           FROM session s
                                    JOIN event e ON s.event_id = e.event_id
                           WHERE e.event_name LIKE %s
                             AND e.year = %s
                             AND s.session_type = 'R'
                           """, (f'%{event_name}%', year))

            session_row = cursor.fetchone()
            session_id = session_row[0] if session_row else None

            cursor.execute("""
                           INSERT INTO analysis
                           (session_id, analysis_type, event_name, year, analysis_name, is_public, description)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           RETURNING analysis_id
                           """, (
                               session_id,
                               'race',
                               event_name,
                               year,
                               f"{' vs '.join(drivers)} Race Analysis",
                               True,
                               f"Race analysis for {' vs '.join(drivers)} at {event_name} {year}"
                           ))

            analysis_id = cursor.fetchone()[0]

            drivers_json = json.dumps(drivers)
            tire_data_json = json.dumps(tire_data)
            compound_performance_json = json.dumps({})

            cursor.execute("""
                           INSERT INTO race_analysis
                           (analysis_id, drivers_json, tire_data_json, compound_performance_json, markdown_insights,
                            lap_times_plot_path, tire_strategy_plot_path, position_plot_path)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           """, (
                               analysis_id,
                               drivers_json,
                               tire_data_json,
                               compound_performance_json,
                               insights,
                               lap_times_path,
                               tire_strategy_path,
                               position_path
                           ))

            self.conn.commit()
            print(f"Analysis saved to database with ID: {analysis_id}")
            return analysis_id

        except Exception as e:
            self.conn.rollback()
            print(f"Error saving to database: {e}")
            traceback.print_exc()
            return None

    def check_existing_analysis(self, event_name, year, drivers):
        if not self.conn:
            self.connect()

        try:
            cursor = self.conn.cursor()

            sorted_drivers = sorted(drivers)
            drivers_json = json.dumps(sorted_drivers)

            cursor.execute("""
                           SELECT a.analysis_id,
                                  ra.markdown_insights,
                                  ra.lap_times_plot_path,
                                  ra.tire_strategy_plot_path,
                                  ra.position_plot_path,
                                  ra.tire_data_json
                           FROM analysis a
                                    JOIN race_analysis ra ON a.analysis_id = ra.analysis_id
                           WHERE a.event_name LIKE %s
                             AND a.year = %s
                             AND ra.drivers_json @> %s
                             AND jsonb_array_length(ra.drivers_json) = %s
                           ORDER BY a.created_at DESC
                           LIMIT 1
                           """, (
                               f'%{event_name}%',
                               year,
                               drivers_json,
                               len(drivers)
                           ))

            result = cursor.fetchone()

            if result:
                analysis_id, markdown, lap_times_path, tire_strategy_path, position_path, tire_data_json = result

                try:
                    tire_data = json.loads(tire_data_json) if tire_data_json else {}
                except:
                    tire_data = {}

                print(f"Found existing analysis (ID: {analysis_id}) for {' vs '.join(drivers)} at {event_name} {year}")

                return {
                    "analysis_id": analysis_id,
                    "lap_times_viz": lap_times_path,
                    "tire_strategy_viz": tire_strategy_path,
                    "position_viz": position_path,
                    "insights": markdown,
                    "tire_data": tire_data,
                    "from_database": True
                }

            return None

        except Exception as e:
            print(f"Error checking for existing analysis: {e}")
            return None

    def run_race_analysis(self, event_name, year, drivers, save_to_db=False, output_dir=None):
        if not isinstance(drivers, list) or len(drivers) < 1:
            raise ValueError("drivers must be a list with at least one driver code")

        existing_analysis = self.check_existing_analysis(event_name, year, drivers)
        if existing_analysis:
            print(f"Using existing analysis for {' vs '.join(drivers)} at {event_name} {year}")
            return {
                'existing_analysis': True,
                'analysis_id': existing_analysis['analysis_id']
            }

        print(f"Starting race analysis for {' vs '.join(drivers)} at {event_name} {year}")

        if not output_dir:
            base_path = os.path.join("analysis", "race_analysis", event_name.replace(' ', '_'),
                                     f"{drivers[0]}_vs_{drivers[1]}")
        else:
            base_path = output_dir
            print(f"Using custom output directory: {base_path}")

        os.makedirs(base_path, exist_ok=True)

        output_file = os.path.join(base_path, "analysis.md")
        lap_times_path = os.path.join(base_path, "pace_comparison.png")
        tire_strategy_path = os.path.join(base_path, "strategy_comparison.png")
        position_path = os.path.join(base_path, "position_changes.png")

        all_laps = {}
        for driver in drivers:
            driver_laps = self.get_driver_race_laps(event_name, year, driver)
            if driver_laps is not None and not driver_laps.empty:
                all_laps[driver] = driver_laps
                print(f"Found {len(all_laps[driver])} laps for {driver}")
            else:
                print(f"WARNING: No valid laps found for {driver}!")

        if all(driver not in all_laps or all_laps[driver].empty for driver in drivers):
            print("No valid lap data available for any driver. Analysis aborted.")
            return {
                "error": "No valid lap data found",
                "markdown_file": None,
                "lap_times_viz": None,
                "tire_strategy_viz": None,
                "position_viz": None
            }

        print("Creating lap time visualization...")
        self.visualize_lap_times(event_name, year, drivers, lap_times_path)

        print("Creating tire strategy visualization...")
        self.visualize_tire_strategy(event_name, year, drivers, tire_strategy_path)

        print("Creating position changes visualization...")
        self.visualize_position_changes(event_name, year, drivers, position_path)

        print("Analyzing tire compounds...")
        tire_data = self.analyze_tire_compounds(event_name, year, drivers)

        print("Generating race insights...")
        insights = self.generate_race_insights(event_name, year, drivers, tire_data)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(insights)
        print(f"Analysis complete! Results saved to {output_file}")

        if save_to_db:
            try:
                self.save_to_database(event_name, year, drivers, insights,
                                      lap_times_path, tire_strategy_path, position_path, tire_data)
            except Exception as e:
                print(f"Error saving to database: {e}")

        self._create_analysis_index(base_path, {
            'event': event_name,
            'year': year,
            'drivers': drivers,
            'type': 'race',
            'files': {
                'analysis': os.path.basename(output_file),
                'lap_times': os.path.basename(lap_times_path),
                'tire_strategy': os.path.basename(tire_strategy_path),
                'position_changes': os.path.basename(position_path)
            }
        })

        return {
            "markdown_file": output_file,
            "lap_times_viz": lap_times_path,
            "tire_strategy_viz": tire_strategy_path,
            "position_viz": position_path,
            "insights": insights,
            "tire_data": tire_data
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="F1 Race Analysis Tool (Database Version)")
    parser.add_argument("--event", required=True, help="Event name (e.g. Monaco)")
    parser.add_argument("--year", required=True, type=int, help="Year of the event")
    parser.add_argument("--drivers", required=True, help="Comma-separated driver codes (e.g. VER,LEC)")
    parser.add_argument("--db-save", action="store_true", help="Save results to database")
    parser.add_argument("--debug", action="store_true", help="Print diagnostic information")

    args = parser.parse_args()

    driver_list = [d.strip() for d in args.drivers.split(',')]
    if len(driver_list) < 1:
        print("Error: At least 1 driver code must be provided.")
        exit(1)

    db_params = {
        'host': 'localhost',
        'database': 'f1_telemetry',
        'user': 'madalin',
        'password': 'madalin',
        'port': 5432
    }

    analyzer = DBF1RaceAnalyzer(db_params)
    results = analyzer.run_race_analysis(
        event_name=args.event,
        year=args.year,
        drivers=driver_list,
        save_to_db=args.db_save
    )

    print(f"\nAnalysis complete!")
    if results:
        print("Files generated:")
        if 'markdown_file' in results and results['markdown_file']:
            print(f"- Markdown: {results['markdown_file']}")
        if 'lap_times_viz' in results and results['lap_times_viz']:
            print(f"- Lap times visualization: {results['lap_times_viz']}")
        if 'tire_strategy_viz' in results and results['tire_strategy_viz']:
            print(f"- Tire strategy visualization: {results['tire_strategy_viz']}")
        if 'position_viz' in results and results['position_viz']:
            print(f"- Position changes visualization: {results['position_viz']}")
    else:
        print("No results were generated due to errors.")