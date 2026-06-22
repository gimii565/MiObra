import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, make_response
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from datetime import date, timedelta, datetime
from weasyprint import HTML as WPHTML
from supabase import create_client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SECRET_KEY')
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'planilla_obras_2025'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = os.path.join('static', 'fotos')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# ─────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    fecha_registro = db.Column(db.Date, default=date.today)
    nombre_completo = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    foto_perfil = db.Column(db.String(200))
    obras = db.relationship('Obra', backref='usuario', lazy=True)

class Obra(db.Model):
    __tablename__ = 'obras'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(200))
    presupuesto_total = db.Column(db.Float, default=0)
    fecha_inicio = db.Column(db.Date, default=date.today)
    activa = db.Column(db.Boolean, default=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    trabajadores = db.relationship('Trabajador', backref='obra', lazy=True)
    retiros = db.relationship('Retiro', backref='obra', lazy=True)
    fotos = db.relationship('Foto', backref='obra', lazy=True)

class Trabajador(db.Model):
    __tablename__ = 'trabajadores'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    foto_perfil = db.Column(db.String(200))
    rol = db.Column(db.String(20), default='ayuco')
    jornal_dia = db.Column(db.Float)
    jornal_noche = db.Column(db.Float, default=0)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'))
    activo = db.Column(db.Boolean, default=True)
    semanas = db.relationship('Semana', backref='trabajador', lazy=True)

class Semana(db.Model):
    __tablename__ = 'semanas'
    id = db.Column(db.Integer, primary_key=True)
    trabajador_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'))
    fecha_inicio = db.Column(db.Date, nullable=False)
    saldo_anterior = db.Column(db.Float, default=0)
    asistencias = db.relationship('Asistencia', backref='semana', lazy=True)
    pagos = db.relationship('Pago', backref='semana', lazy=True)

class Asistencia(db.Model):
    __tablename__ = 'asistencias'
    id = db.Column(db.Integer, primary_key=True)
    semana_id = db.Column(db.Integer, db.ForeignKey('semanas.id'), nullable=False)
    dia = db.Column(db.String(10), nullable=False)
    tipo = db.Column(db.String(20), default='ninguno')

class Pago(db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    semana_id = db.Column(db.Integer, db.ForeignKey('semanas.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    nota = db.Column(db.String(200))
    fecha = db.Column(db.Date, default=date.today)

class Retiro(db.Model):
    __tablename__ = 'retiros'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    nota = db.Column(db.String(200))
    fecha = db.Column(db.Date, default=date.today)

class Foto(db.Model):
    __tablename__ = 'fotos'
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    nota = db.Column(db.String(200))
    fecha = db.Column(db.Date, default=date.today)

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    id = db.Column(db.Integer, primary_key=True)
    contratista_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    trabajador_id  = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    obra_id        = db.Column(db.Integer, db.ForeignKey('obras.id'))
    estado         = db.Column(db.String(20), default='pendiente')
    fecha          = db.Column(db.Date, default=date.today)
    contratista = db.relationship('Usuario', backref='solicitudes')
    trabajador  = db.relationship('Trabajador', backref='solicitudes')
    obra        = db.relationship('Obra', backref='solicitudes')

class TrabajadorObra(db.Model):
    __tablename__ = 'trabajador_obras'
    id = db.Column(db.Integer, primary_key=True)
    trabajador_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'))
    activo = db.Column(db.Boolean, default=True)
    estado = db.Column(db.String(20), default='activa')
    jornal_dia = db.Column(db.Float)
    jornal_noche = db.Column(db.Float)
    rol = db.Column(db.String(20), default='ayuco')
    fecha_ingreso = db.Column(db.Date, default=date.today)
    trabajador = db.relationship('Trabajador', backref='trabajador_obras')
    obra = db.relationship('Obra', backref='trabajador_obras')

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'
    id = db.Column(db.Integer, primary_key=True)
    contratista_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    trabajador_id = db.Column(db.Integer, db.ForeignKey('trabajadores.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'))
    tipo = db.Column(db.String(50))
    leida = db.Column(db.Boolean, default=False)
    fecha = db.Column(db.Date, default=date.today)
    contratista = db.relationship('Usuario', backref='notificaciones')
    trabajador = db.relationship('Trabajador', backref='notificaciones')
    obra = db.relationship('Obra', backref='notificaciones')

class Mensaje(db.Model):
    __tablename__ = 'mensajes'
    id = db.Column(db.Integer, primary_key=True)
    remitente_tipo = db.Column(db.String(20), nullable=False)
    remitente_id = db.Column(db.Integer, nullable=False)
    destinatario_tipo = db.Column(db.String(20), nullable=False)
    destinatario_id = db.Column(db.Integer, nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    leido = db.Column(db.Boolean, default=False)
    fecha = db.Column(db.DateTime, default=datetime.now)

# ─────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────
def calcular_saldo(semana):
    t = semana.trabajador
    total_jornal = semana.saldo_anterior
    for a in semana.asistencias:
        if a.tipo == 'completo':
            total_jornal += t.jornal_dia
        elif a.tipo == 'medio':
            total_jornal += t.jornal_dia / 2
        elif a.tipo == 'noche':
            total_jornal += t.jornal_noche
        elif a.tipo == 'medio_noche':
            total_jornal += (t.jornal_dia / 2) + t.jornal_noche
        elif a.tipo == 'completo_noche':
            total_jornal += t.jornal_dia + t.jornal_noche
    total_pagado = sum(p.monto for p in semana.pagos)
    return total_jornal - total_pagado

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_requerido():
    if not session.get('usuario_id'):
        return redirect(url_for('login'))
    return None

def get_usuario_actual():
    return Usuario.query.get(session.get('usuario_id'))

# ─────────────────────────────────────────
# CONTEXT PROCESSOR
# ─────────────────────────────────────────
SUPABASE_STORAGE_URL = f"https://nstciddinmrdigagjbxy.supabase.co/storage/v1/object/public/Fotos"

@app.context_processor
def utilidades():
    return dict(
        timedelta=timedelta,
        calcular_saldo=calcular_saldo,
        session=session,
        today=date.today,
        supabase_url=SUPABASE_STORAGE_URL
    )

# ─────────────────────────────────────────
# LOGIN Y REGISTRO CONTRATISTA
# ─────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('usuario_id'):
        return redirect(url_for('contratista'))
    error = None
    if request.method == 'POST':
        usuario  = request.form['usuario'].strip()
        password = request.form['password']
        u = Usuario.query.filter_by(usuario=usuario).first()
        if u and check_password_hash(u.password, password):
            session['usuario_id']     = u.id
            session['usuario_nombre'] = u.usuario
            session['foto_perfil']    = u.foto_perfil or ''
            return redirect(url_for('contratista'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if session.get('usuario_id'):
        return redirect(url_for('contratista'))
    error = None
    if request.method == 'POST':
        usuario         = request.form['usuario'].strip()
        password        = request.form['password']
        confirmar       = request.form['confirmar']
        nombre_completo = request.form.get('nombre_completo', '').strip()
        apellido        = request.form.get('apellido', '').strip()
        telefono        = request.form.get('telefono', '').strip()

        if password != confirmar:
            error = 'Las contraseñas no coinciden'
        elif Usuario.query.filter_by(usuario=usuario).first():
            error = 'Ese usuario ya existe'
        elif len(password) < 4:
            error = 'La contraseña debe tener al menos 4 caracteres'
        else:
            u = Usuario(
                usuario=usuario,
                password=generate_password_hash(password),
                nombre_completo=nombre_completo,
                apellido=apellido,
                telefono=telefono
            )
            db.session.add(u)
            db.session.flush()

            if 'foto' in request.files:
                file = request.files['foto']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"perfil_{u.id}_{file.filename}")
                    file_bytes = file.read()
                    supabase_client.storage.from_('Fotos').upload(
                        filename,
                        file_bytes,
                        {'content-type': file.content_type}
                    )
                    u.foto_perfil = filename

            db.session.commit()
            session['usuario_id']     = u.id
            session['usuario_nombre'] = u.usuario
            session['foto_perfil']    = u.foto_perfil or ''
            return redirect(url_for('contratista'))

    return render_template('registro.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─────────────────────────────────────────
# LOGIN Y REGISTRO TRABAJADOR
# ─────────────────────────────────────────
@app.route('/trabajador/login', methods=['GET', 'POST'])
def trabajador_login():
    if session.get('trabajador_id'):
        return redirect(url_for('trabajador_inicio'))
    error = None
    if request.method == 'POST':
        usuario  = request.form['usuario'].strip()
        password = request.form['password']
        t = Trabajador.query.filter_by(email=usuario, activo=True).first()
        if t and t.password and check_password_hash(t.password, password):
            session['trabajador_id']     = t.id
            session['trabajador_nombre'] = f"{t.nombre} {t.apellido or ''}".strip()
            session['trabajador_foto']   = t.foto_perfil or ''
            return redirect(url_for('trabajador_inicio'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('trabajador_login.html', error=error)

@app.route('/trabajador/registro', methods=['GET', 'POST'])
def trabajador_registro():
    error = None
    if request.method == 'POST':
        nombre    = request.form['nombre'].strip()
        apellido  = request.form.get('apellido', '').strip()
        usuario   = request.form['usuario'].strip()
        telefono  = request.form.get('telefono', '').strip()
        password  = request.form['password']
        confirmar = request.form['confirmar']

        if password != confirmar:
            error = 'Las contraseñas no coinciden'
        elif len(password) < 4:
            error = 'La contraseña debe tener al menos 4 caracteres'
        elif Trabajador.query.filter_by(email=usuario).first():
            error = 'Ese usuario ya existe'
        else:
            t = Trabajador(
                nombre=nombre,
                apellido=apellido,
                email=usuario,
                telefono=telefono,
                password=generate_password_hash(password)
            )
            db.session.add(t)
            db.session.flush()

            if 'foto' in request.files:
                file = request.files['foto']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"trab_{t.id}_{file.filename}")
                    file_bytes = file.read()
                    supabase_client.storage.from_('Fotos').upload(
                        filename,
                        file_bytes,
                        {'content-type': file.content_type}
                    )
                    t.foto_perfil = filename

            db.session.commit()
            session['trabajador_id']     = t.id
            session['trabajador_nombre'] = f"{t.nombre} {t.apellido or ''}".strip()
            session['trabajador_foto']   = t.foto_perfil or ''
            return redirect(url_for('trabajador_inicio'))

    return render_template('trabajador_registro.html', error=error)

@app.route('/trabajador/logout')
def trabajador_logout():
    session.pop('trabajador_id', None)
    session.pop('trabajador_nombre', None)
    session.pop('trabajador_foto', None)
    return redirect(url_for('index'))

# ─────────────────────────────────────────
# RUTAS PRINCIPALES
# ─────────────────────────────────────────
@app.route('/')
def index():
    if session.get('usuario_id'):
        return redirect(url_for('contratista'))
    if session.get('trabajador_id'):
        return redirect(url_for('trabajador_inicio'))
    return render_template('index.html')

@app.route('/trabajador/inicio')
def trabajador_inicio():
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    t = Trabajador.query.get_or_404(session['trabajador_id'])

    trabajador_obras = TrabajadorObra.query.filter_by(
        trabajador_id=t.id, activo=True, estado='activa'
    ).all()
    obras = [to.obra for to in trabajador_obras if to.obra.activa]

    obras_archivadas_raw = TrabajadorObra.query.filter_by(
        trabajador_id=t.id, estado='archivada'
    ).all()
    obras_archivadas = []
    for to in obras_archivadas_raw:
        semanas_obra = Semana.query.filter_by(
            trabajador_id=t.id, obra_id=to.obra_id
        ).all()
        deuda = sum(calcular_saldo(s) for s in semanas_obra)
        obras_archivadas.append({'to': to, 'deuda': round(deuda, 2)})

    solicitudes = Solicitud.query.filter_by(trabajador_id=t.id, estado='pendiente').all()
    print(f"DEBUG obras_archivadas: {len(obras_archivadas)} — {obras_archivadas}")
    return render_template('trabajador_inicio.html',
        t=t, obras=obras, obras_archivadas=obras_archivadas, solicitudes=solicitudes
    )

@app.route('/solicitud/<int:solicitud_id>/revisar')
def revisar_solicitud(solicitud_id):
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    trab_id = session['trabajador_id']
    obra_activa = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id, estado='activa'
    ).first()
    deuda = 0
    if obra_activa:
        semanas_obra = Semana.query.filter_by(
            trabajador_id=trab_id, obra_id=obra_activa.obra_id
        ).all()
        deuda = sum(calcular_saldo(s) for s in semanas_obra)
    return render_template('revisar_solicitud.html',
        solicitud=solicitud,
        obra_activa=obra_activa,
        deuda=round(deuda, 2)
    )

@app.route('/solicitud/<int:solicitud_id>/responder', methods=['POST'])
def responder_solicitud(solicitud_id):
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    trab_id = session['trabajador_id']
    accion = request.form.get('accion')

    if accion == 'rechazar':
        solicitud.estado = 'rechazada'
        db.session.commit()
        return redirect(url_for('trabajador_inicio'))

    obra_activa = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id, estado='activa'
    ).first()

    if obra_activa:
        accion_obra = request.form.get('accion_obra')
        semanas_obra = Semana.query.filter_by(
            trabajador_id=trab_id, obra_id=obra_activa.obra_id
        ).all()
        deuda = sum(calcular_saldo(s) for s in semanas_obra)

        if accion_obra == 'salir' and deuda == 0:
            obra_activa.estado = 'salida'
        else:
            obra_activa.estado = 'archivada'
        obra_activa.activo = False
        db.session.flush()

        # Notificar al contratista
        obra_anterior = Obra.query.get(obra_activa.obra_id)
        if obra_anterior:
            tipo_notif = f"salida_con_deuda:{round(deuda,2)}" if deuda > 0 else "salida_sin_deuda"
            notif = Notificacion(
                contratista_id=obra_anterior.usuario_id,
                trabajador_id=trab_id,
                obra_id=obra_activa.obra_id,
                tipo=tipo_notif
            )
            db.session.add(notif)

    # Aceptar la nueva solicitud
    solicitud.estado = 'aceptada'
    t = Trabajador.query.get(trab_id)

    # Si ya existía un registro en trabajador_obras para esta obra, reactivarlo
    to_existente = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id, obra_id=solicitud.obra_id
    ).first()

    if to_existente:
        # Limpiar semanas anteriores de esa obra
        semanas_viejas = Semana.query.filter_by(
            trabajador_id=trab_id, obra_id=solicitud.obra_id
        ).all()
        for s in semanas_viejas:
            for a in s.asistencias:
                db.session.delete(a)
            for p in s.pagos:
                db.session.delete(p)
            db.session.delete(s)
        to_existente.activo = True
        to_existente.estado = 'activa'
        to_existente.jornal_dia = t.jornal_dia
        to_existente.jornal_noche = t.jornal_noche
        to_existente.rol = t.rol
    else:
        nuevo = TrabajadorObra(
            trabajador_id=trab_id,
            obra_id=solicitud.obra_id,
            estado='activa',
            activo=True,
            jornal_dia=t.jornal_dia,
            jornal_noche=t.jornal_noche,
            rol=t.rol
        )
        db.session.add(nuevo)

    db.session.commit()
    return redirect(url_for('trabajador_inicio'))

@app.route('/trabajador/mis-archivadas')
def trabajador_mis_archivadas():
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    t = Trabajador.query.get_or_404(session['trabajador_id'])
    obras_archivadas_raw = TrabajadorObra.query.filter_by(
        trabajador_id=t.id, estado='archivada'
    ).all()
    obras_archivadas = []
    for to in obras_archivadas_raw:
        semanas_obra = Semana.query.filter_by(
            trabajador_id=t.id, obra_id=to.obra_id
        ).all()
        deuda = sum(calcular_saldo(s) for s in semanas_obra)
        obras_archivadas.append({'to': to, 'deuda': round(deuda, 2)})
    return render_template('trabajador_archivadas.html', t=t, obras_archivadas=obras_archivadas)

@app.route('/trabajador/salir-obra/<int:obra_id>')
def salir_obra(obra_id):
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    trab_id = session['trabajador_id']
    to = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id, obra_id=obra_id, activo=True
    ).first()
    if to:
        semanas_obra = Semana.query.filter_by(
            trabajador_id=trab_id, obra_id=obra_id
        ).all()
        deuda = sum(calcular_saldo(s) for s in semanas_obra)
        if deuda > 0:
            to.estado = 'archivada'
        else:
            to.estado = 'salida'
        to.activo = False

        # Notificar al contratista
        obra = Obra.query.get(obra_id)
        if obra:
            tipo_notif = f"salida_con_deuda:{round(deuda,2)}" if deuda > 0 else "salida_sin_deuda"
            notif = Notificacion(
                contratista_id=obra.usuario_id,
                trabajador_id=trab_id,
                obra_id=obra_id,
                tipo=tipo_notif
            )
            db.session.add(notif)

        db.session.commit()
    return redirect(url_for('trabajador_inicio'))

@app.route('/contratista')
def contratista():
    redir = login_requerido()
    if redir: return redir
    usuario = get_usuario_actual()
    obras = Obra.query.filter_by(usuario_id=usuario.id, activa=True).all()
    return render_template('contratista.html', obras=obras, usuario=usuario)

# ─────────────────────────────────────────
# RUTAS CONTRATISTA
# ─────────────────────────────────────────
@app.route('/obra/nueva', methods=['GET', 'POST'])
def nueva_obra():
    redir = login_requerido()
    if redir: return redir
    if request.method == 'POST':
        usuario = get_usuario_actual()
        obra = Obra(
            nombre=request.form['nombre'],
            descripcion=request.form.get('descripcion', ''),
            presupuesto_total=float(request.form.get('presupuesto', 0)),
            fecha_inicio=date.today(),
            usuario_id=usuario.id
        )
        db.session.add(obra)
        db.session.commit()
        return redirect(url_for('contratista'))
    return render_template('nueva_obra.html')

@app.route('/obra/<int:obra_id>')
def ver_obra(obra_id):
    redir = login_requerido()
    if redir: return redir
    obra = Obra.query.get_or_404(obra_id)
    if obra.usuario_id != session.get('usuario_id'):
        return redirect(url_for('contratista'))

    trabajador_obras = TrabajadorObra.query.filter_by(obra_id=obra_id, activo=True, estado='activa').all()
    ids_intermedia   = [to.trabajador_id for to in trabajador_obras]

    trabajadores_directos = Trabajador.query.filter_by(obra_id=obra_id, activo=True).all()
    ids_directos = [t.id for t in trabajadores_directos]

    todos_ids    = list(set(ids_intermedia + ids_directos))
    trabajadores = Trabajador.query.filter(
        Trabajador.id.in_(todos_ids),
        Trabajador.activo == True
    ).all() if todos_ids else []

    hoy    = date.today()
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    lunes_creacion = obra.fecha_inicio - timedelta(days=obra.fecha_inicio.weekday())

    semana_offset = request.args.get('semana_offset', 0, type=int)

    # Límites: no antes de la semana de creación, no después de la semana actual
    offset_minimo = (lunes_creacion - lunes_actual).days // 7
    offset_maximo = 0
    semana_offset = max(offset_minimo, min(offset_maximo, semana_offset))

    lunes  = lunes_actual + timedelta(weeks=semana_offset)
    sabado = lunes + timedelta(days=5)
    es_semana_actual = (semana_offset == 0)
    puede_retroceder = semana_offset > offset_minimo
    puede_avanzar = semana_offset < offset_maximo

    total_retiros    = sum(r.monto for r in obra.retiros)
    saldo_disponible = obra.presupuesto_total - total_retiros
    porcentaje_gastado = round((total_retiros / obra.presupuesto_total * 100), 1) if obra.presupuesto_total else 0

    resumen_trabajadores = []
    total_semana_actual  = 0
    total_deuda_general  = 0
    saldo_maestros       = 0
    saldo_ayucos         = 0

    for t in trabajadores:
        semana_actual = Semana.query.filter_by(
            trabajador_id=t.id, obra_id=obra_id, fecha_inicio=lunes
        ).first()
        saldo_semana  = calcular_saldo(semana_actual) if semana_actual else 0
        total_semana_actual += saldo_semana
        semanas_obra = Semana.query.filter_by(trabajador_id=t.id, obra_id=obra_id).all()
        deuda_total = sum(calcular_saldo(s) for s in semanas_obra)
        total_deuda_general += deuda_total
        resumen_trabajadores.append({
            'trabajador':   t,
            'saldo_semana': round(saldo_semana, 2),
            'deuda_total':  round(deuda_total, 2),
            'semanas': sorted(semanas_obra, key=lambda s: s.fecha_inicio, reverse=True)
        })
        if t.rol == 'maestro':
            saldo_maestros += saldo_semana
        elif t.rol == 'ayuco':
            saldo_ayucos += saldo_semana

    notificaciones = Notificacion.query.filter_by(obra_id=obra_id, leida=False).all()

    return render_template('obra.html',
        obra=obra,
        resumen_trabajadores=resumen_trabajadores,
        total_retiros=total_retiros,
        saldo_disponible=saldo_disponible,
        porcentaje_gastado=porcentaje_gastado,
        total_semana_actual=round(total_semana_actual, 2),
        total_deuda_general=round(total_deuda_general, 2),
        saldo_maestros=round(saldo_maestros, 2),
        saldo_ayucos=round(saldo_ayucos, 2),
        lunes=lunes,
        sabado=sabado,
        semana_offset=semana_offset,
        es_semana_actual=es_semana_actual,
        puede_retroceder=puede_retroceder,
        puede_avanzar=puede_avanzar,
        notificaciones=notificaciones
    )

@app.route('/obra/<int:obra_id>/trabajador/nuevo', methods=['GET', 'POST'])
def nuevo_trabajador(obra_id):
    redir = login_requerido()
    if redir: return redir
    obra = Obra.query.get_or_404(obra_id)
    return render_template('nuevo_trabajador.html', obra=obra)

@app.route('/obra/<int:obra_id>/invitar', methods=['POST'])
def invitar_trabajador(obra_id):
    redir = login_requerido()
    if redir: return redir
    trabajador_id = int(request.form['trabajador_id'])
    jornal_dia    = float(request.form['jornal_dia'])
    jornal_noche  = float(request.form.get('jornal_noche') or jornal_dia / 2)
    rol           = request.form.get('rol', 'ayuco')
    existe = Solicitud.query.filter_by(
        trabajador_id=trabajador_id, obra_id=obra_id, estado='pendiente'
    ).first()
    if not existe:
        solicitud = Solicitud(
            contratista_id=session['usuario_id'],
            trabajador_id=trabajador_id,
            obra_id=obra_id,
            estado='pendiente'
        )
        db.session.add(solicitud)
        t = Trabajador.query.get(trabajador_id)
        if t:
            t.jornal_dia   = jornal_dia
            t.jornal_noche = jornal_noche
            t.rol          = rol
        db.session.commit()
    return redirect(url_for('ver_obra', obra_id=obra_id))

@app.route('/api/buscar-trabajadores')
def buscar_trabajadores():
    redir = login_requerido()
    if redir: return jsonify([])
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    trabajadores = Trabajador.query.filter(
        db.or_(Trabajador.nombre.ilike(f'%{q}%'), Trabajador.apellido.ilike(f'%{q}%'))
    ).limit(10).all()
    return jsonify([{
        'id': t.id, 'nombre': t.nombre,
        'apellido': t.apellido or '', 'telefono': t.telefono or ''
    } for t in trabajadores])

@app.route('/trabajador/<int:trab_id>/editar', methods=['GET', 'POST'])
def editar_trabajador(trab_id):
    redir = login_requerido()
    if redir: return redir
    t = Trabajador.query.get_or_404(trab_id)
    obra_id = request.args.get('obra_id', type=int) or t.obra_id
    if request.method == 'POST':
        t.nombre       = request.form['nombre']
        t.rol          = request.form.get('rol', 'ayuco')
        t.jornal_dia   = float(request.form['jornal_dia'])
        t.jornal_noche = float(request.form.get('jornal_noche') or t.jornal_dia / 2)
        obra_id        = request.form.get('obra_id', type=int) or t.obra_id
        db.session.commit()
        return redirect(url_for('ver_obra', obra_id=obra_id))
    return render_template('editar_trabajador.html', trabajador=t, obra_id=obra_id)

@app.route('/trabajador/<int:trabajador_id>/semana')
def ver_semana(trabajador_id):
    redir = login_requerido()
    if redir: return redir
    trabajador = Trabajador.query.get_or_404(trabajador_id)
    obra_id = request.args.get('obra_id', type=int) or trabajador.obra_id

    hoy = date.today()
    lunes_actual = hoy - timedelta(days=hoy.weekday())

    semana_offset = request.args.get('semana_offset', 0, type=int)
    lunes = lunes_actual + timedelta(weeks=semana_offset)
    sabado = lunes + timedelta(days=5)
    es_semana_actual = (semana_offset == 0)

    semana = Semana.query.filter_by(
        trabajador_id=trabajador_id,
        obra_id=obra_id,
        fecha_inicio=lunes
    ).first()

    if not semana:
        semana_anterior = Semana.query.filter_by(
            trabajador_id=trabajador_id,
            obra_id=obra_id
        ).order_by(Semana.fecha_inicio.desc()).first()

        saldo_ant = calcular_saldo(semana_anterior) if semana_anterior else 0

        semana = Semana(
            trabajador_id=trabajador_id,
            obra_id=obra_id,
            fecha_inicio=lunes,
            saldo_anterior=saldo_ant if es_semana_actual else 0
        )
        db.session.add(semana)
        db.session.commit()

    primera_semana = Semana.query.filter_by(
        trabajador_id=trabajador_id, obra_id=obra_id
    ).order_by(Semana.fecha_inicio.asc()).first()
    offset_minimo = ((primera_semana.fecha_inicio - lunes_actual).days // 7) if primera_semana else 0
    puede_retroceder = semana_offset > offset_minimo
    puede_avanzar = semana_offset < 0

    dias        = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado']
    asistencias = {a.dia: a for a in semana.asistencias}

    return render_template('semana.html',
        trabajador=trabajador,
        semana=semana,
        dias=dias,
        asistencias=asistencias,
        saldo_semana=calcular_saldo(semana),
        sabado=sabado,
        semana_offset=semana_offset,
        es_semana_actual=es_semana_actual,
        puede_retroceder=puede_retroceder,
        puede_avanzar=puede_avanzar
    )

@app.route('/trabajador/<int:trabajador_id>/semana/reporte/pdf')
def descargar_reporte_pdf(trabajador_id):
    redir = login_requerido()
    if redir: return redir

    trabajador = Trabajador.query.get_or_404(trabajador_id)
    obra_id = request.args.get('obra_id', type=int) or trabajador.obra_id
    obra = Obra.query.get_or_404(obra_id)
    contratista = Usuario.query.get_or_404(obra.usuario_id)

    hoy   = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())

    semana = Semana.query.filter_by(
        trabajador_id=trabajador_id,
        obra_id=obra_id,
        fecha_inicio=lunes
    ).first()

    if not semana:
        return redirect(url_for('ver_semana', trabajador_id=trabajador_id))

    asistencias = {a.dia: a for a in semana.asistencias}
    saldo_semana = calcular_saldo(semana)

    t = trabajador
    total_jornales = semana.saldo_anterior
    for a in semana.asistencias:
        if a.tipo == 'completo':
            total_jornales += t.jornal_dia
        elif a.tipo == 'medio':
            total_jornales += t.jornal_dia / 2
        elif a.tipo == 'noche':
            total_jornales += t.jornal_noche
        elif a.tipo == 'medio_noche':
            total_jornales += (t.jornal_dia / 2) + t.jornal_noche
        elif a.tipo == 'completo_noche':
            total_jornales += t.jornal_dia + t.jornal_noche

    total_pagos = sum(p.monto for p in semana.pagos)

    html_str = render_template('reporte_semana.html',
        trabajador=trabajador,
        obra=obra,
        contratista=contratista,
        semana=semana,
        asistencias=asistencias,
        saldo_semana=round(saldo_semana, 2),
        total_jornales=round(total_jornales, 2),
        total_pagos=round(total_pagos, 2),
        fecha_hoy=hoy.strftime('%d/%m/%Y'),
        modo_pdf=True
    )

    pdf = WPHTML(string=html_str, base_url=request.base_url).write_pdf()

    nombre = f"reporte_{trabajador.nombre}_{trabajador.apellido}_semana_{semana.fecha_inicio}.pdf"
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response

@app.route('/trabajador/<int:trabajador_id>/semana/reporte')
def reporte_semana(trabajador_id):
    redir = login_requerido()
    if redir: return redir

    trabajador = Trabajador.query.get_or_404(trabajador_id)
    obra_id = request.args.get('obra_id', type=int) or trabajador.obra_id
    obra = Obra.query.get_or_404(obra_id)
    contratista = Usuario.query.get_or_404(obra.usuario_id)

    hoy   = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())

    semana = Semana.query.filter_by(
        trabajador_id=trabajador_id,
        obra_id=obra_id,
        fecha_inicio=lunes
    ).first()

    if not semana:
        return redirect(url_for('ver_semana', trabajador_id=trabajador_id))

    asistencias = {a.dia: a for a in semana.asistencias}
    saldo_semana = calcular_saldo(semana)

    t = trabajador
    total_jornales = semana.saldo_anterior
    for a in semana.asistencias:
        if a.tipo == 'completo':
            total_jornales += t.jornal_dia
        elif a.tipo == 'medio':
            total_jornales += t.jornal_dia / 2
        elif a.tipo == 'noche':
            total_jornales += t.jornal_noche
        elif a.tipo == 'medio_noche':
            total_jornales += (t.jornal_dia / 2) + t.jornal_noche
        elif a.tipo == 'completo_noche':
            total_jornales += t.jornal_dia + t.jornal_noche

    total_pagos = sum(p.monto for p in semana.pagos)

    return render_template('reporte_semana.html',
        trabajador=trabajador,
        obra=obra,
        contratista=contratista,
        semana=semana,
        asistencias=asistencias,
        saldo_semana=round(saldo_semana, 2),
        total_jornales=round(total_jornales, 2),
        total_pagos=round(total_pagos, 2),
        fecha_hoy=hoy.strftime('%d/%m/%Y')
    )

@app.route('/mi-semana/<int:trabajador_id>')
def mi_semana(trabajador_id):
    if not session.get('trabajador_id') and not session.get('usuario_id'):
        return redirect(url_for('trabajador_login'))

    trabajador = Trabajador.query.get_or_404(trabajador_id)
    obra_id = request.args.get('obra_id', type=int)
    hoy   = date.today()
    lunes_actual = hoy - timedelta(days=hoy.weekday())

    fecha_inicio_param = request.args.get('fecha_inicio')
    if fecha_inicio_param:
        try:
            from datetime import datetime as dt
            lunes = dt.strptime(fecha_inicio_param, '%Y-%m-%d').date()
        except ValueError:
            lunes = lunes_actual
    else:
        lunes = lunes_actual

    semana = Semana.query.filter_by(
        trabajador_id=trabajador_id,
        obra_id=obra_id,
        fecha_inicio=lunes
    ).first()

    if not semana and lunes == lunes_actual:
        semana_anterior = Semana.query.filter_by(
            trabajador_id=trabajador_id,
            obra_id=obra_id
        ).order_by(Semana.fecha_inicio.desc()).first()

        saldo_ant = calcular_saldo(semana_anterior) if semana_anterior else 0

        semana = Semana(
            trabajador_id=trabajador_id,
            obra_id=obra_id,
            fecha_inicio=lunes,
            saldo_anterior=saldo_ant
        )
        db.session.add(semana)
        db.session.commit()

    if not semana:
        return render_template('semana.html',
            trabajador=trabajador,
            semana=None,
            dias=['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado'],
            asistencias={},
            saldo_semana=0,
            lunes=lunes,
            obra_id=obra_id
        )

    dias        = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado']
    asistencias = {a.dia: a for a in semana.asistencias}

    sabado = lunes + timedelta(days=5)
    return render_template('semana.html',
        trabajador=trabajador,
        semana=semana,
        dias=dias,
        asistencias=asistencias,
        saldo_semana=calcular_saldo(semana),
        lunes=lunes,
        sabado=sabado,
        obra_id=obra_id,
        semana_offset=0,
        es_semana_actual=False,
        puede_retroceder=False,
        puede_avanzar=False
    )

@app.route('/semana/<int:semana_id>/pago', methods=['POST'])
def agregar_pago(semana_id):
    redir = login_requerido()
    if redir: return redir
    semana = Semana.query.get_or_404(semana_id)
    pago = Pago(
        semana_id=semana_id,
        monto=float(request.form['monto']),
        nota=request.form.get('nota', ''),
        fecha=date.today()
    )
    db.session.add(pago)
    db.session.commit()
    return redirect(url_for('ver_semana',
        trabajador_id=semana.trabajador_id,
        obra_id=semana.obra_id
    ))

@app.route('/obra/<int:obra_id>/retiro', methods=['POST'])
def agregar_retiro(obra_id):
    redir = login_requerido()
    if redir: return redir
    retiro = Retiro(
        obra_id=obra_id,
        monto=float(request.form['monto']),
        nota=request.form.get('nota', ''),
        fecha=date.today()
    )
    db.session.add(retiro)
    db.session.commit()
    return redirect(url_for('ver_obra', obra_id=obra_id))

# ─────────────────────────────────────────
# RUTAS FOTOS
# ─────────────────────────────────────────
@app.route('/obra/<int:obra_id>/fotos')
def ver_fotos(obra_id):
    redir = login_requerido()
    if redir: return redir
    obra  = Obra.query.get_or_404(obra_id)
    fotos = Foto.query.filter_by(obra_id=obra_id).order_by(Foto.fecha.desc()).all()
    return render_template('fotos.html', obra=obra, fotos=fotos)

@app.route('/obra/<int:obra_id>/fotos/subir', methods=['POST'])
def subir_foto(obra_id):
    redir = login_requerido()
    if redir: return redir
    if 'foto' not in request.files:
        return redirect(url_for('ver_fotos', obra_id=obra_id))
    file = request.files['foto']
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{obra_id}_{date.today()}_{file.filename}")
        file_bytes = file.read()
        try:
            supabase_client.storage.from_('Fotos').upload(
                filename,
                file_bytes,
                {'content-type': file.content_type}
            )
            print(f"Foto subida a Supabase: {filename}")
        except Exception as e:
            print(f"ERROR Supabase upload: {e}")
        foto = Foto(obra_id=obra_id, filename=filename,
                    nota=request.form.get('nota', ''), fecha=date.today())
        db.session.add(foto)
        db.session.commit()
    return redirect(url_for('ver_fotos', obra_id=obra_id))

@app.route('/obra/<int:obra_id>/fotos/eliminar/<int:foto_id>', methods=['POST'])
def eliminar_foto(foto_id, obra_id):
    redir = login_requerido()
    if redir: return redir
    foto = Foto.query.get_or_404(foto_id)
    try:
        supabase_client.storage.from_('Fotos').remove([foto.filename])
    except:
        pass
    db.session.delete(foto)
    db.session.commit()
    return redirect(url_for('ver_fotos', obra_id=obra_id))

# ─────────────────────────────────────────
# API ASISTENCIA
# ─────────────────────────────────────────
@app.route('/api/asistencia', methods=['POST'])
def guardar_asistencia():
    data      = request.json
    semana_id = int(data['semana_id'])
    dia       = data['dia']
    tipo      = data.get('tipo', 'ninguno') or 'ninguno'
    asistencia = Asistencia.query.filter_by(semana_id=semana_id, dia=dia).first()
    if asistencia:
        asistencia.tipo = tipo
    else:
        asistencia = Asistencia(semana_id=semana_id, dia=dia, tipo=tipo)
        db.session.add(asistencia)
    db.session.commit()
    semana = Semana.query.get(semana_id)
    return jsonify({'saldo': calcular_saldo(semana)})

# ─────────────────────────────────────────
# TRABAJADORES — ARCHIVAR / ELIMINAR
# ─────────────────────────────────────────
@app.route('/trabajador/<int:trab_id>/archivar', methods=['POST'])
def archivar_trabajador(trab_id):
    redir = login_requerido()
    if redir: return redir
    obra_id = request.form.get('obra_id', type=int)

    to = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id, obra_id=obra_id, activo=True
    ).first()
    if to:
        to.activo = False
        to.estado = 'archivada'

    t = Trabajador.query.get(trab_id)
    if t and t.obra_id == obra_id:
        t.obra_id = None

    db.session.commit()
    return redirect(url_for('ver_obra', obra_id=obra_id))

@app.route('/trabajador/<int:trab_id>/eliminar', methods=['POST'])
def eliminar_trabajador(trab_id):
    redir = login_requerido()
    if redir: return redir
    obra_id = request.form.get('obra_id', type=int)

    to = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id, obra_id=obra_id, activo=True
    ).first()
    if to:
        to.activo = False
        to.estado = 'salida'

    t = Trabajador.query.get(trab_id)
    if t and t.obra_id == obra_id:
        t.obra_id = None

    db.session.commit()
    return redirect(url_for('ver_obra', obra_id=obra_id))

@app.route('/obra/<int:obra_id>/archivados')
def ver_archivados(obra_id):
    redir = login_requerido()
    if redir: return redir
    obra = Obra.query.get_or_404(obra_id)

    to_archivados = TrabajadorObra.query.filter_by(
        obra_id=obra_id, activo=False, estado='archivada'
    ).all()
    resumen = []
    for to in to_archivados:
        t = to.trabajador
        semanas_obra = Semana.query.filter_by(trabajador_id=t.id, obra_id=obra_id).all()
        deuda = sum(calcular_saldo(s) for s in semanas_obra)
        resumen.append({'trabajador': t, 'deuda_total': round(deuda, 2)})

    return render_template('archivados.html', obra=obra, resumen=resumen)

# ─────────────────────────────────────────
# NOTIFICACIONES
# ─────────────────────────────────────────
@app.route('/notificacion/<int:notif_id>/accion', methods=['POST'])
def accion_notificacion(notif_id):
    redir = login_requerido()
    if redir: return redir
    notif = Notificacion.query.get_or_404(notif_id)
    accion = request.form.get('accion')
    obra_id = notif.obra_id

    if accion == 'archivar':
        notif.leida = True
    elif accion == 'eliminar':
        to = TrabajadorObra.query.filter_by(
            trabajador_id=notif.trabajador_id,
            obra_id=obra_id
        ).first()
        if to:
            to.activo = False
            to.estado = 'salida'
        notif.leida = True

    db.session.commit()
    return redirect(url_for('ver_obra', obra_id=obra_id))

# ─────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────
@app.route('/chat/contratista/<int:trabajador_id>')
def chat_contratista(trabajador_id):
    redir = login_requerido()
    if redir: return redir
    t = Trabajador.query.get_or_404(trabajador_id)
    usuario = get_usuario_actual()
    mensajes = Mensaje.query.filter(
        db.or_(
            db.and_(Mensaje.remitente_tipo=='contratista', Mensaje.remitente_id==usuario.id,
                    Mensaje.destinatario_tipo=='trabajador', Mensaje.destinatario_id==trabajador_id),
            db.and_(Mensaje.remitente_tipo=='trabajador', Mensaje.remitente_id==trabajador_id,
                    Mensaje.destinatario_tipo=='contratista', Mensaje.destinatario_id==usuario.id)
        )
    ).order_by(Mensaje.fecha.asc()).all()
    for m in mensajes:
        if m.destinatario_tipo == 'contratista' and m.destinatario_id == usuario.id:
            m.leido = True
    db.session.commit()
    room = f"chat_{min(usuario.id, trabajador_id)}_{max(usuario.id, trabajador_id)}"
    return render_template('chat.html', mensajes=mensajes, otro=t,
        otro_tipo='trabajador', yo_tipo='contratista', yo_id=usuario.id, room=room)

@app.route('/chat/trabajador/<int:usuario_id>')
def chat_trabajador(usuario_id):
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    u = Usuario.query.get_or_404(usuario_id)
    trab_id = session['trabajador_id']
    mensajes = Mensaje.query.filter(
        db.or_(
            db.and_(Mensaje.remitente_tipo=='trabajador', Mensaje.remitente_id==trab_id,
                    Mensaje.destinatario_tipo=='contratista', Mensaje.destinatario_id==usuario_id),
            db.and_(Mensaje.remitente_tipo=='contratista', Mensaje.remitente_id==usuario_id,
                    Mensaje.destinatario_tipo=='trabajador', Mensaje.destinatario_id==trab_id)
        )
    ).order_by(Mensaje.fecha.asc()).all()
    for m in mensajes:
        if m.destinatario_tipo == 'trabajador' and m.destinatario_id == trab_id:
            m.leido = True
    db.session.commit()
    room = f"chat_{min(usuario_id, trab_id)}_{max(usuario_id, trab_id)}"
    return render_template('chat.html', mensajes=mensajes, otro=u,
        otro_tipo='contratista', yo_tipo='trabajador', yo_id=trab_id, room=room)

@app.route('/chats')
def chats():
    if session.get('usuario_id'):
        usuario = get_usuario_actual()
        trabajador_ids_obras = []
        for obra in usuario.obras:
            for to in TrabajadorObra.query.filter_by(obra_id=obra.id).all():
                trabajador_ids_obras.append(to.trabajador_id)
            for t in Trabajador.query.filter_by(obra_id=obra.id).all():
                trabajador_ids_obras.append(t.id)
        todos_ids = list(set(trabajador_ids_obras))
        contactos = Trabajador.query.filter(Trabajador.id.in_(todos_ids)).all() if todos_ids else []
        contactos_info = []
        for t in contactos:
            no_leidos = Mensaje.query.filter_by(
                remitente_tipo='trabajador', remitente_id=t.id,
                destinatario_tipo='contratista', destinatario_id=usuario.id, leido=False
            ).count()
            ultimo = Mensaje.query.filter(
                db.or_(
                    db.and_(Mensaje.remitente_tipo=='contratista', Mensaje.remitente_id==usuario.id,
                            Mensaje.destinatario_tipo=='trabajador', Mensaje.destinatario_id==t.id),
                    db.and_(Mensaje.remitente_tipo=='trabajador', Mensaje.remitente_id==t.id,
                            Mensaje.destinatario_tipo=='contratista', Mensaje.destinatario_id==usuario.id)
                )
            ).order_by(Mensaje.fecha.desc()).first()
            contactos_info.append({'trabajador': t, 'no_leidos': no_leidos, 'ultimo_mensaje': ultimo})
        contactos_info.sort(
            key=lambda x: x['ultimo_mensaje'].fecha if x['ultimo_mensaje'] else datetime.min,
            reverse=True
        )
        return render_template('chats.html', contactos=contactos_info, tipo='contratista')

    elif session.get('trabajador_id'):
        t = Trabajador.query.get_or_404(session['trabajador_id'])
        trabajador_obras = TrabajadorObra.query.filter_by(trabajador_id=t.id, activo=True).all()
        obras = [to.obra for to in trabajador_obras if to.obra.activa]
        contratistas_ids = list(set([o.usuario_id for o in obras]))
        contratistas = Usuario.query.filter(Usuario.id.in_(contratistas_ids)).all() if contratistas_ids else []
        contactos_info = []
        for u in contratistas:
            no_leidos = Mensaje.query.filter_by(
                remitente_tipo='contratista', remitente_id=u.id,
                destinatario_tipo='trabajador', destinatario_id=t.id, leido=False
            ).count()
            ultimo = Mensaje.query.filter(
                db.or_(
                    db.and_(Mensaje.remitente_tipo=='trabajador', Mensaje.remitente_id==t.id,
                            Mensaje.destinatario_tipo=='contratista', Mensaje.destinatario_id==u.id),
                    db.and_(Mensaje.remitente_tipo=='contratista', Mensaje.remitente_id==u.id,
                            Mensaje.destinatario_tipo=='trabajador', Mensaje.destinatario_id==t.id)
                )
            ).order_by(Mensaje.fecha.desc()).first()
            contactos_info.append({'contratista': u, 'no_leidos': no_leidos, 'ultimo_mensaje': ultimo})
        contactos_info.sort(
            key=lambda x: x['ultimo_mensaje'].fecha if x['ultimo_mensaje'] else datetime.min,
            reverse=True
        )
        return render_template('chats.html', contactos=contactos_info, tipo='trabajador')

    return redirect(url_for('index'))

@app.route('/mensaje/eliminar/<int:mensaje_id>', methods=['POST'])
def eliminar_mensaje(mensaje_id):
    msg = Mensaje.query.get_or_404(mensaje_id)
    if session.get('usuario_id'):
        if not (msg.remitente_tipo == 'contratista' and msg.remitente_id == session['usuario_id']):
            return jsonify({'error': 'No autorizado'}), 403
    elif session.get('trabajador_id'):
        if not (msg.remitente_tipo == 'trabajador' and msg.remitente_id == session['trabajador_id']):
            return jsonify({'error': 'No autorizado'}), 403
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/chat/borrar', methods=['POST'])
def borrar_chat():
    rem_tipo  = request.form.get('rem_tipo')
    rem_id    = int(request.form.get('rem_id'))
    dest_tipo = request.form.get('dest_tipo')
    dest_id   = int(request.form.get('dest_id'))
    Mensaje.query.filter(
        db.or_(
            db.and_(Mensaje.remitente_tipo==rem_tipo, Mensaje.remitente_id==rem_id,
                    Mensaje.destinatario_tipo==dest_tipo, Mensaje.destinatario_id==dest_id),
            db.and_(Mensaje.remitente_tipo==dest_tipo, Mensaje.remitente_id==dest_id,
                    Mensaje.destinatario_tipo==rem_tipo, Mensaje.destinatario_id==rem_id)
        )
    ).delete(synchronize_session=False)
    db.session.commit()
    return redirect(url_for('chats'))

# ─────────────────────────────────────────
# PERFIL CONTRATISTA
# ─────────────────────────────────────────
@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    redir = login_requerido()
    if redir: return redir
    u = get_usuario_actual()
    error = exito = None
    if request.method == 'POST':
        u.nombre_completo = request.form.get('nombre_completo', '').strip()
        u.telefono        = request.form.get('telefono', '').strip()
        actual     = request.form.get('password_actual', '').strip()
        nueva_pass = request.form.get('nueva_password', '').strip()
        confirmar  = request.form.get('confirmar_password', '').strip()
        if nueva_pass:
            if not actual:
                error = 'Debes ingresar tu contraseña actual'
            elif not check_password_hash(u.password, actual):
                error = 'La contraseña actual es incorrecta'
            elif nueva_pass != confirmar:
                error = 'Las contraseñas nuevas no coinciden'
            elif len(nueva_pass) < 4:
                error = 'La contraseña debe tener al menos 4 caracteres'
            else:
                u.password = generate_password_hash(nueva_pass)
            if 'foto' in request.files:
                file = request.files['foto']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"perfil_{u.id}_{file.filename}")
                    file_bytes = file.read()
                    try:
                        supabase_client.storage.from_('Fotos').remove([filename])
                    except:
                        pass
                    supabase_client.storage.from_('Fotos').upload(
                        filename,
                        file_bytes,
                        {'content-type': file.content_type}
                )
                u.foto_perfil = filename
        if not error:
            db.session.commit()
            session['usuario_nombre'] = u.usuario
            session['foto_perfil']    = u.foto_perfil or ''
            exito = 'Perfil actualizado correctamente'
    return render_template('perfil.html', u=u, error=error, exito=exito)

