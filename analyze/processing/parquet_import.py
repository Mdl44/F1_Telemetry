import pandas as pd
import psycopg2
import os
import glob
import argparse
from getpass import getpass
import sys

#transform timpul din string in secunde
def time_to_seconds(time_str):
    if pd.isna(time_str):
        return None
        
    time_parts = time_str.split(':')
    
    if len(time_parts) == 3:
        hours = float(time_parts[0])
        minutes = float(time_parts[1])
        seconds = float(time_parts[2])
        return hours * 3600 + minutes * 60 + seconds
    elif len(time_parts) == 2:
        minutes = float(time_parts[0])
        seconds = float(time_parts[1])
        return minutes * 60 + seconds
    else:
        return float(time_parts[0])

#descompun numele fisierului extras cu framework-ul
def parse_filename(filename):
    base_name = os.path.basename(filename)
    name_without_ext = os.path.splitext(base_name)[0].replace('_telemetry', '')
    
    parts = name_without_ext.split('_')
    
    driver_code = parts[0]
    
    year = int(parts[1])
    
    session_type = parts[-1]
    
    event_name = '_'.join(parts[2:-1])
    event_name = event_name.replace('_', ' ')
    
    full_event_name = f"{year} {event_name}"
    
    return {
        'driver_code': driver_code,
        'year': year,
        'event_name': event_name,
        'full_event_name': full_event_name,
        'session_type': session_type
    }

def get_session_and_driver_ids(conn, driver_code, full_event_name, session_type):
    cursor = conn.cursor()
    #inconsistenta pentru cursa din Brazilia
    race_name_mapping = {
    "2024 São Paulo Grand Prix": "2024 Brazilian Grand Prix",
    "2023 São Paulo Grand Prix": "2023 Brazilian Grand Prix",
    "2022 São Paulo Grand Prix": "2022 Brazilian Grand Prix",
    }
    
    mapped_event_name = race_name_mapping.get(full_event_name, full_event_name)
    
    try:
        cursor.execute("SELECT driver_id FROM driver WHERE driver_code = %s", (driver_code,))
        driver_result = cursor.fetchone()
        
        if not driver_result:
            print(f"Warning: Driver with code '{driver_code}' not found in the database")
            return None, None
        
        driver_id = driver_result[0]
        
        cursor.execute("""
            SELECT s.session_id 
            FROM session s
            JOIN event e ON s.event_id = e.event_id
            WHERE e.event_name = %s AND s.session_type = %s
        """, (mapped_event_name, session_type))
        
        session_result = cursor.fetchone()
        
        if not session_result:
            print(f"Warning: Session for event '{full_event_name}' and type '{session_type}' not found in the database")
            return None, None
        
        session_id = session_result[0]
        
        return session_id, driver_id
        
    finally:
        cursor.close()

