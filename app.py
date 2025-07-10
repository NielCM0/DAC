from flask import Flask, render_template, request, redirect, session, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from flask import jsonify
from flask import Flask, render_template, request, redirect, session, flash
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import Response

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
def get_all_courses():
    conn = get_db_connection()  # Establece la conexión a la base de datos
    cur = conn.cursor()
    
    # Realiza la consulta SQL para obtener todos los cursos
    cur.execute("SELECT id, nombre FROM cursos")
    cursos = cur.fetchall()  # Devuelve todos los resultados de la consulta
    
    # Cierra la conexión
    cur.close()
    conn.close()
    
    return cursos


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

@app.route('/estudiantes')
def estudiantes():
    if session.get('rol') != 'docente':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, dni, nombre, rol FROM usuarios")
    usuarios = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('estudiantes.html', usuarios=usuarios)

@app.route('/crear_usuario_docente', methods=['GET', 'POST'])
def crear_usuario_docente():
    if session.get('rol') != 'docente':  # Verificamos que sea un docente
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        dni = request.form['dni']
        nombre = request.form['nombre']
        password = generate_password_hash(request.form['password'])
        rol = 'estudiante'  # Siempre asignamos rol 'estudiante'
        curso_id = request.form['curso']  

        # Verifica si el DNI ya está registrado
        cur.execute("SELECT id FROM usuarios WHERE dni = %s", (dni,))
        existing_user = cur.fetchone()

        if existing_user:
            flash("Este DNI ya está registrado", "error")
            return redirect('/crear_usuario_docente')

        # Insertar el estudiante en la tabla usuarios
        cur.execute("""
            INSERT INTO usuarios (dni, nombre, password, rol)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (dni, nombre, password, rol))

        # Obtener el id del estudiante recién creado
        estudiante = cur.fetchone()

        # Depuración: Imprimir el resultado de la consulta
        print("Resultado de la inserción del estudiante:", estudiante)

        # Verificamos si se ha insertado correctamente
        if estudiante is None:  # Si no hay respuesta válida, manejamos el error
            flash("Hubo un error al crear el estudiante", "error")
            conn.commit()  # Aseguramos que cualquier cambio en la base de datos se guarde
            cur.close()
            conn.close()
            return redirect('/crear_usuario_docente')

        estudiante_id = estudiante['id']  # Acceder a la columna 'id' de RealDictRow

        # Depuración: Verificar que estudiante_id es válido
        print(f"Estudiante ID: {estudiante_id}")

        # Insertar relación estudiante-curso en la tabla estudiantes_cursos
        cur.execute("""
            INSERT INTO estudiantes_cursos (curso_id, estudiante_id)
            VALUES (%s, %s)
        """, (curso_id, estudiante_id))

        conn.commit()  # Guardamos los cambios
        cur.close()
        conn.close()

        flash('Estudiante creado y asignado al curso correctamente', 'success')
        return redirect('/docente')

    # Obtener los cursos disponibles para mostrarlos en el formulario
    cur.execute("SELECT id, nombre, seccion FROM cursos")
    cursos = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('crear_usuario_docente.html', cursos=cursos)

@app.route('/crear_curso', methods=['GET', 'POST'])
def crear_curso():
    # Verificar si el usuario es un administrador
    if session.get('rol') != 'admin':
        return redirect('/')

    # Conexión a la base de datos
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        docente_id = request.form['docente_id']
        grado = request.form['grado']
        seccion = request.form['seccion']  # Obtener el valor de la sección

        # Ejecutar la consulta para insertar el nuevo curso en la base de datos
        cur.execute("INSERT INTO cursos (nombre, docente_id, grado, seccion) VALUES (%s, %s, %s, %s)", 
                    (nombre, docente_id, grado, seccion))

        # Confirmar la transacción
        conn.commit()

        # Cerrar la conexión a la base de datos
        cur.close()
        conn.close()

        # Redirigir a la página de administración
        return redirect('/admin')

    # Si es GET, cargar los docentes disponibles
    cur.execute("SELECT id, nombre FROM usuarios WHERE rol = 'docente'")
    docentes = cur.fetchall()

    # Cerrar la conexión a la base de datos
    cur.close()
    conn.close()

    # Renderizar la plantilla con los docentes disponibles
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
        SELECT c.nombre, c.seccion, n.tipo, n.nota
        FROM notas n
        JOIN cursos c ON c.id = n.curso_id
        WHERE n.estudiante_id = %s
        ORDER BY c.nombre, n.tipo
    """, (session['user_id'],))
    notas = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('estudiante_panel.html', notas=notas)

