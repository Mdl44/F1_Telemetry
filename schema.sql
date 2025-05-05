DROP VIEW IF EXISTS effective_user_permissions;
DROP VIEW IF EXISTS user_permissions;

DROP TRIGGER IF EXISTS time_str_to_seconds ON telemetry;
DROP TRIGGER IF EXISTS event_entry_team_consistency ON event_entry;
DROP TRIGGER IF EXISTS update_users_timestamp ON users;
DROP TRIGGER IF EXISTS update_team_timestamp ON team;

DROP TABLE IF EXISTS telemetry;
DROP TABLE IF EXISTS ai_analysis;
DROP TABLE IF EXISTS session;
DROP TABLE IF EXISTS event_entry;
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS driver_team;
DROP TABLE IF EXISTS user_team_access;
DROP TABLE IF EXISTS driver;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS team;

DROP FUNCTION IF EXISTS calculate_time_seconds();
DROP FUNCTION IF EXISTS check_event_entry_team();
DROP FUNCTION IF EXISTS update_modified_timestamp();

DROP INDEX IF EXISTS idx_user_email;
DROP INDEX IF EXISTS idx_user_username;
DROP INDEX IF EXISTS idx_user_primary_team;
DROP INDEX IF EXISTS idx_user_team_access_user;
DROP INDEX IF EXISTS idx_user_team_access_team;
DROP INDEX IF EXISTS idx_driver_code;
DROP INDEX IF EXISTS idx_driver_team_driver;
DROP INDEX IF EXISTS idx_driver_team_team;
DROP INDEX IF EXISTS idx_driver_team_year;
DROP INDEX IF EXISTS idx_telemetry_session_driver;
DROP INDEX IF EXISTS idx_telemetry_lap;

