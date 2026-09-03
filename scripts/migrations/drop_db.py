import pymysql

HOST = "localhost"
USER = "root"
PASSWORD = ""

try:
    conn = pymysql.connect(host=HOST, user=USER, password=PASSWORD)
    cursor = conn.cursor()
    cursor.execute("DROP DATABASE IF EXISTS candway_app")
    print("Dropped candway_app")
    cursor.execute("CREATE DATABASE candway_app")
    print("Created fresh candway_app")
    conn.close()
except Exception as e:
    print(e)