@app.route('/editar_usuario_docente/<int:id>', methods=['GET', 'POST'])
def editar_usuario_docente(id):
    if session.get('rol') != 'docente':
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        cur.execute("UPDATE usuarios SET nombre = %s WHERE id = %s", (nuevo_nombre, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/docente')

    cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/cambiar_contraseña_docente/<int:id>', methods=['GET', 'POST'])
def cambiar_contraseña_docente(id):
    if session.get('rol') != 'docente':
        return redirect('/')
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nueva_clave = generate_password_hash(request.form['password'])
        cur.execute("UPDATE usuarios SET password = %s WHERE id = %s", (nueva_clave, id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/docente')

    cur.execute("SELECT * FROM usuarios WHERE id = %s", (id,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('cambiar_contraseña.html', usuario=usuario)

@app.route('/eliminar_usuario_docente/<int:id>', methods=['POST'])
def eliminar_usuario_docente(id):
    if session.get('rol') != 'docente':
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
    return redirect('/docente')

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
        SELECT c.id, c.nombre, c.seccion, u.nombre AS docente
        FROM cursos c
        JOIN usuarios u ON c.docente_id = u.id
    """)
    cursos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('ver_cursos.html', cursos=cursos)

@app.route('/modificar_nota_curso/<int:curso_id>')
def modificar_nota_curso(curso_id):
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

    return render_template('modificar_nota_curso.html', notas=notas)
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

@app.route('/ingresar_notas/<int:curso_id>', methods=['GET', 'POST'])
def ingresar_notas(curso_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # Obtener las notas y tipos de examen enviados
        for estudiante_id in request.form:
            # Verificamos que el campo es para la nota del estudiante
            if estudiante_id.startswith("nota_"):
                # Obtener la nota y tipo de examen para el estudiante
                nota = request.form[estudiante_id]
                tipo_examen = request.form.get(f"tipo_{estudiante_id.split('_')[1]}")
                
                # Actualizar la tabla con las notas y tipo de examen
                cur.execute("""
                    INSERT INTO notas (estudiante_id, curso_id, nota, tipo)
                    VALUES (%s, %s, %s, %s)
                """, (estudiante_id.split('_')[1], curso_id, nota, tipo_examen))

        conn.commit()
        cur.close()
        conn.close()
        flash("Notas y tipos de examen guardados correctamente", "success")
        return redirect(f"/ingresar_notas/{curso_id}")

    # Obtener los estudiantes del curso
    cur.execute("""
        SELECT u.id, u.nombre, u.dni 
        FROM usuarios u
        JOIN estudiantes_cursos ec ON u.id = ec.estudiante_id
        WHERE ec.curso_id = %s
    """, (curso_id,))
    estudiantes = cur.fetchall()
    print("Estudiantes:", estudiantes)


    cur.close()
    conn.close()

    return render_template('ingresar_notas.html', estudiantes=estudiantes, curso_id=curso_id)

@app.route('/ver_notas_curso/<int:curso_id>', methods=['GET'])
def ver_notas_curso(curso_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Obtener los tipos de examen para el curso
    cur.execute("""
        SELECT DISTINCT tipo
        FROM notas
        WHERE curso_id = %s
    """, (curso_id,))
    tipos_examen = cur.fetchall()

    # Obtener las notas de los estudiantes
    cur.execute("""
        SELECT u.id, u.nombre, u.dni, n.nota, n.tipo
        FROM usuarios u
        JOIN estudiantes_cursos ec ON u.id = ec.estudiante_id
        LEFT JOIN notas n ON u.id = n.estudiante_id AND ec.curso_id = n.curso_id
        WHERE ec.curso_id = %s
    """, (curso_id,))
    estudiantes = cur.fetchall()

    # Organizar las notas por tipo de examen para cada estudiante
    estudiantes_dict = {}
    for estudiante in estudiantes:
        estudiante_id = estudiante['id']
        if estudiante_id not in estudiantes_dict:
            estudiantes_dict[estudiante_id] = {
                'id': estudiante_id,
                'nombre': estudiante['nombre'],
                'dni': estudiante['dni'],
                'notas': {}
            }
        
        estudiantes_dict[estudiante_id]['notas'][estudiante['tipo']] = estudiante['nota']

    cur.close()
    conn.close()

    return render_template('ver_notas_curso.html', estudiantes=estudiantes_dict.values(), curso_id=curso_id, tipos_examen=tipos_examen)


@app.route('/exportar_notas/<int:curso_id>', methods=['GET'])
def exportar_notas(curso_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Obtener el nombre del curso
    cur.execute("""
        SELECT nombre
        FROM cursos
        WHERE id = %s
    """, (curso_id,))
    curso = cur.fetchone()
    curso_nombre = curso['nombre'] if curso else 'Curso Desconocido'

    # Obtener los estudiantes y sus notas para el curso
    cur.execute("""
        SELECT u.id, u.nombre, u.dni, n.tipo, n.nota
        FROM usuarios u
        JOIN estudiantes_cursos ec ON u.id = ec.estudiante_id
        LEFT JOIN notas n ON u.id = n.estudiante_id AND ec.curso_id = n.curso_id
        WHERE ec.curso_id = %s
    """, (curso_id,))
    estudiantes = cur.fetchall()

    # Obtener los tipos de examen
    cur.execute("""
        SELECT DISTINCT tipo
        FROM notas
        WHERE curso_id = %s
    """, (curso_id,))
    tipos_examen = cur.fetchall()

    cur.close()
    conn.close()

    # Crear un archivo PDF en memoria
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Título del curso
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, height - 40, f"Boleta de Notas - {curso_nombre}")

    # Títulos de las columnas
    c.setFont("Helvetica-Bold", 12)
    y_position = height - 80
    c.drawString(30, y_position, "ID")
    c.drawString(80, y_position, "DNI")
    c.drawString(160, y_position, "Nombre")

    # Agregar las columnas de tipos de examen, comenzando a partir de una posición más a la derecha
    x_position = 340
    for tipo in tipos_examen:
        c.drawString(x_position, y_position, tipo['tipo'])
        x_position += 50  # Espaciado entre columnas para los tipos de examen

    y_position -= 20  # Espacio después de los encabezados

    # Crear un diccionario para agrupar las notas por estudiante
    estudiantes_dict = {}
    for estudiante in estudiantes:
        if estudiante['id'] not in estudiantes_dict:
            estudiantes_dict[estudiante['id']] = {
                'id': estudiante['id'],
                'nombre': estudiante['nombre'],
                'dni': estudiante['dni'],
                'notas': {}
            }
        estudiantes_dict[estudiante['id']]['notas'][estudiante['tipo']] = estudiante['nota']

    # Ajustar el tamaño de la fuente
    font_size = 10  # Fuente normal
    c.setFont("Helvetica", font_size)

    # Mostrar las notas de los estudiantes
    for estudiante in estudiantes_dict.values():
        c.setFont("Helvetica", font_size)  # Fuente más pequeña para las notas
        c.drawString(30, y_position, str(estudiante['id']))
        c.drawString(80, y_position, str(estudiante['dni']))

        # Ajuste automático del nombre para que no se desborde, y dividirlo si es necesario
        name = estudiante['nombre']
        max_name_width = 160  # Ancho máximo permitido para el nombre
        name_lines = []

        # Ajustar el nombre si excede el ancho de la columna
        max_width = max_name_width  # Ancho máximo permitido para la columna de nombre
        words = name.split()  # Dividir el nombre en palabras
        current_line = ""
        for word in words:
            # Si agregar la palabra excede el límite de ancho, comenzamos una nueva línea
            if c.stringWidth(current_line + " " + word, "Helvetica", font_size) < max_width:
                current_line += " " + word
            else:
                name_lines.append(current_line)
                current_line = word
        if current_line:  # Añadir la última línea
            name_lines.append(current_line)

        # Dibujar el nombre (ahora dividido en líneas)
        y_offset = 0
        for line in name_lines:
            c.drawString(160, y_position - y_offset, line)
            y_offset += 12  # Desplazar hacia abajo para cada nueva línea del nombre

        y_position -= (y_offset)  # Ajustar la posición Y en función del número de líneas de nombre

        # Mostrar las notas por tipo de examen
        x_position = 340
        for tipo in tipos_examen:
            tipo_examen = tipo['tipo']
            # Mostrar la nota si existe para ese tipo de examen, sino mostrar un guion
            c.drawString(x_position, y_position, estudiante['notas'].get(tipo_examen, '--'))
            x_position += 50  # Espaciado entre columnas

        y_position -= 50  # Espacio entre filas de estudiantes

        # Verificar si hay espacio suficiente en la página, si no, agregar una nueva página
        if y_position < 60:
            c.showPage()
            c.setFont("Helvetica", font_size)
            y_position = height - 80

    # Guardar el archivo PDF en memoria
    c.showPage()
    c.save()

    # Obtener el contenido del PDF generado
    buffer.seek(0)
    pdf_content = buffer.getvalue()

    # Enviar el PDF al navegador como respuesta HTTP
    return Response(pdf_content, content_type='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)