--Tabele--------------------------------------------------------------------
CREATE TABLE team (
    team_id VARCHAR(50) PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    team_code VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    
    role_id VARCHAR(20) NOT NULL DEFAULT 'viewer' 
        CHECK (role_id IN ('viewer', 'team_member', 'analyst', 'admin')),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_team_access (
    access_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    team_id VARCHAR(50) REFERENCES team(team_id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, team_id)
);

CREATE TABLE driver (
    driver_id SERIAL PRIMARY KEY,
    driver_code VARCHAR(3) UNIQUE NOT NULL CHECK (driver_code = UPPER(driver_code)),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    number INT,
    country VARCHAR(50),
    date_of_birth DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE driver_team (
    driver_team_id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES driver(driver_id) ON DELETE CASCADE,
    team_id VARCHAR(50) REFERENCES team(team_id) ON DELETE CASCADE,
    year INTEGER NOT NULL CHECK (year >= 1950 AND year <= 2100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(driver_id, team_id, year)
);

CREATE TABLE event (
    event_id SERIAL PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    circuit_name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    country VARCHAR(50) NOT NULL,
    event_date DATE NOT NULL
);

CREATE TABLE event_entry (
    entry_id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES event(event_id) NOT NULL,
    driver_id INTEGER REFERENCES driver(driver_id) NOT NULL,
    team_id VARCHAR(50) REFERENCES team(team_id) NOT NULL,
    UNIQUE(event_id, driver_id)
);

CREATE TABLE session (
    session_id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES event(event_id) NOT NULL,
    session_type CHAR(1) NOT NULL CHECK (session_type IN ('Q', 'R')),
    session_date TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE telemetry (
    telemetry_id BIGSERIAL PRIMARY KEY,
    
    session_id INTEGER REFERENCES session(session_id),
    driver_id INTEGER REFERENCES driver(driver_id),
    driver VARCHAR(3),
    team VARCHAR(100),
    team_id VARCHAR(50),
    time_str VARCHAR(20),
    speed FLOAT,
    throttle FLOAT,
    brake BOOLEAN,
    rpm FLOAT,
    drs INTEGER,
    lap_number FLOAT,
    lap_time VARCHAR(20),
    position FLOAT,
    is_fastest_lap BOOLEAN,
    tire_compound VARCHAR(20),
    tyre_life FLOAT,
    track_status VARCHAR(20),
    air_temp FLOAT,
    track_temp FLOAT,
    rainfall FLOAT,
    
    time_seconds FLOAT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE telemetry ADD COLUMN distance FLOAT;
ALTER TABLE telemetry ADD COLUMN n_gear INTEGER;
ALTER TABLE telemetry ADD COLUMN x FLOAT;
ALTER TABLE telemetry ADD COLUMN y FLOAT;
ALTER TABLE telemetry ADD COLUMN z FLOAT;
ALTER TABLE telemetry ADD COLUMN sector1_time FLOAT;
ALTER TABLE telemetry ADD COLUMN sector2_time FLOAT;
ALTER TABLE telemetry ADD COLUMN sector3_time FLOAT;
ALTER TABLE telemetry ADD COLUMN humidity FLOAT;
ALTER TABLE telemetry ADD COLUMN wind_speed FLOAT;
ALTER TABLE telemetry ADD COLUMN wind_direction FLOAT;
ALTER TABLE telemetry ADD COLUMN driver_ahead VARCHAR(3);
ALTER TABLE telemetry ADD COLUMN distance_to_driver_ahead FLOAT;


CREATE TABLE analysis (
    analysis_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES session(session_id),
    analysis_type VARCHAR(50) NOT NULL CHECK (analysis_type IN ('qualifying', 'race')),
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    event_name VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    analysis_name VARCHAR(100),
    is_public BOOLEAN DEFAULT FALSE,
    description TEXT
);

CREATE TABLE quali_analysis (
    quali_analysis_id SERIAL PRIMARY KEY,
    analysis_id INTEGER REFERENCES analysis(analysis_id) ON DELETE CASCADE,
    driver1_code VARCHAR(3) NOT NULL,
    driver2_code VARCHAR(3) NOT NULL,
    results_json JSONB,
    markdown_insights TEXT,
    delta_plot_path VARCHAR(255),
    speed_plot_path VARCHAR(255)
);

CREATE TABLE race_analysis (
    race_analysis_id SERIAL PRIMARY KEY,
    analysis_id INTEGER REFERENCES analysis(analysis_id) ON DELETE CASCADE,
    drivers_json JSONB,
    tire_data_json JSONB,
    compound_performance_json JSONB,
    markdown_insights TEXT,
    lap_times_plot_path VARCHAR(255),
    tire_strategy_plot_path VARCHAR(255),
    position_plot_path VARCHAR(255)
);

-------------------------------------------------------------------------------

--Index------------------------------------------------------------------------
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_user_username ON users(username);
CREATE INDEX idx_user_team_access_user ON user_team_access(user_id);
CREATE INDEX idx_user_team_access_team ON user_team_access(team_id);
CREATE INDEX idx_driver_code ON driver(driver_code);
CREATE INDEX idx_driver_team_driver ON driver_team(driver_id);
CREATE INDEX idx_driver_team_team ON driver_team(team_id);
CREATE INDEX idx_driver_team_year ON driver_team(year);
CREATE INDEX idx_telemetry_session_driver ON telemetry(session_id, driver_id);
CREATE INDEX idx_telemetry_lap ON telemetry(session_id, driver_id, lap_number);
CREATE UNIQUE INDEX idx_user_primary_team 
ON user_team_access (user_id) 
WHERE is_primary = TRUE;
CREATE INDEX idx_telemetry_position ON telemetry(session_id, x, y);
-------------------------------------------------------------------------------

--View-------------------------------------------------------------------------
CREATE VIEW user_permissions AS
SELECT 
    user_id,
    username,
    email,
    role_id,
    TRUE AS can_view_telemetry,
    
    (role_id IN ('team_member', 'analyst', 'admin')) AS can_use_ai,
    
    (role_id IN ('analyst', 'admin')) AS can_create,
    (role_id IN ('analyst', 'admin')) AS can_update,
    (role_id IN ('analyst', 'admin')) AS can_delete,
    
    (role_id = 'admin') AS can_admin
FROM 
    users;

CREATE OR REPLACE VIEW effective_user_permissions AS
SELECT
    u.user_id,
    u.username,
    u.role_id,
    p.can_view_telemetry,
    p.can_use_ai,
    p.can_create,
    p.can_update,
    p.can_delete,
    p.can_admin,
    array_agg(COALESCE(uta.team_id, 'none')) FILTER (WHERE uta.team_id IS NOT NULL) AS accessible_teams,
    (SELECT team_id FROM user_team_access 
     WHERE user_id = u.user_id AND is_primary = TRUE) AS primary_team
FROM
    users u
JOIN
    user_permissions p ON u.user_id = p.user_id
LEFT JOIN
    user_team_access uta ON u.user_id = uta.user_id
GROUP BY
    u.user_id, u.username, u.role_id, 
    p.can_view_telemetry, p.can_use_ai, p.can_create, 
    p.can_update, p.can_delete, p.can_admin;
--View-------------------------------------------------------------------------------

--Functions-------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION check_event_entry_team() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.team_id NOT IN (
        SELECT dt.team_id
        FROM driver_team dt
        JOIN event e ON dt.year = e.year
        WHERE dt.driver_id = NEW.driver_id
          AND e.event_id = NEW.event_id
    ) THEN
        RAISE EXCEPTION 'Driver % team (%) does not match any of their official teams for this year', 
                        NEW.driver_id, NEW.team_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_time_seconds() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.time_str IS NOT NULL THEN

        NEW.time_seconds := CASE
            WHEN NEW.time_str ~ '^[0-9]+:[0-9]+:[0-9]+\.[0-9]+$' THEN
                EXTRACT(EPOCH FROM (NEW.time_str)::interval)
                
            WHEN NEW.time_str ~ '^[0-9]+:[0-9]+\.[0-9]+$' THEN
                EXTRACT(EPOCH FROM ('00:' || NEW.time_str)::interval)
                
            ELSE
                NULL
        END;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_modified_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
--------------------------------------------------------------------------------------------


--Trigers-----------------------------------------------------------------------------------
CREATE TRIGGER event_entry_team_consistency
BEFORE INSERT OR UPDATE ON event_entry
FOR EACH ROW EXECUTE FUNCTION check_event_entry_team();

CREATE TRIGGER time_str_to_seconds
BEFORE INSERT OR UPDATE ON telemetry
FOR EACH ROW EXECUTE FUNCTION calculate_time_seconds();

CREATE TRIGGER update_team_timestamp
BEFORE UPDATE ON team
FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();

CREATE TRIGGER update_users_timestamp
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_modified_timestamp();
-------------------------------------------------------------------------------------------


--Insert-uri-------------------------------------------------------------------------------
INSERT INTO team (team_id, team_name, team_code) VALUES
('mercedes', 'Mercedes-AMG Petronas F1 Team', 'MER'),
('red_bull', 'Oracle Red Bull Racing', 'RBR'),
('ferrari', 'Scuderia Ferrari', 'FER'),
('mclaren', 'McLaren F1 Team', 'MCL'),
('alpine', 'BWT Alpine F1 Team', 'ALP'),
('aston_martin', 'Aston Martin Aramco F1 Team', 'AMR'),
('williams', 'Williams Racing', 'WIL'),
('haas', 'MoneyGram Haas F1 Team', 'HAS');

INSERT INTO team(team_id,team_name,team_code) VALUES
('alphatauri', 'Scuderia AlphaTauri', 'AT'),
('rb', 'Visa Cash App RB F1 Team', 'RB');

INSERT INTO team (team_id, team_name, team_code) VALUES
('alfa', 'Alfa Romeo F1 Team Stake', 'ARO'),
('sauber', 'Stake F1 Team Kick Sauber', 'SAU');

INSERT INTO users (username, email, password_hash, first_name, last_name, role_id)
VALUES
    ('admin', 'admin@f1telemetry.com', 
     '$2a$12$iE1SrRk0uIBji0IpDtMGYeQjMvv.wAEm5EmKfuDJOkx7blxo4OsPG',
     'Admin', 'User', 'admin'),
     
    ('analyst', 'analyst@f1telemetry.com', 
     '$2a$12$8jGuU8TtqM/swa6NSvCU0uXUweyT2CQ0QFnvsQDYoB2b2xtqJ6D9q',
     'Data', 'Analyst', 'analyst'),
     
    ('mercedes_engineer', 'engineer@mercedes-f1.com', 
     '$2a$12$2lEAlmA54Kf.oFFZq8l1IeM7s3XqgdF2CCAvOQwRuWVIO3msxQlnS',
     'Mercedes', 'Engineer', 'team_member'),
     
    ('viewer', 'viewer@f1fans.com', 
     '$2a$12$8jGuU8TtqM/swa6NSvCU0uXUweyT2CQ0QFnvsQDYoB2b2xtqJ6D9q',
     'Fan', 'User', 'viewer');

INSERT INTO user_team_access (user_id, team_id, is_primary) 
SELECT 
    (SELECT user_id FROM users WHERE username = 'admin'),
    team_id,
    team_id = 'mercedes'
FROM team;

INSERT INTO user_team_access (user_id, team_id, is_primary) VALUES
((SELECT user_id FROM users WHERE username = 'analyst'), 'ferrari', true),
((SELECT user_id FROM users WHERE username = 'analyst'), 'mclaren', false);

INSERT INTO user_team_access (user_id, team_id, is_primary) VALUES
((SELECT user_id FROM users WHERE username = 'mercedes_engineer'), 
 'mercedes', 
 true);


INSERT INTO driver (driver_code, first_name, last_name, number, country, date_of_birth, is_active)
VALUES

    ('HAM', 'Lewis', 'Hamilton', 44, 'United Kingdom', '1985-01-07', true),
    ('RUS', 'George', 'Russell', 63, 'United Kingdom', '1998-02-15', true),
    

    ('VER', 'Max', 'Verstappen', 1, 'Netherlands', '1997-09-30', true),
    ('PER', 'Sergio', 'Perez', 11, 'Mexico', '1990-01-26', true),


    ('LEC', 'Charles', 'Leclerc', 16, 'Monaco', '1997-10-16', true),
    ('SAI', 'Carlos', 'Sainz', 55, 'Spain', '1994-09-01', true),
    ('BEA', 'Oliver', 'Bearman', 50, 'United Kingdom', '2005-05-08', true),
    

    ('NOR', 'Lando', 'Norris', 4, 'United Kingdom', '1999-11-13', true),
    ('RIC', 'Daniel', 'Ricciardo', 3, 'Australia', '1989-07-01', true),
    ('PIA', 'Oscar', 'Piastri', 81, 'Australia', '2001-04-06', true),
    

    ('ALO', 'Fernando', 'Alonso', 14, 'Spain', '1981-07-29', true),
    ('OCO', 'Esteban', 'Ocon', 31, 'France', '1996-09-17', true),
    ('GAS', 'Pierre', 'Gasly', 10, 'France', '1996-02-07', true),
    ('DOO', 'Jack', 'Doohan', 88, 'Australia', '2003-01-20', true),
    

    ('TSU', 'Yuki', 'Tsunoda', 22, 'Japan', '2000-05-11', true),
    ('DEV', 'Nyck', 'de Vries', 21, 'Netherlands', '1995-02-06', false),
    ('LAW', 'Liam', 'Lawson', 40, 'New Zealand', '2002-02-11', true),
    

    ('VET', 'Sebastian', 'Vettel', 5, 'Germany', '1987-07-03', false),
    ('STR', 'Lance', 'Stroll', 18, 'Canada', '1998-10-29', true),
    

    ('LAT', 'Nicholas', 'Latifi', 6, 'Canada', '1995-06-29', false),
    ('ALB', 'Alexander', 'Albon', 23, 'Thailand', '1996-03-23', true),
    ('SAR', 'Logan', 'Sargeant', 2, 'United States', '2000-12-31', true),
    ('COL', 'Franco', 'Colapinto', 43, 'Argentina', '2003-05-27', true),
    

    ('BOT', 'Valtteri', 'Bottas', 77, 'Finland', '1989-08-28', true),
    ('ZHO', 'Guanyu', 'Zhou', 24, 'China', '1999-05-30', true),
    

    ('MSC', 'Mick', 'Schumacher', 47, 'Germany', '1999-03-22', false),
    ('MAG', 'Kevin', 'Magnussen', 20, 'Denmark', '1992-10-05', true),
    ('HUL', 'Nico', 'Hulkenberg', 27, 'Germany', '1987-08-19', true);


INSERT INTO driver_team (driver_id, team_id, year) VALUES

    ((SELECT driver_id FROM driver WHERE driver_code = 'HAM'), 'mercedes', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'RUS'), 'mercedes', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'VER'), 'red_bull', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'PER'), 'red_bull', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'LEC'), 'ferrari', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'SAI'), 'ferrari', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'NOR'), 'mclaren', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'RIC'), 'mclaren', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'ALO'), 'alpine', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'OCO'), 'alpine', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'GAS'), 'alphatauri', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'TSU'), 'alphatauri', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'VET'), 'aston_martin', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'STR'), 'aston_martin', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'HUL'), 'aston_martin', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'LAT'), 'williams', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'ALB'), 'williams', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'DEV'), 'williams', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'BOT'), 'alfa', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'ZHO'), 'alfa', 2022),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'MSC'), 'haas', 2022),
    ((SELECT driver_id FROM driver WHERE driver_code = 'MAG'), 'haas', 2022);