# ─────────────────────────────────────────
# PERFIL TRABAJADOR
# ─────────────────────────────────────────
@app.route('/trabajador/perfil', methods=['GET', 'POST'])
def trabajador_perfil():
    if not session.get('trabajador_id'):
        return redirect(url_for('trabajador_login'))
    t = Trabajador.query.get_or_404(session['trabajador_id'])
    error = exito = None
    if request.method == 'POST':
        t.nombre   = request.form.get('nombre', '').strip()
        t.apellido = request.form.get('apellido', '').strip()
        t.telefono = request.form.get('telefono', '').strip()
        actual    = request.form.get('password_actual', '').strip()
        nueva     = request.form.get('nueva_password', '').strip()
        confirmar = request.form.get('confirmar_password', '').strip()
        if nueva:
            if not actual:
                error = 'Debes ingresar tu contraseña actual'
            elif not t.password or not check_password_hash(t.password, actual):
                error = 'La contraseña actual es incorrecta'
            elif nueva != confirmar:
                error = 'Las contraseñas nuevas no coinciden'
            elif len(nueva) < 4:
                error = 'La contraseña debe tener al menos 4 caracteres'
            else:
                t.password = generate_password_hash(nueva)
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"trab_{t.id}_{file.filename}")
                file_bytes = file.read()
                try:
                    supabase_client.storage.from_('Fotos').remove([filename])
                except:
                    pass
                try:
                    supabase_client.storage.from_('Fotos').upload(
                        filename,
                        file_bytes,
                        {'content-type': file.content_type}
                    )
                    print(f"Foto perfil subida: {filename}")
                except Exception as e:
                    print(f"ERROR perfil upload: {e}")
                u.foto_perfil = filename
                session['trabajador_foto'] = filename
        if not error:
            db.session.commit()
            session['trabajador_nombre'] = f"{t.nombre} {t.apellido or ''}".strip()
            exito = 'Perfil actualizado correctamente'
    return render_template('trabajador_perfil.html', t=t, error=error, exito=exito)