def import_telemetry_data(file_path, session_id, driver_id, conn, batch_size=1000):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return 0
    
    print(f"Processing {file_path}...")
    
    try:
        df = pd.read_parquet(file_path)
        
    except Exception as e:
        print(f"Error reading Parquet file: {e}")
        return 0
    
    rows_inserted = 0
    total_rows = len(df)
    batch_data = [] #buffer de date pentru insert
    cursor = conn.cursor()
    
    try:
        for index, row in df.iterrows():
            try:
                time_seconds = time_to_seconds(row.get('Time'))
                
                driver = row.get('Driver', row.get('driver', None))
                team = row.get('Team', row.get('team', None))
                team_id = row.get('TeamId', row.get('team_id', None))
                time_str = row.get('Time', row.get('time_str', None))
                speed = row.get('Speed', row.get('speed', None))
                throttle = row.get('Throttle', row.get('throttle', None))
                brake = row.get('Brake', row.get('brake', False))
                rpm = row.get('RPM', row.get('rpm', None))
                drs = row.get('DRS', row.get('drs', None))
                lap_number = row.get('LapNumber', row.get('lap_number', None))
                lap_time = row.get('LapTime', row.get('lap_time', None))
                position = row.get('Position', row.get('position', None))
                is_fastest_lap = row.get('IsFastestLap', row.get('is_fastest_lap', False))
                tire_compound = row.get('TireCompound', row.get('tire_compound', None))
                tyre_life = row.get('TyreLife', row.get('tyre_life', None))
                track_status = row.get('TrackStatus', row.get('track_status', None))
                air_temp = row.get('AirTemp', row.get('air_temp', None))
                track_temp = row.get('TrackTemp', row.get('track_temp', None))
                rainfall = row.get('Rainfall', row.get('rainfall', None))
                
                distance = row.get('Distance', None)
                n_gear = row.get('n_gear', None)
                x = row.get('X', row.get('x', None))
                y = row.get('Y', row.get('y', None))
                z = row.get('Z', row.get('z', None))
                sector = row.get('Sector', None)
                sector1_time = row.get('Sector1Time', None)
                sector2_time = row.get('Sector2Time', None)
                sector3_time = row.get('Sector3Time', None)
                humidity = row.get('Humidity', row.get('humidity', None))
                wind_speed = row.get('WindSpeed', row.get('wind_speed', None))
                wind_direction = row.get('WindDirection', row.get('wind_direction', None)) 
                driver_ahead = row.get('DriverAhead', None)
                distance_to_driver_ahead = row.get('DistanceToDriverAhead', None)
                
                if speed is not None and not pd.isna(speed):
                    speed = float(speed)
                if throttle is not None and not pd.isna(throttle):
                    throttle = float(throttle)
                if brake is not None and isinstance(brake, str):
                    brake = (brake.lower() == 'true')
                if rpm is not None and not pd.isna(rpm):
                    rpm = float(rpm)
                if drs is not None and not pd.isna(drs):
                    drs = int(drs)
                if lap_number is not None and not pd.isna(lap_number):
                    lap_number = float(lap_number)
                if position is not None and not pd.isna(position):
                    position = float(position)
                if is_fastest_lap is not None and isinstance(is_fastest_lap, str):
                    is_fastest_lap = (is_fastest_lap.lower() == 'true')
                if tyre_life is not None and not pd.isna(tyre_life):
                    tyre_life = float(tyre_life)
                if air_temp is not None and not pd.isna(air_temp):
                    air_temp = float(air_temp)
                if track_temp is not None and not pd.isna(track_temp):
                    track_temp = float(track_temp)
                if rainfall is not None and not pd.isna(rainfall):
                    rainfall = float(rainfall)
                if track_status is not None:
                    track_status = str(track_status)
                if distance is not None and not pd.isna(distance):
                    distance = float(distance)
                if n_gear is not None and not pd.isna(n_gear):
                    n_gear = int(n_gear)
                if x is not None and not pd.isna(x):
                    x = float(x)
                if y is not None and not pd.isna(y):
                    y = float(y)
                if z is not None and not pd.isna(z):
                    z = float(z)
                if sector is not None and not pd.isna(sector):
                    sector = int(sector)
                if sector1_time is not None and not pd.isna(sector1_time):
                    sector1_time = float(sector1_time)
                if sector2_time is not None and not pd.isna(sector2_time):
                    sector2_time = float(sector2_time)
                if sector3_time is not None and not pd.isna(sector3_time):
                    sector3_time = float(sector3_time)
                if humidity is not None and not pd.isna(humidity):
                    humidity = float(humidity)
                if wind_speed is not None and not pd.isna(wind_speed):
                    wind_speed = float(wind_speed)
                if wind_direction is not None and not pd.isna(wind_direction):
                    wind_direction = float(wind_direction)
                if distance_to_driver_ahead is not None and not pd.isna(distance_to_driver_ahead):
                    distance_to_driver_ahead = float(distance_to_driver_ahead)
                
                batch_data.append((
                    session_id,
                    driver_id,
                    driver,
                    team,
                    team_id,
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
                    track_status,
                    air_temp,
                    track_temp,
                    rainfall,
                    time_seconds,
                    distance,
                    n_gear,
                    x,
                    y,
                    z,
                    sector1_time,
                    sector2_time, 
                    sector3_time,
                    humidity,
                    wind_speed,
                    wind_direction,
                    driver_ahead,
                    distance_to_driver_ahead
            ))
                
                if len(batch_data) >= batch_size:
                    try:
                        insert_batch(cursor, batch_data)
                        rows_inserted += len(batch_data)
                        conn.commit()
                        print(f"Progress: {rows_inserted}/{total_rows} rows inserted ({rows_inserted/total_rows*100:.1f}%)")
                    except Exception as e:
                        conn.rollback()
                        print(f"Error inserting batch: {e}")
                        print(f"Skipping batch of {len(batch_data)} rows")
                    finally:
                        batch_data = []
                
            except Exception as e:
                print(f"Error processing row {index}: {e}")
        
        if batch_data:
            try:
                insert_batch(cursor, batch_data)
                rows_inserted += len(batch_data)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"Error inserting final batch: {e}")
        
        print(f"Completed importing {file_path}. Total rows inserted: {rows_inserted}/{total_rows}")
        return rows_inserted
        
    except Exception as e:
        conn.rollback() 
        print(f"Error during import: {e}")
        return 0
    finally:
        cursor.close()

