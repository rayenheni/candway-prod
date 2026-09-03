"""
Migration: Add calibration columns to applications table
These store onboarding calibration data for better AI interview questions
"""

import os

import pymysql


def run_migration():
    # Get MySQL credentials from environment
    host = os.environ.get("MYSQL_HOST", "localhost")
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "candway_db")

    connection = pymysql.connect(
        host=host, user=user, password=password, database=database
    )

    columns_to_add = [
        ("calibration_json", "LONGTEXT"),
        ("calibration_score", "FLOAT"),
        ("calibration_verified_skills", "LONGTEXT"),
    ]

    try:
        with connection.cursor() as cursor:
            for col_name, col_type in columns_to_add:
                try:
                    sql = f"ALTER TABLE applications ADD COLUMN {col_name} {col_type} DEFAULT NULL"
                    cursor.execute(sql)
                    print(f"Added column: {col_name}")
                except pymysql.err.OperationalError as e:
                    if e.args[0] == 1060:  # Column already exists
                        print(f"Column already exists: {col_name}")
                    else:
                        raise

        connection.commit()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration error: {e}")
        connection.rollback()
    finally:
        connection.close()


if __name__ == "__main__":
    run_migration()
