import os
import json
import argparse
import numpy as np
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
from datetime import datetime
import traceback

class DBF1QualifyingAnalyzer:
    def __init__(self, db_params):
        self.db_params = db_params
        self.conn = None
        
        #stilizare grafice
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
                    if i == 0: #primul pilot
                        driver_styles[driver] = {
                            'color': team_color,
                            'linestyle': '-'
                        }
                    else: #al doilea
                        driver_styles[driver] = {
                            'color': '#FF00FF',
                            'linestyle': '--'
                        }
            else: # nu sunt coechiperi
                driver_styles[team_drivers[0]] = {
                    'color': team_color,
                    'linestyle': '-'
                }
        
        return driver_styles
    
    def get_team_for_driver(self, driver_code, year):
        if not self.conn:
            self.connect()
        #caut echipa pilotului
        query = """
        SELECT t.team_id
        FROM driver d
        JOIN driver_team dt ON d.driver_id = dt.driver_id
        JOIN team t ON dt.team_id = t.team_id
        WHERE d.driver_code = %s AND dt.year = %s
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

    def generate_quali_insights(self, event_name, year, drivers):
        insights = [
            f"# {' vs '.join(drivers)}: {event_name} {year} Qualifying Analysis",
            "\n## Lap-by-Lap Comparison"
        ]
        # extragerea tuturor tururilor
        all_laps = {} #dictionar care va avea lungime 2
        for driver in drivers:
            driver_laps = self.get_all_driver_laps(event_name, year, driver)
            if driver_laps is not None and not driver_laps.empty:
                all_laps[driver] = driver_laps.sort_values('lap_time')
        
        if len(all_laps) != 2:
            insights.append("\n### No valid lap data found for both drivers")
            return "\n".join(insights)
        
        #comparatia tururilor rapide
        insights.append("\n### Fastest Lap Comparison")
        
        if all(driver in all_laps for driver in drivers):
            fastest_times = {driver: laps.iloc[0]['lap_time'] for driver, laps in all_laps.items()}
            
            table_rows = ["|Driver|Fastest Lap|Delta|", "|------|-----------|-----|"]
            ref_driver = min(fastest_times.items(), key=lambda x: x[1])[0] #cel mai rapid absolut
            ref_time = fastest_times[ref_driver]
            
            for driver, lap_time in fastest_times.items():
                delta = lap_time - ref_time
                delta_str = "Reference" if driver == ref_driver else f"+{delta:.3f}s"
                table_rows.append(f"|{driver}|{lap_time:.3f}s|{delta_str}|")
                
            insights.extend(table_rows)
        else:
            insights.append("No valid fastest lap times available")
        
        max_delta = 1.2 #marja de eroare a tururilor 
        max_sector_delta = 1.0 #marja de eroare a sectoarelor
        comparable_laps = {}
        #se cauta tururi compatibile(i.e se filtreaza tururile eronate cauzate de intervalul de 1 secunda de generare a telemetrie din framework)
        for driver, laps in all_laps.items():
            comparable_laps[driver] = []
            for _, lap in laps.iterrows():
                lap_time = lap['lap_time']
                other_driver = [d for d in drivers if d != driver][0]
                other_laps = all_laps[other_driver]
                
                time_diffs_abs = abs(other_laps['lap_time'] - lap_time)
                min_diff_idx = time_diffs_abs.idxmin() if not time_diffs_abs.empty else None
                
                if min_diff_idx is not None:
                    min_diff_abs = time_diffs_abs[min_diff_idx]
                    if min_diff_abs <= max_delta:
                        other_lap = other_laps.loc[min_diff_idx]
                        
                        directional_delta = lap_time - other_lap['lap_time']
                        
                        s1_diff = abs(lap['sector1_time'] - other_lap['sector1_time'])
                        s2_diff = abs(lap['sector2_time'] - other_lap['sector2_time'])
                        s3_diff = abs(lap['sector3_time'] - other_lap['sector3_time'])
                        
                        if s1_diff <= max_sector_delta and s2_diff <= max_sector_delta and s3_diff <= max_sector_delta:
                            comparable_laps[driver].append((lap, directional_delta, other_lap))
            
            print(f"Found {len(comparable_laps[driver])} comparable laps (within 1s total and sector times) for {driver}")
        
        insights.append("\n### Comparable Lap Progression")
        for driver in drivers:
            if driver in comparable_laps and comparable_laps[driver]:
                insights.append(f"\n#### {driver}")
                lap_table = ["|Lap Number|Lap Time|Delta to Best|Delta to Other Driver|", "|----------|--------|-------------|-------------------|"]
                
                best_time = all_laps[driver].iloc[0]['lap_time']
                sorted_laps = sorted(comparable_laps[driver], key=lambda x: x[0]['lap_time'])
                
                for lap, directional_delta, other_lap in sorted_laps:
                    delta = lap['lap_time'] - best_time
                    delta_str = "Best Lap" if delta == 0 else f"+{delta:.3f}s"
                    
                    if directional_delta > 0:
                        delta_str_other = f"+{directional_delta:.3f}s"
                        delta_str_other = f"{directional_delta:.3f}s"
                    
                    if pd.isna(lap['lap_number']):
                        lap_num = "Unknown"
                    else:
                        lap_num = int(lap['lap_number'])
                        
                    lap_table.append(f"|{lap_num}|{lap['lap_time']:.3f}s|{delta_str}|{delta_str_other}|")
                
                insights.extend(lap_table)
            else:
                insights.append(f"\n#### {driver}: No comparable laps found")
        
        insights.append("\n## Sector Performance Analysis")
    
        fastest_laps = {}
        for driver, laps in all_laps.items():
            if not laps.empty:
                fastest_laps[driver] = laps.iloc[0]
        
        if len(fastest_laps) == 2:
            insights.append("\n### Fastest Lap Sector Times")
            sector_table = ["|Driver|Sector 1|Sector 2|Sector 3|", "|------|--------|--------|--------|"]
            
            for driver, lap in fastest_laps.items():
                sector_table.append(f"|{driver}|{lap['sector1_time']:.3f}s|{lap['sector2_time']:.3f}s|{lap['sector3_time']:.3f}s|")
            
            insights.extend(sector_table)
            
            first_driver, second_driver = list(fastest_laps.keys())
            s1_delta = fastest_laps[second_driver]['sector1_time'] - fastest_laps[first_driver]['sector1_time']
            s2_delta = fastest_laps[second_driver]['sector2_time'] - fastest_laps[first_driver]['sector2_time']
            s3_delta = fastest_laps[second_driver]['sector3_time'] - fastest_laps[first_driver]['sector3_time']
            
            insights.append(f"\n### Sector Deltas ({second_driver} vs {first_driver})")
            sector_delta_rows = ["|Sector|Delta|", "|------|-----|"]
            
            s1_prefix = "+" if s1_delta > 0 else ""
            sector_delta_rows.append(f"|Sector 1|{s1_prefix}{s1_delta:.3f}s|")
            
            s2_prefix = "+" if s2_delta > 0 else ""
            sector_delta_rows.append(f"|Sector 2|{s2_prefix}{s2_delta:.3f}s|")
            
            s3_prefix = "+" if s3_delta > 0 else ""
            sector_delta_rows.append(f"|Sector 3|{s3_prefix}{s3_delta:.3f}s|")
            
            insights.extend(sector_delta_rows)
            
            total_delta = s1_delta + s2_delta + s3_delta
            total_prefix = "+" if total_delta > 0 else ""
            insights.append(f"\n#### Total Lap Delta Based on Fastest Lap Sectors")
            insights.append(f"{second_driver} is {total_prefix}{total_delta:.3f}s compared to {first_driver}")
        
            insights.append("\n### Median Sector Times (from comparable laps)")
            median_sectors = {}
            for driver in drivers:
                if driver in comparable_laps and comparable_laps[driver]:
                    comp_lap_dfs = [lap_tuple[0] for lap_tuple in comparable_laps[driver]]
                    if comp_lap_dfs:
                        comp_lap_df = pd.DataFrame(comp_lap_dfs)
                        median_sectors[driver] = {
                            'S1': comp_lap_df['sector1_time'].median(),
                            'S2': comp_lap_df['sector2_time'].median(),
                            'S3': comp_lap_df['sector3_time'].median()
                        }
            
            if len(median_sectors) == 2:
                sector_table = ["|Driver|Sector 1|Sector 2|Sector 3|", "|------|--------|--------|--------|"]
                
                for driver, sectors in median_sectors.items():
                    sector_table.append(f"|{driver}|{sectors['S1']:.3f}s|{sectors['S2']:.3f}s|{sectors['S3']:.3f}s|")
                
                insights.extend(sector_table)
            else:
                insights.append("No comparable lap data available for median sector analysis")
            
            insights.append("\n## Driver Strengths")
            
            if s1_delta < 0:
                insights.append(f"- {second_driver} is faster in Sector 1 by {abs(s1_delta):.3f}s")
            else:
                insights.append(f"- {first_driver} is faster in Sector 1 by {s1_delta:.3f}s")
                
            if s2_delta < 0:
                insights.append(f"- {second_driver} is faster in Sector 2 by {abs(s2_delta):.3f}s")
            else:
                insights.append(f"- {first_driver} is faster in Sector 2 by {s2_delta:.3f}s")
                
            if s3_delta < 0:
                insights.append(f"- {second_driver} is faster in Sector 3 by {abs(s3_delta):.3f}s")
            else:
                insights.append(f"- {first_driver} is faster in Sector 3 by {s3_delta:.3f}s")
        else:
            insights.append("\n### Insufficient comparable lap data for sector analysis")
        
        return "\n".join(insights)

    def get_all_driver_laps(self, event_name, year, driver):
        if not self.conn:
            self.connect()
            
        query = """
        SELECT 
            lap_number,
            MIN(NULLIF(NULLIF(lap_time, ''), 'No time')::interval) as lap_time,
            MIN(NULLIF(sector1_time, 0)) as sector1_time,
            MIN(NULLIF(sector2_time, 0)) as sector2_time,
            MIN(NULLIF(sector3_time, 0)) as sector3_time
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
            AND s.session_type = 'Q'
            AND lap_number > 0
            AND lap_time IS NOT NULL 
            AND lap_time != 'No time'
            AND sector1_time IS NOT NULL AND sector1_time > 0
            AND sector2_time IS NOT NULL AND sector2_time > 0
            AND sector3_time IS NOT NULL AND sector3_time > 0
        GROUP BY 
            lap_number
        ORDER BY 
            MIN(NULLIF(NULLIF(lap_time, ''), 'No time')::interval)
        """
        
        try:
            df = pd.read_sql(query, self.conn, params=(f'%{event_name}%', year, driver))
            
            if not df.empty:
                if pd.api.types.is_datetime64_dtype(df['lap_time']) or hasattr(df['lap_time'].iloc[0], 'total_seconds'):
                    df['lap_time'] = df['lap_time'].apply(lambda x: x.total_seconds() if hasattr(x, 'total_seconds') else x)
                
                max_sector_time = 50.0 #timp nerealist de sector
                df = df[
                    (df['sector1_time'] < max_sector_time) &
                    (df['sector2_time'] < max_sector_time) &
                    (df['sector3_time'] < max_sector_time)
                ]
                
                df['sector_sum'] = df['sector1_time'] + df['sector2_time'] + df['sector3_time']
                df['time_diff'] = abs(df['lap_time'] - df['sector_sum'])
                df = df[df['time_diff'] < 2.0]
                
                df = df.drop(columns=['sector_sum', 'time_diff'])
                
                if not df.empty:
                    print(f"Retrieved {len(df)} valid laps for {driver}")
                    print(f"Best lap: {df['lap_time'].min():.3f}s")
        
            return df
        except Exception as e:
            print(f"Error retrieving lap data for {driver}: {e}")
            traceback.print_exc()
            return None

    def visualize_fastest_lap_speed_comparison(self, event_name, year, drivers, save_path=None):
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        plt.title(f"Fastest Lap Speed Comparison - {' vs '.join(drivers)}\n"
                f"{event_name} {year}", fontsize=16)
        
        driver_styles = self.get_driver_styling(drivers, year)
        
        plotted_data = False
        max_speed = 0
        
        for driver in drivers:
            fastest_lap = self.get_fastest_lap_telemetry(event_name, year, driver)
            
            if fastest_lap is not None and 'telemetry' in fastest_lap:
                tel = fastest_lap['telemetry']
                
                if 'distance' in tel.columns and 'speed' in tel.columns:
                    tel = tel.dropna(subset=['distance', 'speed'])
                    
                    #filtrare de tipul 3-sigma pentru a elimina erori de masurare
                    speed_mean = tel['speed'].mean()
                    speed_std = tel['speed'].std()
                    tel = tel[(tel['speed'] >= 0) & 
                            (tel['speed'] < speed_mean + 3 * speed_std)]
                    
                    if not tel.empty:
                        tel = tel.sort_values('distance')
                        
                        max_speed = max(max_speed, tel['speed'].max() * 1.1)
                        
                        style = driver_styles.get(driver, {'color': 'gray', 'linestyle': '-'})
                        
                        ax.plot(tel['distance'], tel['speed'], 
                                color=style['color'],
                                linestyle=style['linestyle'],
                                label=f"{driver}",
                                linewidth=2)
                        plotted_data = True
        
        if not plotted_data:
            ax.text(0.5, 0.5, "No telemetry data available", 
                    ha='center', va='center', fontsize=14, transform=ax.transAxes)
        else:
            ax.set_xlabel('Distance (m)', fontsize=12)
            ax.set_ylabel('Speed (km/h)', fontsize=12)
            
            ax.set_ylim(0, max_speed)
            
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper right')
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Speed comparison visualization saved to {save_path}")
            
        return fig

    def get_fastest_lap_telemetry(self, event_name, year, driver):
        if not self.conn:
            self.connect()
            
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT lap_number
            FROM telemetry t
            JOIN driver d ON t.driver_id = d.driver_id
            JOIN session s ON t.session_id = s.session_id
            JOIN event e ON s.event_id = e.event_id
            WHERE e.event_name LIKE %s
            AND e.year = %s
            AND d.driver_code = %s
            AND s.session_type = 'Q'
            AND lap_number > 0
            AND lap_time IS NOT NULL
            AND lap_time != 'No time'
            AND sector1_time IS NOT NULL AND sector1_time > 0
            AND sector2_time IS NOT NULL AND sector2_time > 0
            AND sector3_time IS NOT NULL AND sector3_time > 0
            GROUP BY lap_number
            ORDER BY MIN(NULLIF(NULLIF(lap_time, ''), 'No time')::interval)
            LIMIT 1
        """, (f'%{event_name}%', year, driver))
        
        lap_row = cursor.fetchone()
        if not lap_row:
            print(f"No valid lap found for {driver}")
            return None
            
        lap_number = lap_row[0]
        print(f"Found fastest lap {lap_number} for {driver}")
        
        telemetry_query = """
        SELECT 
            t.time_str,
            t.distance,
            t.speed,
            t.throttle, 
            t.brake,
            t.rpm,
            t.drs,
            t.n_gear,
            t.x, t.y, t.z,
            t.sector1_time,
            t.sector2_time,
            t.sector3_time
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
            AND s.session_type = 'Q'
            AND t.lap_number = %s
        ORDER BY 
            t.time_seconds
        """
        
        try:
            telemetry_df = pd.read_sql(telemetry_query, self.conn, 
                                    params=(f'%{event_name}%', year, driver, lap_number))
            
            if telemetry_df.empty:
                print(f"No telemetry data found for {driver}'s lap {lap_number}")
                return None
            
            if 'speed' in telemetry_df.columns:
                telemetry_df = telemetry_df[(telemetry_df['speed'] >= 0) & (telemetry_df['speed'] <= 400)]
                
            if 'distance' in telemetry_df.columns:
                telemetry_df = telemetry_df[telemetry_df['distance'] >= 0]
                telemetry_df = telemetry_df.sort_values('distance')
            
            print(f"Retrieved {len(telemetry_df)} telemetry points for {driver}'s lap {lap_number}")
            return {
                'Driver': driver,
                'LapNumber': lap_number,
                'telemetry': telemetry_df
            }
        except Exception as e:
            print(f"Error retrieving telemetry for {driver}: {e}")
            traceback.print_exc()
            return None
        
    def create_delta_plot(self, event_name, year, drivers, save_path=None):
        median_sectors = {}
        for driver in drivers:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 
                    MIN(NULLIF(sector1_time, 0)) as s1_time,
                    MIN(NULLIF(sector2_time, 0)) as s2_time,
                    MIN(NULLIF(sector3_time, 0)) as s3_time
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
                    AND s.session_type = 'Q'
                    AND lap_number = (
                        SELECT lap_number 
                        FROM telemetry 
                        WHERE driver_id = d.driver_id
                        AND session_id = s.session_id
                        AND lap_time IS NOT NULL 
                        AND lap_time != 'No time'
                        ORDER BY lap_time
                        LIMIT 1
                    )
            """, (f'%{event_name}%', year, driver))
            
            row = cursor.fetchone()
            if row and all(x is not None for x in row):
                median_sectors[driver] = {
                    'S1': row[0],
                    'S2': row[1],
                    'S3': row[2]
                }
                print(f"Fastest lap sectors for {driver}:")
                print(f"S1: {row[0]:.3f}s")
                print(f"S2: {row[1]:.3f}s")
                print(f"S3: {row[2]:.3f}s")
            else:
                print(f"No valid sector times found for {driver}'s fastest lap")
        
        if len(median_sectors) != 2:
            print("Not enough data to create delta plot")
            return None
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        driver_styles = self.get_driver_styling(drivers, year)
        
        ref_tel = None
        for driver in drivers:
            lap_data = self.get_fastest_lap_telemetry(event_name, year, driver)
            if lap_data and 'telemetry' in lap_data and 'distance' in lap_data['telemetry'].columns:
                tel_df = lap_data['telemetry']
                if not tel_df.empty:
                    tel_df = tel_df.dropna(subset=['distance'])
                    tel_df = tel_df[tel_df['distance'] >= 0]
                    if not tel_df.empty:
                        ref_tel = tel_df
                        break
        
        if ref_tel is None:
            print("No telemetry data available for track distance")
            return None
        
        track_length = ref_tel['distance'].max()
        #aproximarea din cauza lipsei datelor exacte pentru sectoare
        sector1_end = track_length * 0.33
        sector2_end = track_length * 0.66
        
        ref_driver = drivers[0]
        comp_driver = drivers[1]
        
        s1_delta = median_sectors[comp_driver]['S1'] - median_sectors[ref_driver]['S1']
        s2_delta = median_sectors[comp_driver]['S2'] - median_sectors[ref_driver]['S2']
        s3_delta = median_sectors[comp_driver]['S3'] - median_sectors[ref_driver]['S3']
        total_delta = s1_delta + s2_delta + s3_delta
        
        anchor_points = [
            [0, 0],
            [sector1_end, s1_delta],
            [sector2_end, s1_delta + s2_delta],
            [track_length, total_delta]
        ]
        
        anchor_points = np.array(anchor_points)
        
        distance_range = np.linspace(0, track_length, 1000)
        delta_interp = np.interp(distance_range, anchor_points[:, 0], anchor_points[:, 1])
        
        ax.plot(distance_range, delta_interp, color='white', linewidth=2)
        
        ref_style = driver_styles.get(ref_driver, {'color': 'magenta'})
        comp_style = driver_styles.get(comp_driver, {'color': 'green'})
        
        ax.fill_between(distance_range, 0, delta_interp, where=(delta_interp > 0), 
                        color=ref_style['color'], alpha=0.5,
                        label=f"{ref_driver} ahead")
        ax.fill_between(distance_range, 0, delta_interp, where=(delta_interp < 0), 
                        color=comp_style['color'], alpha=0.5,
                        label=f"{comp_driver} ahead")
        
        ax.axvline(x=sector1_end, color='gray', linestyle='--', alpha=0.7)
        ax.axvline(x=sector2_end, color='gray', linestyle='--', alpha=0.7)
        
        ax.text(sector1_end/2, 0, "Sector 1", ha='center')
        ax.text(sector1_end + (sector2_end-sector1_end)/2, 0, "Sector 2", ha='center')
        ax.text(sector2_end + (track_length-sector2_end)/2, 0, "Sector 3", ha='center')
        
        ax.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
        
        ax.set_title(f"Fastest Lap Sector Delta: {comp_driver} vs {ref_driver}\n{event_name} {year}", fontsize=16)
        ax.set_xlabel('Distance (m)', fontsize=12)
        ax.set_ylabel('Delta (s)', fontsize=12)
        
        y_max = max(0.5, abs(total_delta) * 1.5)
        ax.set_ylim(-y_max, y_max)
        
        sign = "+" if total_delta > 0 else ""
        ax.text(0.98, 0.05, f"Final delta: {sign}{total_delta:.3f}s", 
                transform=ax.transAxes, ha='right', fontsize=12,
                bbox=dict(facecolor='black', alpha=0.7))
        
        s1_sign = "+" if s1_delta > 0 else ""
        s2_sign = "+" if s2_delta > 0 else ""
        s3_sign = "+" if s3_delta > 0 else ""
        
        sector_text = (f"Sector deltas (fastest lap):\n"
             f"S1: {s1_sign}{s1_delta:.3f}s\n"
             f"S2: {s2_sign}{s2_delta:.3f}s\n"
             f"S3: {s3_sign}{s3_delta:.3f}s")
        
        ax.text(0.02, 0.95, sector_text, 
            transform=ax.transAxes, ha='left', va='top', fontsize=10,
            bbox=dict(facecolor='black', alpha=0.7))
    
        
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Delta time plot saved to {save_path}")
        
        return fig

    def run_quali_analysis(self, event_name, year, drivers, save_to_db=False):
        if not isinstance(drivers, list) or len(drivers) != 2:
            raise ValueError("drivers must be a list of exactly 2 driver codes")
        
        existing_analysis = self.check_existing_analysis(event_name, year, drivers)
        if existing_analysis:
            print(f"Using existing analysis for {' vs '.join(drivers)} at {event_name} {year}")
            return existing_analysis
        
        print(f"Starting qualifying analysis for {' vs '.join(drivers)} at {event_name} {year}")
        
        base_path = os.path.join("analysis", "quali_analysis", event_name, f"{drivers[0]}_vs_{drivers[1]}")
        os.makedirs(base_path, exist_ok=True)
        
        output_file = os.path.join(base_path, f"analysis.md")
        speed_viz_path = os.path.join(base_path, f"speed_comparison.png")
        delta_viz_path = os.path.join(base_path, f"delta_time.png")
        
        all_laps = {}
        for driver in drivers:
            driver_laps = self.get_all_driver_laps(event_name, year, driver)
            if driver_laps is not None and not driver_laps.empty:
                all_laps[driver] = driver_laps.sort_values('lap_time')
                print(f"Found {len(all_laps[driver])} valid laps for {driver}")
                if len(all_laps[driver]) > 0:
                    print(f"  Lap times range: {all_laps[driver]['lap_time'].min():.3f}s - {all_laps[driver]['lap_time'].max():.3f}s")
            else:
                print(f"WARNING: No valid laps found for {driver}!")
        
        print("Generating insights...")
        insights = self.generate_quali_insights(event_name, year, drivers)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(insights)
        print(f"Analysis complete! Results saved to {output_file}")
        
        print("Creating visualizations...")
        speed_fig = self.visualize_fastest_lap_speed_comparison(event_name, year, drivers, speed_viz_path)
        delta_fig = self.create_delta_plot(event_name, year, drivers, delta_viz_path)
        print("Done! Visualizations and analyses saved.")
        
        if save_to_db:
            try:
                self.save_to_database(event_name, year, drivers, insights, speed_viz_path, delta_viz_path)
            except Exception as e:
                print(f"Error saving to database: {e}")
        
        self._create_analysis_index(base_path, {
            'event': event_name,
            'year': year,
            'drivers': drivers,
            'type': 'qualifying',
            'files': {
                'analysis': os.path.basename(output_file),
                'speed_comparison': os.path.basename(speed_viz_path),
                'delta_time': os.path.basename(delta_viz_path)
            }
        })
        
        return {
            "markdown_file": output_file,
            "speed_viz": speed_viz_path,
            "delta_viz": delta_viz_path,
            "insights": insights
        }

    def _create_analysis_index(self, folder_path, metadata):
        index_path = os.path.join(folder_path, "index.json")
        metadata['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(index_path, 'w') as f:
            json.dump(metadata, f, indent=4)
            
    def save_to_database(self, event_name, year, drivers, insights, speed_viz_path, delta_viz_path):
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
                AND s.session_type = 'Q'
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
                'qualifying',
                event_name,
                year,
                f"{drivers[0]} vs {drivers[1]} Qualifying Analysis",
                True,
                f" Qualifying analysis for {drivers[0]} vs {drivers[1]} at {event_name} {year}"
            ))
            
            analysis_id = cursor.fetchone()[0]
    
            results_json = {
                'event': event_name,
                'year': year,
                'drivers': drivers,
            }
            
            cursor.execute("""
                INSERT INTO quali_analysis
                (analysis_id, driver1_code, driver2_code, results_json, markdown_insights, 
                 delta_plot_path, speed_plot_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                analysis_id,
                drivers[0],
                drivers[1],
                json.dumps(results_json),
                insights,
                delta_viz_path,
                speed_viz_path
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
            
            cursor.execute("""
                SELECT 
                    a.analysis_id, 
                    qa.markdown_insights, 
                    qa.delta_plot_path, 
                    qa.speed_plot_path,
                    qa.results_json
                FROM 
                    analysis a
                    JOIN quali_analysis qa ON a.analysis_id = qa.analysis_id
                WHERE 
                    a.event_name LIKE %s 
                    AND a.year = %s
                    /* Removed the analysis_type condition */
                    AND (
                        (qa.driver1_code = %s AND qa.driver2_code = %s)
                        OR 
                        (qa.driver1_code = %s AND qa.driver2_code = %s)
                    )
                ORDER BY a.created_at DESC
                LIMIT 1
            """, (
                f'%{event_name}%',
                year, 
                sorted_drivers[0], sorted_drivers[1],
                sorted_drivers[1], sorted_drivers[0]
            ))
            
            result = cursor.fetchone()
            
            if result:
                analysis_id, markdown, delta_path, speed_path, results_json = result
                
                print(f"Found existing analysis (ID: {analysis_id}) for {' vs '.join(drivers)} at {event_name} {year}")
                
                return {
                    "analysis_id": analysis_id,
                    "markdown_file": None,
                    "speed_viz": speed_path,
                    "delta_viz": delta_path, 
                    "insights": markdown,
                    "from_database": True
                }
            
            return None
            
        except Exception as e:
            print(f"Error checking for existing analysis: {e}")
            return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="F1 Qualifying Analysis Tool (Database Version)")
    parser.add_argument("--event", required=True, help="Event name (e.g. Monaco)")
    parser.add_argument("--year", required=True, type=int, help="Year of the event")        
    parser.add_argument("--drivers", required=True, help="Comma-separated driver codes (e.g. LEC,SAI)")
    parser.add_argument("--db-save", action="store_true", help="Save results to database")
    parser.add_argument("--debug", action="store_true", help="Print diagnostic information")
        
    args = parser.parse_args()
        
    driver_list = [d.strip() for d in args.drivers.split(',')]
    if len(driver_list) != 2:
        print("Error: Exactly 2 driver codes must be provided.")
        exit(1)
        
    db_params = {
        'host': 'localhost',
        'database': 'f1_telemetry',
        'user': 'madalin',
        'password': 'madalin',
        'port': 5432
    }
    
    analyzer = DBF1QualifyingAnalyzer(db_params)
    results = analyzer.run_quali_analysis(
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
        if 'speed_viz' in results and results['speed_viz']:
            print(f"- Speed visualization: {results['speed_viz']}")
        if 'delta_viz' in results and results['delta_viz']:
            print(f"- Delta time visualization: {results['delta_viz']}")
    else:
        print("No results were generated due to errors.")