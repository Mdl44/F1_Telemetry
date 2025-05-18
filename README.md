# F1 Telemetry Analyzer

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🏎️ Advanced Formula 1 Telemetry Analysis Platform

F1 Telemetry Analyzer is a comprehensive web application for analyzing, visualizing, and comparing Formula 1 telemetry data. Built for racing enthusiasts, team members, and analysts, this platform provides deep insights into driver performance, race strategies, and car behavior across Grand Prix weekends.

## ✨ Key Features

- **Qualifying Analysis:** Compare drivers' fastest laps with detailed delta timing and speed analysis
- **Race Strategy Analysis:** Visualize tire strategies, pit stops timing, and race pace evolution
- **Team-Based Access Control:** Secure data access with role-based permissions (viewer, team_member, analyst, admin)
- **Telemetry Visualization:** Interactive charts for speed, throttle, brake, RPM, and gear data
- **Data Quality Reporting:** Comprehensive metrics on telemetry data completeness and reliability
- **Historical Data:** Store and analyze data across multiple seasons and Grand Prix events

## 🛠️ Technology Stack

- **Backend:** Python 3.11+ with Django 5.2
- **Database:** PostgreSQL 16 with optimized schema for telemetry data
- **Data Processing:** FastF1, Pandas, and NumPy for telemetry analysis
- **Frontend:** Django Templates, JavaScript, and Bootstrap
- **Deployment:** Nginx and Gunicorn

## 📊 Data Insights

The analyzer processes approximately 100,000 telemetry data points per race session, providing insights such as:

- Optimal braking points and racing lines
- Acceleration performance comparisons
- Tire degradation analysis
- Sector-by-sector performance evaluation
- Speed comparison across similar track sections