INSERT INTO driver_team (driver_id, team_id, year) VALUES

    ((SELECT driver_id FROM driver WHERE driver_code = 'HAM'), 'mercedes', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'RUS'), 'mercedes', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'VER'), 'red_bull', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'PER'), 'red_bull', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'LEC'), 'ferrari', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'SAI'), 'ferrari', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'NOR'), 'mclaren', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'PIA'), 'mclaren', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'GAS'), 'alpine', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'OCO'), 'alpine', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'DEV'), 'alphatauri', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'TSU'), 'alphatauri', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'RIC'), 'alphatauri', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'LAW'), 'alphatauri', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'ALO'), 'aston_martin', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'STR'), 'aston_martin', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'ALB'), 'williams', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'SAR'), 'williams', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'BOT'), 'alfa', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'ZHO'), 'alfa', 2023),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'HUL'), 'haas', 2023),
    ((SELECT driver_id FROM driver WHERE driver_code = 'MAG'), 'haas', 2023);


INSERT INTO driver_team (driver_id, team_id, year) VALUES

    ((SELECT driver_id FROM driver WHERE driver_code = 'HAM'), 'mercedes', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'RUS'), 'mercedes', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'VER'), 'red_bull', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'PER'), 'red_bull', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'LEC'), 'ferrari', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'SAI'), 'ferrari', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'BEA'), 'ferrari', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'NOR'), 'mclaren', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'PIA'), 'mclaren', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'GAS'), 'alpine', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'OCO'), 'alpine', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'DOO'), 'alpine', 2024),
    
 
    ((SELECT driver_id FROM driver WHERE driver_code = 'TSU'), 'rb', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'RIC'), 'rb', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'LAW'), 'rb', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'ALO'), 'aston_martin', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'STR'), 'aston_martin', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'ALB'), 'williams', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'SAR'), 'williams', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'COL'), 'williams', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'BOT'), 'sauber', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'ZHO'), 'sauber', 2024),
    

    ((SELECT driver_id FROM driver WHERE driver_code = 'HUL'), 'haas', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'MAG'), 'haas', 2024),
    ((SELECT driver_id FROM driver WHERE driver_code = 'BEA'), 'haas', 2024);




