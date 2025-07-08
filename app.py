from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from flask import jsonify

app = Flask(__name__)
app.secret_key = 'supersecretkey'

DB_HOST = 'crossover.proxy.rlwy.net'
DB_NAME = 'railway'
DB_USER = 'postgres'
DB_PASS = 'pNVPcUtwfiazPLdnCiYKKWuaRjbpCtTl'
DB_PORT = '57099'

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT,
        cursor_factory=RealDictCursor
    )

@app.route('/', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        dni = request.form['dni']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE dni = %s", (dni,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['rol'] = user['rol']
            session['nombre'] = user['nombre']
            if user['rol'] == 'admin':
                return redirect(url_for('admin_panel'))
            elif user['rol'] == 'docente':
                return redirect(url_for('docente_panel'))
            else:
                return redirect(url_for('estudiante_panel'))
        else:
            error = 'Credenciales inválidas'
    return render_template('login.html', error=error)

@app.route('/admin')
def admin_panel():
    if session.get('rol') != 'admin':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, dni, nombre, rol FROM usuarios")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('admin_panel.html', usuarios=usuarios)


@app.route('/crear_usuario', methods=['GET', 'POST'])
def crear_usuario():
    if session.get('rol') != 'admin':
        return redirect('/')
    if request.method == 'POST':
        dni = request.form['dni']
        nombre = request.form['nombre']
        password = generate_password_hash(request.form['password'])
        rol = request.form['rol']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO usuarios (dni, nombre, password, rol) VALUES (%s, %s, %s, %s)",
                    (dni, nombre, password, rol))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/admin')
    return render_template('crear_usuario.html')

@app.route('/crear_curso', methods=['GET', 'POST'])
def crear_curso():
    if session.get('rol') != 'admin':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.form['nombre']
        docente_id = request.form['docente_id']
        grado = request.form['grado']
        cur.execute("INSERT INTO cursos (nombre, docente_id, grado) VALUES (%s, %s, %s)", (nombre, docente_id, grado))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/admin')

    # Si es GET, cargar los docentes disponibles
    cur.execute("SELECT id, nombre FROM usuarios WHERE rol = 'docente'")
    docentes = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('crear_curso.html', docentes=docentes)