def insert_batch(cursor, batch_data):
    sql = """
    INSERT INTO telemetry (
        session_id, driver_id, driver, team, team_id, time_str, speed, throttle, brake,
        rpm, drs, lap_number, lap_time, position, is_fastest_lap, tire_compound, tyre_life,
        track_status, air_temp, track_temp, rainfall, time_seconds, 
        distance, n_gear, x, y, z, sector1_time, sector2_time, sector3_time,
        humidity, wind_speed, wind_direction, driver_ahead, distance_to_driver_ahead
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    cursor.executemany(sql, batch_data)

def process_directory(directory_path, db_params, batch_size=1000, year_filter="2022"):
    parquet_pattern = os.path.join(directory_path, "*_telemetry.parquet")
    all_files = glob.glob(parquet_pattern)

    if year_filter:
        files = [f for f in all_files if f"_{year_filter}_" in os.path.basename(f)]
        print(f"Filtering for {year_filter} data only")
    else:
        files = all_files
    
    if not files:
        print(f"No matching telemetry Parquet files found in {directory_path}")
        return
    
    print(f"Found {len(files)} telemetry files to process")
    
    try:
        conn = psycopg2.connect(
            host=db_params['host'],
            database=db_params['database'],
            user=db_params['user'],
            password=db_params['password'],
            port=db_params.get('port', 5432)
        )
    except Exception as e:
        print(f"Database connection error: {e}")
        return
    
    total_imported = 0
    
    for file_path in files:
        try:
            metadata = parse_filename(file_path)
            print(f"\nProcessing file: {os.path.basename(file_path)}")
            print(f"  Driver: {metadata['driver_code']}")
            print(f"  Event: {metadata['full_event_name']}")
            print(f"  Session: {metadata['session_type']}")
            
            session_id, driver_id = get_session_and_driver_ids(
                conn, 
                metadata['driver_code'],
                metadata['full_event_name'],
                metadata['session_type']
            )
            
            if session_id is None or driver_id is None:
                print(f"  Skipping file due to missing database references")
                continue
                
            print(f"  Found session_id: {session_id}, driver_id: {driver_id}")
            
            imported = import_telemetry_data(file_path, session_id, driver_id, conn, batch_size)
            total_imported += imported
            
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
    
    print(f"\nImport completed. Total records imported: {total_imported}")
    conn.close()

def check_postgres_connection(db_params):
    print("\n=== PostgreSQL Connection Information ===")
    print(f"Attempting to connect to: {db_params['host']}:{db_params['port']}")
    print(f"Database: {db_params['database']}")
    print(f"User: {db_params['user']}")
    
    try:
        conn = psycopg2.connect(
            host=db_params['host'],
            database=db_params['database'],
            user=db_params['user'],
            password=db_params['password'],
            port=db_params.get('port', 5432)
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT current_user, current_database(), version()")
        user_info = cursor.fetchone()
        
        print("\nSuccessfully connected!")
        print(f"Connected as: {user_info[0]}")
        print(f"Current database: {user_info[1]}")
        print(f"PostgreSQL version: {user_info[2]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"\nConnection failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Import F1 telemetry data into database')
    
    parser.add_argument('--host', default='localhost', help='Database host')
    parser.add_argument('--port', type=int, default=5432, help='Database port')
    parser.add_argument('--database', help='Database name')
    parser.add_argument('--user', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--prompt-password', action='store_true', help='Prompt for password')
    parser.add_argument('--directory', default='D:\\mds\\f1_data_parquet', help='Directory containing telemetry Parquet files')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for inserts')
    parser.add_argument('--check', action='store_true', help='Check connection only without importing')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode to enter connection details')
    parser.add_argument('--year', default='2022', help='Filter files by year (e.g., 2022)')
    
    args = parser.parse_args()
    
    if args.interactive:
        print("\n=== PostgreSQL Connection Setup ===")
        host = input(f"Database host [{args.host}]: ") or args.host
        port = input(f"Database port [{args.port}]: ") or args.port
        database = input("Database name [postgres]: ") or 'postgres'
        user = input("Database user [postgres]: ") or 'postgres'
        password = getpass("Database password: ")
        
        db_params = {
            'host': host,
            'port': int(port),
            'database': database,
            'user': user,
            'password': password,
        }
    else:
        db_params = {
            'host': args.host,
            'port': args.port,
            'database': args.database or os.environ.get('PGDATABASE') or 'postgres',
            'user': args.user or os.environ.get('PGUSER') or 'postgres',
            'password': args.password or os.environ.get('PGPASSWORD') or '',
        }
        
        if args.prompt_password or not db_params['password']:
            db_params['password'] = getpass("Enter PostgreSQL password: ")
    
    print(f"Connecting as user: {db_params['user']}")
    if not check_postgres_connection(db_params):
        print("Connection failed. Please check your credentials.")
        sys.exit(1)
        
    if args.check:
        print("Connection check completed.")
        return
    
    process_directory(args.directory, db_params, args.batch_size, args.year)

if __name__ == "__main__":
    main()