INSERT INTO event (event_name, year, circuit_name, location, country, event_date) VALUES
('2022 Bahrain Grand Prix', 2022, 'Bahrain International Circuit', 'Sakhir', 'Bahrain', '2022-03-20'),
('2022 Saudi Arabian Grand Prix', 2022, 'Jeddah Corniche Circuit', 'Jeddah', 'Saudi Arabia', '2022-03-27'),
('2022 Australian Grand Prix', 2022, 'Albert Park Circuit', 'Melbourne', 'Australia', '2022-04-10'),
('2022 Emilia Romagna Grand Prix', 2022, 'Autodromo Enzo e Dino Ferrari', 'Imola', 'Italy', '2022-04-24'),
('2022 Miami Grand Prix', 2022, 'Miami International Autodrome', 'Miami', 'United States', '2022-05-08'),
('2022 Spanish Grand Prix', 2022, 'Circuit de Barcelona-Catalunya', 'Montmeló', 'Spain', '2022-05-22'),
('2022 Monaco Grand Prix', 2022, 'Circuit de Monaco', 'Monte Carlo', 'Monaco', '2022-05-29'),
('2022 Azerbaijan Grand Prix', 2022, 'Baku City Circuit', 'Baku', 'Azerbaijan', '2022-06-12'),
('2022 Canadian Grand Prix', 2022, 'Circuit Gilles Villeneuve', 'Montreal', 'Canada', '2022-06-19'),
('2022 British Grand Prix', 2022, 'Silverstone Circuit', 'Silverstone', 'United Kingdom', '2022-07-03'),
('2022 Austrian Grand Prix', 2022, 'Red Bull Ring', 'Spielberg', 'Austria', '2022-07-10'),
('2022 French Grand Prix', 2022, 'Circuit Paul Ricard', 'Le Castellet', 'France', '2022-07-24'),
('2022 Hungarian Grand Prix', 2022, 'Hungaroring', 'Mogyoród', 'Hungary', '2022-07-31'),
('2022 Belgian Grand Prix', 2022, 'Circuit de Spa-Francorchamps', 'Spa', 'Belgium', '2022-08-28'),
('2022 Dutch Grand Prix', 2022, 'Circuit Zandvoort', 'Zandvoort', 'Netherlands', '2022-09-04'),
('2022 Italian Grand Prix', 2022, 'Autodromo Nazionale Monza', 'Monza', 'Italy', '2022-09-11'),
('2022 Singapore Grand Prix', 2022, 'Marina Bay Street Circuit', 'Singapore', 'Singapore', '2022-10-02'),
('2022 Japanese Grand Prix', 2022, 'Suzuka International Racing Course', 'Suzuka', 'Japan', '2022-10-09'),
('2022 United States Grand Prix', 2022, 'Circuit of the Americas', 'Austin', 'United States', '2022-10-23'),
('2022 Mexico City Grand Prix', 2022, 'Autódromo Hermanos Rodríguez', 'Mexico City', 'Mexico', '2022-10-30'),
('2022 Brazilian Grand Prix', 2022, 'Autódromo José Carlos Pace', 'São Paulo', 'Brazil', '2022-11-13'),
('2022 Abu Dhabi Grand Prix', 2022, 'Yas Marina Circuit', 'Abu Dhabi', 'United Arab Emirates', '2022-11-20'),