@app.route('/eliminar_curso/<int:curso_id>', methods=['POST'])
def eliminar_curso(curso_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Primero elimina los registros relacionados
    cur.execute("DELETE FROM estudiantes_cursos WHERE curso_id = %s", (curso_id,))
    cur.execute("DELETE FROM notas WHERE curso_id = %s", (curso_id,))

    # Luego elimina el curso
    cur.execute("DELETE FROM cursos WHERE id = %s", (curso_id,))
    
    conn.commit()
    cur.close()
    conn.close()

    return redirect('/ver_cursos')


@app.route('/docente')
def docente_panel():
    if session.get('rol') != 'docente':
        return redirect('/')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cursos WHERE docente_id = %s", (session['user_id'],))
    cursos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('docente_panel.html', cursos=cursos)
@app.route('/ingresar_nota/<int:curso_id>', methods=['GET', 'POST'])
def ingresar_nota(curso_id):
    if session.get('rol') != 'docente':
        return redirect('/')

    if request.method == 'POST':
        estudiante_id = request.form['estudiante_id']
        tipo = request.form['tipo']
        nota = request.form['nota']

        conn = get_db_connection()
        cur = conn.cursor()

        # Verifica si existe el estudiante con ese ID
        cur.execute("SELECT id FROM usuarios WHERE id = %s AND rol = 'estudiante'", (estudiante_id,))
        estudiante = cur.fetchone()

        if not estudiante:
            cur.close()
            conn.close()
            return "Error: El estudiante no existe o no es estudiante"

        # Insertar relación estudiante-curso si no existe
        cur.execute("""
            INSERT INTO estudiantes_cursos (curso_id, estudiante_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (curso_id, estudiante_id))

        # Insertar o actualizar la nota
        cur.execute("""
            INSERT INTO notas (curso_id, estudiante_id, tipo, nota)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (curso_id, estudiante_id, tipo)
            DO UPDATE SET nota = EXCLUDED.nota
        """, (curso_id, estudiante_id, tipo, nota))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(f"/ver_notas/{curso_id}")

    return render_template('ingresar_nota.html', curso_id=curso_id)

@app.route('/estudiante')
def estudiante_panel():
    if session.get('rol') != 'estudiante':
        return redirect('/')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.nombre, n.tipo, n.nota
        FROM notas n
        JOIN cursos c ON c.id = n.curso_id
        WHERE n.estudiante_id = %s
        ORDER BY c.nombre, n.tipo
    """, (session['user_id'],))
    notas = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('estudiante_panel.html', notas=notas)



@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if session.get('rol') != 'admin':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        cur.execute("UPDATE usuarios SET nombre = %s WHERE id = %s", (nuevo_nombre, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/admin')

    cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/cambiar_contraseña/<int:id>', methods=['GET', 'POST'])
def cambiar_contraseña(id):
    if session.get('rol') != 'admin':
        return redirect('/')
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nueva_clave = generate_password_hash(request.form['password'])
        cur.execute("UPDATE usuarios SET password = %s WHERE id = %s", (nueva_clave, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/admin')

    cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('cambiar_contraseña.html', usuario=usuario)

@app.route('/eliminar_usuario/<int:id>', methods=['POST'])
def eliminar_usuario(id):
    if session.get('rol') != 'admin':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    # Eliminar relaciones antes de borrar el usuario
    cur.execute("DELETE FROM estudiantes_cursos WHERE estudiante_id = %s", (id,))
    cur.execute("DELETE FROM notas WHERE estudiante_id = %s", (id,))
    cur.execute("DELETE FROM cursos WHERE docente_id = %s", (id,))
    cur.execute("DELETE FROM usuarios WHERE id = %s", (id,))
    
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/admin')
@app.route('/ver_cursos')
def ver_cursos():
    if session.get('rol') != 'admin':
        return redirect('/')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.nombre, u.nombre AS docente
        FROM cursos c
        JOIN usuarios u ON c.docente_id = u.id
    """)
    cursos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('ver_cursos.html', cursos=cursos)

@app.route('/ver_notas/<int:curso_id>')
def ver_notas(curso_id):
    if session.get('rol') != 'docente':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT n.curso_id, n.estudiante_id, u.nombre, n.tipo, n.nota
        FROM notas n
        JOIN usuarios u ON u.id = n.estudiante_id
        WHERE n.curso_id = %s
        ORDER BY n.estudiante_id, n.tipo
    """, (curso_id,))
    notas = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('ver_notas.html', notas=notas)
@app.route('/modificar_nota/<int:curso_id>/<int:estudiante_id>/<tipo>', methods=['GET', 'POST'])
def modificar_nota(curso_id, estudiante_id, tipo):
    if session.get('rol') != 'docente':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nueva_nota = request.form['nota']
        cur.execute("""
            UPDATE notas SET nota = %s 
            WHERE curso_id = %s AND estudiante_id = %s AND tipo = %s
        """, (nueva_nota, curso_id, estudiante_id, tipo))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(f"/ver_notas/{curso_id}")

    # Obtener datos actuales
    cur.execute("SELECT nombre FROM usuarios WHERE id = %s", (estudiante_id,))
    estudiante = cur.fetchone()

    cur.execute("""
        SELECT nota FROM notas
        WHERE curso_id = %s AND estudiante_id = %s AND tipo = %s
    """, (curso_id, estudiante_id, tipo))
    nota = cur.fetchone()['nota']

    cur.close()
    conn.close()
    return render_template('modificar_nota.html', estudiante=estudiante, nota=nota, tipo=tipo, curso_id=curso_id)
# ⚠️ Reemplaza con tu token de apisperu.com

#   para buscar automaticamente los DNI de las personas
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6ImxlZGFuaV82QGhvdG1haWwuY29tIn0.8veTO84MzQbh0h6zdoeLvv-O2PKwzNGvDtKk24ixikM"

@app.route("/api/reniec/<dni>")
def obtener_datos_dni(dni):
    url = f"https://dniruc.apisperu.com/api/v1/dni/{dni}?token={API_TOKEN}"
    try:
        response = requests.get(url)
        data = response.json()

        if "nombres" in data:
            nombre_completo = f"{data['nombres']} {data['apellidoPaterno']} {data['apellidoMaterno']}"
            return jsonify({"nombre": nombre_completo})
        else:
            return jsonify({"error": "DNI no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": "Error en la consulta"}), 500

#   al momento de ingresar nota busca al estudante 
@app.route('/buscar_estudiante')
def buscar_estudiante():
    query = request.args.get('query', '').lower()

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # permite usar e['nombre']
        cur.execute("""
            SELECT id, nombre, dni FROM usuarios
            WHERE LOWER(nombre) LIKE %s AND rol = 'estudiante'
        """, (f"%{query}%",))
        estudiantes = cur.fetchall()
        cur.close()
        conn.close()

        resultados = [{"id": e["id"], "nombre": e["nombre"], "dni": e["dni"]} for e in estudiantes]
        return jsonify(resultados)
    
    except Exception as e:
        print("ERROR en /buscar_estudiante:", e)
        return jsonify({"error": "Error al buscar estudiantes"}), 500

if __name__ == '__main__':
    app.run(debug=True)