import os
import shutil
import sys
from django.core.management.base import BaseCommand
from django.db import connection
from f1_analysis.analyzers.db_qualifying_analyzer import DBF1QualifyingAnalyzer

#comanda django pentru tool-ul de calificari
# python manage.py quali_analysis...
class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--event', required=True)
        parser.add_argument('--year', required=True, type=int)
        parser.add_argument('--drivers', required=True)
        parser.add_argument('--save-db', action='store_true')

    def handle(self, *args, **options):
        driver_list = [d.strip() for d in options['drivers'].split(',')]
        if len(driver_list) != 2:
            self.stderr.write("Error: Exactly 2 driver codes must be provided.")
            return

        db_params = {
            'host': 'localhost',
            'database': 'f1_telemetry',
            'user': 'madalin',
            'password': 'madalin',
            'port': 5432
        }

        static_folder = os.path.join("f1_dashboard", "static")
        event_folder = f"{options['event'].replace(' ', '_')}_{options['year']}"
        driver_str = "_vs_".join(sorted(driver_list))

        image_path = os.path.join("images", "quali_analysis", event_folder, driver_str)
        full_image_path = os.path.join(static_folder, image_path)
        os.makedirs(full_image_path, exist_ok=True)

        temp_output_dir = os.path.join("analysis", "quali_analysis", event_folder, driver_str)
        os.makedirs(temp_output_dir, exist_ok=True)

        analyzer = DBF1QualifyingAnalyzer(db_params)
        results = analyzer.run_quali_analysis(
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
                rel_speed_path = os.path.join(image_path, "speed_comparison.png")
                rel_delta_path = os.path.join(image_path, "delta_time.png")

                if 'speed_viz' in results and results['speed_viz'] and os.path.exists(results['speed_viz']):
                    shutil.copy(results['speed_viz'], os.path.join(static_folder, rel_speed_path))

                if 'delta_viz' in results and results['delta_viz'] and os.path.exists(results['delta_viz']):
                    shutil.copy(results['delta_viz'], os.path.join(static_folder, rel_delta_path))

                with connection.cursor() as cursor:
                    cursor.execute("""
                                   UPDATE quali_analysis
                                   SET speed_plot_path = %s,
                                       delta_plot_path = %s
                                   WHERE analysis_id IN (SELECT qa.analysis_id
                                                         FROM quali_analysis qa
                                                                  JOIN analysis a ON qa.analysis_id = a.analysis_id
                                                         WHERE a.event_name LIKE %s
                                                           AND a.year = %s
                                                           AND ((qa.driver1_code = %s AND qa.driver2_code = %s) OR
                                                                (qa.driver1_code = %s AND qa.driver2_code = %s))
                                                         ORDER BY a.created_at DESC
                                       LIMIT 1
                                       )
                                   """, [
                                       rel_speed_path, rel_delta_path,
                                       f"%{options['event']}%", options['year'],
                                       driver_list[0], driver_list[1], driver_list[1], driver_list[0]
                                   ])

    def run(*args):
        sys.argv = ['manage.py', 'quali_analysis'] + list(args)

        cmd = Command()
        cmd.run_from_argv(sys.argv)