('2023 Bahrain Grand Prix', 2023, 'Bahrain International Circuit', 'Sakhir', 'Bahrain', '2023-03-05'),
('2023 Saudi Arabian Grand Prix', 2023, 'Jeddah Corniche Circuit', 'Jeddah', 'Saudi Arabia', '2023-03-19'),
('2023 Australian Grand Prix', 2023, 'Albert Park Circuit', 'Melbourne', 'Australia', '2023-04-02'),
('2023 Azerbaijan Grand Prix', 2023, 'Baku City Circuit', 'Baku', 'Azerbaijan', '2023-04-30'),
('2023 Miami Grand Prix', 2023, 'Miami International Autodrome', 'Miami', 'United States', '2023-05-07'),
('2023 Monaco Grand Prix', 2023, 'Circuit de Monaco', 'Monte Carlo', 'Monaco', '2023-05-28'),
('2023 Spanish Grand Prix', 2023, 'Circuit de Barcelona-Catalunya', 'Montmeló', 'Spain', '2023-06-04'),
('2023 Canadian Grand Prix', 2023, 'Circuit Gilles Villeneuve', 'Montreal', 'Canada', '2023-06-18'),
('2023 Austrian Grand Prix', 2023, 'Red Bull Ring', 'Spielberg', 'Austria', '2023-07-02'),
('2023 British Grand Prix', 2023, 'Silverstone Circuit', 'Silverstone', 'United Kingdom', '2023-07-09'),
('2023 Hungarian Grand Prix', 2023, 'Hungaroring', 'Mogyoród', 'Hungary', '2023-07-23'),
('2023 Belgian Grand Prix', 2023, 'Circuit de Spa-Francorchamps', 'Spa', 'Belgium', '2023-07-30'),
('2023 Dutch Grand Prix', 2023, 'Circuit Zandvoort', 'Zandvoort', 'Netherlands', '2023-08-27'),
('2023 Italian Grand Prix', 2023, 'Autodromo Nazionale Monza', 'Monza', 'Italy', '2023-09-03'),
('2023 Singapore Grand Prix', 2023, 'Marina Bay Street Circuit', 'Singapore', 'Singapore', '2023-09-17'),
('2023 Japanese Grand Prix', 2023, 'Suzuka International Racing Course', 'Suzuka', 'Japan', '2023-09-24'),
('2023 Qatar Grand Prix', 2023, 'Lusail International Circuit', 'Lusail', 'Qatar', '2023-10-08'),
('2023 United States Grand Prix', 2023, 'Circuit of the Americas', 'Austin', 'United States', '2023-10-22'),
('2023 Mexico City Grand Prix', 2023, 'Autódromo Hermanos Rodríguez', 'Mexico City', 'Mexico', '2023-10-29'),
('2023 Brazilian Grand Prix', 2023, 'Autódromo José Carlos Pace', 'São Paulo', 'Brazil', '2023-11-05'),
('2023 Las Vegas Grand Prix', 2023, 'Las Vegas Strip Circuit', 'Las Vegas', 'United States', '2023-11-18'),
('2023 Abu Dhabi Grand Prix', 2023, 'Yas Marina Circuit', 'Abu Dhabi', 'United Arab Emirates', '2023-11-26'),

