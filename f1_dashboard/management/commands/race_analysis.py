import os
import sys
import shutil
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from f1_core.analyzers.db_race_analyzer import DBF1RaceAnalyzer
import json

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--event', type=str, required=True, help='Numele evenimentului')
        parser.add_argument('--year', type=int, required=True, help='Anul evenimentului')
        parser.add_argument('--drivers', type=str, required=True, help='Codurile piloților separate prin virgulă (ex: VER,LEC)')
        parser.add_argument('--save-db', action='store_true', help='Salvează analiza în baza de date')
        parser.add_argument('--output-dir', type=str, help='Director pentru output')

    def handle(self, *args, **options):
        event_name = options['event']
        year = options['year']
        drivers_str = options['drivers']
        save_to_db = options['save_db']
        output_dir = options['output_dir']

        self.stdout.write(f"Generating race analysis for {event_name} {year} with drivers {drivers_str}")

        db_params = {
            'host': 'localhost',
            'database': 'f1_telemetry',
            'user': 'madalin',
            'password': 'madalin',
            'port': 5432
        }

        driver_list = [d.strip() for d in drivers_str.split(',')]
        if len(driver_list) != 2:
            raise CommandError("Trebuie să specificați exact doi piloți")

        static_folder = "f1_dashboard/static"
        relative_path = f"images/race_analysis/{event_name.replace(' ', '_')}_{year}/{driver_list[0]}_vs_{driver_list[1]}"
        image_path = relative_path
        temp_output_dir = output_dir or os.path.join("analysis/race_analysis", 
                                  f"{event_name.replace(' ', '_')}_{year}",
                                  f"{driver_list[0]}_vs_{driver_list[1]}")

        os.makedirs(os.path.join(static_folder, relative_path), exist_ok=True)

        analyzer = DBF1RaceAnalyzer(db_params)
        results = analyzer.run_race_analysis(
            event_name=options['event'],
            year=options['year'],
            drivers=driver_list,
            save_to_db=options['save_db'],
            output_dir=temp_output_dir
        )

        if results and options['save_db']:
            if 'existing_analysis' in results and results['existing_analysis']:
                self.stdout.write(f"Using existing analysis. Paths are already in database.")
            else:
                rel_pace_path = os.path.join(image_path, "pace_comparison.png")
                rel_strategy_path = os.path.join(image_path, "strategy_comparison.png")
                rel_position_path = os.path.join(image_path, "position_changes.png")

                if 'lap_times_viz' in results and results['lap_times_viz'] and os.path.exists(results['lap_times_viz']):
                    shutil.copy(results['lap_times_viz'], os.path.join(static_folder, rel_pace_path))
                    self.stdout.write(f"Copied pace visualization to {rel_pace_path}")

                if 'tire_strategy_viz' in results and results['tire_strategy_viz'] and os.path.exists(results['tire_strategy_viz']):
                    shutil.copy(results['tire_strategy_viz'], os.path.join(static_folder, rel_strategy_path))
                    self.stdout.write(f"Copied strategy visualization to {rel_strategy_path}")
                    
                if 'position_viz' in results and results['position_viz'] and os.path.exists(results['position_viz']):
                    shutil.copy(results['position_viz'], os.path.join(static_folder, rel_position_path))
                    self.stdout.write(f"Copied position visualization to {rel_position_path}")

                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE race_analysis
                        SET lap_times_plot_path = %s,
                            tire_strategy_plot_path = %s,
                            position_plot_path = %s
                        WHERE analysis_id IN (
                            SELECT ra.analysis_id
                            FROM race_analysis ra
                            JOIN analysis a ON ra.analysis_id = a.analysis_id
                            WHERE a.event_name LIKE %s
                            AND a.year = %s
                            AND ra.drivers_json @> %s::jsonb
                            AND jsonb_array_length(ra.drivers_json) = 2
                            ORDER BY a.created_at DESC
                            LIMIT 1
                        )
                    """, [
                        rel_pace_path, 
                        rel_strategy_path, 
                        rel_position_path,
                        f"%{options['event']}%", 
                        options['year'],
                        json.dumps(sorted(driver_list))
                    ])

        if results:
            self.stdout.write(self.style.SUCCESS("Analysis complete!"))
        else:
            self.stdout.write(self.style.ERROR("No results were generated due to errors."))