@app.route('/trabajador/elegir', methods=['GET', 'POST'])
def elegir_trabajador():
    usuario = error = None
    if request.method == 'POST':
        nombre  = request.form['contratista'].strip()
        usuario = Usuario.query.filter_by(usuario=nombre).first()
        if not usuario:
            error = 'No se encontró ese contratista'
    return render_template('elegir_trabajador.html', usuario=usuario, error=error)

@app.route('/obra/<int:obra_id>/eliminar', methods=['POST'])
def eliminar_obra(obra_id):
    redir = login_requerido()
    if redir: return redir
    obra = Obra.query.get_or_404(obra_id)
    if obra.usuario_id != session.get('usuario_id'):
        return redirect(url_for('contratista'))
    obra.activa = False
    db.session.commit()
    return redirect(url_for('contratista'))

@app.route('/config')
def configuracion():
    return render_template('config.html')

# ─────────────────────────────────────────
# SOCKETIO
# ─────────────────────────────────────────
@socketio.on('join')
def on_join(data):
    join_room(data['room'])

@socketio.on('mensaje')
def on_mensaje(data):
    contenido = data['contenido'].strip()
    if not contenido:
        return
    msg = Mensaje(
        remitente_tipo=data['remitente_tipo'],
        remitente_id=int(data['remitente_id']),
        destinatario_tipo=data['destinatario_tipo'],
        destinatario_id=int(data['destinatario_id']),
        contenido=contenido,
        fecha=datetime.now()
    )
    db.session.add(msg)
    db.session.commit()
    emit('nuevo_mensaje', {
        'id': msg.id,
        'contenido': contenido,
        'remitente_tipo': data['remitente_tipo'],
        'remitente_id': int(data['remitente_id']),
        'fecha': msg.fecha.strftime('%H:%M')
    }, room=data['room'])

@app.route('/trabajador/<int:trab_id>/desarchivar', methods=['POST'])
def desarchivar_trabajador(trab_id):
    redir = login_requerido()
    if redir: return redir
    obra_id = request.form.get('obra_id', type=int)

    to = TrabajadorObra.query.filter_by(
        trabajador_id=trab_id,
        obra_id=obra_id,
        activo=False
    ).first()
    if to:
        to.activo = True
        to.estado = 'activa'

    t = Trabajador.query.get(trab_id)
    if t and t.obra_id is None:
        t.obra_id = obra_id

    db.session.commit()
    return redirect(url_for('ver_archivados', obra_id=obra_id))

# ─────────────────────────────────────────
# INICIALIZACIÓN
# ─────────────────────────────────────────
with app.app_context():
    db.create_all()
    db.engine.connect()
    print("Conexion exitosa a PostgreSQL")