('2024 Bahrain Grand Prix', 2024, 'Bahrain International Circuit', 'Sakhir', 'Bahrain', '2024-03-02'),
('2024 Saudi Arabian Grand Prix', 2024, 'Jeddah Corniche Circuit', 'Jeddah', 'Saudi Arabia', '2024-03-09'),
('2024 Australian Grand Prix', 2024, 'Albert Park Circuit', 'Melbourne', 'Australia', '2024-03-24'),
('2024 Japanese Grand Prix', 2024, 'Suzuka International Racing Course', 'Suzuka', 'Japan', '2024-04-07'),
('2024 Chinese Grand Prix', 2024, 'Shanghai International Circuit', 'Shanghai', 'China', '2024-04-21'),
('2024 Miami Grand Prix', 2024, 'Miami International Autodrome', 'Miami', 'United States', '2024-05-05'),
('2024 Emilia Romagna Grand Prix', 2024, 'Autodromo Enzo e Dino Ferrari', 'Imola', 'Italy', '2024-05-19'),
('2024 Monaco Grand Prix', 2024, 'Circuit de Monaco', 'Monte Carlo', 'Monaco', '2024-05-26'),
('2024 Canadian Grand Prix', 2024, 'Circuit Gilles Villeneuve', 'Montreal', 'Canada', '2024-06-09'),
('2024 Spanish Grand Prix', 2024, 'Circuit de Barcelona-Catalunya', 'Montmeló', 'Spain', '2024-06-23'),
('2024 Austrian Grand Prix', 2024, 'Red Bull Ring', 'Spielberg', 'Austria', '2024-06-30'),
('2024 British Grand Prix', 2024, 'Silverstone Circuit', 'Silverstone', 'United Kingdom', '2024-07-07'),
('2024 Hungarian Grand Prix', 2024, 'Hungaroring', 'Mogyoród', 'Hungary', '2024-07-21'),
('2024 Belgian Grand Prix', 2024, 'Circuit de Spa-Francorchamps', 'Spa', 'Belgium', '2024-07-28'),
('2024 Dutch Grand Prix', 2024, 'Circuit Zandvoort', 'Zandvoort', 'Netherlands', '2024-08-25'),
('2024 Italian Grand Prix', 2024, 'Autodromo Nazionale Monza', 'Monza', 'Italy', '2024-09-01'),
('2024 Azerbaijan Grand Prix', 2024, 'Baku City Circuit', 'Baku', 'Azerbaijan', '2024-09-15'),
('2024 Singapore Grand Prix', 2024, 'Marina Bay Street Circuit', 'Singapore', 'Singapore', '2024-09-22'),
('2024 United States Grand Prix', 2024, 'Circuit of the Americas', 'Austin', 'United States', '2024-10-20'),
('2024 Mexico City Grand Prix', 2024, 'Autódromo Hermanos Rodríguez', 'Mexico City', 'Mexico', '2024-10-27'),
('2024 Brazilian Grand Prix', 2024, 'Autódromo José Carlos Pace', 'São Paulo', 'Brazil', '2024-11-03'),
('2024 Las Vegas Grand Prix', 2024, 'Las Vegas Strip Circuit', 'Las Vegas', 'United States', '2024-11-23'),
('2024 Qatar Grand Prix', 2024, 'Lusail International Circuit', 'Lusail', 'Qatar', '2024-12-01'),
('2024 Abu Dhabi Grand Prix', 2024, 'Yas Marina Circuit', 'Abu Dhabi', 'United Arab Emirates', '2024-12-08');


CREATE OR REPLACE FUNCTION create_2022_event_entry(race_name TEXT) RETURNS VOID AS $$
DECLARE
    race_id INTEGER;
BEGIN
    SELECT event_id INTO race_id FROM event WHERE event_name = race_name;
    
    INSERT INTO event_entry (event_id, driver_id, team_id)
    SELECT 
        race_id,
        d.driver_id,
        dt.team_id
    FROM 
        driver d
    JOIN 
        driver_team dt ON d.driver_id = dt.driver_id
    WHERE 
        dt.year = 2022
        AND d.driver_code NOT IN ('HUL', 'DEV')
        AND NOT (
            (race_name IN ('2022 Bahrain Grand Prix', '2022 Saudi Arabian Grand Prix') 
             AND d.driver_code = 'VET')
            OR (race_name = '2022 Italian Grand Prix' AND d.driver_code = 'ALB')
        );
    
    IF race_name = '2022 Bahrain Grand Prix' OR race_name = '2022 Saudi Arabian Grand Prix' THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'HUL'),
            'aston_martin'
        );
    ELSIF race_name = '2022 Italian Grand Prix' THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'DEV'),
            'williams'
        );
    END IF;
    
    RAISE NOTICE 'Created entries for %', race_name;
END;
$$ LANGUAGE plpgsql;


