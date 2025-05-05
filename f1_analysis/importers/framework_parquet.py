import fastf1 #libraria de unde am extras toate datele(foloseste F1 API)
import pandas as pd #date
import os
import numpy as np #operatii matematice
from datetime import timedelta #operatii pe date de timp
import json
import time

CACHE_DIR = os.environ.get('F1_CACHE_DIR', r'D:\mds\cache') #pachetul fiind bazat pe un api, are nevoie de un fisier unde sa stocheze cache-ul
OUTPUT_DIR = os.environ.get('F1_DATA_DIR', r'D:\mds\f1_data_parquet')

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
fastf1.Cache.enable_cache(CACHE_DIR)

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

SEASONS = {
    2022: {
        'races': range(1, 23),
        'sessions': ['R', 'Q'] 
    },
    2023: {
        'races': range(1, 24),
        'sessions': ['R', 'Q']
    },
    2024: {
        'races': range(1, 25),
        'sessions': ['R', 'Q']
    }
}

def extract_telemetry(year, race_name, session_type, driver_code, sample_interval):
    try:
        print(f"Extracting telemetry for {driver_code} - {year} {race_name} {session_type}")
        
        #se incarca sesiunea
        session = fastf1.get_session(year, race_name, session_type)
        session.load()
        
        #link pentru pilot-echipa
        driver_info = None
        try:
            for _, driver_row in session.results.iterrows():
                if driver_row['Abbreviation'] == driver_code:
                    driver_info = driver_row
                    break
            
            if driver_info is None:
                driver_info = session.get_driver(driver_code)
                
            team_name = driver_info.get('TeamName', 'Unknown')
            team_id = driver_info.get('TeamId', 'Unknown')
            print(f"Driver {driver_code} belongs to team: {team_name} (ID: {team_id})")
            
        except Exception as e:
            print(f"Warning: Could not get team information for {driver_code}: {e}")
            team_name = "Unknown"
            team_id = "Unknown"
            
        
        #extragerea tururilor si a info despre vreme
        driver_laps = session.laps.pick_drivers(driver_code)
        if driver_laps.empty:
            print(f"No lap data found for {driver_code}")
            return None
        
        all_laps = session.laps
        fastest_laps = {} #pentru fiecare tur
        for lap_num in all_laps['LapNumber'].unique():
            lap_subset = all_laps[all_laps['LapNumber'] == lap_num]
            if lap_subset['LapTime'].isna().all(): #tur valid
                continue
            fastest_time = lap_subset['LapTime'].min()
            fastest_driver = lap_subset[lap_subset['LapTime'] == fastest_time]['Driver'].iloc[0]
            fastest_laps[lap_num] = fastest_driver
        
        try:
            session_weather = session.weather_data
        except:
            session_weather = None
            print(f"Warning: Could not load session weather data for {driver_code}")
        
        #procesarea datelor de telemetrie
        telemetry_frames = []
        for _, lap in driver_laps.iterlaps():
            try:
                tel = lap.get_car_data() #dataframe pandas cu datele masinii
                if tel.empty:
                    continue
                    
                lap_num = lap['LapNumber']
                
                tel['LapNumber'] = lap_num
                tel['Position'] = lap['Position'] if 'Position' in lap and not pd.isna(lap['Position']) else None
                
                tel['Team'] = team_name
                tel['TeamId'] = team_id
                
                tel['TireCompound'] = lap['Compound'] if 'Compound' in lap and not pd.isna(lap['Compound']) else 'Unknown'
                
                tel['TyreLife'] = lap['TyreLife'] if 'TyreLife' in lap and not pd.isna(lap['TyreLife']) else None
                
                tel['TrackStatus'] = lap['TrackStatus'] if 'TrackStatus' in lap and not pd.isna(lap['TrackStatus']) else None
                
                #date de pozitie x,y,z
                try:
                    pos_tel = lap.get_pos_data()
                    if not pos_tel.empty:
                        tel = tel.merge_channels(pos_tel)
                except Exception as pe:
                    print(f"Warning: Could not get position data for lap {lap_num}: {pe}")
                
                #alte date care pot ajuta din metoda get_telemetry()
                try:
                    full_tel = lap.get_telemetry()
                    if not full_tel.empty:
                        missing_cols = set(full_tel.columns) - set(tel.columns)
                        for col in missing_cols:
                            if col in full_tel.columns:
                                tel[col] = full_tel[col]
                except Exception as te:
                    print(f"Warning: Could not get additional telemetry for lap {lap_num}: {te}")
                
                #date de vreme
                if session_weather is not None and not session_weather.empty:
                    try:
                        tel['AirTemp'] = session_weather['AirTemp'].median() if 'AirTemp' in session_weather else None
                        tel['TrackTemp'] = session_weather['TrackTemp'].median() if 'TrackTemp' in session_weather else None 
                        tel['Rainfall'] = session_weather['Rainfall'].median() if 'Rainfall' in session_weather else None
                        tel['Humidity'] = session_weather['Humidity'].median() if 'Humidity' in session_weather else None
                        tel['WindSpeed'] = session_weather['WindSpeed'].median() if 'WindSpeed' in session_weather else None
                        tel['WindDirection'] = session_weather['WindDirection'].median() if 'WindDirection' in session_weather else None
                    except Exception as e:
                        print(f"Warning: Weather data error: {e}")
                        tel['AirTemp'] = None
                        tel['TrackTemp'] = None
                        tel['Rainfall'] = None
                else:
                    tel['AirTemp'] = None
                    tel['TrackTemp'] = None
                    tel['Rainfall'] = None
                
                #marcare pentru tur rapid
                is_fastest = fastest_laps.get(lap_num) == driver_code
                tel['IsFastestLap'] = is_fastest
                
                #formatez timpul in string pentru baza de date
                if pd.notna(lap['LapTime']):
                    seconds = lap['LapTime'].total_seconds()
                    minutes = int(seconds // 60)
                    remaining_seconds = seconds % 60
                    formatted_lap_time = f"{minutes}:{remaining_seconds:.3f}"
                else:
                    formatted_lap_time = "No time"
                    
                tel['LapTime'] = formatted_lap_time
                tel['Driver'] = driver_code
                
                #timpii pe sectoare
                for i in range(1, 4):
                    sector_col = f'Sector{i}Time'
                    if sector_col in lap and not pd.isna(lap[sector_col]):
                        tel[f'Sector{i}Time'] = lap[sector_col].total_seconds()
                    else:
                        tel[f'Sector{i}Time'] = None
                
                if 'Distance' not in tel.columns:
                    try:
                        tel = tel.add_distance()
                    except Exception as de:
                        print(f"Warning: Could not add distance for lap {lap_num}: {de}")
                
                #interval de 1 secunda pentru date
                tel = tel.reset_index(drop=True)
                tel['Seconds'] = tel['Time'].dt.total_seconds() #timestamp-urile 
                tel['SecondBin'] = tel['Seconds'].apply(lambda x: sample_interval * np.floor(x/sample_interval))
                
                tel_resampled = tel.groupby('SecondBin').first().reset_index()#pastreaza doar prima data 
                
                tel_resampled['Time'] = tel_resampled['Time'].apply(
                    lambda x: str(timedelta(seconds=x.total_seconds())).split(', ')[-1]
                )
                
                telemetry_frames.append(tel_resampled.copy())
                
            except Exception as e:
                print(f"Error processing lap {lap_num if 'lap_num' in locals() else 'unknown'} for {driver_code}: {e}")
                continue
        
        if telemetry_frames:
            driver_telemetry = pd.concat(telemetry_frames, ignore_index=True)
            
            columns_to_keep = [
                'Driver', 'Team', 'TeamId', 'Time', 'Distance', 'Speed', 'Throttle', 'Brake', 'RPM', 
                'n_gear', 'DRS', 'LapNumber', 'LapTime', 'X', 'Y', 'Z', 'Sector',
                'Position', 'IsFastestLap', 'TireCompound', 'TyreLife', 'TrackStatus',
                'Sector1Time', 'Sector2Time', 'Sector3Time',
                'AirTemp', 'TrackTemp', 'Rainfall', 'Humidity', 'WindSpeed', 'WindDirection',
                'DriverAhead', 'DistanceToDriverAhead'
            ]
            
            available_cols = [col for col in columns_to_keep if col in driver_telemetry.columns]
            driver_telemetry = driver_telemetry[available_cols]
            
            all_columns = driver_telemetry.columns.tolist()
            if 'Driver' in all_columns and all_columns[0] != 'Driver':
                all_columns.remove('Driver')
                all_columns = ['Driver'] + all_columns
                driver_telemetry = driver_telemetry[all_columns]
            
            output_parquet = os.path.join(OUTPUT_DIR, f"{driver_code}_{year}_{race_name}_{session_type}_telemetry.parquet")
            driver_telemetry.to_parquet(output_parquet, compression='gzip', index=False)
            
            print(f"Parquet file exported successfully as {output_parquet}")
            print(f"Total data points: {len(driver_telemetry)}")
            return output_parquet
        else:
            print(f"No telemetry data for {driver_code}")
            return None
    
    except Exception as e:
        print(f"Error extracting telemetry for {driver_code}: {e}")
        return None

DRIVERS_BY_SEASON = {
    2022: {
        'mercedes': ['HAM', 'RUS'],
        'red_bull': ['VER', 'PER'],
        'ferrari': ['LEC', 'SAI'],
        'mclaren': ['NOR', 'RIC'],
        'alpine': ['ALO', 'OCO'],
        'alphatauri': ['GAS', 'TSU'],
        'aston_martin': ['VET', 'STR'],
        'williams': ['LAT', 'ALB'],
        'alfa': ['BOT', 'ZHO'],
        'haas': ['MSC', 'MAG']
    },
    2023: {
        'mercedes': ['HAM', 'RUS'],
        'red_bull': ['VER', 'PER'],
        'ferrari': ['LEC', 'SAI'],
        'mclaren': ['NOR', 'PIA'],
        'alpine': ['GAS', 'OCO'],
        'alphatauri': ['DEV', 'TSU', 'RIC'],
        'aston_martin': ['ALO', 'STR'],
        'williams': ['ALB', 'SAR'],
        'alfa': ['BOT', 'ZHO'],
        'haas': ['HUL', 'MAG']
    },
    2024: {
        'mercedes': ['HAM', 'RUS'],
        'red_bull': ['VER', 'PER'],
        'ferrari': ['LEC', 'SAI'],
        'mclaren': ['NOR', 'PIA'],
        'alpine': ['GAS', 'OCO'],
        'rb': ['TSU', 'RIC'],
        'aston_martin': ['ALO', 'STR'],
        'williams': ['ALB', 'SAR'],
        'sauber': ['BOT', 'ZHO'],
        'haas': ['HUL', 'MAG']
    }
}

#gasirea pilotilor pentru fiecare sesiune
def get_drivers_for_session(session):
    drivers = []
    
    try:
        if hasattr(session, 'results') and not session.results.empty:
            for _, row in session.results.iterrows():
                if 'Abbreviation' in row and pd.notna(row['Abbreviation']):
                    drivers.append(row['Abbreviation'])
        
        if not drivers and hasattr(session, 'drivers'):
            drivers = list(session.drivers.keys())
    
        drivers = [d for d in drivers if d and pd.notna(d)]
        
        if drivers:
            print(f"Discovered {len(drivers)} drivers in session: {', '.join(drivers)}")
            return drivers
        else:
            raise ValueError("No drivers found in session")
            
    except Exception as e:
        print(f"Error discovering drivers: {e}")
        return []

def main():
    #un punct de save 
    progress_file = os.path.join(OUTPUT_DIR, "extraction_progress.json")
    
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            completed = json.load(f)
    else:
        completed = {}
    
    for year, season_data in SEASONS.items():
        if str(year) not in completed:
            completed[str(year)] = {}
            
        for race_num in season_data['races']:
            try:
                race_info = fastf1.get_event(year, race_num)
                race_name = race_info.EventName
                
                race_key = f"race_{race_num}"
                if race_key not in completed[str(year)]:
                    completed[str(year)][race_key] = {}
                
                use_dynamic_discovery = True
                
                for session_type in season_data['sessions']:
                    session_key = f"{session_type}"
                    
                    if session_key not in completed[str(year)][race_key]:
                        completed[str(year)][race_key][session_key] = []
                    
                    drivers_to_extract = None

                    
                    if use_dynamic_discovery: #caut dinamic cu datele pachetului, daca nu merge folosesc lista predefinita
                        try:
                            session = fastf1.get_session(year, race_name, session_type)
                            session.load(laps=True, telemetry=False)
                            
                            drivers_to_extract = get_drivers_for_session(session)
                            
                        except Exception as e:
                            print(f"Error loading session to discover drivers: {e}")
                            
                            
                    if not drivers_to_extract:
                        year_drivers = []
                        for team_drivers in DRIVERS_BY_SEASON.get(year, {}).values():
                            year_drivers.extend(team_drivers)
                        drivers_to_extract = year_drivers
                        print(f"Using predefined driver list for {year}: {drivers_to_extract}")
                        
                    
                    #daca exista deja fisierul trece peste
                    for driver_code in drivers_to_extract:
                        if driver_code in completed[str(year)][race_key][session_key]:
                            print(f"Skipping already completed: {year} {race_name} {session_type} - {driver_code}")
                            continue
                        
                        print(f"\n{'='*50}")
                        print(f"Processing: {year} {race_name} {session_type} - {driver_code}")
                        print(f"{'='*50}\n")
                        
                        parquet_file = extract_telemetry(year, race_name, session_type, driver_code, sample_interval=1.0) #1 secunda
                        
                        if parquet_file:
                            completed[str(year)][race_key][session_key].append(driver_code)
                            
                            with open(progress_file, 'w') as f:
                                json.dump(completed, f)
                            
                            print(f"Completed {year} {race_name} {session_type} - {driver_code}")
                        
                        time.sleep(2) #limita de 2 secunde impusa de api
            
            except Exception as e:
                print(f"Error processing race {race_num} in {year}: {e}")
                continue

if __name__ == "__main__":
    year = 2024
    for race_num in SEASONS[year]['races']:
        try:
            race_info = fastf1.get_event(year, race_num)
            race_name = race_info.EventName
            
            for session_type in SEASONS[year]['sessions']:
                print(f"\n{'='*50}")
                print(f"Processing race: {race_name} - {session_type}")
                print(f"{'='*50}\n")
                
                # Process all teams and drivers for 2024
                for team, drivers in DRIVERS_BY_SEASON[year].items():
                    print(f"Processing team: {team}")
                    for driver_code in drivers:
                        print(f"Extracting data for {driver_code}")
                        extract_telemetry(year, race_name, session_type, driver_code, sample_interval=1.0)
                        time.sleep(2)  # Prevent API rate limiting
        except Exception as e:
            print(f"Error processing race {race_num}: {e}")
            continue