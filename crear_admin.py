
import psycopg2
from werkzeug.security import generate_password_hash

conn = psycopg2.connect(
    host="crossover.proxy.rlwy.net",
    database="railway",
    user="postgres",
    password="pNVPcUtwfiazPLdnCiYKKWuaRjbpCtTl",
    port="57099"
)

cur = conn.cursor()
cur.execute("DELETE FROM usuarios WHERE dni = %s", ('99999999',))
cur.execute("INSERT INTO usuarios (dni, nombre, password, rol) VALUES (%s, %s, %s, %s)",
            ('74991946', 'Admin Principal', generate_password_hash('150799'), 'admin'))
conn.commit()
cur.close()
conn.close()
print("✅ Admin creado")