DO $$
BEGIN
    PERFORM create_2022_event_entry('2022 Bahrain Grand Prix');
    PERFORM create_2022_event_entry('2022 Saudi Arabian Grand Prix');
    PERFORM create_2022_event_entry('2022 Australian Grand Prix');
    PERFORM create_2022_event_entry('2022 Emilia Romagna Grand Prix');
    PERFORM create_2022_event_entry('2022 Miami Grand Prix');
    PERFORM create_2022_event_entry('2022 Spanish Grand Prix');
    PERFORM create_2022_event_entry('2022 Monaco Grand Prix');
    PERFORM create_2022_event_entry('2022 Azerbaijan Grand Prix');
    PERFORM create_2022_event_entry('2022 Canadian Grand Prix');
    PERFORM create_2022_event_entry('2022 British Grand Prix');
    PERFORM create_2022_event_entry('2022 Austrian Grand Prix');
    PERFORM create_2022_event_entry('2022 French Grand Prix');
    PERFORM create_2022_event_entry('2022 Hungarian Grand Prix');
    PERFORM create_2022_event_entry('2022 Belgian Grand Prix');
    PERFORM create_2022_event_entry('2022 Dutch Grand Prix');
    PERFORM create_2022_event_entry('2022 Italian Grand Prix');
    PERFORM create_2022_event_entry('2022 Singapore Grand Prix');
    PERFORM create_2022_event_entry('2022 Japanese Grand Prix');
    PERFORM create_2022_event_entry('2022 United States Grand Prix');
    PERFORM create_2022_event_entry('2022 Mexico City Grand Prix');
    PERFORM create_2022_event_entry('2022 Brazilian Grand Prix');
    PERFORM create_2022_event_entry('2022 Abu Dhabi Grand Prix');
    
    RAISE NOTICE 'All 2022 event entries created successfully';
END $$;

DROP FUNCTION IF EXISTS create_2022_event_entry(TEXT);

CREATE OR REPLACE FUNCTION create_2023_event_entry(race_name TEXT) RETURNS VOID AS $$
DECLARE
    race_id INTEGER;
    race_date DATE;
BEGIN
    SELECT event_id, event_date INTO race_id, race_date 
    FROM event WHERE event_name = race_name;
    
    INSERT INTO event_entry (event_id, driver_id, team_id)
    SELECT 
        race_id,
        d.driver_id,
        dt.team_id
    FROM 
        driver d
    JOIN 
        driver_team dt ON d.driver_id = dt.driver_id
    WHERE 
        dt.year = 2023
        AND NOT (
            (d.driver_code = 'DEV' AND race_date >= '2023-07-23')
            
            OR (d.driver_code = 'RIC' AND 
               (race_date < '2023-07-23'
                OR (race_date >= '2023-08-27' AND race_date <= '2023-10-08')))
                
            OR (d.driver_code = 'LAW' AND 
               (race_date < '2023-08-27' OR race_date > '2023-10-08'))
        );
    
    RAISE NOTICE 'Created entries for %', race_name;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    PERFORM create_2023_event_entry('2023 Bahrain Grand Prix');
    PERFORM create_2023_event_entry('2023 Saudi Arabian Grand Prix');
    PERFORM create_2023_event_entry('2023 Australian Grand Prix');
    PERFORM create_2023_event_entry('2023 Azerbaijan Grand Prix');
    PERFORM create_2023_event_entry('2023 Miami Grand Prix');
    PERFORM create_2023_event_entry('2023 Monaco Grand Prix');
    PERFORM create_2023_event_entry('2023 Spanish Grand Prix');
    PERFORM create_2023_event_entry('2023 Canadian Grand Prix');
    PERFORM create_2023_event_entry('2023 Austrian Grand Prix');
    PERFORM create_2023_event_entry('2023 British Grand Prix');
    PERFORM create_2023_event_entry('2023 Hungarian Grand Prix');
    PERFORM create_2023_event_entry('2023 Belgian Grand Prix');
    PERFORM create_2023_event_entry('2023 Dutch Grand Prix');
    PERFORM create_2023_event_entry('2023 Italian Grand Prix');
    PERFORM create_2023_event_entry('2023 Singapore Grand Prix');
    PERFORM create_2023_event_entry('2023 Japanese Grand Prix');
    PERFORM create_2023_event_entry('2023 Qatar Grand Prix');
    PERFORM create_2023_event_entry('2023 United States Grand Prix');
    PERFORM create_2023_event_entry('2023 Mexico City Grand Prix');
    PERFORM create_2023_event_entry('2023 Brazilian Grand Prix');
    PERFORM create_2023_event_entry('2023 Las Vegas Grand Prix');
    PERFORM create_2023_event_entry('2023 Abu Dhabi Grand Prix');
    
    RAISE NOTICE 'All 2023 event entries created successfully';
END $$;

DROP FUNCTION IF EXISTS create_2023_event_entry(TEXT);

CREATE OR REPLACE FUNCTION create_2024_event_entry(race_name TEXT) RETURNS VOID AS $$
DECLARE
    race_id INTEGER;
    race_date DATE;
