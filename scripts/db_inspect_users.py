import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', db='candway_db')
with conn.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM users')
    print('total users in DB:', cur.fetchone()[0])
    cur.execute('SELECT COUNT(*) FROM users WHERE deleted_at IS NULL')
    print('users with deleted_at IS NULL:', cur.fetchone()[0])
    cur.execute("SELECT role, COUNT(*) FROM users WHERE deleted_at IS NULL GROUP BY role")
    print('by role:', cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM users WHERE deleted_at IS NOT NULL")
    print('soft-deleted users:', cur.fetchone()[0])
    cur.execute("SELECT id, email, role, deleted_at, created_at FROM users ORDER BY id LIMIT 5")
    for r in cur.fetchall():
        print('  ', r)
conn.close()