BEGIN
    SELECT event_id, event_date INTO race_id, race_date 
    FROM event WHERE event_name = race_name;
    
    INSERT INTO event_entry (event_id, driver_id, team_id)
    SELECT 
        race_id,
        d.driver_id,
        dt.team_id
    FROM 
        driver d
    JOIN 
        driver_team dt ON d.driver_id = dt.driver_id
    WHERE 
        dt.year = 2024
        AND d.driver_code NOT IN ('BEA', 'COL', 'LAW', 'DOO')
        AND NOT (
            (race_name = '2024 Saudi Arabian Grand Prix' AND d.driver_code = 'SAI')
            
            OR (race_name IN ('2024 Azerbaijan Grand Prix', '2024 Brazilian Grand Prix') 
                AND d.driver_code = 'MAG')
            
            OR (d.driver_code = 'SAR' 
                AND race_date >= (SELECT event_date FROM event WHERE event_name = '2024 Italian Grand Prix'))
            
            OR (d.driver_code = 'RIC' 
                AND race_date >= (SELECT event_date FROM event WHERE event_name = '2024 United States Grand Prix'))
                
            OR (race_name = '2024 Abu Dhabi Grand Prix' AND d.driver_code = 'OCO')
        );
    
    
    IF race_name = '2024 Saudi Arabian Grand Prix' THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'BEA'),
            'ferrari'
        );
    ELSIF race_name IN ('2024 Azerbaijan Grand Prix', '2024 Brazilian Grand Prix') THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'BEA'),
            'haas'
        );
    END IF;
    
    IF race_date >= (SELECT event_date FROM event WHERE event_name = '2024 Italian Grand Prix') THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'COL'),
            'williams'
        );
    END IF;
    
    IF race_date >= (SELECT event_date FROM event WHERE event_name = '2024 United States Grand Prix') THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'LAW'),
            'rb'
        );
    END IF;
    
    IF race_name = '2024 Abu Dhabi Grand Prix' THEN
        INSERT INTO event_entry (event_id, driver_id, team_id)
        VALUES (
            race_id,
            (SELECT driver_id FROM driver WHERE driver_code = 'DOO'),
            'alpine'
        );
    END IF;
    
    RAISE NOTICE 'Created entries for %', race_name;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    PERFORM create_2024_event_entry('2024 Bahrain Grand Prix');
    PERFORM create_2024_event_entry('2024 Saudi Arabian Grand Prix');
    PERFORM create_2024_event_entry('2024 Australian Grand Prix');
    PERFORM create_2024_event_entry('2024 Japanese Grand Prix');
    PERFORM create_2024_event_entry('2024 Chinese Grand Prix');
    PERFORM create_2024_event_entry('2024 Miami Grand Prix');
    PERFORM create_2024_event_entry('2024 Emilia Romagna Grand Prix');
    PERFORM create_2024_event_entry('2024 Monaco Grand Prix');
    PERFORM create_2024_event_entry('2024 Canadian Grand Prix');
    PERFORM create_2024_event_entry('2024 Spanish Grand Prix');
    PERFORM create_2024_event_entry('2024 Austrian Grand Prix');
    PERFORM create_2024_event_entry('2024 British Grand Prix');
    PERFORM create_2024_event_entry('2024 Hungarian Grand Prix');
    PERFORM create_2024_event_entry('2024 Belgian Grand Prix');
    PERFORM create_2024_event_entry('2024 Dutch Grand Prix');
    PERFORM create_2024_event_entry('2024 Italian Grand Prix');
    PERFORM create_2024_event_entry('2024 Azerbaijan Grand Prix');
    PERFORM create_2024_event_entry('2024 Singapore Grand Prix');
    PERFORM create_2024_event_entry('2024 United States Grand Prix');
    PERFORM create_2024_event_entry('2024 Mexico City Grand Prix');
    PERFORM create_2024_event_entry('2024 Brazilian Grand Prix');
    PERFORM create_2024_event_entry('2024 Las Vegas Grand Prix');
    PERFORM create_2024_event_entry('2024 Qatar Grand Prix');
    PERFORM create_2024_event_entry('2024 Abu Dhabi Grand Prix');
    
    RAISE NOTICE 'All 2024 event entries created successfully';
END $$;

DROP FUNCTION IF EXISTS create_2024_event_entry(TEXT);

CREATE OR REPLACE FUNCTION create_sessions() RETURNS VOID AS $$
DECLARE
    event_record RECORD;
BEGIN
    FOR event_record IN 
        SELECT event_id, event_name, event_date
        FROM event
        ORDER BY event_date
    LOOP
        INSERT INTO session (event_id, session_type, session_date)
        VALUES (
            event_record.event_id, 
            'Q', 
            (event_record.event_date - INTERVAL '1 day')::date + TIME '14:00:00'
        );
        
        INSERT INTO session (event_id, session_type, session_date)
        VALUES (
            event_record.event_id,
            'R',
            event_record.event_date::date + TIME '13:00:00'
        );
        
        RAISE NOTICE 'Created sessions for %', event_record.event_name;
    END LOOP;
    
    RAISE NOTICE 'All sessions created successfully';
END;
$$ LANGUAGE plpgsql;

SELECT create_sessions();

DROP FUNCTION IF EXISTS create_sessions();

----------------------------------------------------------------------------